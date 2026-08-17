from __future__ import annotations

import copy
import logging
from collections import defaultdict
from typing import Any, Literal

import networkx as nx

from .gap_objects import MotifHit
from .utils import bounded, model_dump, normalize_label, stable_id

_logger = logging.getLogger(__name__)


MOTIF_QUERIES = [
    {
        "name": "shared_failure_condition",
        "description": "FailureCondition nodes connected to multiple Methods/Papers from at least two papers.",
    },
    {
        "name": "repeated_unaddressed_limitation",
        "description": "Limitation nodes mentioned by at least N papers with no addresses edge.",
    },
    {
        "name": "conflicting_claims",
        "description": "Claim nodes linked by contradicts edges OR methods with opposite-polarity relations across papers.",
    },
    {
        "name": "sparse_evaluation",
        "description": "Method/task pairs with repeated mention but sparse dataset/metric evaluation.",
    },
    {
        "name": "assumption_mismatch",
        "description": "Methods that both assume a condition and fail under a related condition.",
    },
    {
        "name": "unrealistic_assumption",
        "description": "Methods that rely on assumptions requiring oracle access, known parameters, or idealized conditions unavailable in practice.",
    },
    {
        "name": "theory_practice_gap",
        "description": "Methods with documented theoretical results or claims but no real dataset/benchmark evaluation, yet with known failure conditions.",
    },
    {
        "name": "transfer_solution_gap",
        "description": "A limitation/failure is solved for Method A but still affects Method B — missed transfer opportunity.",
    },
    {
        "name": "unresolved_tradeoff",
        "description": "Method improves something but introduces an unresolved limitation that no method currently addresses.",
    },
    {
        "name": "missing_stress_test",
        "description": "A failure condition affects multiple methods/papers but has little benchmark coverage.",
    },
    {
        "name": "claim_without_measurement",
        "description": "Method makes positive claims (addresses/improves_over) but has no measurement support.",
    },
    {
        "name": "missing_baseline_comparison",
        "description": "Method is evaluated on benchmarks but never compared to other methods via improves_over.",
    },
    {
        "name": "shared_unrealistic_assumption",
        "description": "Multiple methods share the same idealized assumption, and at least one has documented failures or limitations.",
    },
]

KNOWN_MOTIFS: frozenset[str] = frozenset(q["name"] for q in MOTIF_QUERIES)

# Maps motif name -> legacy disable key in motifs config
_LEGACY_DISABLE_KEYS: dict[str, str] = {
    "sparse_evaluation": "disable_sparse_evaluation",
    "transfer_solution_gap": "disable_transfer_solution_gap",
    "unresolved_tradeoff": "disable_unresolved_tradeoff",
    "missing_stress_test": "disable_missing_stress_test",
    "claim_without_measurement": "disable_claim_without_measurement",
    "missing_baseline_comparison": "disable_missing_baseline_comparison",
    "shared_unrealistic_assumption": "disable_shared_unrealistic_assumption",
}

# Strict threshold overrides per motif (merged into config when state=="strict")
_STRICT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "claim_without_measurement": {
        "min_claim_without_measurement_papers": 2,
        "min_claim_without_measurement_claim_edges": 2,
        "require_claim_keyword": True,
        "max_claim_measurement_edges": 0,
    },
    "unresolved_tradeoff": {
        "min_tradeoff_positive_edges": 2,
        "min_tradeoff_limitation_mentions": 2,
        "min_tradeoff_papers": 2,
    },
    "sparse_evaluation": {
        "sparse_evaluation_min_mentions": 4,
        "sparse_evaluation_max_evaluations": 1,
    },
    "missing_baseline_comparison": {
        "min_baseline_eval_edges": 2,
        "min_baseline_method_papers": 2,
    },
    "theory_practice_gap": {
        "min_theory_practice_papers": 3,
    },
}

# Built-in named profiles
_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "conservative_debug": {
        "default_enabled": False,
        "enabled": [
            "conflicting_claims", "unrealistic_assumption",
            "shared_unrealistic_assumption", "assumption_mismatch",
            "repeated_unaddressed_limitation", "missing_stress_test",
        ],
        "strict": [],
        "disabled": [
            "claim_without_measurement", "unresolved_tradeoff",
            "missing_baseline_comparison", "sparse_evaluation", "theory_practice_gap",
        ],
    },
    "bandits_theory": {
        "default_enabled": False,
        "enabled": [
            "conflicting_claims", "unrealistic_assumption",
            "shared_unrealistic_assumption", "assumption_mismatch",
            "theory_practice_gap", "shared_failure_condition", "missing_stress_test",
        ],
        "strict": ["sparse_evaluation"],
        "disabled": [
            "claim_without_measurement", "unresolved_tradeoff", "missing_baseline_comparison",
        ],
    },
    "llm_reasoning": {
        "default_enabled": False,
        "enabled": [
            "conflicting_claims", "unrealistic_assumption", "assumption_mismatch",
            "repeated_unaddressed_limitation", "missing_stress_test",
        ],
        "strict": ["sparse_evaluation", "theory_practice_gap"],
        "disabled": [
            "claim_without_measurement", "unresolved_tradeoff",
            "missing_baseline_comparison", "shared_unrealistic_assumption",
        ],
    },
    "empirical_ml": {
        "default_enabled": False,
        "enabled": [
            "conflicting_claims", "shared_failure_condition",
            "repeated_unaddressed_limitation", "missing_stress_test",
            "sparse_evaluation", "missing_baseline_comparison",
        ],
        "strict": ["claim_without_measurement", "unresolved_tradeoff"],
        "disabled": [],
    },
}

