"""Resolution extraction pass — finds explicit solution/address claims in paper corpus."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .llm_client import LLMClient
from .prompt_templates import resolution_extraction_prompt
from .utils import append_jsonl, ensure_dir, model_dump, read_text, stable_id, utc_now_iso, write_json


class ResolutionRecord(BaseModel):
    record_id: str
    paper_id: str
    method: str
    resolution_relation: Literal[
        "addresses_limitation",
        "relaxes_assumption",
        "handles_failure_condition",
        "resolves_failure_condition",
        "partially_addresses",
        "improves_under_condition",
    ]
    target_problem: str
    target_problem_type: Literal["assumption", "limitation", "failure_condition", "benchmark_gap", "unclear"]
    addressed_condition: str = ""
    prior_work_or_baseline: str = ""
    scope: str = ""
    claim_strength: Literal["full", "partial", "empirical_only", "theoretical_only", "unclear"]
    evidence_text: str
    section: str = ""
    confidence: float  # 0.0-1.0


def _safe_paper_id(paper_id: str) -> str:
    return paper_id.replace("/", "_").replace(":", "_")


# Confidence imputed when the LLM omits the field but all required content is present.
# Configurable via resolution_extraction.missing_confidence_default in run config.
_MISSING_CONFIDENCE_DEFAULT: float = 0.70

_VALID_RELATIONS = {
    "addresses_limitation",
    "relaxes_assumption",
    "handles_failure_condition",
    "resolves_failure_condition",
    "partially_addresses",
    "improves_under_condition",
}

_VALID_PROBLEM_TYPES = {"assumption", "limitation", "failure_condition", "benchmark_gap", "unclear"}
_VALID_CLAIM_STRENGTHS = {"full", "partial", "empirical_only", "theoretical_only", "unclear"}


def _parse_resolution_records(
    paper_id: str,
    raw: dict[str, Any],
    missing_confidence_default: float = _MISSING_CONFIDENCE_DEFAULT,
) -> list[dict[str, Any]]:
    """Parse LLM output into a list of record dicts."""
    items = raw.get("resolutions", raw.get("items", []))
    if not isinstance(items, list):
        return []
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Normalize relation
        rel = str(item.get("resolution_relation", "")).strip().lower().replace(" ", "_")
        if rel not in _VALID_RELATIONS:
            rel = "addresses_limitation"
        # Normalize problem type
        pt = str(item.get("target_problem_type", "unclear")).strip().lower()
        if pt not in _VALID_PROBLEM_TYPES:
            pt = "unclear"
        # Normalize claim strength
        cs = str(item.get("claim_strength", "unclear")).strip().lower()
        if cs not in _VALID_CLAIM_STRENGTHS:
            cs = "unclear"
        method = str(item.get("method", "")).strip()
        target = str(item.get("target_problem", "")).strip()
        evidence = str(item.get("evidence_text", "")).strip()
        addressed_condition = str(item.get("addressed_condition", "")).strip()

        # Confidence: if the LLM omits the field entirely, impute only when all
        # required content fields are present — do not impute for truly empty records.
        raw_conf = item.get("confidence")
        confidence_was_imputed = False
        imputed_reason = ""
        if raw_conf is None:
            # Missing field: impute only if evidence + method + (target or condition) present
            if evidence and method and (target or addressed_condition):
                conf = missing_confidence_default
                confidence_was_imputed = True
                imputed_reason = "missing_confidence_but_required_fields_present"
            else:
                conf = 0.0  # will be dropped by caller
        else:
            try:
                conf = float(raw_conf)
                conf = max(0.0, min(1.0, conf))
            except (TypeError, ValueError):
                conf = 0.0  # malformed: drop

        record_id = stable_id("res", paper_id, method, target, evidence)
        rec = {
            "record_id": record_id,
            "paper_id": paper_id,
            "method": method,
            "resolution_relation": rel,
            "target_problem": target,
            "target_problem_type": pt,
            "addressed_condition": addressed_condition,
            "prior_work_or_baseline": str(item.get("prior_work_or_baseline", "")).strip(),
            "scope": str(item.get("scope", "")).strip(),
            "claim_strength": cs,
            "evidence_text": evidence,
            "section": str(item.get("section", "")).strip(),
            "confidence": conf,
        }
        if confidence_was_imputed:
            rec["confidence_was_imputed"] = True
            rec["imputed_confidence_reason"] = imputed_reason
        records.append(rec)
    return records


def extract_resolution_records(
    ctx: Any,
    *,
    paper_ids: list[str] | None = None,
    llm_base_url: str | None = None,
    min_confidence: float = 0.65,
    resume: bool = True,
    missing_confidence_default: float | None = None,
) -> list[ResolutionRecord]:
    """Run a separate extraction pass to find explicit resolution/address claims.

    Args:
        ctx: RunContext
        paper_ids: If provided, only process these paper IDs.
        llm_base_url: Override LLM base URL.
        min_confidence: Drop records below this confidence threshold.
        resume: Skip papers that already have output file.

    Returns:
        List of valid ResolutionRecord objects.
    """
    out_dir = ctx.path("resolution_extractions")
    ensure_dir(out_dir)

    all_jsonl = out_dir / "all_resolution_records.jsonl"
    dropped_jsonl = out_dir / "dropped_records.jsonl"

    # Load parsed manifest
    manifest_path = ctx.path("parsed", "parsed_manifest.json")
    if not manifest_path.exists():
        print("[resolution_extraction] No parsed_manifest.json found, returning empty.", flush=True)
        return []

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest_raw = json.load(f)

    # Filter to requested paper_ids
    if paper_ids is not None:
        paper_ids_set = set(paper_ids)
        manifest_raw = [p for p in manifest_raw if p.get("paper_id") in paper_ids_set or p.get("arxiv_id") in paper_ids_set]

    # Allow config or caller to override the imputed confidence default
    res_cfg = ctx.config.get("resolution_extraction", {})
    allow_imputation = bool(res_cfg.get("allow_confidence_imputation", True))
    if missing_confidence_default is None:
        missing_confidence_default = float(
            res_cfg.get("missing_confidence_default", _MISSING_CONFIDENCE_DEFAULT)
        )
    # If imputation is disabled, use 0.0 so imputed records fall below any threshold
    _effective_missing_default = missing_confidence_default if allow_imputation else 0.0

    llm = LLMClient(ctx, base_url=llm_base_url)
    all_records: list[ResolutionRecord] = []

    for paper_meta in manifest_raw:
        pid = paper_meta.get("paper_id") or paper_meta.get("arxiv_id", "")
        title = paper_meta.get("title", "")
        text_path = paper_meta.get("text_path", "")

        safe_id = _safe_paper_id(pid)
        out_path = out_dir / f"{safe_id}.json"

        if resume and out_path.exists():
            # Load already-computed records
            try:
                with out_path.open("r", encoding="utf-8") as f:
                    existing = json.load(f)
                for rec in existing:
                    try:
                        all_records.append(ResolutionRecord(**rec))
                    except Exception:
                        pass
            except Exception:
                pass
            continue

        text = read_text(text_path)
        if not text.strip():
            print(f"[resolution_extraction] Skipping {pid}: empty text", flush=True)
            continue

        prompt = resolution_extraction_prompt(pid, title, text)
        valid_records: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []

        try:
            raw, _, _, _ = llm.complete_json(
                stage="resolution_extraction",
                agent_name="resolution_extractor",
                prompt=prompt,
                schema_name="ResolutionRecord",
            )
            parsed = _parse_resolution_records(pid, raw, missing_confidence_default=_effective_missing_default)

            for rec in parsed:
                drop_reason = None
                if not rec["evidence_text"]:
                    drop_reason = "empty_evidence"
                elif rec["confidence"] < min_confidence:
                    drop_reason = f"low_confidence:{rec['confidence']:.2f}"

                if drop_reason:
                    dropped.append({**rec, "drop_reason": drop_reason, "timestamp": utc_now_iso()})
                else:
                    valid_records.append(rec)

        except Exception as exc:
            print(f"[resolution_extraction] Failed for {pid}: {exc}", flush=True)

        # Write per-paper output
        write_json(out_path, valid_records)

        # Append to all JSONL
        for rec in valid_records:
            append_jsonl(all_jsonl, rec)
            try:
                all_records.append(ResolutionRecord(**rec))
            except Exception:
                pass

        # Log dropped
        for dropped_rec in dropped:
            append_jsonl(dropped_jsonl, dropped_rec)

        print(
            f"[resolution_extraction] {pid}: {len(valid_records)} valid, {len(dropped)} dropped",
            flush=True,
        )

    print(f"[resolution_extraction] Total records: {len(all_records)}", flush=True)
    return all_records
