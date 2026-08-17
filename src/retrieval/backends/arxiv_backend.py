from __future__ import annotations

import hashlib
import time

from .base import BaseBackend, PaperCandidate


class ArxivBackend(BaseBackend):
    def __init__(self, *, polite_delay: float = 1.0):
        self._polite_delay = polite_delay
        self._avail: bool | None = None

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def available(self) -> bool:
        if self._avail is None:
            try:
                import arxiv  # noqa: F401
                self._avail = True
            except ImportError:
                self._avail = False
        return self._avail

    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]:
        import arxiv

        # Convert natural language query to fielded arXiv syntax if it's plain text
        arxiv_query = _to_arxiv_query(query)
        client = arxiv.Client(page_size=min(max_results, 50), delay_seconds=self._polite_delay, num_retries=3)
        search = arxiv.Search(query=arxiv_query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)
        results: list[PaperCandidate] = []
        for r in client.results(search):
            arxiv_id = r.get_short_id()
            pid = f"arxiv:{arxiv_id}"
            results.append(PaperCandidate(
                paper_id=pid,
                source_ids={"arxiv": arxiv_id},
                title=r.title,
                abstract=r.summary or "",
                authors=[a.name for a in r.authors],
                year=r.published.year if r.published else None,
                published_date=r.published.isoformat() if r.published else "",
                updated_date=r.updated.isoformat() if r.updated else "",
                source_names=["arxiv"],
                arxiv_id=arxiv_id,
                doi=r.doi,
                url=r.entry_id or "",
                pdf_url=r.pdf_url or "",
                categories=list(r.categories),
                raw_source_payloads={"arxiv": {"id": arxiv_id, "categories": list(r.categories)}},
                retrieval_queries=[query],
                retrieval_backend="arxiv",
            ))
        time.sleep(self._polite_delay)
        return results


_KNOWN_PHRASES = [
    "in-context learning", "few-shot prompting", "few-shot learning",
    "prompt robustness", "prompt sensitivity", "prompt perturbation",
    "demonstration selection", "example selection", "exemplar selection",
    "chain-of-thought", "large language model", "large language models",
    "instruction tuning", "foundation model",
]


def _to_arxiv_query(query: str) -> str:
    """Wrap plain-text query in ti/abs fielded search for better precision."""
    if any(op in query for op in ("ti:", "abs:", "au:", "cat:")):
        return query
    import re
    # Extract explicit quoted phrases
    explicit_phrases = re.findall(r'"([^"]+)"', query)
    remainder = re.sub(r'"[^"]+"', "", query).strip()

    # Greedily extract known multi-word phrases from the remainder (longest first)
    detected: list[str] = []
    lowered = remainder.lower()
    for phrase in sorted(_KNOWN_PHRASES, key=len, reverse=True):
        if phrase in lowered:
            detected.append(phrase)
            lowered = lowered.replace(phrase, " ")

    parts: list[str] = []
    for phrase in explicit_phrases + detected:
        parts.append(f'(ti:"{phrase}" OR abs:"{phrase}")')

    # Any leftover significant single words
    leftover = [w for w in lowered.split() if len(w) > 3 and w.isalpha()]
    if leftover and not parts:
        # Fallback: just OR the key words so we get some results
        word_parts = [f'(ti:{w} OR abs:{w})' for w in leftover[:4]]
        parts.append("(" + " OR ".join(word_parts) + ")")

    return " AND ".join(parts) if parts else query
