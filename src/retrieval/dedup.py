"""Deduplicate PaperCandidates by DOI, arXiv ID, S2/OA IDs, and normalized title."""
from __future__ import annotations

import re

from .backends.base import PaperCandidate


def deduplicate(candidates: list[PaperCandidate]) -> list[PaperCandidate]:
    """Merge duplicates. Returns one canonical record per unique paper."""
    # Buckets keyed by canonical identity
    by_doi: dict[str, int] = {}       # doi → index in merged
    by_arxiv: dict[str, int] = {}     # bare arxiv id (no version) → index
    by_ss: dict[str, int] = {}        # semantic scholar id → index
    by_oa: dict[str, int] = {}        # openalex id → index
    by_title: dict[str, int] = {}     # normalized title → index
    merged: list[PaperCandidate] = []

    for candidate in candidates:
        idx = _find_existing(candidate, by_doi, by_arxiv, by_ss, by_oa, by_title, merged)
        if idx is not None:
            merged[idx] = merged[idx].merge(candidate)
            _register(merged[idx], idx, by_doi, by_arxiv, by_ss, by_oa, by_title)
        else:
            idx = len(merged)
            merged.append(candidate)
            _register(candidate, idx, by_doi, by_arxiv, by_ss, by_oa, by_title)

    return merged


def _find_existing(
    c: PaperCandidate,
    by_doi: dict[str, int],
    by_arxiv: dict[str, int],
    by_ss: dict[str, int],
    by_oa: dict[str, int],
    by_title: dict[str, int],
    merged: list[PaperCandidate],
) -> int | None:
    if c.doi:
        doi_key = _norm_doi(c.doi)
        if doi_key in by_doi:
            return by_doi[doi_key]
    if c.arxiv_id:
        bare = _bare_arxiv(c.arxiv_id)
        if bare in by_arxiv:
            return by_arxiv[bare]
    if c.semantic_scholar_id and c.semantic_scholar_id in by_ss:
        return by_ss[c.semantic_scholar_id]
    if c.openalex_id and c.openalex_id in by_oa:
        return by_oa[c.openalex_id]
    # Fuzzy title match
    nt = _norm_title(c.title)
    if nt and nt in by_title:
        return by_title[nt]
    # Jaccard title similarity (threshold 0.95)
    for existing_title, idx in by_title.items():
        if _jaccard(nt, existing_title) >= 0.95:
            return idx
    return None


def _register(
    c: PaperCandidate,
    idx: int,
    by_doi: dict[str, int],
    by_arxiv: dict[str, int],
    by_ss: dict[str, int],
    by_oa: dict[str, int],
    by_title: dict[str, int],
) -> None:
    if c.doi:
        by_doi[_norm_doi(c.doi)] = idx
    if c.arxiv_id:
        by_arxiv[_bare_arxiv(c.arxiv_id)] = idx
    if c.semantic_scholar_id:
        by_ss[c.semantic_scholar_id] = idx
    if c.openalex_id:
        by_oa[c.openalex_id] = idx
    nt = _norm_title(c.title)
    if nt:
        by_title[nt] = idx


def _norm_doi(doi: str) -> str:
    return doi.lower().strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")


def _bare_arxiv(arxiv_id: str) -> str:
    # Strip version suffix: 2301.12345v2 → 2301.12345
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def _norm_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
