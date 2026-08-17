from __future__ import annotations

import time
from typing import Any

import requests

from .base import BaseBackend, PaperCandidate

_OA_BASE = "https://api.openalex.org"


class OpenAlexBackend(BaseBackend):
    def __init__(self, *, email: str = "research@example.com", polite_delay: float = 1.0):
        self._email = email
        self._polite_delay = polite_delay

    @property
    def name(self) -> str:
        return "openalex"

    @property
    def available(self) -> bool:
        return True

    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]:
        params = {
            "search": query,
            "per-page": min(max_results, 50),
            "filter": "type:article",
            "select": "id,title,abstract_inverted_index,authorships,publication_year,publication_date,doi,open_access,primary_location,cited_by_count,concepts,topics,best_oa_location",
            "mailto": self._email,
        }
        results: list[PaperCandidate] = []
        try:
            resp = requests.get(f"{_OA_BASE}/works", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return results
        for item in data.get("results", []):
            p = _parse_oa_work(item, query)
            if p:
                results.append(p)
        time.sleep(self._polite_delay)
        return results


def _parse_oa_work(item: dict[str, Any], query: str) -> PaperCandidate | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    oa_id = item.get("id", "")  # e.g. "https://openalex.org/W12345"
    short_id = oa_id.split("/")[-1] if oa_id else ""
    doi = item.get("doi", "")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    abstract = _reconstruct_abstract(item.get("abstract_inverted_index") or {})
    authors = [a.get("author", {}).get("display_name", "") for a in (item.get("authorships") or [])]
    year = item.get("publication_year")
    pub_date = item.get("publication_date", "") or ""
    concepts = [c.get("display_name", "") for c in (item.get("concepts") or [])]
    oa_info = item.get("open_access") or {}
    best_oa = item.get("best_oa_location") or {}
    pdf_url = best_oa.get("pdf_url", "") or oa_info.get("oa_url", "")
    pid = f"doi:{doi}" if doi else f"openalex:{short_id}"
    return PaperCandidate(
        paper_id=pid,
        source_ids={"openalex": short_id, **({"doi": doi} if doi else {})},
        title=title,
        abstract=abstract,
        authors=[a for a in authors if a],
        year=year,
        published_date=pub_date,
        source_names=["openalex"],
        openalex_id=short_id,
        doi=doi or None,
        url=oa_id,
        pdf_url=pdf_url or "",
        citation_count=item.get("cited_by_count"),
        fields_of_study=concepts[:10],
        raw_source_payloads={"openalex": {k: item.get(k) for k in ("id", "title", "doi", "cited_by_count", "concepts")}},
        retrieval_queries=[query],
        retrieval_backend="openalex",
    )


def _reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))
