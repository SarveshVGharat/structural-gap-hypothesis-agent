"""Counterevidence discovery: links resolution records to gap nodes in the graph."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import networkx as nx
from pydantic import BaseModel

from .gap_objects import CandidateGap
from .llm_client import LLMClient
from .prompt_templates import counterevidence_classifier_prompt
from .resolution_extraction import ResolutionRecord
from .utils import append_jsonl, ensure_dir, model_dump, stable_id, utc_now_iso, write_json


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CounterevidenceCandidate(BaseModel):
    candidate_id: str
    gap_node_id: str
    gap_node_label: str
    gap_type: str  # assumption|limitation|failure_condition|motif_gap
    resolution_record_id: str
    resolution_method: str
    target_problem: str
    addressed_condition: str
    paper_id: str
    candidate_reason: str
    candidate_score: float
    evidence_text: str


class ClassifierResult(BaseModel):
    label: Literal[
        "fully_addresses",
        "partially_addresses",
        "relaxes_assumption",
        "handles_failure_condition",
        "related_but_not_solution",
        "unrelated",
        "unclear",
    ]
    confidence: float
    scope_match: Literal["full", "partial", "mismatch", "unclear"]
    why: str
    remaining_gap_scope: str
    should_create_counterevidence_edge: bool


_LABEL_TO_EDGE_TYPE = {
    "fully_addresses": "counterevidence_for",
    "partially_addresses": "partially_addresses_gap",
    "relaxes_assumption": "relaxes_assumption_of",
    "handles_failure_condition": "handles_failure_of",
}

_COUNTEREVIDENCE_NODE_TYPES = {"Assumption", "Limitation", "FailureCondition", "Gap"}

_CONTRAST_PREFIXES = [
    "non-", "un-", "without", "free", "agnostic", "robust", "misspecified",
    "corrupted", "adversarial", "distribution-free", "prior-free", "horizon-free",
    "model-free", "heavy-tail", "heavy tail", "parameter-free", "anytime", "adaptive",
]

_VALID_LABELS = {
    "fully_addresses", "partially_addresses", "relaxes_assumption",
    "handles_failure_condition", "related_but_not_solution", "unrelated", "unclear",
}
_VALID_SCOPE_MATCHES = {"full", "partial", "mismatch", "unclear"}


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase alphanumeric tokens of length >= 3."""
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _token_overlap(a: set[str], b: set[str]) -> float:
    """Normalized intersection / union (Jaccard)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Anchor term computation
# ---------------------------------------------------------------------------

def _build_anchor_terms(graph: nx.MultiDiGraph, top_n: int = 100) -> set[str]:
    """Derive anchor terms from top-N most frequent tokens in node labels (length >= 5)."""
    freq: Counter[str] = Counter()
    for _, data in graph.nodes(data=True):
        label = str(data.get("label", ""))
        for tok in re.findall(r"[a-z0-9]{5,}", label.lower()):
            freq[tok] += 1
    return {tok for tok, _ in freq.most_common(top_n)}


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

def _build_score_indexes(graph: nx.MultiDiGraph) -> dict[str, Any]:
    """Precompute graph indexes once so _score_candidate avoids per-pair full scans.

    Returns a dict with:
      - paper_to_improved_targets: paper_id -> set of target paper_ids reachable via
        an improves_over edge whose source node includes that paper. Used by block C.
      - paper_to_method_tokens: paper_id -> union of Method/Claim node label tokens
        for nodes associated with that paper. Used by block "prior work overlap".
    These are pure restructurings of the same data the original inner-loop scans read,
    so candidate scores are unchanged.
    """
    paper_to_improved_targets: dict[str, set[str]] = {}
    for src, tgt, _, edata in graph.edges(keys=True, data=True):
        if edata.get("relation") != "improves_over":
            continue
        src_papers = graph.nodes[src].get("paper_ids", []) if src in graph.nodes else []
        tgt_papers = set(graph.nodes[tgt].get("paper_ids", []) if tgt in graph.nodes else [])
        if not tgt_papers:
            continue
        for p in src_papers:
            paper_to_improved_targets.setdefault(p, set()).update(tgt_papers)

    paper_to_method_tokens: dict[str, set[str]] = {}
    for node_id, ndata in graph.nodes(data=True):
        if ndata.get("type") not in {"Method", "Claim"}:
            continue
        node_tokens = _tokenize(str(ndata.get("label", "")))
        if not node_tokens:
            continue
        for p in ndata.get("paper_ids", []):
            paper_to_method_tokens.setdefault(p, set()).update(node_tokens)

    return {
        "paper_to_improved_targets": paper_to_improved_targets,
        "paper_to_method_tokens": paper_to_method_tokens,
    }


def _gap_method_tokens_for_papers(paper_ids: set[str], paper_to_method_tokens: dict[str, set[str]]) -> set[str]:
    """Union of Method/Claim label tokens across all papers associated with a gap."""
    out: set[str] = set()
    for p in paper_ids:
        toks = paper_to_method_tokens.get(p)
        if toks:
            out |= toks
    return out


def _score_candidate(
    gap_node_id: str,
    gap_label: str,
    gap_node_type: str,
    gap_paper_ids: set[str],
    gap_evidence_tokens: set[str],
    record: ResolutionRecord,
    graph: nx.MultiDiGraph,
    anchor_terms: set[str],
    *,
    indexes: dict[str, Any] | None = None,
    gap_tokens_raw: set[str] | None = None,
    gap_method_tokens: set[str] | None = None,
) -> tuple[float, str]:
    """Compute candidate score. Returns (score, reason).

    When `indexes` (from _build_score_indexes) and the per-gap precomputed sets
    `gap_tokens_raw` / `gap_method_tokens` are supplied, blocks C and the prior-work
    check use O(1) dict/set lookups instead of scanning every graph edge/node.
    The score values are identical to the original full-scan implementation.
    """

    # A. Token overlap
    res_tokens = _tokenize(
        " ".join([record.target_problem, record.addressed_condition, record.scope, record.method])
    )
    score_a = _token_overlap(gap_evidence_tokens, res_tokens)

    # B. Morphological contrast bonus
    score_b = 0.0
    if gap_tokens_raw is None:
        gap_tokens_raw = gap_evidence_tokens | _tokenize(gap_label)
    res_text_lower = " ".join([record.target_problem, record.addressed_condition, record.evidence_text]).lower()
    for prefix in _CONTRAST_PREFIXES:
        # Check if resolution text mentions a contrast prefix + a token that appears in gap
        for gap_tok in gap_tokens_raw:
            if len(gap_tok) < 4:
                continue
            variant = prefix + gap_tok
            if variant in res_text_lower or prefix + " " + gap_tok in res_text_lower:
                score_b = min(0.3, score_b + 0.1)
                break

    # C. Graph neighborhood bonus
    score_c = 0.0
    rec_paper_id = record.paper_id

    # Same paper → negative signal
    if rec_paper_id in gap_paper_ids:
        score_c -= 0.1
    else:
        # Does resolution paper mention a method that improves_over a method associated with gap's papers?
        if indexes is not None:
            improved = indexes["paper_to_improved_targets"].get(rec_paper_id, set())
            if improved & gap_paper_ids:
                score_c = min(score_c + 0.1, 0.2)
        else:
            for src, tgt, _, edata in graph.edges(keys=True, data=True):
                if edata.get("relation") == "improves_over":
                    src_papers = set(graph.nodes[src].get("paper_ids", []) if src in graph.nodes else [])
                    tgt_papers = set(graph.nodes[tgt].get("paper_ids", []) if tgt in graph.nodes else [])
                    if rec_paper_id in src_papers and tgt_papers & gap_paper_ids:
                        score_c = min(score_c + 0.1, 0.2)
                        break

    # Prior work or baseline overlap
    if record.prior_work_or_baseline:
        prior_tokens = _tokenize(record.prior_work_or_baseline)
        if indexes is not None:
            # gap_method_tokens = union of Method/Claim tokens for nodes sharing a paper
            # with the gap. A non-empty intersection with prior_tokens is equivalent to the
            # original "exists a Method/Claim node sharing a paper AND a token" check.
            if gap_method_tokens is None:
                gap_method_tokens = _gap_method_tokens_for_papers(
                    gap_paper_ids, indexes["paper_to_method_tokens"]
                )
            if prior_tokens & gap_method_tokens:
                score_c = min(score_c + 0.15, 0.2)
        else:
            for node_id, ndata in graph.nodes(data=True):
                if ndata.get("type") not in {"Method", "Claim"}:
                    continue
                node_papers = set(ndata.get("paper_ids", []))
                if not (node_papers & gap_paper_ids):
                    continue
                node_tokens = _tokenize(str(ndata.get("label", "")))
                if len(node_tokens & prior_tokens) >= 1:
                    score_c = min(score_c + 0.15, 0.2)
                    break

    score_c = max(-0.1, min(0.2, score_c))

    # D. Anchor term bonus
    score_d = 0.0
    res_ev_tokens = _tokenize(record.evidence_text)
    shared_anchors = (gap_evidence_tokens & res_ev_tokens) & anchor_terms
    if len(shared_anchors) >= 2:
        score_d = 0.1

    total = min(1.0, score_a + score_b + score_c + score_d)

    parts = []
    if score_a > 0:
        parts.append(f"token_overlap={score_a:.2f}")
    if score_b > 0:
        parts.append(f"contrast_bonus={score_b:.2f}")
    if score_c != 0:
        parts.append(f"graph_bonus={score_c:.2f}")
    if score_d > 0:
        parts.append(f"anchor_bonus={score_d:.2f}")
    reason = "; ".join(parts) if parts else "low_overlap"

    return total, reason


# ---------------------------------------------------------------------------
# Gap node helpers
# ---------------------------------------------------------------------------

def _get_gap_evidence_texts(graph: nx.MultiDiGraph, node_id: str) -> list[str]:
    """Collect evidence texts from a gap node's supporting edges and node data."""
    texts: list[str] = []
    data = graph.nodes.get(node_id, {})
    for ev in data.get("evidence", []):
        if isinstance(ev, dict):
            t = ev.get("evidence_text", "") or ev.get("text", "")
        else:
            t = str(ev)
        if t:
            texts.append(t)
    # Also look at in-edges with supports_gap relation
    for src, _, _, edata in graph.in_edges(node_id, keys=True, data=True):
        if edata.get("relation") == "supports_gap":
            for ev in edata.get("evidence", []):
                if isinstance(ev, dict):
                    t = ev.get("evidence_text", "") or ev.get("text", "")
                else:
                    t = str(ev)
                if t:
                    texts.append(t)
    return texts


