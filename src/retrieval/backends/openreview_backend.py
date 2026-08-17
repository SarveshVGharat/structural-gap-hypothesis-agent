"""OpenReview backend — fetches papers from A* ML/NLP venues.

The backend does NOT hardcode any topic-specific phrases.
Filtering is driven by the caller-supplied `filter_phrases` and
`min_abstract_hits` parameters (populated from the active TopicProfileConfig).
If no filter phrases are given, all papers from the venue pass through.
"""
from __future__ import annotations

import time
from typing import Any

from .base import BaseBackend, PaperCandidate

_BASE_URL = "https://api2.openreview.net"
_BATCH_SIZE = 200
_POLITE_DELAY = 0.5

# Default venue list — overridable via VenueRegistry
_DEFAULT_VENUES: list[tuple[str, str, str]] = [
    ("ICLR.cc/2025/Conference/-/Submission",    "ICLR.cc/2025/Conference",    "ICLR 2025"),
    ("NeurIPS.cc/2024/Conference/-/Submission", "NeurIPS.cc/2024/Conference", "NeurIPS 2024"),
    ("ICML.cc/2024/Conference/-/Submission",    "ICML.cc/2024/Conference",    "ICML 2024"),
    ("ICLR.cc/2024/Conference/-/Submission",    "ICLR.cc/2024/Conference",    "ICLR 2024"),
    ("NeurIPS.cc/2023/Conference/-/Submission", "NeurIPS.cc/2023/Conference", "NeurIPS 2023"),
    ("ICML.cc/2023/Conference/-/Submission",    "ICML.cc/2023/Conference",    "ICML 2023"),
    ("ICLR.cc/2023/Conference/-/Submission",    "ICLR.cc/2023/Conference",    "ICLR 2023"),
    ("NeurIPS.cc/2022/Conference/-/Submission", "NeurIPS.cc/2022/Conference", "NeurIPS 2022"),
    ("ICML.cc/2022/Conference/-/Submission",    "ICML.cc/2022/Conference",    "ICML 2022"),
    ("ICLR.cc/2022/Conference/-/Submission",    "ICLR.cc/2022/Conference",    "ICLR 2022"),
    ("TMLR/-/Submission",                        "TMLR",                       "TMLR"),
]


class OpenReviewBackend(BaseBackend):
    def __init__(
        self,
        *,
        polite_delay: float = _POLITE_DELAY,
        venues: list[tuple[str, str, str]] | None = None,
        # Phrases to match; if empty, no client-side filtering is applied
        filter_phrases: list[str] | None = None,
        # Minimum number of filter_phrases required in the abstract (title match bypasses this)
        min_abstract_hits: int = 2,
    ):
        self._delay = polite_delay
        self._venues = venues or _DEFAULT_VENUES
        self._filter_phrases: list[str] = [p.lower() for p in (filter_phrases or [])]
        self._min_abstract_hits = min_abstract_hits
        self._avail: bool | None = None

    @property
    def name(self) -> str:
        return "openreview"

    @property
    def available(self) -> bool:
        if self._avail is None:
            try:
                import json
                import urllib.request
                resp = urllib.request.urlopen(f"{_BASE_URL}/notes?limit=1", timeout=10)
                json.loads(resp.read())
                self._avail = True
            except Exception:
                self._avail = True  # Assume available; search() will fail gracefully if not
        return self._avail

    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]:
        results: list[PaperCandidate] = []
        seen_ids: set[str] = set()
        per_venue_cap = max(5, max_results // len(self._venues))

        for invitation, venueid, venue_name in self._venues:
            if len(results) >= max_results:
                break
            batch = self._search_venue(
                invitation=invitation,
                venueid=venueid,
                venue_name=venue_name,
                max_results=min(per_venue_cap, max_results - len(results)),
                seen_ids=seen_ids,
            )
            for p in batch:
                if p.paper_id not in seen_ids:
                    seen_ids.add(p.paper_id)
                    results.append(p)

        return results

    def _search_venue(
        self,
        *,
        invitation: str,
        venueid: str,
        venue_name: str,
        max_results: int,
        seen_ids: set[str],
    ) -> list[PaperCandidate]:
        import json
        import urllib.parse
        import urllib.request

        results: list[PaperCandidate] = []
        offset = 0

        while len(results) < max_results:
            params = urllib.parse.urlencode({
                "invitation": invitation,
                "content.venueid": venueid,
                "limit": _BATCH_SIZE,
                "offset": offset,
            })
            url = f"{_BASE_URL}/notes?{params}"
            try:
                resp = urllib.request.urlopen(url, timeout=15)
                data = json.loads(resp.read())
            except Exception:
                break

            notes = data.get("notes", [])
            if not notes:
                break

            for note in notes:
                if len(results) >= max_results:
                    break
                candidate = self._note_to_candidate(note, venue_name=venue_name)
                if candidate and candidate.paper_id not in seen_ids:
                    results.append(candidate)

            if len(notes) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE
            time.sleep(self._delay)

        return results

    def _note_to_candidate(self, note: dict[str, Any], *, venue_name: str) -> PaperCandidate | None:
        c = note.get("content", {})

        def _val(field: str) -> Any:
            v = c.get(field, "")
            return v.get("value", v) if isinstance(v, dict) else v

        title = str(_val("title")).strip()
        abstract = str(_val("abstract")).strip()

        if not title:
            return None

        # Client-side phrase filter — only applies when filter_phrases are set
        if self._filter_phrases:
            title_lower = title.lower()
            abstract_lower = abstract.lower()
            title_hit = any(p in title_lower for p in self._filter_phrases)
            abstract_hits = sum(1 for p in self._filter_phrases if p in abstract_lower)
            if not title_hit and abstract_hits < self._min_abstract_hits:
                return None

        note_id = note.get("id", "")
        pdf_url = f"https://openreview.net/pdf?id={note_id}" if note_id else ""
        url = f"https://openreview.net/forum?id={note_id}" if note_id else ""

        authors_raw = _val("authors")
        authors = authors_raw if isinstance(authors_raw, list) else []

        year_raw = _val("year") or venue_name.split()[-1]
        try:
            year = int(str(year_raw)[:4])
        except (ValueError, TypeError):
            year = None

        keywords_raw = _val("keywords")
        kw_list = keywords_raw if isinstance(keywords_raw, list) else []

        pid = f"openreview:{note_id}"
        return PaperCandidate(
            paper_id=pid,
            source_ids={"openreview": note_id},
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            published_date=str(year) if year else "",
            source_names=["openreview"],
            url=url,
            pdf_url=pdf_url,
            venue=venue_name,
            fields_of_study=kw_list[:5],
            raw_source_payloads={"openreview": {"id": note_id, "venue": venue_name}},
            retrieval_queries=[],
            retrieval_backend="openreview",
        )
