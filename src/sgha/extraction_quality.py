"""Extraction-quality gate helpers.

The default behavior is fail-safe: low extraction yield is a hard stop. Model
scaling experiments can opt into advisory mode so downstream stages continue
while preserving a visible LOW_EXTRACTION_SIGNAL warning.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


PASS = "PASS"
FAIL = "FAIL"
LOW_EXTRACTION_SIGNAL = "LOW_EXTRACTION_SIGNAL"

DEFAULT_EXTRACTION_QUALITY = {
    "min_extracted_fraction": 0.90,
    "max_malformed_fraction": 0.30,
    "min_avg_tuples_per_paper": 2.0,
    "min_total_tuples": 400,
    "enforcement": "fail",
    "allow_downstream_on_low_signal": False,
}


def extraction_quality_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_EXTRACTION_QUALITY)
    override = ((config or {}).get("extraction_quality") or {}) if isinstance(config, Mapping) else {}
    if "min_total_tuples_alternative" in override and "min_total_tuples" not in override:
        override = {**override, "min_total_tuples": override["min_total_tuples_alternative"]}
    cfg.update(override)
    cfg["min_extracted_fraction"] = float(cfg["min_extracted_fraction"])
    cfg["max_malformed_fraction"] = float(cfg["max_malformed_fraction"])
    cfg["min_avg_tuples_per_paper"] = float(cfg["min_avg_tuples_per_paper"])
    cfg["min_total_tuples"] = int(cfg["min_total_tuples"])
    cfg["enforcement"] = str(cfg.get("enforcement") or "fail").lower()
    if cfg["enforcement"] not in {"fail", "warn"}:
        raise ValueError("extraction_quality.enforcement must be 'fail' or 'warn'")
    cfg["allow_downstream_on_low_signal"] = bool(cfg.get("allow_downstream_on_low_signal", False))
    return cfg


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _read_tuples(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def evaluate_extraction_quality(run_dir: str | Path, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate extraction quality for a run directory.

    Returns a summary with both historical fields (`status`, `sanity_gate`) and
    explicit advisory-mode fields (`extraction_quality_status`,
    `low_extraction_signal`, `allow_downstream`).
    """
    run = Path(run_dir)
    qcfg = extraction_quality_config(config)
    parsed = _read_json(run / "parsed" / "parsed_manifest.json", [])
    all_ext = _read_json(run / "extracted" / "all_extractions.json", [])
    tuples = _read_tuples(run / "extracted" / "all_tuples.jsonl")
    relation_counts = Counter(str(t.get("relation", "UNKNOWN")) for t in tuples)

    shard_status: list[dict[str, Any]] = []
    failed: list[str] = []
    malformed: list[str] = []
    for p in sorted((run / "extractions").glob("shard_*/extraction_status.json")):
        st = _read_json(p, {})
        if not isinstance(st, dict):
            continue
        shard_status.append(st)
        failed.extend(st.get("failed", []) or [])
        for pid, err in (st.get("errors") or {}).items():
            text = str(err).lower()
            if any(k in text for k in ("json", "validation", "parse", "schema", "extra data",
                                        "expecting value", "field required", "timeout", "api")):
                malformed.append(str(pid))

    expected = len(parsed)
    extracted = len(all_ext) if isinstance(all_ext, list) else 0
    fail_count = len(set(failed))
    malformed_count = len(set(malformed))
    tuple_count = len(tuples)
    avg = (tuple_count / extracted) if extracted else 0.0
    failure_rate = fail_count / max(1, expected)
    malformed_rate = malformed_count / max(1, expected)

    hard_reasons: list[str] = []
    low_signal_reasons: list[str] = []
    if extracted < int(expected * qcfg["min_extracted_fraction"]):
        hard_reasons.append(
            f"extracted below {qcfg['min_extracted_fraction']:.0%} threshold ({extracted}/{expected})"
        )
    if malformed_rate > qcfg["max_malformed_fraction"]:
        hard_reasons.append(
            f"malformed/API/schema failures above {qcfg['max_malformed_fraction']:.0%} ({malformed_count}/{expected})"
        )
    if not (avg >= qcfg["min_avg_tuples_per_paper"] or tuple_count >= qcfg["min_total_tuples"]):
        low_signal_reasons.append(
            "tuple yield below gate "
            f"({tuple_count} tuples, avg {avg:.2f}; need avg>={qcfg['min_avg_tuples_per_paper']:.1f} "
            f"or total>={qcfg['min_total_tuples']})"
        )
    if tuple_count and len(relation_counts) < 3:
        hard_reasons.append(f"relation distribution degenerate: only {len(relation_counts)} relation types")
    if tuple_count:
        max_rel, max_n = relation_counts.most_common(1)[0]
        if max_n / tuple_count > 0.95:
            hard_reasons.append(f"relation distribution degenerate: {max_rel} accounts for {max_n}/{tuple_count}")

    low_signal = bool(low_signal_reasons)
    advisory = qcfg["enforcement"] == "warn" or qcfg["allow_downstream_on_low_signal"]
    allow_downstream = not hard_reasons and (not low_signal or advisory)
    if hard_reasons or (low_signal and not advisory):
        status = FAIL
    elif low_signal:
        status = LOW_EXTRACTION_SIGNAL
    else:
        status = PASS

    return {
        "expected_parsed_papers": expected,
        "extracted_papers": extracted,
        "failed_extraction_count": fail_count,
        "malformed_count": malformed_count,
        "tuple_count": tuple_count,
        "average_tuples_per_extracted_paper": avg,
        "relation_distribution": dict(sorted(relation_counts.items())),
        "failure_rate": failure_rate,
        "malformed_rate": malformed_rate,
        "status": status,
        "extraction_quality_status": status,
        "low_extraction_signal": low_signal,
        "allow_downstream": allow_downstream,
        "enforcement": qcfg["enforcement"],
        "allow_downstream_on_low_signal": qcfg["allow_downstream_on_low_signal"],
        "reasons": hard_reasons + low_signal_reasons,
        "hard_failure_reasons": hard_reasons,
        "low_extraction_signal_reasons": low_signal_reasons,
        "warning": "; ".join(low_signal_reasons) if low_signal else "",
        "sanity_gate": {
            "min_extracted_fraction": qcfg["min_extracted_fraction"],
            "max_malformed_fraction": qcfg["max_malformed_fraction"],
            "min_avg_tuples_per_paper": qcfg["min_avg_tuples_per_paper"],
            "min_total_tuples": qcfg["min_total_tuples"],
            "enforcement": qcfg["enforcement"],
            "allow_downstream_on_low_signal": qcfg["allow_downstream_on_low_signal"],
        },
        "shards": shard_status,
    }


def load_extraction_quality_summary(run_dir: str | Path) -> dict[str, Any]:
    run = Path(run_dir)
    for name in ("stage2_large_extraction_summary.json",
                 "stage2_4b_extraction_summary.json",
                 "stage2_1b_extraction_summary.json",
                 "stage2_extraction_summary.json"):
        path = run / name
        data = _read_json(path, {})
        if isinstance(data, dict) and data:
            status = data.get("extraction_quality_status") or data.get("status")
            low = bool(data.get("low_extraction_signal")) or status == LOW_EXTRACTION_SIGNAL
            gate = data.get("sanity_gate") or {}
            data.setdefault("extraction_quality_status", status or PASS)
            data.setdefault("low_extraction_signal", low)
            data.setdefault("allow_downstream", status != FAIL)
            data.setdefault("warning", "; ".join(data.get("low_extraction_signal_reasons") or data.get("reasons") or []))
            data.setdefault("enforcement", gate.get("enforcement"))
            data.setdefault("allow_downstream_on_low_signal", gate.get("allow_downstream_on_low_signal"))
            return data
    return {}