def _build_gap_nodes(
    graph: nx.MultiDiGraph,
    gaps: list[CandidateGap],
    candidate_scope: str,
) -> list[tuple[str, str, str, set[str]]]:
    """Build the list of (node_id, label, type, paper_ids) gap-nodes to score against.

    candidate_scope:
      - "surviving_gaps_only" (default): the 60 surviving CandidateGap objects as
        motif_gap nodes, PLUS their traceability/core nodes of type
        Assumption/Limitation/FailureCondition (deduped). Does NOT pull in the whole
        graph's assumption/limitation/failure population.
      - "all_graph_nodes": original behaviour — every Assumption/Limitation/
        FailureCondition/Gap node in the graph, plus the motif gaps.
    """
    gap_nodes: list[tuple[str, str, str, set[str]]] = []
    seen: set[str] = set()

    if candidate_scope == "all_graph_nodes":
        for node_id, ndata in graph.nodes(data=True):
            if str(ndata.get("type", "")) in _COUNTEREVIDENCE_NODE_TYPES:
                gap_nodes.append((node_id, str(ndata.get("label", node_id)),
                                  str(ndata.get("type")), set(ndata.get("paper_ids", []))))
                seen.add(node_id)
        for g in gaps:
            if g.gap_id not in seen:
                gap_nodes.append((g.gap_id, g.gap[:120], "motif_gap", set(g.paper_ids)))
                seen.add(g.gap_id)
        return gap_nodes

    # Default: surviving_gaps_only
    for g in gaps:
        # The motif gap itself
        if g.gap_id not in seen:
            gap_nodes.append((g.gap_id, g.gap[:120], "motif_gap", set(g.paper_ids)))
            seen.add(g.gap_id)
        # Its traceability/core nodes (assumption/limitation/failure only)
        for nid in g.traceability_path:
            if nid in seen or nid not in graph.nodes:
                continue
            ndata = graph.nodes[nid]
            ntype = str(ndata.get("type", ""))
            if ntype in {"Assumption", "Limitation", "FailureCondition"}:
                gap_nodes.append((nid, str(ndata.get("label", nid)), ntype,
                                  set(ndata.get("paper_ids", []))))
                seen.add(nid)
    return gap_nodes