# Keywords that signal an assumption is idealized / unavailable in practice
_IDEALIZED_KEYWORDS = {
    "known", "oracle", "access to", "requires knowledge", "assumes access",
    "given", "available", "labeled", "ground truth", "perfect", "infinite",
    "iid", "i.i.d", "stationary", "gaussian", "linear", "convex",
    "requires labeled", "requires oracle", "known horizon", "known distribution",
    "known reward", "known variance", "known noise", "known parameter",
}

# Keywords that signal a positive performance claim
_CLAIM_KEYWORDS = {
    "robust", "robustness", "efficient", "efficiency", "scalable", "scalability",
    "generalize", "generalization", "improves", "outperforms", "better",
    "reduces", "increases", "accurate", "accuracy",
}

# Relations that imply positive outcome
_POSITIVE_RELATIONS = {"improves_over", "evaluated_on", "addresses", "robust_to"}
# Relations that imply negative outcome
_NEGATIVE_RELATIONS = {"fails_under", "limited_by", "not_addressed_by", "sensitive_to"}
# Pairs of directly opposite relations
_OPPOSITE_PAIRS = [
    ("improves_over", "fails_under"),
    ("improves_over", "limited_by"),
    ("addresses", "not_addressed_by"),
]


def resolve_motif_activation(
    config: dict[str, Any] | None,
    logger: logging.Logger | None = None,
) -> dict[str, Literal["off", "normal", "strict"]]:
    """Return activation state for every known motif.

    Resolution order:
    1. If motif_profile is set, load that profile (user-defined in config takes priority over built-ins).
    2. Apply explicit motifs.enabled / motifs.disabled / motifs.strict overrides on top.
    3. disabled always wins over enabled or strict (with a warning logged).
    4. strict wins over enabled (with a warning logged).
    5. If no new-style keys and no motif_profile, fall back to legacy disable_* keys.
    """
    log = logger or _logger
    cfg_full: dict[str, Any] = config or {}
    motifs_cfg: dict[str, Any] = cfg_full.get("motifs", {}) if isinstance(cfg_full.get("motifs"), dict) else {}

    has_new_keys = any(k in motifs_cfg for k in ("enabled", "disabled", "strict"))
    has_profile = "motif_profile" in cfg_full

    if has_new_keys or has_profile:
        return _resolve_profile_activation(cfg_full, motifs_cfg, log)
    return _resolve_legacy_activation(motifs_cfg, log)


def _resolve_profile_activation(
    cfg_full: dict[str, Any],
    motifs_cfg: dict[str, Any],
    log: logging.Logger,
) -> dict[str, Literal["off", "normal", "strict"]]:
    log.info("Motif activation mode: new_profile_activation")

    # Load base profile if motif_profile is set
    profile_name: str | None = cfg_full.get("motif_profile")
    profile: dict[str, Any] = {}
    if profile_name:
        user_profiles: dict[str, Any] = cfg_full.get("motif_profiles", {})
        if profile_name in user_profiles:
            profile = user_profiles[profile_name]
            log.info("Loaded motif profile '%s' (user-defined)", profile_name)
        elif profile_name in _BUILTIN_PROFILES:
            profile = _BUILTIN_PROFILES[profile_name]
            log.info("Loaded motif profile '%s' (built-in)", profile_name)
        else:
            raise ValueError(
                f"Unknown motif_profile '{profile_name}'. "
                f"Valid built-in profiles: {sorted(_BUILTIN_PROFILES)}"
            )

    default_enabled: bool = bool(
        motifs_cfg.get("default_enabled", profile.get("default_enabled", False))
    )

    profile_enabled: set[str] = set(profile.get("enabled", []))
    profile_disabled: set[str] = set(profile.get("disabled", []))
    profile_strict: set[str] = set(profile.get("strict", []))
    explicit_enabled: set[str] = set(motifs_cfg.get("enabled", []))
    explicit_disabled: set[str] = set(motifs_cfg.get("disabled", []))
    explicit_strict: set[str] = set(motifs_cfg.get("strict", []))

    # Validate motif names
    all_named = (
        profile_enabled | profile_disabled | profile_strict
        | explicit_enabled | explicit_disabled | explicit_strict
    )
    unknown = all_named - KNOWN_MOTIFS
    if unknown:
        raise ValueError(
            f"Unknown motif name(s) in config: {sorted(unknown)}. "
            f"Valid motifs: {sorted(KNOWN_MOTIFS)}"
        )

    # Build activation for every known motif
    result: dict[str, Any] = {}
    for motif in KNOWN_MOTIFS:
        # Start from profile
        if motif in profile_disabled:
            state: str = "off"
        elif motif in profile_strict:
            state = "strict"
        elif motif in profile_enabled:
            state = "normal"
        else:
            state = "normal" if default_enabled else "off"

        # Apply explicit overrides (disabled > strict > enabled)
        if motif in explicit_disabled:
            if motif in explicit_enabled:
                log.warning("Motif '%s' is in both enabled and disabled — disabled wins", motif)
            if motif in explicit_strict:
                log.warning("Motif '%s' is in both strict and disabled — disabled wins", motif)
            state = "off"
        elif motif in explicit_strict:
            if motif in explicit_enabled:
                log.warning("Motif '%s' is in both enabled and strict — treating as strict", motif)
            state = "strict"
        elif motif in explicit_enabled:
            state = "normal"

        result[motif] = state

    normal = sorted(m for m, s in result.items() if s == "normal")
    strict = sorted(m for m, s in result.items() if s == "strict")
    disabled = sorted(m for m, s in result.items() if s == "off")
    log.info(
        "Activation summary — profile=%s default_enabled=%s normal=%s strict=%s off=%s",
        profile_name or "none", default_enabled, normal, strict, disabled,
    )
    return result  # type: ignore[return-value]


