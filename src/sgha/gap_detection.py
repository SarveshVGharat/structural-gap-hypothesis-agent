from __future__ import annotations

from typing import Any

import networkx as nx

from .gap_objects import CandidateGap, MotifHit
from .graph_builder import add_edge
from .graph_export import export_graph, load_graph
from .graph_visualization import write_pyvis_html
from .motif_queries import MOTIF_QUERIES, motif_rows, resolve_motif_activation, run_all_motif_queries
from .scoring import candidate_overall
from .utils import model_dump, stable_id, write_csv, write_json


def detect_gaps(ctx: Any) -> list[CandidateGap]:
    ctx.stage_start("detect_gaps")
    graph = load_graph(ctx.path("graph", "graph.json"))
    hits = run_all_motif_queries(graph, ctx.config)
    from collections import Counter as _Counter
    activation = resolve_motif_activation(ctx.config)
    _hits_by_type = dict(_Counter(h.motif_type for h in hits))
    _activation_summary = {
        "profile": ctx.config.get("motif_profile"),
        "default_enabled": (ctx.config.get("motifs") or {}).get("default_enabled", False),
        "normal": sorted(m for m, s in activation.items() if s == "normal"),
        "strict": sorted(m for m, s in activation.items() if s == "strict"),
        "disabled": sorted(m for m, s in activation.items() if s == "off"),
        "hits_by_type": _hits_by_type,
    }
    write_json(ctx.path("motifs", "motif_activation.json"), _activation_summary)
    write_json(ctx.path("motifs", "motif_queries.json"), MOTIF_QUERIES)
    write_json(ctx.path("motifs", "motif_hits.json"), motif_rows(hits))
    write_csv(ctx.path("motifs", "motif_scores.csv"), [{"motif_id": h.motif_id, "motif_type": h.motif_type, "score": h.score, "paper_count": len(h.paper_ids)} for h in hits])
    gaps = [candidate_gap_from_hit(hit) for hit in hits]
    add_gap_nodes(graph, gaps)
    export_graph(graph, ctx.path("graph"))
    write_pyvis_html(graph, ctx.path("graph", "visualizations", "full_graph_overview.html"), max_nodes=int(ctx.config.get("graph", {}).get("max_visualization_nodes", 500)))
    write_json(ctx.path("gaps", "candidate_gaps.json"), [model_dump(g) for g in gaps])
    write_csv(ctx.path("gaps", "candidate_gaps.csv"), [model_dump(g) for g in gaps])
    write_json(ctx.path("gaps", "gap_traceability.json"), {g.gap_id: g.traceability_path for g in gaps})
    ctx.stage_end("detect_gaps", motif_hits=len(hits), gaps=len(gaps))
    return gaps


def _derive_mechanism(hit: MotifHit) -> str:
    if hit.motif_type == "shared_failure_condition":
        fc = hit.metadata.get("failure_condition", "")[:80]
        return f"Shared failure condition across methods: {fc}"
    if hit.motif_type == "conflicting_claims":
        src = (hit.metadata.get("source_claim") or "")[:60]
        tgt = (hit.metadata.get("target_claim") or "")[:60]
        return f"Cross-paper conflict: '{src}' vs '{tgt}'"
    if hit.motif_type == "assumption_mismatch":
        method = (hit.metadata.get("method") or "")[:60]
        return f"Implicit assumption in {method} violated by observed failure conditions"
    if hit.motif_type == "sparse_evaluation":
        method = (hit.metadata.get("method") or "")[:60]
        return f"Repeated use of {method} without evaluation across diverse datasets/metrics"
    if hit.motif_type == "repeated_unaddressed_limitation":
        lim = (hit.metadata.get("limitation") or "")[:60]
        return f"Unaddressed cross-paper limitation: {lim}"
    if hit.motif_type == "unrealistic_assumption":
        method = (hit.metadata.get("method") or "")[:60]
        assumptions = hit.metadata.get("idealized_assumptions", [])
        failures = hit.metadata.get("failure_conditions", [])
        assumption_str = ", ".join(str(a) for a in assumptions[:2])
        failure_str = ", ".join(str(f) for f in failures[:2])
        if assumption_str and failure_str:
            return f"{method} assumes {assumption_str}, which breaks under {failure_str}"
        return f"Idealized assumption in {method} violated under realistic conditions"
    if hit.motif_type == "theory_practice_gap":
        method = (hit.metadata.get("method") or "")[:60]
        failures = hit.metadata.get("failure_conditions", [])
        failure_str = ", ".join(str(f) for f in failures[:2]) if failures else "real-world conditions"
        return f"{method} has theoretical guarantees not validated empirically; fails under {failure_str}"
    if hit.motif_type == "shared_unrealistic_assumption":
        assumption = (hit.metadata.get("assumption") or "")[:80]
        n = hit.metadata.get("method_count", 0)
        return f"Assumption '{assumption}' shared across {n} methods is unrealistic in practice"
    if hit.motif_type == "missing_stress_test":
        method = (hit.metadata.get("method") or "")[:60]
        return f"{method} lacks evaluation under distribution shift or adversarial conditions"
    return "insufficient evidence"