def generate_candidates(
    graph: nx.MultiDiGraph,
    gaps: list[CandidateGap],
    resolution_records: list[ResolutionRecord],
    *,
    candidate_scope: str = "surviving_gaps_only",
    max_candidates_per_gap: int = 20,
    max_total_candidates: int = 2000,
    min_candidate_score: float = 0.20,
    out_path: Any = None,
    progress_every: int = 20000,
) -> list[CounterevidenceCandidate]:
    """Deterministic candidate generation only (no LLM, no graph writes).

    Uses precomputed graph indexes so the inner loop performs set lookups instead of
    scanning all graph nodes/edges. Streams results to `out_path` + '.tmp' and renames
    on completion so an interrupt does not leave a half-written final file.
    """
    import time
    from pathlib import Path

    anchor_terms = _build_anchor_terms(graph)
    indexes = _build_score_indexes(graph)
    gap_nodes = _build_gap_nodes(graph, gaps, candidate_scope)

    total_pairs = len(gap_nodes) * len(resolution_records)
    print(
        f"[candidate_gen] scope={candidate_scope} gap_nodes={len(gap_nodes)} "
        f"records={len(resolution_records)} pairs={total_pairs}",
        flush=True,
    )

    tmp_path = None
    tmp_fh = None
    if out_path is not None:
        out_path = Path(out_path)
        tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp_fh = open(tmp_path, "w")

    all_candidates: list[CounterevidenceCandidate] = []
    pairs_done = 0
    t0 = time.time()

    for gi, (node_id, label, ntype, paper_ids) in enumerate(gap_nodes):
        ev_texts = _get_gap_evidence_texts(graph, node_id)
        ev_all = label + " " + " ".join(ev_texts[:5])
        gap_evidence_tokens = _tokenize(ev_all)
        gap_tokens_raw = gap_evidence_tokens | _tokenize(label)
        gap_method_tokens = _gap_method_tokens_for_papers(paper_ids, indexes["paper_to_method_tokens"])

        scored: list[tuple[float, CounterevidenceCandidate]] = []
        for record in resolution_records:
            score, reason = _score_candidate(
                node_id, label, ntype, paper_ids, gap_evidence_tokens,
                record, graph, anchor_terms,
                indexes=indexes, gap_tokens_raw=gap_tokens_raw,
                gap_method_tokens=gap_method_tokens,
            )
            pairs_done += 1
            if score < min_candidate_score:
                continue
            cid = stable_id("ce", node_id, record.record_id)
            scored.append((score, CounterevidenceCandidate(
                candidate_id=cid, gap_node_id=node_id, gap_node_label=label,
                gap_type=ntype, resolution_record_id=record.record_id,
                resolution_method=record.method, target_problem=record.target_problem,
                addressed_condition=record.addressed_condition, paper_id=record.paper_id,
                candidate_reason=reason, candidate_score=score,
                evidence_text=record.evidence_text,
            )))

        scored.sort(key=lambda x: -x[0])
        for _, c in scored[:max_candidates_per_gap]:
            all_candidates.append(c)
            if tmp_fh is not None:
                tmp_fh.write(_json_line(c))

        if pairs_done >= progress_every and (gi % 25 == 0 or gi == len(gap_nodes) - 1):
            el = time.time() - t0
            print(
                f"[candidate_gen] gap {gi + 1}/{len(gap_nodes)} | pairs {pairs_done}/{total_pairs} "
                f"| kept {len(all_candidates)} | {el:.1f}s",
                flush=True,
            )

    if tmp_fh is not None:
        tmp_fh.close()

    # Global cap: keep top-N by score
    if len(all_candidates) > max_total_candidates:
        all_candidates.sort(key=lambda c: -c.candidate_score)
        all_candidates = all_candidates[:max_total_candidates]

    # Rewrite final file from the capped set, then atomically replace the .tmp
    if out_path is not None:
        with open(out_path, "w") as f:
            for c in all_candidates:
                f.write(_json_line(c))
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()

    print(
        f"[candidate_gen] DONE pairs={pairs_done} kept={len(all_candidates)} "
        f"elapsed={time.time() - t0:.1f}s",
        flush=True,
    )
    return all_candidates