def _resolve_legacy_activation(
    motifs_cfg: dict[str, Any],
    log: logging.Logger,
) -> dict[str, Literal["off", "normal", "strict"]]:
    log.info("Motif activation mode: legacy_disable_keys (all motifs on by default)")
    result: dict[str, Any] = {}
    for motif in KNOWN_MOTIFS:
        legacy_key = _LEGACY_DISABLE_KEYS.get(motif)
        if legacy_key and motifs_cfg.get(legacy_key, False):
            result[motif] = "off"
        else:
            result[motif] = "normal"
    return result  # type: ignore[return-value]


def merge_strict_thresholds(config: dict[str, Any], motif_name: str) -> dict[str, Any]:
    """Return a copy of config with strict threshold overrides merged into motifs sub-config."""
    defaults = _STRICT_THRESHOLDS.get(motif_name, {})
    user_overrides = (
        (config.get("motifs") or {})
        .get("strict_thresholds", {})
        .get(motif_name, {})
    )
    if not defaults and not user_overrides:
        return config
    merged = copy.deepcopy(config)
    motifs = merged.setdefault("motifs", {})
    motifs.update(defaults)       # built-in strict defaults
    motifs.update(user_overrides) # user's explicit strict overrides win
    return merged


def _run_detector(motif_name: str, graph: nx.MultiDiGraph, config: dict[str, Any]) -> list[MotifHit]:
    """Dispatch to the correct detector function reading thresholds from config."""
    cfg = config.get("motifs", config) if isinstance(config.get("motifs"), dict) else config
    if motif_name == "shared_failure_condition":
        return shared_failure_condition(graph, int(cfg.get("min_shared_failure_methods", 2)))
    if motif_name == "repeated_unaddressed_limitation":
        return repeated_unaddressed_limitation(graph, int(cfg.get("min_repeated_limitation_papers", 2)))
    if motif_name == "conflicting_claims":
        return conflicting_claims(graph)
    if motif_name == "sparse_evaluation":
        return sparse_evaluation(
            graph,
            min_mentions=int(cfg.get("sparse_evaluation_min_mentions", 3)),
            max_evaluations=int(cfg.get("sparse_evaluation_max_evaluations", 1)),
        )
    if motif_name == "assumption_mismatch":
        return assumption_mismatch(graph)
    if motif_name == "unrealistic_assumption":
        return unrealistic_assumption(graph)
    if motif_name == "theory_practice_gap":
        return theory_practice_gap(graph, min_papers=int(cfg.get("min_theory_practice_papers", 2)))
    if motif_name == "transfer_solution_gap":
        return transfer_solution_gap(
            graph,
            min_papers=int(cfg.get("min_transfer_gap_papers", 2)),
            min_methods=int(cfg.get("min_transfer_gap_methods", 2)),
        )
    if motif_name == "unresolved_tradeoff":
        return unresolved_tradeoff(
            graph,
            min_positive_edges=int(cfg.get("min_tradeoff_positive_edges", 1)),
            min_limitation_mentions=int(cfg.get("min_tradeoff_limitation_mentions", 1)),
            min_papers=int(cfg.get("min_tradeoff_papers", 1)),
        )
    if motif_name == "missing_stress_test":
        return missing_stress_test(
            graph,
            min_methods=int(cfg.get("min_stress_test_methods", 2)),
            min_papers=int(cfg.get("min_stress_test_papers", 2)),
            max_eval_edges=int(cfg.get("max_stress_test_eval_edges", 1)),
        )
    if motif_name == "claim_without_measurement":
        return claim_without_measurement(
            graph,
            max_measurement_edges=int(cfg.get("max_claim_measurement_edges", 0)),
            require_claim_keyword=bool(cfg.get("require_claim_keyword", False)),
            min_papers=int(cfg.get("min_claim_without_measurement_papers", 1)),
            min_claim_edges=int(cfg.get("min_claim_without_measurement_claim_edges", 1)),
        )
    if motif_name == "missing_baseline_comparison":
        return missing_baseline_comparison(
            graph,
            min_eval_edges=int(cfg.get("min_baseline_eval_edges", 1)),
            min_method_papers=int(cfg.get("min_baseline_method_papers", 1)),
        )
    if motif_name == "shared_unrealistic_assumption":
        return shared_unrealistic_assumption(graph, min_methods=int(cfg.get("min_shared_unrealistic_methods", 2)))
    _logger.warning("No detector implemented for motif '%s'", motif_name)
    return []


def run_all_motif_queries(graph: nx.MultiDiGraph, config: dict[str, Any] | None = None) -> list[MotifHit]:
    activation = resolve_motif_activation(config)
    hits: list[MotifHit] = []
    for motif_name in sorted(KNOWN_MOTIFS):  # sorted for deterministic order
        state = activation[motif_name]
        if state == "off":
            _logger.debug("Skipping motif '%s' (activation=off)", motif_name)
            continue
        local_config = merge_strict_thresholds(config or {}, motif_name) if state == "strict" else (config or {})
        _logger.debug("Running motif '%s' (activation=%s)", motif_name, state)
        hits.extend(_run_detector(motif_name, graph, local_config))
    return hits


