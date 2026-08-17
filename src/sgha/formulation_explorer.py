"""Domain-general Problem Formulation Explorer.

For each cleaned gap seed: infer formulation axes from the graph/corpus (NOT hardcoded
domain vocabulary), enumerate multiple structured problem formulations, and review each
for viability. Produces a formulation atlas. Does not run any upstream/downstream stage.

IMPORTANT: this module contains NO domain-specific term lists. Every axis is derived from
graph node/edge data, gap evidence, or optional LLM induction. Domain vocabulary may only
appear in tests, example configs, and generated reports.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

import networkx as nx

from .gap_objects import DomainAxisInventory, ProblemFormulation
from .prompt_templates import (
    axis_induction_prompt, formulation_generation_prompt, formulation_viability_prompt,
)
from .utils import stable_id

# Generic (domain-agnostic) impossibility cues — linguistic, not domain terms.
_IMPOSSIBILITY_CUES = [
    "impossible", "impossibility", "lower bound", "cannot achieve", "no algorithm can",
    "minimax lower bound", "ω(", "omega(", "intractable", "np-hard", "rules out", "unavoidable",
]

# Generic stopwords for label/keyphrase frequency — NOT domain terms.
_GENERIC_STOP = {
    "the", "and", "for", "with", "under", "that", "this", "from", "into", "over",
    "via", "using", "based", "method", "methods", "approach", "approaches", "model",
    "models", "problem", "algorithm", "algorithms", "framework", "general", "novel",
    "robust", "efficient", "based", "setting", "settings",
}

# Map graph node types -> which DomainAxisInventory field they feed.
_NODE_TYPE_TO_AXIS = {
    "Method": "method_families",
    "Task": "problem_contexts",
    "Assumption": "assumptions",
    "FailureCondition": "failure_conditions",
    "Limitation": "limitations",
    "Metric": "metrics",
    "Dataset": "benchmarks_or_datasets",
}
_COUNTEREVIDENCE_RELATIONS = {
    "counterevidence_for", "partially_addresses_gap", "relaxes_assumption_of", "handles_failure_of",
}


def _top_labels(graph: nx.MultiDiGraph, ntype: str, k: int = 25) -> list[str]:
    c: Counter[str] = Counter()
    for _, d in graph.nodes(data=True):
        if d.get("type") == ntype:
            lbl = str(d.get("label", "")).strip()
            if lbl:
                c[lbl] += len(d.get("paper_ids", [])) or 1
    return [lbl for lbl, _ in c.most_common(k)]


def build_axis_inventory_from_graph(graph: nx.MultiDiGraph, gaps: list[dict]) -> DomainAxisInventory:
    """Infer axes purely from graph node/edge frequencies + gap evidence. No domain terms."""
    inv = DomainAxisInventory()
    for ntype, axis in _NODE_TYPE_TO_AXIS.items():
        setattr(inv, axis, _top_labels(graph, ntype))

    # comparators: objects of improves_over edges
    comp: Counter[str] = Counter()
    rel_patterns: Counter[str] = Counter()
    ce_terms: Counter[str] = Counter()
    for u, v, _, d in graph.edges(keys=True, data=True):
        rel = d.get("relation", "")
        rel_patterns[rel] += 1
        if rel == "improves_over":
            lbl = str(graph.nodes.get(v, {}).get("label", "")).strip()
            if lbl:
                comp[lbl] += 1
        if rel in _COUNTEREVIDENCE_RELATIONS:
            m = str(d.get("resolution_method", "")).strip()
            if m:
                ce_terms[m] += 1
    inv.comparators = [c for c, _ in comp.most_common(20)]
    inv.relation_patterns = [f"{r}:{n}" for r, n in rel_patterns.most_common(20)]
    inv.counterevidence_terms = [c for c, _ in ce_terms.most_common(20)]

    # objectives + evidence terms: keyphrase frequency from gap text + evidence
    obj: Counter[str] = Counter()
    ev: Counter[str] = Counter()
    for g in gaps:
        for tok in re.findall(r"[a-z][a-z\-]{4,}", (g.get("gap", "") + " " + g.get("mechanism", "")).lower()):
            if tok not in _GENERIC_STOP:
                obj[tok] += 1
        for e in g.get("supporting_evidence", [])[:6]:
            if isinstance(e, dict):
                for tok in re.findall(r"[a-z][a-z\-]{4,}", str(e.get("evidence_text", "")).lower()):
                    if tok not in _GENERIC_STOP:
                        ev[tok] += 1
    inv.objectives = [t for t, _ in obj.most_common(20)]
    inv.evidence_terms = [t for t, _ in ev.most_common(25)]
    inv.frequent_node_labels = (inv.method_families + inv.problem_contexts)[:30]
    inv.notes = [f"axes inferred from {graph.number_of_nodes()} nodes / {graph.number_of_edges()} edges, {len(gaps)} gaps"]
    return inv


def induce_axes_llm(graph: nx.MultiDiGraph, gaps: list[dict], llm: Any) -> dict:
    """Optional LLM axis induction (domain-neutral). Returns {} on failure."""
    labels_by_type = {nt: _top_labels(graph, nt, 30) for nt in _NODE_TYPE_TO_AXIS}
    top_gaps = [g.get("gap", "")[:160] for g in gaps[:25]]
    ce = [g.get("counterevidence_summary", "") or g.get("remaining_gap_scope", "") for g in gaps if g.get("counterevidence_status")]
    try:
        raw, _, _, _ = llm.complete_json(
            stage="evolve", agent_name="formulation_axis_inducer",
            prompt=axis_induction_prompt(labels_by_type, top_gaps, ce[:15]),
            schema_name="DomainAxes",
        )
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def merge_llm_axes(inv: DomainAxisInventory, llm_axes: dict) -> DomainAxisInventory:
    """Merge LLM-induced axes as ADDITIONS; graph-derived axes are never overridden."""
    mapping = {
        "method_families": "method_families", "settings": "problem_contexts",
        "objectives": "objectives", "assumptions_to_relax": "assumptions",
        "failure_modes": "failure_conditions", "comparators": "comparators",
        "evaluation_targets": "metrics", "constraints": "constraints",
        "deployment_contexts": "deployment_settings", "notes": "notes",
    }
    for llm_key, axis in mapping.items():
        vals = llm_axes.get(llm_key) or []
        if isinstance(vals, list):
            cur = list(getattr(inv, axis, []))
            for v in vals:
                if isinstance(v, str) and v.strip() and v not in cur:
                    cur.append(v.strip())
            setattr(inv, axis, cur)
    return inv


def _gap_is_known_solved(gap: dict) -> bool:
    return gap.get("counterevidence_status") == "known_solved_in_corpus" or gap.get("solved_in_corpus") is True


def generate_formulations_for_gap(gap: dict, axes: dict, llm: Any, max_formulations: int = 8) -> list[ProblemFormulation]:
    """Generate structured formulations for a single (non-solved) gap."""
    if _gap_is_known_solved(gap):
        return []
    try:
        raw, _, _, _ = llm.complete_json(
            stage="evolve", agent_name="formulation_generator",
            prompt=formulation_generation_prompt(gap, axes, max_formulations),
            schema_name="Formulations",
        )
        items = raw.get("formulations", raw.get("items", [])) if isinstance(raw, dict) else []
    except Exception:
        items = []
    out: list[ProblemFormulation] = []
    for i, it in enumerate(items[:max_formulations]):
        if not isinstance(it, dict):
            continue
        fid = stable_id("formulation", gap.get("gap_id", "?"), str(i), it.get("short_name", ""))
        out.append(ProblemFormulation(
            formulation_id=fid,
            source_gap_id=gap.get("gap_id", "?"),
            source_motif_type=gap.get("motif_type", ""),
            source_gap_description=gap.get("gap", ""),
            counterevidence_status=gap.get("counterevidence_status", ""),
            remaining_gap_scope=gap.get("remaining_gap_scope", ""),
            supporting_papers=gap.get("paper_ids", []) or gap.get("supporting_papers", []),
            counterevidence_papers=gap.get("counterevidence_papers", []),
            traceability_path=gap.get("traceability_path", []),
            **{k: str(it.get(k, "")) for k in (
                "short_name", "formulation_question", "problem_context", "method_or_system_family",
                "input_or_data_setting", "environment_or_deployment_setting", "feedback_or_observation_model",
                "objective", "metric_or_target_quantity", "comparator_or_baseline", "assumption_relaxed",
                "failure_condition_targeted", "resource_or_constraint_dimension", "evaluation_protocol",
                "theoretical_target", "empirical_target", "algorithmic_target", "known_counterevidence",
                "why_counterevidence_does_not_solve", "falsification_condition",
            )},
            formulation_type=it.get("formulation_type", "algorithm"),
        ))
    return out


def _heuristic_impossibility(formulation: ProblemFormulation, gap: dict) -> bool:
    blob = " ".join([
        formulation.known_counterevidence, formulation.why_counterevidence_does_not_solve,
        gap.get("remaining_gap_scope", ""),
        " ".join(str(e.get("evidence_text", "")) for e in gap.get("supporting_evidence", [])[:6] if isinstance(e, dict)),
    ]).lower()
    return sum(1 for c in _IMPOSSIBILITY_CUES if c in blob) >= 2


def review_formulation(formulation: ProblemFormulation, gap: dict, llm: Any) -> ProblemFormulation:
    """Review one formulation; merge heuristic impossibility + artificial-scope signals."""
    gap_ctx = {
        "remaining_gap_scope": gap.get("remaining_gap_scope", ""),
        "counterevidence_status": gap.get("counterevidence_status", ""),
        "counterevidence_summary": gap.get("counterevidence_summary", ""),
        "supporting_evidence": [e.get("evidence_text", "") for e in gap.get("supporting_evidence", [])[:5] if isinstance(e, dict)],
    }
    try:
        raw, _, _, _ = llm.complete_json(
            stage="evolve", agent_name="formulation_reviewer",
            prompt=formulation_viability_prompt(formulation.model_dump() if hasattr(formulation, "model_dump") else dict(formulation), gap_ctx),
            schema_name="FormulationViability",
        )
    except Exception as exc:
        raw = {"viability_label": "INSUFFICIENT_EVIDENCE", "reason": f"review error: {exc}"}

    label = str(raw.get("viability_label", "NEEDS_EXTERNAL_LIT_CHECK")).strip().upper().replace(" ", "_")
    try:
        score = max(0.0, min(1.0, float(raw.get("viability_score", 0.0))))
    except (TypeError, ValueError):
        score = 0.0

    # Heuristic overrides
    if _heuristic_impossibility(formulation, gap) and label in {"VIABLE_FORMULATION", "POSSIBLE_FORMULATION_WITH_REWRITE"}:
        label = "IMPOSSIBLE_FORMULATION"
    rem = (gap.get("remaining_gap_scope", "") or "").lower()
    if ("none identified" in rem or "covered" in rem) and label == "VIABLE_FORMULATION":
        label = "ARTIFICIAL_SCOPE"

    formulation.viability_label = label
    formulation.viability_score = score
    formulation.novelty_risk = str(raw.get("novelty_risk", "medium")).lower()
    formulation.feasibility = str(raw.get("feasibility", "moderate")).lower()
    formulation.reason = str(raw.get("reason", ""))
    if raw.get("falsification_condition"):
        formulation.falsification_condition = str(raw.get("falsification_condition"))
    formulation.likely_existing_literature = str(raw.get("likely_existing_literature", ""))
    return formulation


# Production no-hardcoding guarantee: this module references no domain-specific term
# lists. The only constant lists are _IMPOSSIBILITY_CUES (linguistic) and _GENERIC_STOP
# (English stopwords + generic research words). Verified by test + no_hardcoding audit.
PRODUCTION_DOMAIN_TERM_LISTS: list[str] = []  # intentionally empty
