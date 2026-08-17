from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    quota: int = 15
    enabled: bool = True


class HardFilterConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    require_positive_in_title_or_abstract: bool = True
    reject_if_negative_without_positive: bool = True
    openreview_requires_strong_positive: bool = True
    reject_llm_contamination_for_non_llm_topics: bool = False


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    positive_title_weight: float = 6.0
    positive_abstract_weight: float = 4.0
    anchor_weight: float = 2.0
    negative_title_penalty: float = 7.0
    negative_abstract_penalty: float = 3.0
    preferred_venue_bonus: float = 1.0
    semantic_similarity_weight: float = 10.0
    keep_threshold: float = 10.0


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    target_papers: int = 40
    max_raw_candidates: int = 500
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    positive_phrases: list[str] = Field(default_factory=list)
    anchor_phrases: list[str] = Field(default_factory=list)
    negative_phrases: list[str] = Field(default_factory=list)
    preferred_venues: list[str] = Field(default_factory=list)
    query_expansions: list[str] = Field(default_factory=list)
    hard_filters: HardFilterConfig = Field(default_factory=HardFilterConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)

    @model_validator(mode="before")
    @classmethod
    def _coerce_sources(cls, data: Any) -> Any:
        if isinstance(data, dict) and "sources" in data:
            raw = data["sources"]
            if isinstance(raw, dict):
                data["sources"] = {
                    k: v if isinstance(v, dict) else {"quota": 15, "enabled": bool(v)}
                    for k, v in raw.items()
                }
        return data


class ExtractionConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    focus: list[str] = Field(default_factory=lambda: ["methods", "results", "limitations", "assumptions", "failure_modes"])
    relation_ontology: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)


class CanonConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = True
    use_embedding_clustering: bool = False
    similarity_threshold: float = 0.88


class GraphConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    canonicalization: CanonConfig = Field(default_factory=CanonConfig)
    condition_clustering: CanonConfig = Field(default_factory=CanonConfig)
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class MotifThresholds(BaseModel):
    model_config = ConfigDict(extra="allow")
    min_degree: int = 3
    min_supporting_papers: int = 2
    min_methods: int = 2
    min_papers: int = 2
    require_opposite_polarity: bool = True


class GapDetectionConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled_motifs: list[str] = Field(default_factory=lambda: ["sparse_evaluation", "assumption_mismatch", "conflicting_claims", "shared_failure_condition"])
    motif_thresholds: dict[str, MotifThresholds] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_thresholds(cls, data: Any) -> Any:
        if isinstance(data, dict) and "motif_thresholds" in data:
            raw = data["motif_thresholds"]
            if isinstance(raw, dict):
                data["motif_thresholds"] = {
                    k: v if isinstance(v, dict) else {}
                    for k, v in raw.items()
                }
        return data


class VerificationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    top_k_to_verify: int = 10
    agents: list[str] = Field(default_factory=lambda: ["advocate", "skeptic", "domain_expert", "methodologist"])
    confidence_aggregation: str = "weighted_average"


class EvolutionConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    initial_variants_per_gap: int = 3
    population_size: int = 40
    generations: int = 8
    mutation_rate: float = 0.35
    random_immigrants_per_generation: int = 4
    use_pareto_ranking: bool = True
    diversity_weight: float = 0.25


class ReportConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    top_k_hypotheses: int = 8
    include_evidence_bundles: bool = True
    include_caveats: bool = True


class TopicProfile(BaseModel):
    """Full topic profile loaded from configs/topics/<name>.yaml."""
    model_config = ConfigDict(extra="allow")

    topic_name: str
    description: str = ""
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    gap_detection: GapDetectionConfig = Field(default_factory=GapDetectionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    final_report: ReportConfig = Field(default_factory=ReportConfig)

    def enabled_sources(self) -> list[str]:
        return [k for k, v in self.retrieval.sources.items() if v.enabled]

    def source_quota(self, source: str) -> int:
        src = self.retrieval.sources.get(source)
        return src.quota if src else 0

    def alias_map(self) -> dict[str, str]:
        """Return phrase→canonical_key mapping from graph.aliases."""
        out: dict[str, str] = {}
        for canonical, phrases in self.graph.aliases.items():
            for phrase in phrases:
                out[phrase.lower()] = canonical
        return out


def load_topic_profile(path: str | Path) -> TopicProfile:
    """Load and validate a topic profile YAML. Fails loudly on missing required fields."""
    import sys
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Topic profile not found: {p}")
    raw = _load_yaml(p)
    if not isinstance(raw, dict):
        raise ValueError(f"Topic profile must be a YAML mapping, got {type(raw)}: {p}")
    if "topic_name" not in raw:
        raise ValueError(f"topic_name is required in topic profile: {p}")
    return TopicProfile.model_validate(raw)


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pass
    try:
        from ruamel.yaml import YAML
        y = YAML()
        with path.open("r", encoding="utf-8") as f:
            return dict(y.load(f))
    except ImportError:
        raise ImportError("Neither pyyaml nor ruamel.yaml is installed. Install one of them.")