def shared_failure_condition(graph: nx.MultiDiGraph, min_methods: int = 2) -> list[MotifHit]:
    hits = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != "FailureCondition":
            continue

        # Path A: Method nodes with explicit fails_under edges
        methods_explicit: list[str] = []
        edge_ids: list[str] = []
        paper_ids: set[str] = set()
        spans: list[dict[str, Any]] = []
        for source, _, key, edata in graph.in_edges(node_id, keys=True, data=True):
            rel = edata.get("relation", "")
            src_type = graph.nodes[source].get("type", "")
            if rel == "fails_under" and src_type == "Method":
                methods_explicit.append(source)
                edge_ids.append(key)
                paper_ids.update(edata.get("paper_ids", []))
                spans.extend(edata.get("evidence", []))

        # Path B: Papers that mention this FailureCondition (via mentions edges)
        mentioning_papers: set[str] = set()
        for source, _, key, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") == "mentions" and graph.nodes[source].get("type") == "Paper":
                mentioning_papers.update(edata.get("paper_ids", [source.replace("paper:", "")]))

        # Merge: use explicit methods if enough, else fall back to paper-level mentions
        total_papers = paper_ids | mentioning_papers
        has_explicit = len(set(methods_explicit)) >= min_methods and len(paper_ids) >= 2
        has_mention = len(mentioning_papers) >= max(2, min_methods)

        if has_explicit:
            hits.append(
                MotifHit(
                    motif_type="shared_failure_condition",
                    motif_id=stable_id("motif", "shared_failure_condition", node_id),
                    description=f"Multiple methods fail under shared condition: {data.get('label')}",
                    supporting_node_ids=[node_id, *sorted(set(methods_explicit))],
                    supporting_edge_ids=edge_ids,
                    paper_ids=sorted(paper_ids),
                    source_text_spans=spans,
                    score=bounded(0.4 + 0.15 * len(set(methods_explicit)) + 0.1 * len(paper_ids)),
                    metadata={"failure_condition": data.get("label"), "methods": sorted(set(methods_explicit)), "detection_path": "fails_under_edges"},
                )
            )
        elif has_mention:
            # Weaker signal: multiple papers acknowledge this failure condition
            hits.append(
                MotifHit(
                    motif_type="shared_failure_condition",
                    motif_id=stable_id("motif", "shared_failure_condition_mention", node_id),
                    description=f"Multiple papers report shared failure condition: {data.get('label')}",
                    supporting_node_ids=[node_id],
                    supporting_edge_ids=[],
                    paper_ids=sorted(mentioning_papers),
                    source_text_spans=[],
                    score=bounded(0.35 + 0.1 * len(mentioning_papers)),
                    metadata={"failure_condition": data.get("label"), "mentioning_papers": sorted(mentioning_papers), "detection_path": "mentions_edges"},
                )
            )
    return hits


def repeated_unaddressed_limitation(graph: nx.MultiDiGraph, min_papers: int = 2) -> list[MotifHit]:
    hits = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != "Limitation":
            continue
        paper_ids = set(data.get("paper_ids", []))
        # Also collect papers that mention this limitation via mentions edges
        for source, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") == "mentions":
                paper_ids.update(edata.get("paper_ids", []))
        has_address = any(edata.get("relation") == "addresses" for _, _, _, edata in graph.in_edges(node_id, keys=True, data=True))
        if len(paper_ids) >= min_papers and not has_address:
            spans = data.get("evidence", [])
            hits.append(
                MotifHit(
                    motif_type="repeated_unaddressed_limitation",
                    motif_id=stable_id("motif", "repeated_unaddressed_limitation", node_id),
                    description=f"Repeated limitation appears unaddressed: {data.get('label')}",
                    supporting_node_ids=[node_id],
                    supporting_edge_ids=[],
                    paper_ids=sorted(paper_ids),
                    source_text_spans=spans,
                    score=bounded(0.45 + 0.15 * len(paper_ids)),
                    metadata={"limitation": data.get("label"), "has_address_edge": has_address},
                )
            )
    return hits


def conflicting_claims(graph: nx.MultiDiGraph) -> list[MotifHit]:
    hits = []

    # Path A: explicit contradicts edges
    for source, target, key, data in graph.edges(keys=True, data=True):
        if data.get("relation") != "contradicts":
            continue
        paper_ids = set(data.get("paper_ids", []))
        paper_ids.update(graph.nodes[source].get("paper_ids", []))
        paper_ids.update(graph.nodes[target].get("paper_ids", []))
        if len(paper_ids) < 2:
            continue
        hits.append(
            MotifHit(
                motif_type="conflicting_claims",
                motif_id=stable_id("motif", "conflicting_claims", source, target, key),
                description=f"Conflicting claims: {graph.nodes[source].get('label')} vs {graph.nodes[target].get('label')}",
                supporting_node_ids=[source, target],
                supporting_edge_ids=[key],
                paper_ids=sorted(paper_ids),
                source_text_spans=data.get("evidence", []),
                score=0.75,
                metadata={
                    "source_claim": graph.nodes[source].get("label"),
                    "target_claim": graph.nodes[target].get("label"),
                    "detection_path": "contradicts_edge",
                },
            )
        )

    # Path B: implicit conflicts — same target node, opposite relations from different papers
    # Build target → {(relation, paper_id, source_node, edge_key)} index
    target_rel_index: dict[str, list[tuple[str, str, str, str, list[dict]]]] = defaultdict(list)
    for source, target, key, edata in graph.edges(keys=True, data=True):
        rel = edata.get("relation", "")
        if rel not in (_POSITIVE_RELATIONS | _NEGATIVE_RELATIONS):
            continue
        for pid in edata.get("paper_ids", []):
            target_rel_index[target].append((rel, pid, source, key, edata.get("evidence", [])))

    seen_conflicts: set[frozenset] = set()
    for target, entries in target_rel_index.items():
        # Group by relation polarity
        positive_entries = [(rel, pid, src, k, evid) for rel, pid, src, k, evid in entries if rel in _POSITIVE_RELATIONS]
        negative_entries = [(rel, pid, src, k, evid) for rel, pid, src, k, evid in entries if rel in _NEGATIVE_RELATIONS]
        if not positive_entries or not negative_entries:
            continue
        pos_papers = {pid for _, pid, _, _, _ in positive_entries}
        neg_papers = {pid for _, pid, _, _, _ in negative_entries}
        cross_papers = pos_papers & neg_papers
        # Only a conflict if different papers are involved (at least one on each side without overlap)
        if not (pos_papers - cross_papers) or not (neg_papers - cross_papers):
            conflict_papers = pos_papers | neg_papers
        else:
            conflict_papers = pos_papers | neg_papers
        if len(conflict_papers) < 2:
            continue
        # Deduplicate by target node
        conflict_key = frozenset([target, *sorted(conflict_papers)])
        if conflict_key in seen_conflicts:
            continue
        seen_conflicts.add(conflict_key)
        target_label = graph.nodes[target].get("label", target)
        pos_rels = sorted({r for r, _, _, _, _ in positive_entries})
        neg_rels = sorted({r for r, _, _, _, _ in negative_entries})
        all_spans: list[dict] = []
        for _, _, _, _, evid in positive_entries[:3] + negative_entries[:3]:
            all_spans.extend(evid)
        all_node_ids = [target] + sorted({src for _, _, src, _, _ in positive_entries + negative_entries})
        all_edge_keys = sorted({k for _, _, _, k, _ in positive_entries + negative_entries})
        hits.append(
            MotifHit(
                motif_type="conflicting_claims",
                motif_id=stable_id("motif", "implicit_conflict", target, *sorted(conflict_papers)),
                description=f"Implicit conflict on '{target_label}': positive evidence ({', '.join(pos_rels)}) vs negative evidence ({', '.join(neg_rels)}) across papers",
                supporting_node_ids=all_node_ids[:10],
                supporting_edge_ids=all_edge_keys[:10],
                paper_ids=sorted(conflict_papers),
                source_text_spans=all_spans[:6],
                score=bounded(0.55 + 0.1 * len(conflict_papers)),
                metadata={
                    "target": target_label,
                    "positive_relations": pos_rels,
                    "negative_relations": neg_rels,
                    "positive_papers": sorted(pos_papers),
                    "negative_papers": sorted(neg_papers),
                    "detection_path": "implicit_polarity_conflict",
                },
            )
        )

    return hits


