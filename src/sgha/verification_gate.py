"""Deterministic verification pass/fail gate over existing verification artifacts."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .utils import ensure_dir

AGENTS = ["support_agent", "skeptic_agent", "feasibility_agent", "mechanism_agent", "critic"]
MODE_SURVIVAL_SCORE = "survival_score"
MODE_CRITIC_LABEL = "critic_label"
MODE_REVIEWED_ONLY = "reviewed_only"
ALLOWED_MODES = {MODE_SURVIVAL_SCORE, MODE_CRITIC_LABEL, MODE_REVIEWED_ONLY}

DEFAULT_GATE_CONFIG: dict[str, Any] = {
    "enabled": True,
    "mode": MODE_SURVIVAL_SCORE,
    "min_survival_score": 0.60,
    "require_all_agents": True,
    "require_critic_non_reject": True,
    "min_critic_confidence": 0.50,
    "fail_on_agent_parse_failure": True,
    "allow_reviewed_only_fallback": False,
}

_REJECT_LABELS = {
    "DROP",
    "REJECT",
    "REJECTED",
    "UNSUPPORTED",
    "DROP_GENERIC",
    "DROP_ALREADY_SOLVED",
    "DROP_IMPOSSIBLE",
    "DROP_ARTIFICIAL_SCOPE",
    "DROP_OFF_DOMAIN",
    "DROP_DUPLICATE",
    "DROP_TOO_SINGLE_PAPER_FRAGILE",
}


class VerificationGateError(RuntimeError):
    """Raised when verification artifacts cannot support the configured gate."""


@dataclass
class VerificationGateAssessment:
    config: dict[str, Any]
    source: str
    reviewed_ids: set[str] = field(default_factory=set)
    passed_ids: set[str] = field(default_factory=set)
    failed_ids: set[str] = field(default_factory=set)
    agent_presence: dict[str, set[str]] = field(default_factory=dict)
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    survival_scores: dict[str, float] = field(default_factory=dict)
    warning: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "verification_gate_enabled": bool(self.config.get("enabled", True)),
            "verification_gate_mode": self.config.get("mode", MODE_SURVIVAL_SCORE),
            "verification_gate_threshold": self.config.get("min_survival_score"),
            "verification_gate_require_all_agents": bool(self.config.get("require_all_agents", True)),
            "verification_gate_require_critic_non_reject": bool(self.config.get("require_critic_non_reject", True)),
            "verification_gate_min_critic_confidence": self.config.get("min_critic_confidence"),
            "verification_gate_fail_on_agent_parse_failure": bool(self.config.get("fail_on_agent_parse_failure", True)),
            "verification_gate_allow_reviewed_only_fallback": bool(self.config.get("allow_reviewed_only_fallback", False)),
            "verification_gate_source": self.source,
            "verification_gate_warning": self.warning,
            "verification_reviewed_count": len(self.reviewed_ids),
            "verification_passed_count": len(self.passed_ids),
            "verification_failed_count": len(self.failed_ids),
        }


def resolve_gate_config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(DEFAULT_GATE_CONFIG)
    if config:
        cfg.update(config)
    mode = str(cfg.get("mode", MODE_SURVIVAL_SCORE)).strip()
    if mode not in ALLOWED_MODES:
        raise VerificationGateError(f"verification_gate.mode must be one of {sorted(ALLOWED_MODES)}; got {mode!r}")
    cfg["mode"] = mode
    cfg["enabled"] = _as_bool(cfg.get("enabled", True))
    cfg["require_all_agents"] = _as_bool(cfg.get("require_all_agents", True))
    cfg["require_critic_non_reject"] = _as_bool(cfg.get("require_critic_non_reject", True))
    cfg["allow_reviewed_only_fallback"] = _as_bool(cfg.get("allow_reviewed_only_fallback", False))
    cfg["fail_on_agent_parse_failure"] = _as_bool(cfg.get("fail_on_agent_parse_failure", True))
    cfg["min_survival_score"] = _as_float(cfg.get("min_survival_score", 0.60), 0.60)
    cfg["min_critic_confidence"] = _as_float(cfg.get("min_critic_confidence", 0.50), 0.50)
    return cfg


def assess_verification_gate(run_dir: Path, config: dict[str, Any] | None = None, *, require_outputs: bool = True) -> VerificationGateAssessment:
    """Load existing verification artifacts and classify reviewed/passed/failed gaps."""
    gate_cfg = resolve_gate_config(config)
    verification_dir = run_dir / "verification"
    rows_by_gap, source = _load_agent_rows(verification_dir)
    survival_scores = _load_survival_scores(verification_dir / "gap_survival_scores.csv")
    summary_rows = _load_results_summary(verification_dir / "verification_results_summary.csv")

    if not rows_by_gap and require_outputs:
        raise VerificationGateError("NEEDS_VERIFICATION_OUTPUTS: no verification_summary.json or per-agent verification results found")

    agent_presence = {gid: set(rows) for gid, rows in rows_by_gap.items()}
    required_agents = set(AGENTS) if gate_cfg["require_all_agents"] else set()
    if gate_cfg["require_all_agents"]:
        reviewed = {gid for gid, agents in agent_presence.items() if required_agents <= agents}
    else:
        reviewed = set(agent_presence)

    if gate_cfg["mode"] == MODE_SURVIVAL_SCORE and reviewed:
        missing_scores = sorted(gid for gid in reviewed if gid not in survival_scores)
        if missing_scores:
            if gate_cfg["allow_reviewed_only_fallback"]:
                gate_cfg["mode"] = MODE_REVIEWED_ONLY
            else:
                raise VerificationGateError(
                    "verification_gate.mode=survival_score requires gap_survival_scores.csv rows for every reviewed gap; "
                    f"missing {len(missing_scores)} score(s)"
                )

    assessment = VerificationGateAssessment(
        config=gate_cfg,
        source=source,
        reviewed_ids=set(reviewed),
        agent_presence=agent_presence,
        survival_scores=survival_scores,
    )

    if not gate_cfg["enabled"] or gate_cfg["mode"] == MODE_REVIEWED_ONLY:
        assessment.warning = "reviewed_only_mode: Stage 7 may consume verification-reviewed gaps, not verification-passed gaps"
        for gid in sorted(reviewed):
            assessment.decisions[gid] = _decision(
                gid,
                "reviewed_only",
                rows_by_gap,
                survival_scores,
                summary_rows,
                gate_cfg,
                passed=False,
                reasons=["reviewed_only_mode_no_pass_gate"],
            )
        return assessment

    passed: set[str] = set()
    failed: set[str] = set()
    for gid in sorted(reviewed):
        reasons = _failure_reasons(gid, rows_by_gap, survival_scores, summary_rows, gate_cfg)
        if reasons:
            failed.add(gid)
        else:
            passed.add(gid)
        assessment.decisions[gid] = _decision(
            gid,
            gate_cfg["mode"],
            rows_by_gap,
            survival_scores,
            summary_rows,
            gate_cfg,
            passed=not reasons,
            reasons=reasons,
        )
    assessment.passed_ids = passed
    assessment.failed_ids = failed
    return assessment


def write_verification_gate_artifacts(run_dir: Path, assessment: VerificationGateAssessment) -> dict[str, str]:
    out = run_dir / "verification" / "verification_gate"
    ensure_dir(out)
    decisions = [assessment.decisions[gid] for gid in sorted(assessment.decisions)]
    (out / "verification_gate_decisions.json").write_text(json.dumps({
        "summary": assessment.summary(),
        "decisions": decisions,
    }, indent=2) + "\n")
    with (out / "verification_gate_decisions.csv").open("w", newline="") as fh:
        fields = [
            "gap_id", "gate_mode", "reviewed", "passed", "survival_score", "critic_confidence",
            "agents_present", "parse_failure_count", "failure_reasons",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in decisions:
            writer.writerow({
                "gap_id": row["gap_id"],
                "gate_mode": row["gate_mode"],
                "reviewed": row["reviewed"],
                "passed": row["passed"],
                "survival_score": row.get("survival_score"),
                "critic_confidence": row.get("critic_confidence"),
                "agents_present": ";".join(row.get("agents_present", [])),
                "parse_failure_count": row.get("parse_failure_count", 0),
                "failure_reasons": ";".join(row.get("failure_reasons", [])),
            })
    return {
        "verification_gate_decisions_json": str(out / "verification_gate_decisions.json"),
        "verification_gate_decisions_csv": str(out / "verification_gate_decisions.csv"),
    }


def _failure_reasons(
    gid: str,
    rows_by_gap: dict[str, dict[str, dict[str, Any]]],
    survival_scores: dict[str, float],
    summary_rows: dict[str, dict[str, Any]],
    gate_cfg: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    rows = rows_by_gap.get(gid, {})
    if gate_cfg["require_all_agents"]:
        missing = sorted(set(AGENTS) - set(rows))
        if missing:
            reasons.append("missing_required_agents:" + ",".join(missing))
    if gate_cfg["fail_on_agent_parse_failure"]:
        parse_failures = _parse_failure_count(gid, rows, summary_rows)
        if parse_failures > 0:
            reasons.append(f"agent_parse_failures:{parse_failures}")
    if gate_cfg["mode"] == MODE_SURVIVAL_SCORE:
        score = survival_scores.get(gid)
        if score is None:
            reasons.append("missing_survival_score")
        elif score < float(gate_cfg["min_survival_score"]):
            reasons.append(f"survival_score_below_threshold:{score:.3f}<" + f"{float(gate_cfg['min_survival_score']):.3f}")
    if gate_cfg["require_critic_non_reject"] and not _critic_non_reject(rows.get("critic"), gate_cfg):
        reasons.append("critic_reject_or_low_confidence")
    if gate_cfg["mode"] == MODE_CRITIC_LABEL and not _critic_non_reject(rows.get("critic"), gate_cfg):
        reasons.append("critic_label_gate_failed")
    return reasons


def _decision(
    gid: str,
    mode: str,
    rows_by_gap: dict[str, dict[str, dict[str, Any]]],
    survival_scores: dict[str, float],
    summary_rows: dict[str, dict[str, Any]],
    gate_cfg: dict[str, Any],
    *,
    passed: bool,
    reasons: list[str],
) -> dict[str, Any]:
    rows = rows_by_gap.get(gid, {})
    critic = rows.get("critic") or {}
    return {
        "gap_id": gid,
        "gate_mode": mode,
        "reviewed": bool(rows),
        "passed": bool(passed),
        "survival_score": survival_scores.get(gid),
        "threshold": gate_cfg.get("min_survival_score"),
        "critic_confidence": _as_float(critic.get("confidence"), None),
        "agents_present": sorted(a for a in rows if a in AGENTS),
        "parse_failure_count": _parse_failure_count(gid, rows, summary_rows),
        "failure_reasons": reasons,
    }


def _load_agent_rows(verification_dir: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], str]:
    rows_by_gap: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    sources: list[str] = []
    summary_path = verification_dir / "verification_summary.json"
    if summary_path.exists():
        data = json.loads(summary_path.read_text())
        if isinstance(data, dict):
            for gid, rows in data.items():
                if isinstance(rows, list):
                    for row in rows:
                        _add_row(rows_by_gap, str(gid), row)
                elif isinstance(rows, dict):
                    _add_row(rows_by_gap, str(gid), rows)
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    _add_row(rows_by_gap, str(row.get("gap_id") or row.get("id") or ""), row)
        sources.append("verification_summary.json")
    for agent in AGENTS:
        p = verification_dir / f"{agent}_results.jsonl"
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("agent_name", agent)
            _add_row(rows_by_gap, str(row.get("gap_id") or ""), row)
        sources.append(f"{agent}_results.jsonl")
    return {gid: dict(rows) for gid, rows in rows_by_gap.items() if gid}, "+".join(sources) if sources else "missing"


def _add_row(rows_by_gap: dict[str, dict[str, dict[str, Any]]], gid: str, row: Any) -> None:
    if not gid or not isinstance(row, dict):
        return
    agent = row.get("agent_name")
    if not agent:
        for candidate in AGENTS:
            if candidate in row and isinstance(row[candidate], dict):
                nested = dict(row[candidate])
                nested.setdefault("agent_name", candidate)
                rows_by_gap[gid][candidate] = nested
        return
    rows_by_gap[gid][str(agent)] = row


def _load_survival_scores(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    out: dict[str, float] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            gid = row.get("gap_id")
            score = _as_float(row.get("gap_survival_score"), None)
            if gid and score is not None:
                out[str(gid)] = score
    return out


def _load_results_summary(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(newline="") as fh:
        return {str(row["gap_id"]): dict(row) for row in csv.DictReader(fh) if row.get("gap_id")}


def _parse_failure_count(gid: str, rows: dict[str, dict[str, Any]], summary_rows: dict[str, dict[str, Any]]) -> int:
    summary_count = 0
    if gid in summary_rows:
        try:
            summary_count = int(float(summary_rows[gid].get("parse_failures") or 0))
        except Exception:
            pass
    row_count = sum(1 for row in rows.values() if _row_is_parse_failure(row))
    return max(summary_count, row_count)


def _row_is_parse_failure(row: dict[str, Any]) -> bool:
    failure_modes = [str(x).lower() for x in row.get("failure_modes", []) or []]
    summary = str(row.get("summary", "")).lower()
    return any("parse_failure" in x for x in failure_modes) or "failed after retries" in summary


def _critic_non_reject(row: dict[str, Any] | None, gate_cfg: dict[str, Any]) -> bool:
    if not isinstance(row, dict) or _row_is_parse_failure(row):
        return False
    label_fields = ["critic_label", "review_label", "quality_label", "recommendation", "verdict"]
    for key in label_fields:
        value = str(row.get(key, "")).strip().upper().replace(" ", "_")
        if value in _REJECT_LABELS or value.startswith("DROP") or value.startswith("REJECT"):
            return False
    confidence = _as_float(row.get("confidence"), 0.0)
    return confidence >= float(gate_cfg.get("min_critic_confidence", 0.50))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_float(value: Any, default: float | None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default
