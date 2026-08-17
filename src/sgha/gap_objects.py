from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GraphNodeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    label: str
    paper_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class GraphEdgeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source: str
    target: str
    relation: str
    paper_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MotifHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    motif_type: str
    motif_id: str
    description: str
    supporting_node_ids: list[str] = Field(default_factory=list)
    supporting_edge_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    source_text_spans: list[dict[str, Any]] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateGap(BaseModel):
    model_config = ConfigDict(extra="allow")

    gap_id: str
    gap: str
    target: str = ""
    scope: str = ""
    mechanism: str = ""
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence: list[dict[str, Any]] = Field(default_factory=list)
    traceability_path: list[str] = Field(default_factory=list)
    novelty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    motif_type: str = ""
    motif_id: str = ""
    paper_ids: list[str] = Field(default_factory=list)
    extraction_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    # Counterevidence discovery fields
    counterevidence_edges: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence_papers: list[str] = Field(default_factory=list)
    counterevidence_status: str = ""  # known_solved_in_corpus|partially_addressed_in_corpus|none
    counterevidence_summary: str = ""
    remaining_gap_scope: str = ""
    novelty_status: str = ""
    novelty_rationale: str = ""
    # Author-profile personalization (populated only when personalization enabled)
    author_alignment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    author_alignment_reason: str = ""
    related_author_papers: list[str] = Field(default_factory=list)
    related_cited_papers: list[str] = Field(default_factory=list)
    related_citing_papers: list[str] = Field(default_factory=list)


AgentName = Literal["support_agent", "skeptic_agent", "feasibility_agent", "mechanism_agent", "critic"]


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    gap_id: str
    agent_name: AgentName
    summary: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    failure_modes: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("counterevidence", "evidence", mode="before")
    @classmethod
    def _coerce_dict_list(cls, v: Any) -> list[dict[str, Any]]:
        if isinstance(v, str):
            return [{"text": v}] if v.strip() else []
        if isinstance(v, list):
            return [x if isinstance(x, dict) else {"text": str(x)} for x in v]
        return []

    @field_validator("failure_modes", mode="before")
    @classmethod
    def _coerce_str_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        if isinstance(v, str):
            import re
            m = re.search(r"(\d+(?:\.\d+)?)", v)
            if m:
                val = float(m.group(1))
                return min(1.0, val / 100.0 if val > 1.0 else val)
        return 0.5

    @field_validator("scores", mode="before")
    @classmethod
    def _coerce_scores(cls, v: Any) -> dict[str, float]:
        if isinstance(v, (int, float)):
            return {"overall": float(v)}
        if isinstance(v, dict):
            out: dict[str, float] = {}
            for k, val in v.items():
                if isinstance(val, (int, float)):
                    out[k] = float(val)
                elif isinstance(val, str):
                    import re
                    m = re.search(r"(\d+(?:\.\d+)?)", val)
                    if m:
                        fv = float(m.group(1))
                        out[k] = min(1.0, fv / 100.0 if fv > 1.0 else fv)
            return out
        return {}


class EvolutionCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_id: str
    gap_id: str
    generation: int
    problem_statement: str
    gap: str
    target: str = ""
    scope: str = ""
    mechanism: str = ""
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence: list[dict[str, Any]] = Field(default_factory=list)
    traceability_path: list[str] = Field(default_factory=list)
    novelty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    survival_score: float = Field(default=0.0, ge=0.0, le=1.0)
    fitness: float = Field(default=0.0, ge=0.0, le=1.0)
    lineage: list[str] = Field(default_factory=list)
    operator: str = "seed"
    # Robust lineage / origin tracking
    origin_signature: str = ""
    root_origin_signatures: list[str] = Field(default_factory=list)
    primary_origin_signature: str = ""
    origin_gap_ids: list[str] = Field(default_factory=list)
    origin_motif_types: list[str] = Field(default_factory=list)
    parent_candidate_ids: list[str] = Field(default_factory=list)
    operator_type: str = "seed"
    lineage_depth: int = 0
    lineage_invalid: bool = False
    # Counterevidence metadata carried from cleaned gaps
    counterevidence_status: str = ""
    remaining_gap_scope: str = ""
    counterevidence_edges: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence_papers: list[str] = Field(default_factory=list)
    original_gap_description: str = ""
    downstream_gap_description: str = ""


class EvolutionEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    generation: int
    operator: str
    parent_ids: list[str] = Field(default_factory=list)
    child_id: str | None = None
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


_REVIEW_LABELS = {
    "STRONG_CANDIDATE", "POSSIBLE_WITH_REWRITE", "WEAK_AFTER_READING",
    "DROP_GENERIC", "DROP_ALREADY_SOLVED", "DROP_IMPOSSIBLE",
    "DROP_ARTIFICIAL_SCOPE", "DROP_OFF_DOMAIN", "DROP_DUPLICATE",
    "DROP_TOO_SINGLE_PAPER_FRAGILE",
}
_ACCEPTABLE_REVIEW_LABELS = {"STRONG_CANDIDATE", "POSSIBLE_WITH_REWRITE"}


class HypothesisDeepReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    hypothesis_id: str
    original_rank: int = 0
    problem_statement: str = ""
    review_label: str = "WEAK_AFTER_READING"
    deep_review_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    remaining_gap_realness: float = Field(default=0.0, ge=0.0, le=1.0)
    counterevidence_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    impossibility_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    already_solved_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    specificity: float = Field(default=0.0, ge=0.0, le=1.0)
    feasibility: float = Field(default=0.0, ge=0.0, le=1.0)
    project_concreteness: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_risk: str = "medium"
    main_reason: str = ""
    falsification_condition: str = ""
    clean_rewrite: str = ""
    recommended_next_step: str = ""
    supporting_evidence_summary: str = ""
    counterevidence_summary: str = ""
    remaining_gap_scope: str = ""
    # carried-through metadata for selection
    origin_signature: str = ""
    primary_origin_signature: str = ""
    root_origin_signatures: list[str] = Field(default_factory=list)
    origin_motif_types: list[str] = Field(default_factory=list)
    counterevidence_status: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    counterevidence_papers: list[str] = Field(default_factory=list)
    fitness: float = 0.0

    @field_validator("review_label", mode="before")
    @classmethod
    def _coerce_label(cls, v: Any) -> str:
        s = str(v).strip().upper().replace(" ", "_")
        return s if s in _REVIEW_LABELS else "WEAK_AFTER_READING"

    def is_acceptable(self) -> bool:
        return self.review_label in _ACCEPTABLE_REVIEW_LABELS


