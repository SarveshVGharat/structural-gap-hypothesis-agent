from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class PaperCandidate(BaseModel):
    paper_id: str
    source_ids: dict[str, str] = Field(default_factory=dict)
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    published_date: str = ""
    updated_date: str = ""
    venue: str = ""
    source_names: list[str] = Field(default_factory=list)
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    doi: str | None = None
    url: str = ""
    pdf_url: str = ""
    citation_count: int | None = None
    influential_citation_count: int | None = None
    fields_of_study: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    raw_source_payloads: dict[str, Any] = Field(default_factory=dict)
    retrieval_queries: list[str] = Field(default_factory=list)
    retrieval_backend: str = ""

    def merge(self, other: "PaperCandidate") -> "PaperCandidate":
        """Merge another candidate's data into this one (self is primary)."""
        merged = self.model_copy(deep=True)
        merged.source_ids.update(other.source_ids)
        merged.source_names = sorted(set(merged.source_names) | set(other.source_names))
        merged.retrieval_queries = sorted(set(merged.retrieval_queries) | set(other.retrieval_queries))
        merged.fields_of_study = sorted(set(merged.fields_of_study) | set(other.fields_of_study))
        merged.categories = sorted(set(merged.categories) | set(other.categories))
        merged.raw_source_payloads.update(other.raw_source_payloads)
        if len(other.abstract) > len(merged.abstract):
            merged.abstract = other.abstract
        if not merged.pdf_url and other.pdf_url:
            merged.pdf_url = other.pdf_url
        if not merged.doi and other.doi:
            merged.doi = other.doi
        if not merged.arxiv_id and other.arxiv_id:
            merged.arxiv_id = other.arxiv_id
        if not merged.semantic_scholar_id and other.semantic_scholar_id:
            merged.semantic_scholar_id = other.semantic_scholar_id
        if not merged.openalex_id and other.openalex_id:
            merged.openalex_id = other.openalex_id
        if other.citation_count is not None:
            merged.citation_count = max(merged.citation_count or 0, other.citation_count)
        if other.influential_citation_count is not None:
            merged.influential_citation_count = max(merged.influential_citation_count or 0, other.influential_citation_count)
        if not merged.venue and other.venue:
            merged.venue = other.venue
        return merged


class BaseBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]: ...
