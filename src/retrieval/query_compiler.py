"""Compile RetrievalFacets into arXiv fielded query strings."""
from __future__ import annotations

from .models import CompiledArxivQuery, RetrievalFacet, RetrievalPlan


def compile_plan(plan: RetrievalPlan, *, max_results_per_facet: int = 100) -> list[CompiledArxivQuery]:
    return [
        CompiledArxivQuery(
            facet_id=facet.facet_id,
            facet_label=facet.label,
            query_string=_compile_facet(facet),
            max_results=max_results_per_facet,
        )
        for facet in plan.facets
    ]


def _compile_facet(facet: RetrievalFacet) -> str:
    parts: list[str] = []

    # Title + abstract keyword search (OR across keywords, split into ti/abs)
    if facet.keywords:
        kw_parts = [f'ti:"{kw}" OR abs:"{kw}"' for kw in facet.keywords[:6]]
        parts.append("(" + " OR ".join(kw_parts) + ")")

    # Category filter (OR across categories)
    if facet.categories:
        cat_parts = [f"cat:{c}" for c in facet.categories]
        parts.append("(" + " OR ".join(cat_parts) + ")")

    return " AND ".join(parts) if parts else " ".join(facet.keywords)
