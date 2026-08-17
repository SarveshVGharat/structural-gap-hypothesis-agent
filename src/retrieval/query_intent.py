"""Derive a RetrievalIntent from a RetrievalConfig.

The intent bundles phrase lists and query expansions that the rest of the
pipeline consumes. ICL-specific (or any other topic-specific) phrases come
exclusively from the active TopicProfileConfig; there are no hardcoded topic
assumptions here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import RetrievalConfig, TopicProfileConfig


@dataclass
class RetrievalIntent:
    """Resolved intent produced from a RetrievalConfig."""

    normalized_topic: str
    # Phrases that, if found in a paper's title, are strong positive signal
    must_have_phrases: list[str] = field(default_factory=list)
    # Phrases that, if found in abstract, provide weaker positive signal
    should_have_phrases: list[str] = field(default_factory=list)
    # Phrases that indicate an off-topic paper
    exclude_phrases: list[str] = field(default_factory=list)
    # arXiv category targets
    arxiv_categories: list[str] = field(default_factory=lambda: ["cs.LG", "cs.CL", "cs.AI", "stat.ML"])
    # Field-of-study bonuses / penalties
    on_domain_fields: list[str] = field(default_factory=list)
    off_domain_fields: list[str] = field(default_factory=list)
    # Intent weights (used by query expander and scorer to bias retrieval)
    theory_weight: float = 0.33
    empirical_weight: float = 0.33
    robustness_weight: float = 0.33
    # Derived expanded queries (produced separately by query_expander.py)
    expanded_queries: list[str] = field(default_factory=list)
    # Meta
    intent_mode: str = "balanced"
    profile_name: str | None = None
    # Minimum abstract hits required for OpenReview acceptance (client-side filter)
    openreview_min_abstract_hits: int = 2


def build_intent(config: "RetrievalConfig") -> RetrievalIntent:
    """Build a RetrievalIntent from a config, merging generic base with active profile."""
    from .config import TopicProfileConfig

    profile: TopicProfileConfig | None = config.active_profile()
    query_text = config.query.text.strip()
    intent_mode = config.query.intent

    # Start from generic: derive phrases from the query itself
    # (no hardcoded topic knowledge — just tokenisation)
    generic_phrases = _tokenise_to_phrases(query_text)

    # Theory / empirical / robustness weights from intent mode
    t_w, e_w, r_w = _intent_weights(intent_mode)

    if profile:
        must_have = list(profile.positive_phrases) or generic_phrases
        should_have = list(profile.anchor_phrases)
        exclude = list(profile.negative_phrases)
        arxiv_cats = list(profile.arxiv_categories)
        on_domain = list(profile.on_domain_fields)
        off_domain = list(profile.off_domain_fields)
        or_min_hits = profile.openreview_min_abstract_hits
        profile_name = profile.name or config.query.topic_profile
    else:
        # Generic: use tokenised query as must_have phrases, empty exclude list
        must_have = generic_phrases
        should_have = []
        exclude = []
        arxiv_cats = ["cs.LG", "cs.CL", "cs.AI", "stat.ML"]
        on_domain = [
            "natural language processing", "artificial intelligence",
            "machine learning", "information retrieval",
        ]
        off_domain = [
            "computer vision", "robotics", "medicine", "biology",
            "chemistry", "materials science", "physics",
        ]
        or_min_hits = 2
        profile_name = None

    return RetrievalIntent(
        normalized_topic=query_text,
        must_have_phrases=must_have,
        should_have_phrases=should_have,
        exclude_phrases=exclude,
        arxiv_categories=arxiv_cats,
        on_domain_fields=on_domain,
        off_domain_fields=off_domain,
        theory_weight=t_w,
        empirical_weight=e_w,
        robustness_weight=r_w,
        intent_mode=intent_mode,
        profile_name=profile_name,
        openreview_min_abstract_hits=or_min_hits,
    )


def _intent_weights(mode: str) -> tuple[float, float, float]:
    """Return (theory, empirical, robustness) weights for a given intent mode."""
    if mode == "theory":
        return 0.7, 0.15, 0.15
    if mode == "empirical":
        return 0.15, 0.7, 0.15
    if mode == "robustness":
        return 0.15, 0.15, 0.7
    if mode == "mechanism":
        return 0.6, 0.2, 0.2
    # balanced / auto
    return 0.33, 0.33, 0.33


_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "was",
    "has", "can", "its", "into", "via", "how", "why", "what", "does",
    "when", "where", "which", "not", "all", "any", "use", "using",
}


def _tokenise_to_phrases(query: str) -> list[str]:
    """Extract meaningful multi-word phrases and single terms from a query string."""
    words = [w.lower() for w in re.split(r"\W+", query) if len(w) > 2 and w.lower() not in _STOPWORDS]
    # Return the full cleaned query as the primary phrase + individual words
    cleaned = " ".join(words)
    phrases = []
    if cleaned:
        phrases.append(cleaned)
    phrases.extend(w for w in words if w not in phrases)
    return phrases[:8]  # cap to avoid overly broad matching
