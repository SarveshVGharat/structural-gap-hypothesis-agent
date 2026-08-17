from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Relation = Literal[
    "evaluated_on",
    "improves_over",
    "fails_under",
    "assumes",
    "contradicts",
    "uses_dataset",
    "measured_by",
    "limited_by",
    "addresses",
    "not_addressed_by",
]

ClaimType = Literal["method", "result", "limitation", "assumption", "comparison", "failure", "hypothesis", "evaluation", "unknown"]
Polarity = Literal["positive", "negative", "neutral", "mixed", "unknown"]
Direction = Literal["improves", "worsens", "no_change", "unknown"]
EvidenceType = Literal["empirical", "theoretical", "ablation", "qualitative", "assumption", "citation", "benchmark", "unknown"]
Strength = Literal["strong", "moderate", "weak", "unknown"]
SubjectScope = Literal["own_method", "prior_work", "general"]


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_id: str
    section: str = ""
    evidence_text: str
    start_char: int | None = None
    end_char: int | None = None


_DIRECTION_MAP: dict[str, str] = {
    "increases": "improves", "increase": "improves", "increased": "improves",
    "positive": "improves", "better": "improves", "higher": "improves",
    "improves": "improves", "improve": "improves", "improved": "improves",
    "decreases": "worsens", "decrease": "worsens", "decreased": "worsens",
    "negative": "worsens", "worse": "worsens", "lower": "worsens",
    "worsens": "worsens", "worsen": "worsens", "worsened": "worsens",
    "neutral": "no_change", "unchanged": "no_change", "stable": "no_change",
    "no_change": "no_change", "none": "no_change", "no change": "no_change",
}

_CLAIM_TYPE_MAP: dict[str, str] = {
    "methods": "method", "results": "result", "limitations": "limitation",
    "assumptions": "assumption", "comparisons": "comparison", "failures": "failure",
    "hypotheses": "hypothesis", "evaluations": "evaluation",
}

_POLARITY_MAP: dict[str, str] = {
    "pos": "positive", "neg": "negative", "neut": "neutral",
}

_EVIDENCE_MAP: dict[str, str] = {
    "experiment": "empirical", "experiments": "empirical", "experimental": "empirical",
    "theory": "theoretical", "theoretical": "theoretical", "ablations": "ablation",
    "qualitative": "qualitative", "assumptions": "assumption", "citations": "citation",
    "benchmarks": "benchmark",
}

_STRENGTH_MAP: dict[str, str] = {
    "strongly": "strong", "strongly supported": "strong",
    "moderately": "moderate", "weakly": "weak",
}

_RELATION_MAP: dict[str, str] = {
    "evaluated": "evaluated_on", "evaluate": "evaluated_on", "tests": "evaluated_on",
    "improves": "improves_over", "improves over": "improves_over", "outperforms": "improves_over",
    "fails": "fails_under", "fails on": "fails_under",
    "assume": "assumes", "assumed": "assumes",
    "contradict": "contradicts", "contradicted": "contradicts",
    "uses": "uses_dataset", "use dataset": "uses_dataset",
    "measured": "measured_by", "measure": "measured_by",
    "limited": "limited_by", "limit": "limited_by",
    "address": "addresses", "addressed": "addresses",
    "not addressed": "not_addressed_by",
}


def _coerce_enum(value: Any, valid: set[str], mapping: dict[str, str], default: str) -> str:
    if not isinstance(value, str):
        return default
    v = value.strip().lower()
    if v in valid:
        return v
    return mapping.get(v, default)


class ScientificTuple(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: str
    relation: Relation
    object: str
    evidence_text: str
    section: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    claim_type: ClaimType = "unknown"
    polarity: Polarity = "unknown"
    condition: str = ""
    task: str = ""
    dataset: str = ""
    model: str = ""
    metric: str = ""
    direction: Direction = "unknown"
    evidence_type: EvidenceType = "unknown"
    strength: Strength = "unknown"
    source_span: str = ""
    subject_scope: SubjectScope = "own_method"
    resolved_by_paper: bool = False
    in_related_work: bool = False

    @field_validator("direction", mode="before")
    @classmethod
    def coerce_direction(cls, v: Any) -> str:
        return _coerce_enum(v, set(Direction.__args__), _DIRECTION_MAP, "unknown")

    @field_validator("claim_type", mode="before")
    @classmethod
    def coerce_claim_type(cls, v: Any) -> str:
        return _coerce_enum(v, set(ClaimType.__args__), _CLAIM_TYPE_MAP, "unknown")

    @field_validator("polarity", mode="before")
    @classmethod
    def coerce_polarity(cls, v: Any) -> str:
        return _coerce_enum(v, set(Polarity.__args__), _POLARITY_MAP, "unknown")

    @field_validator("evidence_type", mode="before")
    @classmethod
    def coerce_evidence_type(cls, v: Any) -> str:
        return _coerce_enum(v, set(EvidenceType.__args__), _EVIDENCE_MAP, "unknown")

    @field_validator("strength", mode="before")
    @classmethod
    def coerce_strength(cls, v: Any) -> str:
        return _coerce_enum(v, set(Strength.__args__), _STRENGTH_MAP, "unknown")

    @field_validator("relation", mode="before")
    @classmethod
    def coerce_relation(cls, v: Any) -> str:
        valid = {
            "evaluated_on", "improves_over", "fails_under", "assumes",
            "contradicts", "uses_dataset", "measured_by", "limited_by",
            "addresses", "not_addressed_by",
        }
        return _coerce_enum(v, valid, _RELATION_MAP, "addresses")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float:
        try:
            f = float(v)
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("subject_scope", mode="before")
    @classmethod
    def coerce_subject_scope(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "own_method"
        v = v.strip().lower().replace(" ", "_")
        if v in {"own_method", "prior_work", "general"}:
            return v
        if "prior" in v or "baseline" in v or "existing" in v or "previous" in v:
            return "prior_work"
        if "general" in v or "field" in v:
            return "general"
        return "own_method"


class PaperExtraction(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_id: str
    methods: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    results: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    contradictions_or_tensions: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    tuples: list[ScientificTuple] = Field(default_factory=list)


class ArxivPaper(BaseModel):
    model_config = ConfigDict(extra="allow")

    arxiv_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    categories: list[str] = Field(default_factory=list)
    published: str = ""
    updated: str = ""
    pdf_url: str = ""
    local_pdf_path: str = ""
    download_status: str = "not_downloaded"
    sha256: str = ""
    source_query: str = ""


class ParsedPaper(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_id: str
    arxiv_id: str = ""
    title: str = ""
    text_path: str
    sections_path: str
    parser: str
    full_text_chars: int
    pages: int = 0
    quality: dict[str, Any] = Field(default_factory=dict)


EXTRACTION_SCHEMA_JSON = PaperExtraction.model_json_schema() if hasattr(PaperExtraction, "model_json_schema") else {}
