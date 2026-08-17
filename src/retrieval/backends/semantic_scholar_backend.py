from __future__ import annotations

import os
import time
from typing import Any

import requests

from .base import BaseBackend, PaperCandidate

_SS_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,abstract,year,authors,url,openAccessPdf,externalIds,citationCount,influentialCitationCount,fieldsOfStudy,publicationVenue,publicationDate"


class SemanticScholarBackend(BaseBackend):
    def __init__(self, *, api_key: str | None = None, polite_delay: float = 1.5):
        self._api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        self._polite_delay = polite_delay

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def available(self) -> bool:
        return True  # always try; fails gracefully on network error

    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]:
        headers = {"x-api-key": self._api_key} if self._api_key else {}
        params = {"query": query, "fields": _FIELDS, "limit": min(max_results, 100), "offset": 0}
        results: list[PaperCandidate] = []
        try:
            resp = requests.get(f"{_SS_BASE}/paper/search", params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return results
        for item in data.get("data", []):
            p = _parse_ss_paper(item, query)
            if p:
                results.append(p)
        time.sleep(self._polite_delay)
        return results


def _parse_ss_paper(item: dict[str, Any], query: str) -> PaperCandidate | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    ss_id = item.get("paperId", "")
    ext = item.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    doi = ext.get("DOI")
    openalex_id = ext.get("OpenAlex")
    pid = f"doi:{doi}" if doi else (f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{ss_id}")
    oa = item.get("openAccessPdf") or {}
    pdf_url = oa.get("url", "")
    venue_data = item.get("publicationVenue") or {}
    venue = venue_data.get("name", "") or item.get("venue", "")
    pub_date = item.get("publicationDate", "") or ""
    year = item.get("year")
    if not year and pub_date:
        year = int(pub_date[:4]) if pub_date[:4].isdigit() else None
    return PaperCandidate(
        paper_id=pid,
        source_ids={"semantic_scholar": ss_id, **({"arxiv": arxiv_id} if arxiv_id else {}), **({"doi": doi} if doi else {})},
        title=title,
        abstract=item.get("abstract") or "",
        authors=[a.get("name", "") for a in (item.get("authors") or [])],
        year=year,
        published_date=pub_date,
        venue=venue,
        source_names=["semantic_scholar"],
        arxiv_id=arxiv_id,
        semantic_scholar_id=ss_id,
        openalex_id=openalex_id,
        doi=doi,
        url=item.get("url", ""),
        pdf_url=pdf_url,
        citation_count=item.get("citationCount"),
        influential_citation_count=item.get("influentialCitationCount"),
        fields_of_study=list(item.get("fieldsOfStudy") or []),
        raw_source_payloads={"semantic_scholar": item},
        retrieval_queries=[query],
        retrieval_backend="semantic_scholar",
    )
