from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalFacet(BaseModel):
    facet_id: str
    label: str
    keywords: list[str]
    must_include_any: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    min_year: int = 0


class RetrievalPlan(BaseModel):
    original_query: str
    facets: list[RetrievalFacet]
    strategy: Literal["rule_based", "llm"] = "rule_based"


class CompiledArxivQuery(BaseModel):
    facet_id: str
    facet_label: str
    query_string: str
    max_results: int = 100


class CandidatePaper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    published: str = ""
    pdf_url: str = ""
    source_facet: str = ""
    local_pdf_path: str | None = None
    download_status: str = "not_downloaded"


class ScoredPaper(CandidatePaper):
    metadata_score: float = 0.0
    embedding_score: float = 0.0
    mmr_score: float = 0.0
    final_score: float = 0.0
    rejection_reason: str | None = None
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