def candidate_gap_from_hit(hit: MotifHit) -> CandidateGap:
    label = hit.metadata.get("failure_condition") or hit.metadata.get("limitation") or hit.metadata.get("method") or hit.description
    novelty = min(1.0, 0.45 + hit.score * 0.35)
    feasibility = 0.65 if hit.source_text_spans else 0.45
    impact = min(1.0, 0.45 + 0.1 * len(hit.paper_ids))
    overall = candidate_overall(novelty, feasibility, impact, hit.score)
    return CandidateGap(
        gap_id=stable_id("gap", hit.motif_id),
        gap=hit.description,
        target=str(label),
        scope=f"Motif type: {hit.motif_type}; corpus-supported papers: {len(hit.paper_ids)}",
        mechanism=_derive_mechanism(hit),
        supporting_evidence=hit.source_text_spans,
        counterevidence=[],
        traceability_path=[*hit.supporting_node_ids, *hit.supporting_edge_ids],
        novelty_score=novelty,
        feasibility_score=feasibility,
        impact_score=impact,
        overall_score=overall,
        motif_type=hit.motif_type,
        motif_id=hit.motif_id,
        paper_ids=hit.paper_ids,
        extraction_uncertainty=max(0.0, 1.0 - hit.score),
    )


def add_gap_nodes(graph: nx.MultiDiGraph, gaps: list[CandidateGap]) -> None:
    for gap in gaps:
        node_id = f"gap:{gap.gap_id}"
        graph.add_node(node_id, type="Gap", label=gap.gap, paper_ids=gap.paper_ids, evidence=gap.supporting_evidence, gap_id=gap.gap_id)
        for trace_id in gap.traceability_path:
            if trace_id in graph.nodes:
                add_edge(graph, trace_id, node_id, "supports_gap", gap.paper_ids[0] if gap.paper_ids else "", evidence_text=gap.gap, section="motif")


def load_candidate_gaps(ctx: Any) -> list[CandidateGap]:
    from .utils import model_validate, read_json

    return [model_validate(CandidateGap, item) for item in read_json(ctx.path("gaps", "candidate_gaps.json"), default=[])]


def run_novelty_filter(ctx: Any, llm_base_url: str | None = None) -> None:
    """LLM post-filter: classifies gaps as trivial/known_open/known_solved/novel.

    Overwrites candidate_gaps.json in-place, keeping only novel and known_open gaps.
    Writes novelty_filter_audit.json for traceability.
    Skips silently if no LLM is configured.
    """
    import sys

    from .llm_client import LLMClient
    from .novelty_filter import filter_novel_gaps

    gaps = load_candidate_gaps(ctx)
    if not gaps:
        return

    ctx.stage_start("novelty_filter")
    gaps_before = len(gaps)
    try:
        llm = LLMClient(ctx)
        if llm_base_url:
            llm.base_url = llm_base_url

        raw_query = ctx.config.get("query", "")
        query_str = raw_query.get("text", "") if isinstance(raw_query, dict) else str(raw_query)
        topic_description = (
            ctx.config.get("venue_retrieval", {}).get("topic_description", "").strip()
            or query_str
        )

        checkpoint_path = ctx.path("gaps", "novelty_filter_verdicts.jsonl")
        filtered, audit = filter_novel_gaps(
            gaps, llm_client=llm, topic_description=topic_description,
            checkpoint_path=checkpoint_path,
        )

        write_json(ctx.path("gaps", "candidate_gaps.json"), [model_dump(g) for g in filtered])
        write_csv(ctx.path("gaps", "candidate_gaps.csv"), [model_dump(g) for g in filtered])
        write_json(ctx.path("gaps", "novelty_filter_audit.json"), audit)
        ctx.stage_end("novelty_filter", gaps_before=gaps_before, gaps_after=len(filtered))
    except Exception as exc:
        print(f"[novelty_filter] WARNING: {exc} — keeping all {gaps_before} gaps", file=sys.stderr)
        ctx.stage_end("novelty_filter", gaps_before=gaps_before, gaps_after=gaps_before)