def sparse_evaluation(graph: nx.MultiDiGraph, min_mentions: int = 2, max_evaluations: int = 1) -> list[MotifHit]:
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue
        paper_ids = set(data.get("paper_ids", []))
        task_edges = [(target, key, edata) for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True) if edata.get("relation") == "evaluated_on"]
        eval_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"uses_dataset", "measured_by"}
        ]
        if len(paper_ids) >= min_mentions and len(eval_edges) <= max_evaluations:
            task_ids = [target for target, _, _ in task_edges]
            edge_ids = [key for _, key, _ in task_edges + eval_edges]
            spans: list[dict[str, Any]] = []
            for _, _, edata in task_edges + eval_edges:
                spans.extend(edata.get("evidence", []))
            hits.append(
                MotifHit(
                    motif_type="sparse_evaluation",
                    motif_id=stable_id("motif", "sparse_evaluation", method_id),
                    description=f"Method has repeated mentions but sparse dataset/metric evaluation: {data.get('label')}",
                    supporting_node_ids=[method_id, *task_ids],
                    supporting_edge_ids=edge_ids,
                    paper_ids=sorted(paper_ids),
                    source_text_spans=spans or data.get("evidence", []),
                    score=bounded(0.45 + 0.1 * len(paper_ids) - 0.1 * len(eval_edges)),
                    metadata={"method": data.get("label"), "evaluation_edges": len(eval_edges)},
                )
            )
    return hits


def assumption_mismatch(graph: nx.MultiDiGraph) -> list[MotifHit]:
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue
        assumptions = [(target, key, edata) for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True) if edata.get("relation") == "assumes"]
        failures = [(target, key, edata) for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True) if edata.get("relation") == "fails_under"]
        if assumptions and failures:
            paper_ids = set(data.get("paper_ids", []))
            edge_ids = []
            spans: list[dict[str, Any]] = []
            nodes = [method_id]
            for target, key, edata in assumptions + failures:
                nodes.append(target)
                edge_ids.append(key)
                paper_ids.update(edata.get("paper_ids", []))
                spans.extend(edata.get("evidence", []))
            assumption_labels = [graph.nodes[t].get("label", "") for t, _, _ in assumptions[:2]]
            failure_labels = [graph.nodes[t].get("label", "") for t, _, _ in failures[:2]]
            description = (
                f"{data.get('label')} assumes ({'; '.join(assumption_labels[:2])}) "
                f"but fails under ({'; '.join(failure_labels[:2])})"
            )
            hits.append(
                MotifHit(
                    motif_type="assumption_mismatch",
                    motif_id=stable_id("motif", "assumption_mismatch", method_id),
                    description=description,
                    supporting_node_ids=sorted(set(nodes)),
                    supporting_edge_ids=edge_ids,
                    paper_ids=sorted(paper_ids),
                    source_text_spans=spans[:6],
                    score=bounded(0.60 + 0.05 * len(paper_ids)),
                    metadata={
                        "method": data.get("label"),
                        "assumptions": assumption_labels,
                        "failure_conditions": failure_labels,
                    },
                )
            )
    return hits


