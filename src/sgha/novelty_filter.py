from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import networkx as nx

from .gap_objects import CandidateGap


_KEEP_CLASSES: set[str] = {"novel", "known_open", "partially_addressed_in_corpus"}
_ALL_CLASSES: set[str] = {
    "trivial", "known_open", "known_solved", "novel",
    "known_solved_in_corpus", "partially_addressed_in_corpus",
}

_CLASS_SCORE_DELTA: dict[str, float] = {
    "novel": 0.15,
    "known_open": 0.05,
    "known_solved": -0.20,
    "trivial": -0.30,
    "known_solved_in_corpus": -0.30,
    "partially_addressed_in_corpus": -0.05,
}

_COUNTEREVIDENCE_EDGE_TYPES = {
    "counterevidence_for",
    "solution_targets_problem",
    "partially_addresses_gap",
    "relaxes_assumption_of",
    "handles_failure_of",
    "handles_failure_condition",
    "addresses_limitation",
    "relaxes_assumption",
    "resolves_failure_condition",
    "partially_addresses",
}

# Labels that, on their own, indicate only a partial solve (never a full solve).
_PARTIAL_LABELS = {
    "partially_addresses", "relaxes_assumption", "handles_failure_condition",
}

# Direct-ID fields on a CandidateGap that may point at graph nodes.
_GAP_ID_FIELDS = (
    "id", "gap_id", "target_id", "target_node_id", "gap_node_id", "motif_id",
)
# Collection-of-IDs fields that may point at graph core nodes.
_GAP_IDLIST_FIELDS = (
    "method_ids", "assumption_ids", "limitation_ids", "failure_condition_ids",
    "target_ids", "core_method_ids", "core_assumption_ids", "core_limitation_ids",
    "core_failure_condition_ids", "method_id", "assumption_id", "limitation_id",
    "failure_condition_id",
)


def _edge_id_index(graph: nx.MultiDiGraph) -> dict[str, tuple[str, str]]:
    """Map each edge's 'id' attribute (and its key) to its (source, target) endpoints."""
    idx: dict[str, tuple[str, str]] = {}
    for u, v, k, d in graph.edges(keys=True, data=True):
        eid = d.get("id")
        if eid is not None:
            idx[str(eid)] = (u, v)
        idx[str(k)] = (u, v)
    return idx


def collect_gap_lookup_nodes(gap: CandidateGap, graph: nx.MultiDiGraph) -> set[str]:
    """Gather every graph node that could carry counterevidence for this gap.

    Sources: direct ID fields, traceability_path node IDs, edge IDs in the
    traceability_path resolved to their endpoints, structured core-node ID fields,
    and exact gap-label matches. Only IDs that are actual graph nodes are kept.
    """
    candidates: set[str] = set()

    def _add(x: Any) -> None:
        if isinstance(x, str) and x:
            candidates.add(x)

    # 1. Direct ID fields (plain attrs and any pydantic extras)
    _extra0 = getattr(gap, "model_extra", None) or {}
    for f in _GAP_ID_FIELDS:
        _add(getattr(gap, f, None))
        _add(_extra0.get(f))

    # 2 + 4. Traceability path: node IDs directly, edge IDs resolved to endpoints
    edge_idx = _edge_id_index(graph)
    for tid in getattr(gap, "traceability_path", []) or []:
        tid = str(tid)
        if tid in graph.nodes:
            candidates.add(tid)
        elif tid in edge_idx:
            u, v = edge_idx[tid]
            candidates.add(u)
            candidates.add(v)

    # 3. Structured core-node ID fields (single or list)
    extra = getattr(gap, "model_extra", None) or {}
    for f in _GAP_IDLIST_FIELDS:
        val = getattr(gap, f, None)
        if val is None:
            val = extra.get(f)
        if isinstance(val, str):
            _add(val)
        elif isinstance(val, (list, tuple, set)):
            for x in val:
                _add(x)

    # 5. Exact gap-label match (legacy behaviour, retained)
    gap_label_lower = gap.gap.lower()[:80]
    for node_id, ndata in graph.nodes(data=True):
        if ndata.get("type") in {"Gap", "Assumption", "Limitation", "FailureCondition"}:
            if str(ndata.get("label", "")).lower() == gap_label_lower:
                candidates.add(node_id)

    # Keep only IDs that are real graph nodes
    return {c for c in candidates if c in graph.nodes}