def _json_line(c: CounterevidenceCandidate) -> str:
    import json
    return json.dumps(model_dump(c)) + "\n"


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------

def _classify_candidate(
    candidate: CounterevidenceCandidate,
    graph: nx.MultiDiGraph,
    llm: LLMClient,
) -> ClassifierResult | None:
    """Run LLM classifier on a candidate. Returns None on failure."""
    # Get gap evidence text
    ev_texts = _get_gap_evidence_texts(graph, candidate.gap_node_id)
    gap_evidence = " | ".join(ev_texts[:3]) if ev_texts else candidate.gap_node_label

    prompt = counterevidence_classifier_prompt(
        gap_label=candidate.gap_node_label,
        gap_type=candidate.gap_type,
        gap_evidence=gap_evidence,
        resolution_method=candidate.resolution_method,
        target_problem=candidate.target_problem,
        addressed_condition=candidate.addressed_condition,
        scope="",
        evidence_text=candidate.evidence_text,
        prior_work_or_baseline="",
    )

    # Per-role generation limits: the classifier is a short structured-JSON task, so we
    # disable the long reasoning trace and cap output. This is the dominant latency fix
    # (Qwen3.5 thinking-on generations of ~4000 tokens were ~94s/call).
    _ce_cfg = llm.ctx.config.get("counterevidence_linking", {}) if hasattr(llm, "ctx") else {}
    _clf_max_tokens = int(_ce_cfg.get("classifier_max_tokens", 800))
    _clf_temperature = float(_ce_cfg.get("classifier_temperature", 0.0))
    _clf_enable_thinking = bool(_ce_cfg.get("classifier_enable_thinking", False))

    try:
        raw, _, _, _ = llm.complete_json(
            stage="counterevidence_discovery",
            agent_name="counterevidence_classifier",
            prompt=prompt,
            schema_name="ClassifierResult",
            max_tokens=_clf_max_tokens,
            temperature=_clf_temperature,
            enable_thinking=_clf_enable_thinking,
        )
        label = str(raw.get("label", "unclear")).strip().lower()
        if label not in _VALID_LABELS:
            label = "unclear"
        scope_match = str(raw.get("scope_match", "unclear")).strip().lower()
        if scope_match not in _VALID_SCOPE_MATCHES:
            scope_match = "unclear"
        try:
            conf = float(raw.get("confidence", 0.5))
            conf = max(0.0, min(1.0, conf))
        except (TypeError, ValueError):
            conf = 0.5

        return ClassifierResult(
            label=label,  # type: ignore[arg-type]
            confidence=conf,
            scope_match=scope_match,  # type: ignore[arg-type]
            why=str(raw.get("why", "")),
            remaining_gap_scope=str(raw.get("remaining_gap_scope", "")),
            should_create_counterevidence_edge=bool(raw.get("should_create_counterevidence_edge", False)),
        )
    except Exception as exc:
        print(f"[counterevidence_linking] Classifier failed: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Resumable, checkpointed classifier runner
# ---------------------------------------------------------------------------

def _read_completed_ids(out_path: Path, malformed_path: Path) -> set[str]:
    """Candidate IDs that must be skipped on resume.

    From the main output file: any record with a valid candidate_id and a real
    classification label (not "error"). From the malformed file: only records that
    carry BOTH a valid candidate_id AND an explicit failure label — those are treated
    as terminally done so we do not retry them forever. Half-written/corrupt lines are
    ignored, so a JSONL truncated by an interrupt remains safe to resume from.
    """
    done: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue  # ignore a partial final line from an interrupted write
            cid = rec.get("candidate_id")
            label = rec.get("classifier_label")
            if cid and label and label != "error":
                done.add(cid)
    if malformed_path.exists():
        for line in malformed_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            cid = rec.get("candidate_id")
            label = rec.get("classifier_label", "")
            if cid and (rec.get("api_failure") is True or label == "error"):
                done.add(cid)
    return done


def _read_valid_records(out_path: Path) -> list[dict[str, Any]]:
    """Load previously-completed valid classification records (for downstream reuse)."""
    out: list[dict[str, Any]] = []
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("candidate_id") and rec.get("classifier_label") and rec.get("classifier_label") != "error":
                out.append(rec)
    return out


def classify_candidates_checkpointed(
    candidates: list[CounterevidenceCandidate],
    graph: nx.MultiDiGraph,
    llm: Any,
    *,
    out_path: Any,
    malformed_path: Any,
    summary_path: Any,
    resume: bool = True,
    progress_every: int = 10,
    classify_fn: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify candidates, writing each result to disk immediately (append + flush +
    fsync) so progress survives an interrupt/timeout and can be resumed.

    - Valid classifications -> out_path (one JSONL line each).
    - API failures / None results -> malformed_path (kept separate; never counted as
      a valid classification).
    - On resume, already-completed candidate_ids are skipped.
    - A checkpoint summary is written to summary_path.

    Returns (valid_records, summary). `classify_fn` is injectable for testing.
    """
    out_path, malformed_path, summary_path = Path(out_path), Path(malformed_path), Path(summary_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _classify = classify_fn or _classify_candidate

    completed_ids = _read_completed_ids(out_path, malformed_path) if resume else set()
    valid_records = _read_valid_records(out_path) if resume else []
    resumed = len(completed_ids)

    newly = 0
    failures = 0
    t0 = time.time()
    of = open(out_path, "a", encoding="utf-8")
    mf = open(malformed_path, "a", encoding="utf-8")
    try:
        for c in candidates:
            if c.candidate_id in completed_ids:
                continue
            r = _classify(c, graph, llm)
            base = model_dump(c)
            if r is None:
                failures += 1
                rec = {**base, "classifier_label": "error", "classifier_confidence": 0.0,
                       "api_failure": True, "timestamp": utc_now_iso()}
                mf.write(json.dumps(rec) + "\n"); mf.flush(); os.fsync(mf.fileno())
            else:
                rec = {**base, "classifier_label": r.label, "classifier_confidence": r.confidence,
                       "scope_match": r.scope_match, "why": r.why,
                       "remaining_gap_scope": r.remaining_gap_scope,
                       "should_create_counterevidence_edge": r.should_create_counterevidence_edge,
                       "api_failure": False, "timestamp": utc_now_iso()}
                of.write(json.dumps(rec) + "\n"); of.flush(); os.fsync(of.fileno())
                completed_ids.add(c.candidate_id)
                valid_records.append(rec)
                newly += 1
            if (newly + failures) % progress_every == 0:
                print(f"[classifier] completed={len(completed_ids)} new={newly} fail={failures} "
                      f"| {time.time() - t0:.0f}s", flush=True)
    finally:
        of.close(); mf.close()

    summary = {
        "total_candidates": len(candidates),
        "completed": len(completed_ids),
        "resumed_skipped": resumed,
        "newly_classified": newly,
        "api_failures": failures,
        "remaining": max(0, len(candidates) - len(completed_ids)),
        "runtime_seconds": round(time.time() - t0, 1),
        "out_path": str(out_path),
        "malformed_path": str(malformed_path),
    }
    write_json(summary_path, summary)
    return valid_records, summary


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def discover_counterevidence(
    ctx: Any,
    resolution_records: list[ResolutionRecord],
    graph: nx.MultiDiGraph,
    gaps: list[CandidateGap],
    *,
    llm_base_url: str | None = None,
    max_candidates_per_gap: int = 20,
    min_candidate_score: float = 0.20,
    classifier_min_confidence: float = 0.70,
    create_edges_for: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Discover in-corpus counterevidence for gaps.

    Args:
        ctx: RunContext
        resolution_records: From extract_resolution_records()
        graph: Knowledge graph (will be modified in-place with new edges)
        gaps: Candidate gaps from detect_gaps()
        llm_base_url: Override LLM base URL
        max_candidates_per_gap: Cap candidates per gap before LLM classification
        min_candidate_score: Minimum score to consider a candidate
        classifier_min_confidence: Minimum classifier confidence to create edge
        create_edges_for: Set of classifier labels to create edges for (default: all 4 main types)

    Returns:
        (candidates_classified_dicts, counterevidence_edges_metadata)
    """
    if create_edges_for is None:
        create_edges_for = {"fully_addresses", "partially_addresses", "relaxes_assumption", "handles_failure_condition"}

    out_dir = ctx.path("counterevidence_discovery")
    ensure_dir(out_dir)
    edges_jsonl = out_dir / "counterevidence_edges.jsonl"
    candidates_jsonl = out_dir / "candidates.jsonl"

    llm = LLMClient(ctx, base_url=llm_base_url)
    anchor_terms = _build_anchor_terms(graph)

    # Build gap node set: collect nodes of counterevidence-relevant types
    gap_nodes: list[tuple[str, str, str, set[str]]] = []  # (node_id, label, type, paper_ids)

    # From graph nodes directly
    for node_id, ndata in graph.nodes(data=True):
        ntype = str(ndata.get("type", ""))
        if ntype in _COUNTEREVIDENCE_NODE_TYPES:
            label = str(ndata.get("label", node_id))
            paper_ids = set(ndata.get("paper_ids", []))
            gap_nodes.append((node_id, label, ntype, paper_ids))

    # Also from CandidateGap objects (they may have motif-specific gap labels)
    gap_id_to_gap = {g.gap_id: g for g in gaps}
    gap_node_ids_from_gaps: set[str] = set()
    for g in gaps:
        # Try to find matching Gap node in graph
        for node_id, ndata in graph.nodes(data=True):
            if ndata.get("type") == "Gap" and (
                node_id == g.gap_id
                or str(ndata.get("label", "")).lower() == g.gap.lower()[:80]
            ):
                gap_node_ids_from_gaps.add(node_id)
                break
        # If no matching graph node, add virtual entry from CandidateGap
        virtual_id = g.gap_id
        if not any(nid == virtual_id for nid, *_ in gap_nodes):
            gap_nodes.append((virtual_id, g.gap[:120], "motif_gap", set(g.paper_ids)))

    print(f"[counterevidence_linking] {len(gap_nodes)} gap nodes, {len(resolution_records)} resolution records", flush=True)

    # ---------------------------------------------------------------------------
    # Candidate generation (deterministic)
    # ---------------------------------------------------------------------------
    all_candidates: list[CounterevidenceCandidate] = []
    candidates_per_gap: dict[str, list[tuple[float, CounterevidenceCandidate]]] = {}

    for node_id, label, ntype, paper_ids in gap_nodes:
        ev_texts = _get_gap_evidence_texts(graph, node_id)
        # Also include gap label in evidence tokens
        ev_all = label + " " + " ".join(ev_texts[:5])
        gap_ev_tokens = _tokenize(ev_all)

        scored: list[tuple[float, CounterevidenceCandidate]] = []
        for record in resolution_records:
            score, reason = _score_candidate(
                node_id, label, ntype, paper_ids, gap_ev_tokens,
                record, graph, anchor_terms,
            )
            if score < min_candidate_score:
                continue

            cid = stable_id("ce", node_id, record.record_id)
            cand = CounterevidenceCandidate(
                candidate_id=cid,
                gap_node_id=node_id,
                gap_node_label=label,
                gap_type=ntype,
                resolution_record_id=record.record_id,
                resolution_method=record.method,
                target_problem=record.target_problem,
                addressed_condition=record.addressed_condition,
                paper_id=record.paper_id,
                candidate_reason=reason,
                candidate_score=score,
                evidence_text=record.evidence_text,
            )
            scored.append((score, cand))

        # Sort by score desc, cap
        scored.sort(key=lambda x: -x[0])
        scored = scored[:max_candidates_per_gap]
        candidates_per_gap[node_id] = scored
        for _, c in scored:
            all_candidates.append(c)
            append_jsonl(candidates_jsonl, model_dump(c))

    print(f"[counterevidence_linking] {len(all_candidates)} total candidates generated", flush=True)

    # ---------------------------------------------------------------------------
    # LLM semantic classifier
    # ---------------------------------------------------------------------------
    # Configurable minimum candidate score before the LLM is invoked. Default 0.35,
    # overridable via counterevidence_linking.classifier_candidate_min_score so that
    # cross-terminology links (e.g. uniINF→sub-Gaussian, score ~0.31) can be reached.
    _ce_cfg = ctx.config.get("counterevidence_linking", {}) if hasattr(ctx, "config") else {}
    LLM_SCORE_THRESHOLD = float(_ce_cfg.get("classifier_candidate_min_score", 0.35))
    classified_dicts: list[dict[str, Any]] = []
    counterevidence_edges: list[dict[str, Any]] = []

    for candidate in all_candidates:
        cdict = model_dump(candidate)
        if candidate.candidate_score < LLM_SCORE_THRESHOLD:
            cdict["classifier_label"] = "skipped_low_score"
            cdict["classifier_confidence"] = 0.0
            classified_dicts.append(cdict)
            continue

        result = _classify_candidate(candidate, graph, llm)
        if result is None:
            cdict["classifier_label"] = "error"
            cdict["classifier_confidence"] = 0.0
            classified_dicts.append(cdict)
            continue

        cdict["classifier_label"] = result.label
        cdict["classifier_confidence"] = result.confidence
        cdict["scope_match"] = result.scope_match
        cdict["why"] = result.why
        cdict["remaining_gap_scope"] = result.remaining_gap_scope
        cdict["should_create_counterevidence_edge"] = result.should_create_counterevidence_edge
        classified_dicts.append(cdict)

        # Create edge if classifier approves and confidence sufficient
        if (
            result.should_create_counterevidence_edge
            and result.label in create_edges_for
            and result.confidence >= classifier_min_confidence
        ):
            edge_type = _LABEL_TO_EDGE_TYPE.get(result.label, "counterevidence_for")
            edge_meta = {
                "relation": edge_type,
                "source_paper": candidate.paper_id,
                "resolution_method": candidate.resolution_method,
                "record_id": candidate.resolution_record_id,
                "classifier_label": result.label,
                "classifier_confidence": result.confidence,
                "scope_match": result.scope_match,
                "remaining_gap_scope": result.remaining_gap_scope,
                "evidence_text": candidate.evidence_text[:300],
                "rationale": result.why[:300],
                "timestamp": utc_now_iso(),
            }
            # Add paper node for resolution paper if not already in graph
            paper_node_id = f"paper:{candidate.paper_id}"
            if paper_node_id not in graph.nodes:
                graph.add_node(paper_node_id, type="Paper", label=candidate.paper_id, paper_ids=[candidate.paper_id])

            # Add edge: resolution paper → gap node
            gap_node_id = candidate.gap_node_id
            # If gap node is a virtual motif gap ID, we may need to add it
            if gap_node_id not in graph.nodes:
                graph.add_node(
                    gap_node_id,
                    type="Gap",
                    label=candidate.gap_node_label,
                    paper_ids=list(set()),
                )

            edge_key = stable_id("cedge", paper_node_id, gap_node_id, result.label)
            graph.add_edge(paper_node_id, gap_node_id, key=edge_key, **edge_meta)

            edge_record = {
                "edge_key": edge_key,
                "source": paper_node_id,
                "target": gap_node_id,
                **edge_meta,
            }
            counterevidence_edges.append(edge_record)
            append_jsonl(edges_jsonl, edge_record)

    print(
        f"[counterevidence_linking] {len(counterevidence_edges)} counterevidence edges created",
        flush=True,
    )
    return classified_dicts, counterevidence_edges
