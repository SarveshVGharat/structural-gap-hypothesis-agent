"""Deterministic metadata scoring and hard rejection for candidate papers."""
from __future__ import annotations

from .models import CandidatePaper, RetrievalFacet, RetrievalPlan, ScoredPaper


def score_candidates(
    papers: list[CandidatePaper],
    plan: RetrievalPlan,
    *,
    global_must_include_any: list[str] | None = None,
    global_must_exclude: list[str] | None = None,
) -> tuple[list[ScoredPaper], list[ScoredPaper]]:
    """Score papers and split into accepted and rejected."""
    facet_map = {f.facet_id: f for f in plan.facets}
    accepted: list[ScoredPaper] = []
    rejected: list[ScoredPaper] = []

    for paper in papers:
        facet = facet_map.get(paper.source_facet)
        scored = _score_one(paper, facet, global_must_include_any=global_must_include_any, global_must_exclude=global_must_exclude)
        if scored.rejection_reason:
            rejected.append(scored)
        else:
            accepted.append(scored)

    return accepted, rejected


def _score_one(
    paper: CandidatePaper,
    facet: RetrievalFacet | None,
    *,
    global_must_include_any: list[str] | None,
    global_must_exclude: list[str] | None,
) -> ScoredPaper:
    scored = ScoredPaper(**paper.model_dump())
    title_lower = paper.title.lower()
    abstract_lower = paper.abstract.lower()
    text = title_lower + " " + abstract_lower
    breakdown: dict[str, float] = {}

    # --- Hard rejection checks ---
    must_excl = list(facet.must_exclude if facet else []) + list(global_must_exclude or [])
    for term in must_excl:
        if term.lower() in text:
            scored.rejection_reason = f"excluded term: {term}"
            scored.metadata_score = -999.0
            scored.score_breakdown = breakdown
            return scored

    # Check year
    if facet and facet.min_year and paper.published:
        year_str = paper.published[:4]
        if year_str.isdigit() and int(year_str) < facet.min_year:
            scored.rejection_reason = f"too old: {year_str} < {facet.min_year}"
            scored.metadata_score = -999.0
            scored.score_breakdown = breakdown
            return scored

    # --- Positive scoring ---
    score = 0.0

    # Must-include check — at least one term must appear in title+abstract
    must_incl = list(facet.must_include_any if facet else []) + list(global_must_include_any or [])
    incl_hits = [t for t in must_incl if t.lower() in text]
    if must_incl and not incl_hits:
        scored.rejection_reason = "no must_include_any term found"
        scored.metadata_score = -999.0
        scored.score_breakdown = breakdown
        return scored

    if incl_hits:
        title_hits = [t for t in incl_hits if t.lower() in title_lower]
        abstract_hits = [t for t in incl_hits if t.lower() in abstract_lower]
        title_bonus = min(5.0, len(title_hits) * 2.5)
        abstract_bonus = min(3.0, len(abstract_hits) * 1.5)
        breakdown["title_must_include"] = title_bonus
        breakdown["abstract_must_include"] = abstract_bonus
        score += title_bonus + abstract_bonus

    # Keyword hits (facet keywords)
    if facet and facet.keywords:
        kw_hits = sum(1 for kw in facet.keywords if kw.lower() in text)
        kw_bonus = min(4.0, kw_hits * 1.0)
        breakdown["keyword_hits"] = kw_bonus
        score += kw_bonus

    # Category match
    if facet and facet.categories:
        cat_matches = sum(1 for c in paper.categories if c in facet.categories)
        cat_bonus = min(3.0, cat_matches * 1.5)
        breakdown["category_match"] = cat_bonus
        score += cat_bonus

    scored.metadata_score = round(score, 4)
    scored.final_score = scored.metadata_score
    scored.score_breakdown = breakdown
    return scored
