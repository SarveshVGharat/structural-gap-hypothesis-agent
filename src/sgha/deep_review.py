"""Final hypothesis deep-review stage: critically evaluate evolved hypotheses for
genuine scientific usefulness, reject weak ones, rerank, and only emit a top-20 if at
least 10 acceptable hypotheses survive. Read-only w.r.t. upstream pipeline stages."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .gap_objects import HypothesisDeepReview, _ACCEPTABLE_REVIEW_LABELS
from .prompt_templates import deep_review_prompt
from .utils import ensure_dir

_IMPOSSIBILITY_KEYWORDS = [
    "impossible", "impossibility", "lower bound", "cannot achieve", "no algorithm can",
    "minimax lower bound", "ω(", "omega(", "intractable", "np-hard", "exponential lower bound",
    "rules out", "unavoidable",
]

_HARD_DROP = {
    "DROP_IMPOSSIBLE", "DROP_ALREADY_SOLVED", "DROP_OFF_DOMAIN", "DROP_DUPLICATE",
}


def _evidence_text_blob(cand: dict) -> str:
    parts = []
    for ev in cand.get("supporting_evidence", [])[:8]:
        if isinstance(ev, dict):
            parts.append(str(ev.get("evidence_text", "")))
    for ev in cand.get("counterevidence", [])[:8]:
        if isinstance(ev, dict):
            parts.append(str(ev.get("evidence_text", "") or ev.get("rationale", "")))
    parts.append(str(cand.get("remaining_gap_scope", "")))
    return " ".join(parts).lower()


def detect_impossibility(cand: dict) -> float:
    """Heuristic impossibility risk from evidence text keywords (0..1)."""
    blob = _evidence_text_blob(cand)
    hits = sum(1 for kw in _IMPOSSIBILITY_KEYWORDS if kw in blob)
    if hits >= 2:
        return 1.0
    if hits == 1:
        return 0.7
    return 0.0


def _build_payload(cand: dict) -> dict:
    return {
        "problem_statement": cand.get("problem_statement", ""),
        "origin_motif_types": cand.get("origin_motif_types", []),
        "original_gap_description": cand.get("original_gap_description", "") or cand.get("gap", ""),
        "downstream_gap_description": cand.get("downstream_gap_description", ""),
        "counterevidence_status": cand.get("counterevidence_status", ""),
        "remaining_gap_scope": cand.get("remaining_gap_scope", ""),
        "supporting_papers": cand.get("supporting_papers", []) or sorted(
            {ev.get("paper_id") for ev in cand.get("supporting_evidence", []) if isinstance(ev, dict) and ev.get("paper_id")}
        ),
        "supporting_evidence_snippets": [
            ev.get("evidence_text", "") for ev in cand.get("supporting_evidence", [])[:6] if isinstance(ev, dict)
        ],
        "counterevidence_papers": cand.get("counterevidence_papers", []),
        "counterevidence_snippets": [
            (ev.get("evidence_text", "") or ev.get("rationale", "")) for ev in cand.get("counterevidence", [])[:6] if isinstance(ev, dict)
        ],
        "traceability_path_len": len(cand.get("traceability_path", [])),
        "operator_type": cand.get("operator_type", ""),
        "n_supporting_papers": len(cand.get("supporting_papers", []) or []),
    }


def review_candidate(cand: dict, llm: Any) -> HypothesisDeepReview:
    """Run the deep-review LLM on one candidate; merge heuristic impossibility signal."""
    payload = _build_payload(cand)
    hid = cand.get("hypothesis_id") or cand.get("candidate_id", "?")
    imposs_heur = detect_impossibility(cand)

    raw: dict = {}
    try:
        raw, _, _, _ = llm.complete_json(
            stage="evolve", agent_name="hypothesis_deep_reviewer",
            prompt=deep_review_prompt(payload), schema_name="HypothesisDeepReview",
        )
    except Exception as exc:
        raw = {"review_label": "WEAK_AFTER_READING", "main_reason": f"review error: {exc}"}

    def _f(k, d=0.0):
        try:
            return max(0.0, min(1.0, float(raw.get(k, d))))
        except (TypeError, ValueError):
            return d

    label = str(raw.get("review_label", "WEAK_AFTER_READING")).strip().upper().replace(" ", "_")
    imposs = max(imposs_heur, _f("impossibility_risk"))
    # Hard override: strong impossibility evidence forces DROP_IMPOSSIBLE
    if imposs >= 1.0 and label in _ACCEPTABLE_REVIEW_LABELS:
        label = "DROP_IMPOSSIBLE"

    # Single-paper fragility override
    n_sup = payload["n_supporting_papers"]
    if n_sup <= 1 and _f("evidence_strength") < 0.4 and label in _ACCEPTABLE_REVIEW_LABELS:
        label = "DROP_TOO_SINGLE_PAPER_FRAGILE"

    return HypothesisDeepReview(
        hypothesis_id=hid,
        original_rank=int(cand.get("rank", 0) or 0),
        problem_statement=cand.get("problem_statement", ""),
        review_label=label,
        deep_review_score=_f("deep_review_score"),
        evidence_strength=_f("evidence_strength"),
        remaining_gap_realness=_f("remaining_gap_realness"),
        counterevidence_risk=_f("counterevidence_risk"),
        impossibility_risk=imposs,
        already_solved_risk=_f("already_solved_risk"),
        specificity=_f("specificity"),
        feasibility=_f("feasibility"),
        project_concreteness=_f("project_concreteness"),
        novelty_risk=str(raw.get("novelty_risk", "medium")).lower(),
        main_reason=str(raw.get("main_reason", "")),
        falsification_condition=str(raw.get("falsification_condition", "")),
        clean_rewrite=str(raw.get("clean_rewrite", "")),
        recommended_next_step=str(raw.get("recommended_next_step", "")),
        supporting_evidence_summary="; ".join(payload["supporting_evidence_snippets"][:3]),
        counterevidence_summary="; ".join(payload["counterevidence_snippets"][:3]),
        remaining_gap_scope=cand.get("remaining_gap_scope", ""),
        origin_signature=cand.get("origin_signature", ""),
        primary_origin_signature=cand.get("primary_origin_signature", ""),
        root_origin_signatures=cand.get("root_origin_signatures", []),
        origin_motif_types=cand.get("origin_motif_types", []),
        counterevidence_status=cand.get("counterevidence_status", ""),
        supporting_papers=payload["supporting_papers"],
        counterevidence_papers=cand.get("counterevidence_papers", []),
        fitness=float(cand.get("fitness", 0.0) or 0.0),
    )


def _semantic_key(r: HypothesisDeepReview) -> str:
    sw = {"problem", "designing", "bandit", "bandits", "regret", "robust", "sublinear",
          "bounds", "despite", "achieve", "achieves", "algorithm", "algorithms"}
    toks = sorted(w for w in re.findall(r"[a-z]{5,}", r.problem_statement.lower()) if w not in sw)[:6]
    return "|".join(toks)


def select_reviewed_final(
    reviews: list[HypothesisDeepReview],
    limit: int = 20,
    *,
    max_per_primary: int = 2,
    max_theme_frac: float = 0.40,
) -> tuple[list[HypothesisDeepReview], str]:
    """Hard-filter, then rerank acceptable reviews with diversity caps.

    Returns (selected, status) where status is REVIEWED_REPORT_READY or
    INSUFFICIENT_MEANINGFUL_HYPOTHESES.
    """
    acceptable = [
        r for r in reviews
        if r.is_acceptable()
        and r.review_label not in _HARD_DROP
        and r.counterevidence_status != "known_solved_in_corpus"
        and r.supporting_papers
    ]
    acceptable.sort(
        key=lambda r: (r.deep_review_score, r.evidence_strength, r.remaining_gap_realness,
                       r.project_concreteness, r.feasibility),
        reverse=True,
    )

    selected: list[HypothesisDeepReview] = []
    prim_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}
    seen_sigs: set[str] = set()
    theme_cap = max(1, int(limit * max_theme_frac))

    for r in acceptable:
        if len(selected) >= limit:
            break
        if r.origin_signature and r.origin_signature in seen_sigs:
            continue  # no duplicate origin signature
        prim = r.primary_origin_signature or r.origin_signature
        if prim_counts.get(prim, 0) >= max_per_primary:
            continue
        tk = _semantic_key(r)
        if theme_counts.get(tk, 0) >= theme_cap:
            continue
        selected.append(r)
        seen_sigs.add(r.origin_signature)
        prim_counts[prim] = prim_counts.get(prim, 0) + 1
        theme_counts[tk] = theme_counts.get(tk, 0) + 1

    status = "REVIEWED_REPORT_READY" if len(selected) >= 10 else "INSUFFICIENT_MEANINGFUL_HYPOTHESES"
    return selected, status


def load_candidate_archive(run_dir: Path) -> list[dict]:
    """Union of all generation populations (deduped by candidate_id), enriched with the
    final hypotheses' evidence where ids overlap."""
    archive: dict[str, dict] = {}
    for g in sorted((run_dir / "evolution").glob("generation_*.json")):
        data = json.load(open(g))
        pop = data.get("population", data) if isinstance(data, dict) else data
        for c in pop:
            cid = c.get("candidate_id")
            if cid:
                archive[cid] = c
    return list(archive.values())
