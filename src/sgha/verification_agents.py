from __future__ import annotations

from typing import Any

from .gap_detection import load_candidate_gaps
from .gap_objects import CandidateGap, VerificationResult
from .llm_client import LLMClient
from .pdf_parser import load_parsed_manifest
from .prompt_templates import verification_prompt
from .scoring import aggregate_verification_confidence, compute_gap_survival_score
from .utils import append_jsonl, model_dump, model_validate, read_text, stable_id, utc_now_iso, write_csv, write_json


AGENTS = ["support_agent", "skeptic_agent", "feasibility_agent", "mechanism_agent", "critic"]


def _select_diverse_gaps(all_gaps: list[CandidateGap], top_k: int) -> list[CandidateGap]:
    """Select top_k gaps distributed across motif types.

    Within each motif type, prefer gaps with more supporting papers (stronger cross-paper
    signal) since overall_score defaults are equal across gaps. Allocates slots
    proportionally: each motif type gets at least 1 slot, remainder goes to motif types
    with the most gaps.
    """
    import math
    from collections import defaultdict

    if not all_gaps:
        return []

    by_motif: dict[str, list[CandidateGap]] = defaultdict(list)
    for g in all_gaps:
        by_motif[g.motif_type].append(g)

    # Sort each bucket by paper count desc, then overall_score desc
    for bucket in by_motif.values():
        bucket.sort(key=lambda g: (len(g.paper_ids), g.overall_score), reverse=True)

    motifs = sorted(by_motif.keys(), key=lambda m: len(by_motif[m]), reverse=True)
    n_motifs = len(motifs)

    if n_motifs == 0:
        return all_gaps[:top_k]

    # Give each motif at least 1 slot, distribute remainder to largest motifs
    base = max(1, top_k // n_motifs)
    slots: dict[str, int] = {m: base for m in motifs}
    remainder = top_k - base * n_motifs
    for m in motifs[:remainder]:
        slots[m] += 1

    selected: list[CandidateGap] = []
    for m in motifs:
        selected.extend(by_motif[m][: slots[m]])

    return selected[:top_k]

_REPAIR_PROMPT = """The previous response was invalid JSON. Return ONLY valid JSON with these keys:
gap_id, agent_name, summary, evidence, counterevidence, citations, confidence, failure_modes, scores.

confidence must be a float between 0.0 and 1.0.
scores must be a dict with keys: evidence_support, novelty, feasibility, specificity, scope_validity (all floats 0.0-1.0).

Gap ID: {gap_id}
Agent: {agent_name}
"""


def verify_gaps(ctx: Any, *, llm_base_url: str | None = None, mock_llm: bool | None = None, skeptic_external_arxiv: bool | None = None) -> dict[str, Any]:
    ctx.stage_start("verify_gaps")
    all_gaps = load_candidate_gaps(ctx)
    llm = LLMClient(ctx, base_url=llm_base_url, mock=mock_llm)
    parsed = load_parsed_manifest(ctx)
    text_by_paper = {p.paper_id: read_text(p.text_path) for p in parsed}

    # Respect top_k_to_verify from topic profile or pipeline config
    top_k = int(ctx.config.get("verification", {}).get("top_k_to_verify", 10))
    gaps = _select_diverse_gaps(all_gaps, top_k)
    if not gaps and all_gaps:
        gaps = all_gaps[:top_k]

    all_results: dict[str, list[VerificationResult]] = {}
    score_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for gap in gaps:
        gap_results: list[VerificationResult] = []
        evidence = retrieve_local_evidence(gap, text_by_paper, top_k=int(ctx.config.get("verification", {}).get("retrieval_top_k", 6)))
        parse_failures = 0
        for agent in AGENTS:
            prompt = verification_prompt(agent, model_dump(gap), evidence)
            result = _run_agent_with_retry(llm, ctx, gap, agent, prompt)
            if result is None:
                # All retries failed — create a minimal result without zeroing confidence
                parse_failures += 1
                result = VerificationResult(
                    gap_id=gap.gap_id,
                    agent_name=agent,  # type: ignore[arg-type]
                    summary=f"agent failed after retries",
                    confidence=0.0,
                    failure_modes=[f"parse_failure_after_retry"],
                )
                ctx.audit.failure("verify_gaps", RuntimeError("parse_failure"), gap_id=gap.gap_id, agent_name=agent)
            else:
                # Overwrite with deterministic sub-score aggregation
                computed = aggregate_verification_confidence(result)
                if computed > 0.0:
                    result.confidence = computed
            gap_results.append(result)
            append_jsonl(ctx.path("verification", f"{agent}_results.jsonl"), model_dump(result))
        all_results[gap.gap_id] = gap_results
        weights = ctx.config.get("verification", {}).get("survival_weights", {})
        scores = compute_gap_survival_score(gap, gap_results, weights)
        score_rows.append({"gap_id": gap.gap_id, **scores})
        confidences = [r.confidence for r in gap_results if r.confidence > 0.0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        summary_rows.append({
            "gap_id": gap.gap_id,
            "gap": gap.gap[:100],
            "agents_run": len(gap_results),
            "parse_failures": parse_failures,
            "avg_confidence": round(avg_conf, 3),
            "gap_survival_score": round(scores.get("gap_survival_score", 0.0), 3),
        })

    write_csv(ctx.path("verification", "gap_survival_scores.csv"), score_rows)
    write_json(ctx.path("verification", "verification_summary.json"), {gid: [model_dump(r) for r in rows] for gid, rows in all_results.items()})
    write_csv(ctx.path("verification", "verification_results_summary.csv"), summary_rows)
    _write_verification_report(ctx, summary_rows, score_rows, len(all_gaps), top_k)
    ctx.stage_end("verify_gaps", gaps_verified=len(gaps), total_gaps=len(all_gaps), agent_results=sum(len(v) for v in all_results.values()))
    return {"results": all_results, "scores": score_rows}


def _run_agent_with_retry(llm: LLMClient, ctx: Any, gap: CandidateGap, agent: str, prompt: str) -> VerificationResult | None:
    """Run one verification agent with one retry using a repair prompt on parse failure."""
    for attempt in range(2):
        try:
            use_prompt = prompt if attempt == 0 else _REPAIR_PROMPT.format(gap_id=gap.gap_id, agent_name=agent) + "\n\nOriginal gap:\n" + gap.gap
            data, _, _, _ = llm.complete_json(
                stage="verification" if agent != "critic" else "critic",
                agent_name=agent,
                prompt=use_prompt,
                schema_name="VerificationResult",
            )
            data["gap_id"] = gap.gap_id
            data["agent_name"] = agent
            result = model_validate(VerificationResult, data)
            return result
        except Exception:
            if attempt == 1:
                return None
    return None


def retrieve_local_evidence(gap: CandidateGap, text_by_paper: dict[str, str], top_k: int = 6) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in gap.supporting_evidence[:top_k]:
        out.append(ev)
    for paper_id in gap.paper_ids:
        if len(out) >= top_k:
            break
        text = text_by_paper.get(paper_id, "")
        if not text:
            continue
        snippet = _best_snippet(text, [gap.target, gap.gap])
        out.append({"paper_id": paper_id, "evidence_text": snippet, "source": "local_text_retrieval"})
    return out[:top_k]


def _best_snippet(text: str, terms: list[str], window: int = 600) -> str:
    lowered = text.lower()
    positions = [lowered.find(term.lower()[:60]) for term in terms if term]
    positions = [p for p in positions if p >= 0]
    start = max(0, min(positions) - window // 2) if positions else 0
    return text[start : start + window].replace("\n", " ")


def _write_verification_report(ctx: Any, summary_rows: list[dict], score_rows: list[dict], total_gaps: int, top_k: int) -> None:
    lines = [
        "# Verification Summary\n",
        f"- Total candidate gaps: {total_gaps}",
        f"- Gaps selected for verification (top_k): {top_k}",
        f"- Gaps actually verified: {len(summary_rows)}",
        f"- Agents per gap: {len(AGENTS)}",
        "",
        "## Results per Gap",
        "",
        "| gap_id | gap (truncated) | parse_failures | avg_confidence | survival_score |",
        "|--------|----------------|----------------|----------------|----------------|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['gap_id'][:12]} | {row['gap'][:50]} | {row['parse_failures']} | {row['avg_confidence']:.3f} | {row['gap_survival_score']:.3f} |"
        )
    if summary_rows:
        avg_conf = sum(r["avg_confidence"] for r in summary_rows) / len(summary_rows)
        avg_surv = sum(r["gap_survival_score"] for r in summary_rows) / len(summary_rows)
        lines += ["", f"**Average confidence across verified gaps: {avg_conf:.3f}**", f"**Average survival score: {avg_surv:.3f}**"]
    report_path = ctx.path("verification", "verification_summary.md")
    from .utils import write_text
    write_text(report_path, "\n".join(lines))