def unrealistic_assumption(graph: nx.MultiDiGraph) -> list[MotifHit]:
    """Methods that rely on idealized assumptions unavailable in practice, with documented failures."""
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue
        assumption_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") == "assumes"
        ]
        failure_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"fails_under", "limited_by"}
        ]
        if not assumption_edges or not failure_edges:
            continue
        # Find assumptions that are idealized
        idealized = []
        for target, key, edata in assumption_edges:
            label = graph.nodes[target].get("label", "").lower()
            evidence = " ".join(e.get("evidence_text", "") for e in edata.get("evidence", [])).lower()
            text = label + " " + evidence
            if any(kw in text for kw in _IDEALIZED_KEYWORDS):
                idealized.append((target, key, edata))
        if not idealized:
            continue
        paper_ids = set(data.get("paper_ids", []))
        nodes = [method_id]
        edge_ids = []
        spans: list[dict] = []
        for target, key, edata in idealized + failure_edges:
            nodes.append(target)
            edge_ids.append(key)
            paper_ids.update(edata.get("paper_ids", []))
            spans.extend(edata.get("evidence", []))
        assumption_labels = [graph.nodes[t].get("label", "") for t, _, _ in idealized]
        failure_labels = [graph.nodes[t].get("label", "") for t, _, _ in failure_edges[:2]]
        hits.append(
            MotifHit(
                motif_type="unrealistic_assumption",
                motif_id=stable_id("motif", "unrealistic_assumption", method_id),
                description=(
                    f"{data.get('label')} relies on idealized assumption(s) "
                    f"({'; '.join(assumption_labels[:2])}) "
                    f"that break under ({'; '.join(failure_labels[:2])})"
                ),
                supporting_node_ids=sorted(set(nodes)),
                supporting_edge_ids=edge_ids,
                paper_ids=sorted(paper_ids),
                source_text_spans=spans[:6],
                score=bounded(0.70 + 0.05 * len(idealized)),
                metadata={
                    "method": data.get("label"),
                    "idealized_assumptions": assumption_labels,
                    "failure_conditions": failure_labels,
                },
            )
        )
    return hits


def theory_practice_gap(graph: nx.MultiDiGraph, min_papers: int = 2) -> list[MotifHit]:
    """Methods with theoretical results or claims but no real benchmark evaluation and known failures."""
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue
        paper_ids = set(data.get("paper_ids", []))
        if len(paper_ids) < min_papers:
            continue
        has_dataset_eval = any(
            edata.get("relation") in {"uses_dataset", "measured_by"}
            for _, _, _, edata in graph.out_edges(method_id, keys=True, data=True)
        )
        if has_dataset_eval:
            continue
        failure_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"fails_under", "limited_by"}
        ]
        if not failure_edges:
            continue
        nodes = [method_id]
        edge_ids = []
        spans: list[dict] = []
        for target, key, edata in failure_edges:
            nodes.append(target)
            edge_ids.append(key)
            paper_ids.update(edata.get("paper_ids", []))
            spans.extend(edata.get("evidence", []))
        failure_labels = [graph.nodes[t].get("label", "") for t, _, _ in failure_edges[:3]]
        hits.append(
            MotifHit(
                motif_type="theory_practice_gap",
                motif_id=stable_id("motif", "theory_practice_gap", method_id),
                description=(
                    f"{data.get('label')} has theoretical support across {len(paper_ids)} papers "
                    f"but no real benchmark evaluation, with known failures: "
                    f"{'; '.join(failure_labels[:2])}"
                ),
                supporting_node_ids=sorted(set(nodes)),
                supporting_edge_ids=edge_ids,
                paper_ids=sorted(paper_ids),
                source_text_spans=spans[:6],
                score=bounded(0.65 + 0.05 * len(paper_ids)),
                metadata={
                    "method": data.get("label"),
                    "paper_count": len(paper_ids),
                    "failure_conditions": failure_labels,
                },
            )
        )
    return hits


def transfer_solution_gap(
    graph: nx.MultiDiGraph,
    min_papers: int = 2,
    min_methods: int = 2,
) -> list[MotifHit]:
    """A limitation/failure is solved for Method A but still affects Method B — missed transfer opportunity."""
    hits = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") not in {"Limitation", "FailureCondition"}:
            continue

        # Collect methods that address this node
        addressing_methods: set[str] = set()
        addressing_paper_ids: set[str] = set()
        for source, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") == "addresses" and graph.nodes[source].get("type") == "Method":
                addressing_methods.add(source)
                addressing_paper_ids.update(edata.get("paper_ids", []))

        if not addressing_methods:
            continue

        # Collect methods that are limited_by or fail_under this node
        affected_methods: set[str] = set()
        affected_paper_ids: set[str] = set()
        for source, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            rel = edata.get("relation", "")
            if rel in {"limited_by", "fails_under"} and graph.nodes[source].get("type") == "Method":
                method_b = source
                # Method B must not already address this node
                already_addresses = any(
                    edata2.get("relation") == "addresses"
                    for _, tgt, _, edata2 in graph.out_edges(method_b, keys=True, data=True)
                    if tgt == node_id
                )
                if method_b not in addressing_methods and not already_addresses:
                    affected_methods.add(method_b)
                    affected_paper_ids.update(edata.get("paper_ids", []))

        if not affected_methods:
            continue

        combined_paper_ids = addressing_paper_ids | affected_paper_ids
        if len(combined_paper_ids) < min_papers:
            continue
        if len(affected_methods) < min_methods:
            continue

        addressing_labels = [graph.nodes[m].get("label", m) for m in sorted(addressing_methods)]
        affected_labels = [graph.nodes[m].get("label", m) for m in sorted(affected_methods)]
        n = len(combined_paper_ids)

        hits.append(
            MotifHit(
                motif_type="transfer_solution_gap",
                motif_id=stable_id("motif", "transfer_solution_gap", node_id),
                description=(
                    f"'{data.get('label')}' is addressed by {addressing_labels}, "
                    f"but still limits/fails {affected_labels} across {n} papers "
                    f"— possible transfer opportunity."
                ),
                supporting_node_ids=[node_id, *sorted(addressing_methods), *sorted(affected_methods)],
                supporting_edge_ids=[],
                paper_ids=sorted(combined_paper_ids),
                source_text_spans=[],
                score=bounded(0.60 + 0.05 * n + 0.05 * len(affected_methods)),
                metadata={
                    "node": data.get("label"),
                    "addressing_methods": addressing_labels,
                    "affected_methods": affected_labels,
                    "paper_count": n,
                },
            )
        )
    return hits


