from __future__ import annotations

from typing import Any

from .gap_objects import CandidateGap, VerificationResult
from .utils import bounded

# Weights for deterministic sub-score aggregation into per-agent confidence
_SUB_SCORE_WEIGHTS = {
    "evidence_support": 0.30,
    "novelty": 0.20,
    "feasibility": 0.20,
    "specificity": 0.15,
    "scope_validity": 0.15,
}


def aggregate_verification_confidence(result: VerificationResult) -> float:
    """Compute deterministic confidence from sub-scores. Falls back to result.confidence if no sub-scores."""
    scores = result.scores
    if not scores:
        return bounded(result.confidence)
    total = 0.0
    weight_sum = 0.0
    for key, w in _SUB_SCORE_WEIGHTS.items():
        if key in scores:
            total += w * bounded(scores[key])
            weight_sum += w
    if weight_sum < 0.1:
        return bounded(result.confidence)
    # Normalize if not all sub-scores present, then blend with raw confidence
    computed = total / weight_sum
    if result.confidence > 0.0:
        return bounded(0.7 * computed + 0.3 * result.confidence)
    return bounded(computed)


def compute_gap_survival_score(gap: CandidateGap, results: list[VerificationResult], weights: dict[str, float]) -> dict[str, float]:
    score_map = {
        "evidence_diversity": _evidence_diversity(gap, results),
        "failure_recurrence": min(1.0, len(gap.paper_ids) / 3.0),
        "novelty_after_counterevidence": 1.0 - _agent_score(results, "skeptic_agent", "already_solved_score", default=0.2),
        "experimentability": _agent_score(results, "feasibility_agent", "experimentability", default=gap.feasibility_score),
        "mechanism_plausibility": _agent_score(results, "mechanism_agent", "mechanism_plausibility", default=0.5),
        "traceability": min(1.0, len(gap.traceability_path) / 4.0),
        "already_solved_score": _agent_score(results, "skeptic_agent", "already_solved_score", default=0.0),
        "extraction_uncertainty": gap.extraction_uncertainty,
    }
    total = 0.0
    for key, value in score_map.items():
        total += float(weights.get(key, 0.0)) * value
    score_map["gap_survival_score"] = bounded(total)
    return score_map


def candidate_overall(novelty: float, feasibility: float, impact: float, motif_score: float = 0.5) -> float:
    return bounded(0.30 * novelty + 0.25 * feasibility + 0.30 * impact + 0.15 * motif_score)


def _evidence_diversity(gap: CandidateGap, results: list[VerificationResult]) -> float:
    papers = set(gap.paper_ids)
    for result in results:
        papers.update(result.citations)
        for ev in result.evidence:
            if ev.get("paper_id"):
                papers.add(str(ev["paper_id"]))
    return min(1.0, len(papers) / 3.0)


def _agent_score(results: list[VerificationResult], agent: str, key: str, default: float = 0.5) -> float:
    vals = [r.scores.get(key) for r in results if r.agent_name == agent and key in r.scores]
    vals = [float(v) for v in vals if v is not None]
    if not vals:
        return bounded(default)
    return bounded(sum(vals) / len(vals))
