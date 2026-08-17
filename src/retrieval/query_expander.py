"""Profile-aware query expander.

Topic-specific expansion templates live in TopicProfileConfig.query_expansions.
There are no hardcoded ICL (or any other topic) expansions here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .query_intent import RetrievalIntent


def expand_from_intent(intent: "RetrievalIntent", *, max_queries: int = 10) -> list[str]:
    """Return expanded queries driven by the active RetrievalIntent."""
    base = intent.normalized_topic
    queries: list[str] = [base]
    seen = {base.lower()}

    # Profile-supplied expansions come first (highest priority)
    # These are set on the intent by build_intent_with_expansions()
    for q in intent.expanded_queries:
        if q.lower() not in seen:
            queries.append(q)
            seen.add(q.lower())
        if len(queries) >= max_queries:
            return queries

    # Angle-based generic expansions derived from the base topic
    angles = _generic_angle_queries(base, intent.intent_mode, intent.theory_weight, intent.empirical_weight, intent.robustness_weight)
    for q in angles:
        if q.lower() not in seen:
            queries.append(q)
            seen.add(q.lower())
        if len(queries) >= max_queries:
            return queries

    return queries


def expand_query(query: str, *, max_queries: int = 10) -> list[str]:
    """Backwards-compatible rule-based expansion (no topic hardcoding)."""
    from .query_intent import _tokenise_to_phrases
    base_phrases = _tokenise_to_phrases(query)
    topic = " ".join(base_phrases[:3]) if base_phrases else query

    queries = [query]
    seen = {query.lower()}

    angles = _generic_angle_queries(query, "balanced", 0.33, 0.33, 0.33)
    for q in angles:
        if q.lower() not in seen:
            queries.append(q)
            seen.add(q.lower())
        if len(queries) >= max_queries:
            break

    return queries


def expand_query_with_llm(
    query: str,
    *,
    base_url: str,
    model: str = "Qwen/Qwen3.5-9B",
    api_key: str = "EMPTY",
    max_queries: int = 10,
    intent: "RetrievalIntent | None" = None,
) -> list[str]:
    """LLM-assisted query expansion. Falls back to rule-based on failure."""
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key, timeout=60)

        if intent and intent.intent_mode in ("theory", "mechanism"):
            angle_hint = "Focus on theoretical analysis, mechanisms, and formal understanding."
        elif intent and intent.intent_mode == "empirical":
            angle_hint = "Focus on empirical evaluation, benchmarks, and datasets."
        elif intent and intent.intent_mode == "robustness":
            angle_hint = "Focus on robustness, failure modes, sensitivity, and brittleness."
        else:
            angle_hint = "Cover diverse angles: theory, empirical, robustness, applications."

        prompt = (
            f"Generate {max_queries - 1} natural-language search queries that are variations of the following "
            f"research query. {angle_hint} "
            f"Return one query per line, no numbering, no explanation.\n\nQuery: {query}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        content = (resp.choices[0].message.content or "").strip()
        extras = [line.strip("- •·0123456789. ") for line in content.splitlines() if line.strip()]
        queries = [query] + [q for q in extras if q and q.lower() != query.lower()]
        return queries[:max_queries]
    except Exception:
        if intent:
            return expand_from_intent(intent, max_queries=max_queries)
        return expand_query(query, max_queries=max_queries)


def attach_profile_expansions(intent: "RetrievalIntent", config: "object") -> "RetrievalIntent":
    """Populate intent.expanded_queries from the active profile, if any."""
    profile = getattr(config, "active_profile", lambda: None)()
    if profile and profile.query_expansions:
        intent.expanded_queries = list(profile.query_expansions)
    return intent


def _generic_angle_queries(topic: str, mode: str, t_w: float, e_w: float, r_w: float) -> list[str]:
    """Generate angle-based query variants for any topic string."""
    variants: list[str] = []
    if t_w >= 0.3 or mode in ("theory", "mechanism", "auto", "balanced"):
        variants.append(f"{topic} theoretical analysis")
        variants.append(f"{topic} mechanism understanding")
    if e_w >= 0.3 or mode in ("empirical", "auto", "balanced"):
        variants.append(f"{topic} empirical evaluation benchmark")
        variants.append(f"{topic} evaluation datasets metrics")
    if r_w >= 0.3 or mode in ("robustness", "auto", "balanced"):
        variants.append(f"{topic} robustness failure modes")
        variants.append(f"{topic} sensitivity limitations")
    variants.append(f"{topic} survey overview")
    return variants