def unresolved_tradeoff(
    graph: nx.MultiDiGraph,
    min_positive_edges: int = 1,
    min_limitation_mentions: int = 1,
    min_papers: int = 1,
) -> list[MotifHit]:
    """Method improves something but introduces an unresolved limitation."""
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue

        positive_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"improves_over", "addresses"}
        ]
        if len(positive_edges) < min_positive_edges:
            continue

        limited_by_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") == "limited_by"
        ]
        if len(limited_by_edges) < min_limitation_mentions:
            continue

        for lim_target, lim_key, lim_edata in limited_by_edges:
            # Check if any method addresses this limitation
            lim_is_addressed = any(
                edata.get("relation") == "addresses"
                for _, _, _, edata in graph.in_edges(lim_target, keys=True, data=True)
            )
            if lim_is_addressed:
                continue

            # Collect paper_ids for the limitation node
            lim_paper_ids = set(lim_edata.get("paper_ids", []))
            lim_paper_ids.update(graph.nodes[lim_target].get("paper_ids", []))
            limitation_multi_paper = len(lim_paper_ids) >= 2

            paper_ids: set[str] = set(data.get("paper_ids", []))
            for _, _, edata in positive_edges + [(lim_target, lim_key, lim_edata)]:
                paper_ids.update(edata.get("paper_ids", []))

            if len(paper_ids) < min_papers:
                continue

            positive_count = len(positive_edges)
            score = bounded(
                0.65
                + 0.05 * positive_count
                + (0.10 if limitation_multi_paper else 0)
            )

            lim_label = graph.nodes[lim_target].get("label", lim_target)
            hits.append(
                MotifHit(
                    motif_type="unresolved_tradeoff",
                    motif_id=stable_id("motif", "unresolved_tradeoff", method_id, lim_target),
                    description=(
                        f"Method '{data.get('label')}' has {positive_count} reported benefits "
                        f"but is limited by '{lim_label}' which no method currently addresses."
                    ),
                    supporting_node_ids=[method_id, lim_target],
                    supporting_edge_ids=[lim_key],
                    paper_ids=sorted(paper_ids),
                    source_text_spans=lim_edata.get("evidence", []),
                    score=score,
                    metadata={
                        "method": data.get("label"),
                        "limitation": lim_label,
                        "positive_edge_count": positive_count,
                        "limitation_multi_paper": limitation_multi_paper,
                    },
                )
            )
    return hits


def missing_stress_test(
    graph: nx.MultiDiGraph,
    min_methods: int = 2,
    min_papers: int = 2,
    max_eval_edges: int = 1,
) -> list[MotifHit]:
    """A failure condition affects multiple methods/papers but has little benchmark coverage."""
    hits = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != "FailureCondition":
            continue

        # Collect methods with fails_under edges to this node
        affected_methods: list[str] = []
        paper_ids: set[str] = set()
        for source, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") == "fails_under" and graph.nodes[source].get("type") == "Method":
                affected_methods.append(source)
                paper_ids.update(edata.get("paper_ids", []))

        affected_method_count = len(set(affected_methods))
        if affected_method_count < min_methods and len(paper_ids) < min_papers:
            continue

        # Count eval edges: affected methods that also have uses_dataset or measured_by edges
        eval_edge_count = 0
        for method_id in set(affected_methods):
            has_eval = any(
                edata.get("relation") in {"uses_dataset", "measured_by"}
                for _, _, _, edata in graph.out_edges(method_id, keys=True, data=True)
            )
            if has_eval:
                eval_edge_count += 1

        if eval_edge_count > max_eval_edges:
            continue

        p = len(paper_ids)
        score = bounded(0.60 + 0.05 * affected_method_count + 0.05 * p - 0.05 * eval_edge_count)

        hits.append(
            MotifHit(
                motif_type="missing_stress_test",
                motif_id=stable_id("motif", "missing_stress_test", node_id),
                description=(
                    f"Failure condition '{data.get('label')}' affects {affected_method_count} methods "
                    f"across {p} papers but has only {eval_edge_count} benchmark/measurement edges "
                    f"— stress-test coverage is missing."
                ),
                supporting_node_ids=[node_id, *sorted(set(affected_methods))],
                supporting_edge_ids=[],
                paper_ids=sorted(paper_ids),
                source_text_spans=[],
                score=score,
                metadata={
                    "failure_condition": data.get("label"),
                    "affected_method_count": affected_method_count,
                    "paper_count": p,
                    "eval_edge_count": eval_edge_count,
                },
            )
        )
    return hits


