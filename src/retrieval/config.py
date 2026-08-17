"""Config schema for the paper retrieval pipeline.

All ICL-specific or topic-specific phrases live in topic profiles,
not in the pipeline code. Generic defaults work for any ML/NLP topic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel, Field
    _PYDANTIC = True
except ImportError:
    from dataclasses import dataclass, field as Field
    BaseModel = object  # type: ignore
    _PYDANTIC = False


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_yaml(path: str | Path) -> dict[str, Any]:
    # Try standard yaml, then ruamel.yaml, then tomllib, then JSON
    for _try in ("yaml", "ruamel_yaml"):
        try:
            if _try == "yaml":
                import yaml
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            else:
                from ruamel.yaml import YAML
                y = YAML(typ="safe")
                with open(path, encoding="utf-8") as f:
                    return dict(y.load(f) or {})
        except ImportError:
            continue
        except Exception:
            raise
    import json
    # Last resort: JSON file with same stem
    json_path = str(path).rsplit(".", 1)[0] + ".json"
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def _merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base (override wins)."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


# ── sub-configs ───────────────────────────────────────────────────────────────

class RunConfig(BaseModel):
    run_id: str | None = None
    description: str = ""


class QueryConfig(BaseModel):
    text: str = ""
    intent: str = "balanced"  # auto | theory | empirical | balanced | robustness | mechanism
    topic_profile: str | None = None  # name of a profile in topic_profiles


class YearConfig(BaseModel):
    min_year: int = 2020
    max_year: int | None = None


class SourceConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["arxiv", "semantic_scholar", "openalex"])
    max_results_per_query: int = 50
    max_raw_candidates: int = 500
    use_paper_search_mcp: bool = False


class VenueConfig(BaseModel):
    # mode controls which venues to target on OpenReview and other registries
    mode: str = "a_star"   # a_star | top_ml | top_nlp | top_cv | top_ir | custom
    custom_venues: list[str] = Field(default_factory=list)
    # whether to include OpenReview as a source (it uses venue lists, not keyword search)
    include_openreview: bool = True


class RetrievalBehaviorConfig(BaseModel):
    final_k: int = 20
    use_embeddings: bool = False
    use_cross_encoder: bool = False
    use_citation_expansion: bool = False
    download_pdfs: bool = False
    llm_base_url: str | None = None
    llm_model: str | None = None
    model_cache_dir: str | None = None


class ScoringConfig(BaseModel):
    keep_threshold: float = 6.0
    # Weights used in relevance scoring (per RetrievalIntent, not hardcoded for ICL)
    pos_title_weight: float = 6.0
    pos_abstract_weight: float = 4.0
    anchor_title_weight: float = 4.0
    anchor_abstract_weight: float = 3.0
    neg_title_penalty: float = -7.0
    neg_abstract_penalty: float = -3.0
    off_domain_penalty: float = -4.0
    fos_bonus: float = 2.0
    citation_bonus_max: float = 3.0
    multi_source_bonus: float = 1.0


class DiversityConfig(BaseModel):
    lambda_mult: float = 0.75
    diversity_by_venue: bool = True
    diversity_by_year: bool = False


class LoggingConfig(BaseModel):
    verbose: bool = True
    save_audit_trail: bool = True
    output_dir: str | None = None


class TopicProfileConfig(BaseModel):
    """Per-topic phrase lists and search expansion templates.

    These are the ONLY place where topic-specific (e.g. ICL) phrases live.
    The scoring pipeline reads phrases from the active profile — it has no
    built-in knowledge of any particular research topic.
    """
    name: str = ""
    # High-signal phrases: a match in the title is strong evidence
    positive_phrases: list[str] = Field(default_factory=list)
    # Domain anchors: weaker positive signal (e.g. "large language model")
    anchor_phrases: list[str] = Field(default_factory=list)
    # Phrases that reliably indicate off-topic papers
    negative_phrases: list[str] = Field(default_factory=list)
    # Extra search query variants for the query expander
    query_expansions: list[str] = Field(default_factory=list)
    # arXiv categories to target (used by arXiv backend and scoring)
    arxiv_categories: list[str] = Field(default_factory=lambda: ["cs.LG", "cs.CL", "cs.AI", "stat.ML"])
    # For OpenReview: require at least this many positive_phrase hits in abstract-only papers
    openreview_min_abstract_hits: int = 2
    # Fields of study considered on-domain (for FoS scoring bonus)
    on_domain_fields: list[str] = Field(default_factory=lambda: [
        "natural language processing", "artificial intelligence",
        "machine learning", "information retrieval",
    ])
    # Fields of study considered off-domain (for FoS penalty)
    off_domain_fields: list[str] = Field(default_factory=lambda: [
        "computer vision", "robotics", "medicine", "biology",
        "chemistry", "materials science", "physics",
    ])


class TopicProfilesConfig(BaseModel):
    profiles: dict[str, TopicProfileConfig] = Field(default_factory=dict)


class RetrievalConfig(BaseModel):
    run: RunConfig = Field(default_factory=RunConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    years: YearConfig = Field(default_factory=YearConfig)
    sources: SourceConfig = Field(default_factory=SourceConfig)
    venues: VenueConfig = Field(default_factory=VenueConfig)
    behavior: RetrievalBehaviorConfig = Field(default_factory=RetrievalBehaviorConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    diversity: DiversityConfig = Field(default_factory=DiversityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    topic_profiles: TopicProfilesConfig = Field(default_factory=TopicProfilesConfig)

    def active_profile(self) -> TopicProfileConfig | None:
        """Return the active topic profile if one is set and registered."""
        pname = self.query.topic_profile
        if not pname:
            return None
        return self.topic_profiles.profiles.get(pname)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RetrievalConfig":
        data = _load_yaml(path)
        return cls.model_validate(data) if hasattr(cls, "model_validate") else cls(**data)

    @classmethod
    def from_yaml_with_defaults(cls, path: str | Path, defaults_path: str | Path | None = None) -> "RetrievalConfig":
        """Load config, optionally deep-merging on top of a defaults file."""
        if defaults_path and Path(defaults_path).exists():
            base = _load_yaml(defaults_path)
            override = _load_yaml(path)
            data = _merge(base, override)
        else:
            data = _load_yaml(path)
        return cls.model_validate(data) if hasattr(cls, "model_validate") else cls(**data)

    def apply_cli_overrides(self, overrides: dict[str, Any]) -> "RetrievalConfig":
        """Shallow-merge CLI key=value overrides (dot-notation not supported here)."""
        data = self.model_dump() if hasattr(self, "model_dump") else self.__dict__
        data = _merge(data, overrides)
        return self.__class__.model_validate(data) if hasattr(self.__class__, "model_validate") else self.__class__(**data)

    def dump_yaml(self, path: str | Path) -> None:
        data = self.model_dump() if hasattr(self, "model_dump") else self.__dict__
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        except ImportError:
            try:
                from ruamel.yaml import YAML
                y = YAML()
                y.default_flow_style = False
                with open(path, "w", encoding="utf-8") as f:
                    y.dump(data, f)
            except ImportError:
                import json
                json_path = str(path).rsplit(".", 1)[0] + ".json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