class FinalHypothesis(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int
    hypothesis_id: str
    problem_statement: str
    gap: str
    target: str = ""
    scope: str = ""
    mechanism: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    counterevidence: list[dict[str, Any]] = Field(default_factory=list)
    traceability_path: list[str] = Field(default_factory=list)
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    impact_score: float = 0.0
    survival_score: float = 0.0
    fitness: float = 0.0
    evolutionary_lineage: list[str] = Field(default_factory=list)
    # Origin / lineage exposure
    origin_signature: str = ""
    root_origin_signatures: list[str] = Field(default_factory=list)
    primary_origin_signature: str = ""
    origin_gap_ids: list[str] = Field(default_factory=list)
    origin_motif_types: list[str] = Field(default_factory=list)
    operator_type: str = "seed"
    # Counterevidence exposure
    counterevidence_status: str = ""
    remaining_gap_scope: str = ""
    counterevidence_papers: list[str] = Field(default_factory=list)
    original_gap_description: str = ""
    downstream_gap_description: str = ""
    # Proposal-style abstract (Feature A) — filled in the native final-report path.
    proposal_style_abstract: str = ""
    abstract_generation_rationale: str = ""
    abstract_evidence_papers: list[str] = Field(default_factory=list)
    abstract_counterevidence_papers: list[str] = Field(default_factory=list)
    # Author-profile personalization (Feature B) — populated only when personalization
    # is enabled; defaults keep non-personalized runs unchanged.
    original_score: float = 0.0
    personalized_score: float = 0.0
    author_alignment_score: float = 0.0
    author_alignment_reason: str = ""
    related_author_papers: list[str] = Field(default_factory=list)
    related_cited_papers: list[str] = Field(default_factory=list)
    related_citing_papers: list[str] = Field(default_factory=list)
    relationship_to_author_profile: str = ""


# ---------------------------------------------------------------------------
# Domain-general problem-formulation exploration models
# ---------------------------------------------------------------------------

_FORMULATION_TYPES = {
    "theorem", "algorithm", "benchmark", "empirical_study", "lower_bound",
    "impossibility_refinement", "system_design", "dataset_or_evaluation",
    "measurement_study",
}
_VIABILITY_LABELS = {
    "VIABLE_FORMULATION", "POSSIBLE_FORMULATION_WITH_REWRITE",
    "ALREADY_SOLVED_FORMULATION", "IMPOSSIBLE_FORMULATION", "TRIVIAL_REDUCTION",
    "ARTIFICIAL_SCOPE", "TOO_BROAD", "TOO_NARROW", "OFF_DOMAIN",
    "NEEDS_EXTERNAL_LIT_CHECK", "INSUFFICIENT_EVIDENCE",
}
_ACCEPTABLE_FORMULATION_LABELS = {"VIABLE_FORMULATION", "POSSIBLE_FORMULATION_WITH_REWRITE"}


class DomainAxisInventory(BaseModel):
    """Corpus-inferred reusable formulation axes. No hardcoded domain vocabulary —
    every field is populated from graph nodes/edges/evidence or optional LLM induction."""
    model_config = ConfigDict(extra="allow")

    method_families: list[str] = Field(default_factory=list)
    problem_contexts: list[str] = Field(default_factory=list)
    data_or_input_conditions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    benchmarks_or_datasets: list[str] = Field(default_factory=list)
    comparators: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deployment_settings: list[str] = Field(default_factory=list)
    evidence_terms: list[str] = Field(default_factory=list)
    counterevidence_terms: list[str] = Field(default_factory=list)
    relation_patterns: list[str] = Field(default_factory=list)
    frequent_node_labels: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProblemFormulation(BaseModel):
    model_config = ConfigDict(extra="allow")

    formulation_id: str
    source_gap_id: str
    source_motif_type: str = ""
    source_gap_description: str = ""
    counterevidence_status: str = ""
    remaining_gap_scope: str = ""
    short_name: str = ""
    formulation_question: str = ""
    problem_context: str = ""
    method_or_system_family: str = ""
    input_or_data_setting: str = ""
    environment_or_deployment_setting: str = ""
    feedback_or_observation_model: str = ""
    objective: str = ""
    metric_or_target_quantity: str = ""
    comparator_or_baseline: str = ""
    assumption_relaxed: str = ""
    failure_condition_targeted: str = ""
    resource_or_constraint_dimension: str = ""
    evaluation_protocol: str = ""
    theoretical_target: str = ""
    empirical_target: str = ""
    algorithmic_target: str = ""
    known_counterevidence: str = ""
    why_counterevidence_does_not_solve: str = ""
    likely_existing_literature: str = ""
    novelty_risk: str = "medium"
    feasibility: str = "moderate"
    formulation_type: str = "algorithm"
    viability_label: str = "NEEDS_EXTERNAL_LIT_CHECK"
    viability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    falsification_condition: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    counterevidence_papers: list[str] = Field(default_factory=list)
    traceability_path: list[str] = Field(default_factory=list)

    @field_validator("formulation_type", mode="before")
    @classmethod
    def _coerce_ftype(cls, v: Any) -> str:
        s = str(v).strip().lower().replace(" ", "_")
        return s if s in _FORMULATION_TYPES else "algorithm"

    @field_validator("viability_label", mode="before")
    @classmethod
    def _coerce_vlabel(cls, v: Any) -> str:
        s = str(v).strip().upper().replace(" ", "_")
        return s if s in _VIABILITY_LABELS else "NEEDS_EXTERNAL_LIT_CHECK"

    def is_acceptable(self) -> bool:
        return self.viability_label in _ACCEPTABLE_FORMULATION_LABELS

    def has_required_fields(self) -> bool:
        return bool(self.formulation_id and self.source_gap_id and self.formulation_question)