def find_counterevidence_for_gap(gap: CandidateGap, graph: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Return all counterevidence edge dicts reachable from a gap's lookup nodes.

    Also matches counterevidence edges by metadata back-references (linked_gap_id,
    gap_id, motif_gap_id, target_gap_id) so gap-level edges are found even when the
    motif gap is not itself a graph node.
    """
    lookup_nodes = collect_gap_lookup_nodes(gap, graph)
    items: list[dict[str, Any]] = []
    seen: set[int] = set()

    for node_id in lookup_nodes:
        for _, _, _, edata in graph.out_edges(node_id, keys=True, data=True):
            if edata.get("relation") in _COUNTEREVIDENCE_EDGE_TYPES and id(edata) not in seen:
                seen.add(id(edata)); items.append(dict(edata))
        for _, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") in _COUNTEREVIDENCE_EDGE_TYPES and id(edata) not in seen:
                seen.add(id(edata)); items.append(dict(edata))

    # Metadata back-reference match (gap-level edges not attached to a graph node)
    gap_refs = {getattr(gap, "gap_id", None), getattr(gap, "id", None)}
    gap_refs.discard(None)
    for _, _, _, edata in graph.edges(keys=True, data=True):
        if edata.get("relation") not in _COUNTEREVIDENCE_EDGE_TYPES or id(edata) in seen:
            continue
        for mf in ("linked_gap_id", "gap_id", "motif_gap_id", "target_gap_id"):
            if edata.get(mf) in gap_refs:
                seen.add(id(edata)); items.append(dict(edata)); break
    return items


def corpus_aware_novelty_check(gap: CandidateGap, graph: nx.MultiDiGraph) -> dict[str, Any]:
    """Check whether a gap has in-corpus counterevidence edges.

    Traverses the gap's traceability/core nodes (not just the motif-gap node), so
    counterevidence attached to assumption/limitation/failure-condition nodes is found.
    Status is scope-aware: a full solve requires a fully_addresses label with
    scope_match=full and high confidence.

    Returns a dict with:
      in_corpus_status, counterevidence_count, counterevidence_summary,
      remaining_gap_scope, skip_llm
    """
    counterevidence_items = find_counterevidence_for_gap(gap, graph)

    if not counterevidence_items:
        return {
            "in_corpus_status": "no_in_corpus_counterevidence",
            "counterevidence_count": 0,
            "counterevidence_summary": "",
            "remaining_gap_scope": "",
            "skip_llm": False,
        }

    summary_parts = []
    remaining_parts = []
    for item in counterevidence_items[:3]:
        method = item.get("resolution_method", "")
        label = item.get("classifier_label", "")
        conf = item.get("classifier_confidence", 0.0)
        paper = item.get("source_paper", "")
        summary_parts.append(f"{method} ({label}, conf={conf:.2f}, paper={paper})")
        rg = item.get("remaining_gap_scope", "")
        if rg:
            remaining_parts.append(rg)
    summary = "; ".join(summary_parts)
    remaining = " | ".join(remaining_parts)

    # Scope-aware status: known_solved only when a full-solve edge exists.
    def _is_full_solve(it: dict[str, Any]) -> bool:
        label = str(it.get("classifier_label", "")).lower()
        scope = str(it.get("scope_match", "")).lower()
        conf = float(it.get("classifier_confidence", 0.0) or 0.0)
        rel = str(it.get("relation", "")).lower()
        full_label = label == "fully_addresses" or rel == "counterevidence_for"
        return full_label and scope == "full" and conf >= 0.80

    def _is_partial(it: dict[str, Any]) -> bool:
        label = str(it.get("classifier_label", "")).lower()
        scope = str(it.get("scope_match", "")).lower()
        conf = float(it.get("classifier_confidence", 0.0) or 0.0)
        if conf < 0.60:
            return False
        if label in _PARTIAL_LABELS:
            return True
        # fully_addresses but scope not full → partial
        if label == "fully_addresses" and scope != "full":
            return True
        return scope in {"partial", "mismatch"}

    if any(_is_full_solve(it) for it in counterevidence_items):
        status = "known_solved_in_corpus"
        skip_llm = True
    elif any(_is_partial(it) for it in counterevidence_items):
        status = "partially_addressed_in_corpus"
        skip_llm = False
    else:
        status = "no_in_corpus_counterevidence"
        skip_llm = False

    return {
        "in_corpus_status": status,
        "counterevidence_count": len(counterevidence_items),
        "counterevidence_summary": summary,
        "remaining_gap_scope": remaining,
        "skip_llm": skip_llm,
    }


def filter_novel_gaps(
    gaps: list[CandidateGap],
    *,
    llm_client: Any,
    topic_description: str = "",
    batch_size: int = 5,
    keep_classes: set[str] | None = None,
    checkpoint_path: Path | None = None,
    graph: nx.MultiDiGraph | None = None,
) -> tuple[list[CandidateGap], list[dict[str, Any]]]:
    """Classify gaps by novelty and filter out trivial/known-solved ones.

    Supports checkpointing: writes each batch verdict to checkpoint_path immediately,
    so restarts resume from the last completed batch instead of starting over.

    If graph is provided, runs corpus_aware_novelty_check first: gaps that are
    known_solved_in_corpus are filtered without calling the LLM.

    Returns (filtered_gaps, audit_records).
    Kept classes by default: "novel", "known_open", and "partially_addressed_in_corpus".
    """
    if keep_classes is None:
        keep_classes = _KEEP_CLASSES

    # Load existing checkpoint verdicts (gap_id -> {class, reason})
    checkpoint: dict[str, dict[str, str]] = {}
    if checkpoint_path and Path(checkpoint_path).exists():
        try:
            for line in Path(checkpoint_path).read_text().strip().splitlines():
                rec = json.loads(line)
                checkpoint[rec["gap_id"]] = rec
            print(f"[novelty_filter] Resuming: {len(checkpoint)} gaps already classified.", flush=True)
        except Exception:
            pass

    audit: list[dict[str, Any]] = []
    classified: list[tuple[CandidateGap, str, str]] = []

    # --- Corpus-aware pre-check ---
    corpus_skip: dict[str, dict[str, Any]] = {}
    if graph is not None:
        for gap in gaps:
            if gap.gap_id in checkpoint:
                continue
            check = corpus_aware_novelty_check(gap, graph)
            if check["in_corpus_status"] in ("known_solved_in_corpus", "partially_addressed_in_corpus"):
                corpus_skip[gap.gap_id] = check
                # Update CandidateGap fields if they exist
                if hasattr(gap, "counterevidence_status"):
                    gap.counterevidence_status = check["in_corpus_status"]  # type: ignore[assignment]
                if hasattr(gap, "counterevidence_summary"):
                    gap.counterevidence_summary = check["counterevidence_summary"]  # type: ignore[assignment]
                if hasattr(gap, "remaining_gap_scope"):
                    gap.remaining_gap_scope = check["remaining_gap_scope"]  # type: ignore[assignment]

    # Pre-populate checkpoint with corpus-solved gaps
    for gap in gaps:
        if gap.gap_id in corpus_skip and gap.gap_id not in checkpoint:
            check = corpus_skip[gap.gap_id]
            status = check["in_corpus_status"]
            reason = f"corpus_check: {check['counterevidence_summary'][:200]}"
            checkpoint[gap.gap_id] = {
                "gap_id": gap.gap_id,
                "gap": gap.gap,
                "novelty_class": status,
                "reason": reason,
            }
            if checkpoint_path:
                with open(checkpoint_path, "a") as f:
                    f.write(json.dumps(checkpoint[gap.gap_id]) + "\n")

    n_corpus_skipped = sum(1 for g in gaps if g.gap_id in corpus_skip)
    if n_corpus_skipped:
        print(f"[novelty_filter] Corpus check: {n_corpus_skipped} gaps pre-classified, skipping LLM for solved ones.", flush=True)

    for batch_start in range(0, len(gaps), batch_size):
        batch = gaps[batch_start : batch_start + batch_size]

        # Split batch into already-done and pending
        pending = [g for g in batch if g.gap_id not in checkpoint]
        done = [g for g in batch if g.gap_id in checkpoint]

        if pending:
            result = _classify_batch(pending, llm_client=llm_client, topic_description=topic_description)
            for gap, cls, reason in zip(pending, result["classes"], result["reasons"]):
                checkpoint[gap.gap_id] = {"gap_id": gap.gap_id, "gap": gap.gap,
                                           "novelty_class": cls, "reason": reason}
                # Write immediately to checkpoint file
                if checkpoint_path:
                    with open(checkpoint_path, "a") as f:
                        f.write(json.dumps(checkpoint[gap.gap_id]) + "\n")
            batch_num = batch_start // batch_size + 1
            total_batches = (len(gaps) + batch_size - 1) // batch_size
            kept_in_batch = sum(1 for g in pending if checkpoint[g.gap_id]["novelty_class"] in keep_classes)
            print(f"[novelty_filter] batch {batch_num}/{total_batches}: {kept_in_batch}/{len(pending)} kept", flush=True)

        for gap in batch:
            rec = checkpoint[gap.gap_id]
            classified.append((gap, rec["novelty_class"], rec["reason"]))

    filtered: list[CandidateGap] = []
    for gap, cls, reason in classified:
        # Adjust novelty score for partially_addressed_in_corpus using remaining scope
        if cls == "partially_addressed_in_corpus":
            check = corpus_skip.get(gap.gap_id, {})
            remaining = check.get("remaining_gap_scope", "")
            if remaining and hasattr(gap, "remaining_gap_scope"):
                gap.remaining_gap_scope = remaining  # type: ignore[assignment]

        gap.novelty_score = max(0.0, min(1.0, gap.novelty_score + _CLASS_SCORE_DELTA.get(cls, 0.0)))
        audit.append({
            "gap_id": gap.gap_id,
            "gap": gap.gap,
            "novelty_class": cls,
            "reason": reason,
            "kept": cls in keep_classes,
        })
        if cls in keep_classes:
            filtered.append(gap)

    return filtered, audit


def _classify_batch(
    batch: list[CandidateGap],
    *,
    llm_client: Any,
    topic_description: str,
) -> dict[str, list[str]]:
    gap_blocks = []
    for i, gap in enumerate(batch):
        gap_blocks.append(
            f"Gap {i + 1}:\n"
            f"  Description: {gap.gap}\n"
            f"  Target: {gap.target}\n"
            f"  Mechanism: {gap.mechanism}\n"
            f"  Motif type: {gap.motif_type}\n"
            f"  Paper count: {len(gap.paper_ids)}"
        )
    gaps_text = "\n\n".join(gap_blocks)
    topic_hint = f"\nResearch area: {topic_description[:300]}\n" if topic_description else "\n"

    prompt = (
        "You are a senior ML researcher evaluating structural gaps found by automated analysis of a paper corpus. "
        "Your job is to FILTER OUT weak gaps. Most gaps will be trivial — be skeptical by default.\n"
        f"{topic_hint}\n"
        "Classify each gap into exactly one category:\n\n"
        '- "trivial": Classify as trivial if the gap is just "method X can fail" or "X has limitations" '
        "with no named assumption or failure condition. Also trivial: if the target is only a model/paper name "
        "(GPT-4, LLaMA, Dong et al.) with no concrete claim, or if it is covered verbatim in any survey.\n\n"
        '- "known_open": A specific, named gap that experts know about but have not solved. '
        "Must name a concrete assumption, failure condition, or empirical vs theoretical discrepancy — "
        "not just 'X may fail'. Examples: sub-Gaussian noise assumption violated in heavy-tailed reward settings; "
        "chain-of-thought breaks on multi-step arithmetic with ≥5 operations.\n\n"
        '- "known_solved": Already substantially addressed in literature published after 2021.\n\n'
        '- "novel": Non-obvious pattern only visible by reading across multiple papers. '
        "Would surprise a field expert. The gap must name a specific mechanism not discussed in any single paper.\n\n"
        "Be strict about trivial. Be fair about known_open when the gap names a specific assumption or condition. "
        "Default to trivial only for gaps with no named mechanism whatsoever.\n\n"
        f"{gaps_text}\n\n"
        "Respond with a JSON object in this exact format:\n"
        "{\n"
        '  "classifications": [\n'
        '    {"gap_index": 1, "class": "<trivial|known_open|known_solved|novel>", "reason": "<one sentence>"},\n'
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Output only the JSON object. No markdown fences."
    )

    try:
        data, _, _, _ = llm_client.complete_json(
            stage="novelty_filter",
            agent_name="novelty_classifier",
            prompt=prompt,
            schema_name="novelty_classification",
        )
        items = data.get("classifications", data.get("items", []))
        if not isinstance(items, list):
            items = []
        classes: list[str] = []
        reasons: list[str] = []
        for item in sorted(items, key=lambda x: x.get("gap_index", 0)):
            cls = str(item.get("class", "novel")).lower()
            if cls not in _ALL_CLASSES:
                cls = "novel"
            classes.append(cls)
            reasons.append(str(item.get("reason", "")))
        # Pad with "novel" if LLM returned fewer items than batch (safe default = keep)
        while len(classes) < len(batch):
            classes.append("novel")
            reasons.append("no classification returned — defaulting to keep")
        return {"classes": classes[: len(batch)], "reasons": reasons[: len(batch)]}
    except Exception as exc:
        print(f"[novelty_filter] batch classification failed: {exc}", file=sys.stderr)
        return {
            "classes": ["novel"] * len(batch),
            "reasons": [f"classification error: {exc}"] * len(batch),
        }