def claim_without_measurement(
    graph: nx.MultiDiGraph,
    max_measurement_edges: int = 0,
    require_claim_keyword: bool = False,
    min_papers: int = 1,
    min_claim_edges: int = 1,
) -> list[MotifHit]:
    """Method makes positive claims but has no measurement support."""
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue

        claim_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"addresses", "improves_over"}
        ]
        if not claim_edges:
            continue

        if len(claim_edges) < min_claim_edges:
            continue

        measurement_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") == "measured_by"
        ]
        measurement_edge_count = len(measurement_edges)
        if measurement_edge_count > max_measurement_edges:
            continue

        if require_claim_keyword:
            keyword_found = False
            for _, _, edata in claim_edges:
                evidence_text = " ".join(
                    e.get("evidence_text", "") for e in edata.get("evidence", [])
                ).lower()
                if any(kw in evidence_text for kw in _CLAIM_KEYWORDS):
                    keyword_found = True
                    break
            if not keyword_found:
                continue

        claim_edge_count = len(claim_edges)
        paper_ids: set[str] = set(data.get("paper_ids", []))
        for _, _, edata in claim_edges + measurement_edges:
            paper_ids.update(edata.get("paper_ids", []))

        if len(paper_ids) < min_papers:
            continue

        score = bounded(0.50 + 0.10 * claim_edge_count - 0.05 * measurement_edge_count)

        hits.append(
            MotifHit(
                motif_type="claim_without_measurement",
                motif_id=stable_id("motif", "claim_without_measurement", method_id),
                description=(
                    f"Method '{data.get('label')}' has {claim_edge_count} positive claim edges "
                    f"(addresses/improves_over) but only {measurement_edge_count} measurement edges."
                ),
                supporting_node_ids=[method_id, *sorted({t for t, _, _ in claim_edges})],
                supporting_edge_ids=[key for _, key, _ in claim_edges],
                paper_ids=sorted(paper_ids),
                source_text_spans=[],
                score=score,
                metadata={
                    "method": data.get("label"),
                    "claim_edge_count": claim_edge_count,
                    "measurement_edge_count": measurement_edge_count,
                },
            )
        )
    return hits


def missing_baseline_comparison(
    graph: nx.MultiDiGraph,
    min_eval_edges: int = 1,
    min_method_papers: int = 1,
) -> list[MotifHit]:
    """Method is evaluated on benchmarks but never compared to other methods."""
    hits = []
    for method_id, data in graph.nodes(data=True):
        if data.get("type") != "Method":
            continue

        eval_edges = [
            (target, key, edata)
            for _, target, key, edata in graph.out_edges(method_id, keys=True, data=True)
            if edata.get("relation") in {"uses_dataset", "measured_by"}
        ]
        eval_edge_count = len(eval_edges)
        if eval_edge_count < min_eval_edges:
            continue

        has_improves_over = any(
            edata.get("relation") == "improves_over"
            for _, _, _, edata in graph.out_edges(method_id, keys=True, data=True)
        )
        if has_improves_over:
            continue

        paper_ids: set[str] = set(data.get("paper_ids", []))
        for _, _, edata in eval_edges:
            paper_ids.update(edata.get("paper_ids", []))

        if len(paper_ids) < min_method_papers:
            continue

        p = len(paper_ids)
        score = bounded(0.55 + 0.05 * eval_edge_count + 0.05 * p)

        hits.append(
            MotifHit(
                motif_type="missing_baseline_comparison",
                motif_id=stable_id("motif", "missing_baseline_comparison", method_id),
                description=(
                    f"Method '{data.get('label')}' has {eval_edge_count} dataset/metric evaluations "
                    f"but no improves_over/baseline comparison edges across {p} papers."
                ),
                supporting_node_ids=[method_id, *sorted({t for t, _, _ in eval_edges})],
                supporting_edge_ids=[key for _, key, _ in eval_edges],
                paper_ids=sorted(paper_ids),
                source_text_spans=[],
                score=score,
                metadata={
                    "method": data.get("label"),
                    "eval_edge_count": eval_edge_count,
                    "paper_count": p,
                },
            )
        )
    return hits


def shared_unrealistic_assumption(
    graph: nx.MultiDiGraph,
    min_methods: int = 2,
) -> list[MotifHit]:
    """Multiple methods share the same idealized assumption, and at least one has failures."""
    hits = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != "Assumption":
            continue

        # Check if label or evidence text contains idealized keywords
        label = data.get("label", "").lower()
        evidence_texts = " ".join(
            e.get("evidence_text", "") for e in data.get("evidence", [])
        ).lower()
        combined_text = label + " " + evidence_texts
        matched_kws = [kw for kw in _IDEALIZED_KEYWORDS if kw in combined_text]
        if not matched_kws:
            continue

        # Collect methods that assume this node
        assuming_methods: list[str] = []
        paper_ids: set[str] = set()
        for source, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") == "assumes" and graph.nodes[source].get("type") == "Method":
                assuming_methods.append(source)
                paper_ids.update(edata.get("paper_ids", []))

        method_count = len(set(assuming_methods))
        if method_count < min_methods:
            continue

        # Check if at least one assuming method has fails_under or limited_by edges
        methods_with_failures = [
            m for m in set(assuming_methods)
            if any(
                edata.get("relation") in {"fails_under", "limited_by"}
                for _, _, _, edata in graph.out_edges(m, keys=True, data=True)
            )
        ]
        if not methods_with_failures:
            continue

        k = len(methods_with_failures)
        score = bounded(0.65 + 0.05 * method_count + 0.05 * len(paper_ids))

        hits.append(
            MotifHit(
                motif_type="shared_unrealistic_assumption",
                motif_id=stable_id("motif", "shared_unrealistic_assumption", node_id),
                description=(
                    f"Assumption '{data.get('label')}' is shared by {method_count} methods "
                    f"and appears idealized (keywords: {sorted(matched_kws)}); "
                    f"{k} dependent method(s) have documented failures or limitations."
                ),
                supporting_node_ids=[node_id, *sorted(set(assuming_methods))],
                supporting_edge_ids=[],
                paper_ids=sorted(paper_ids),
                source_text_spans=[],
                score=score,
                metadata={
                    "assumption": data.get("label"),
                    "method_count": method_count,
                    "matched_keywords": sorted(matched_kws),
                    "methods_with_failures": sorted(methods_with_failures),
                },
            )
        )
    return hits


def motif_rows(hits: list[MotifHit]) -> list[dict[str, Any]]:
    return [model_dump(hit) for hit in hits]
