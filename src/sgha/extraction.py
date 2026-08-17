from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .corpus_manifest import read_manifest
from .extraction_schemas import PaperExtraction, ParsedPaper
from .json_repair import parse_json_with_repair
from .llm_client import LLMClient
from .pdf_parser import load_parsed_manifest
from .prompt_templates import extraction_prompt, reconciliation_prompt
from .utils import append_jsonl, model_dump, model_validate, read_text, utc_now_iso, write_json


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"-\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def _span_in_text(span: str, text: str) -> bool:
    if not span or len(span) < 15:  # raised from 8 to 15 — short spans are too ambiguous
        return False
    return _normalize(span) in _normalize(text)


_JUNK_SUBJECTS = {
    "method", "the method", "model", "the model", "algorithm", "the algorithm",
    "approach", "the approach", "system", "the system", "technique", "the technique",
    "our method", "our model", "our approach", "our system", "proposed method",
    "proposed model", "proposed approach", "it", "this", "the paper", "the work",
    "algorithm 1", "algorithm 2", "algorithm 3", "existing algorithms",
    "existing methods", "existing approaches", "baseline", "baselines",
    "the baseline", "prior methods", "prior work", "previous methods",
    "the proposed method", "the proposed algorithm", "the proposed approach",
}

# Keywords that indicate a failure_condition is actually an assumption statement
_ASSUMPTION_PHRASES = {
    "assumes ", "we assume", "assume that", "requires ", "require that",
    "assumption ", "rely on the assumption", "relies on the assumption",
}

_GENERIC_TASKS = {
    "regret minimization", "optimization", "learning", "prediction",
    "classification", "regression", "bandits", "reinforcement learning",
}


def _is_assumption_not_failure(text: str) -> bool:
    t = text.lower()
    # If it reads as an assumption statement and doesn't describe what breaks
    if any(t.startswith(p) or f" {p}" in t for p in _ASSUMPTION_PHRASES):
        if not any(kw in t for kw in ("fail", "degrad", "break", "violat", "when", "if not", "does not hold")):
            return True
    return False


def _clean_extracted_data(data: dict) -> dict:
    """Post-extraction cleanup: fix assumption/failure conflation, generic tasks, resolved mislabeling."""
    # Move assumption-phrased items out of failure_conditions into assumptions
    fc = data.get("failure_conditions", [])
    assumptions = data.get("assumptions", [])
    real_failures = []
    for item in fc:
        if _is_assumption_not_failure(item):
            if item not in assumptions:
                assumptions.append(item)
        else:
            real_failures.append(item)
    data["failure_conditions"] = real_failures
    data["assumptions"] = assumptions

    # Filter generic task labels
    tasks = data.get("tasks", [])
    data["tasks"] = [t for t in tasks if t.lower().strip() not in _GENERIC_TASKS]

    # resolved_by_paper=True should not appear on own_method failures —
    # only prior_work limitations can be resolved by the paper
    for t in data.get("tuples", []):
        if (t.get("subject_scope") == "own_method"
                and t.get("relation") in {"fails_under", "limited_by"}
                and t.get("resolved_by_paper") is True):
            t["resolved_by_paper"] = False

    return data


def _reconcile_failure_conditions(
    ctx: Any,
    outputs: list[PaperExtraction],
    parsed_manifest: Any,
    llm: Any,
) -> list[PaperExtraction]:
    """
    Second pass: for every own-method failure/limitation tuple with an empty condition,
    run a targeted LLM call to determine if the failure is conditional and fill in the
    condition field.
    """
    text_by_id = {p.paper_id: read_text(p.text_path) for p in parsed_manifest}
    updated_outputs = []
    total_reconciled = 0
    total_candidates = 0

    for extraction in outputs:
        text = text_by_id.get(extraction.paper_id, "")
        tuples = [model_dump(t) for t in extraction.tuples]
        changed = False

        for t in tuples:
            if not (
                t.get("relation") in {"fails_under", "limited_by"}
                and t.get("subject_scope") == "own_method"
                and not t.get("resolved_by_paper", False)
                and not t.get("condition", "").strip()
            ):
                continue

            total_candidates += 1
            span = t.get("source_span", "") or t.get("evidence_text", "")
            prompt = reconciliation_prompt(
                subject=t["subject"],
                relation=t["relation"],
                object_=t["object"],
                source_span=span,
                text=text,
            )
            try:
                result, _, _, _ = llm.complete_json(
                    stage="reconciliation",
                    agent_name="reconciliation",
                    prompt=prompt,
                    schema_name="Reconciliation",
                )
                if result.get("is_conditional") and result.get("condition", "").strip():
                    t["condition"] = result["condition"].strip()
                    if result.get("contrasting_success", "").strip():
                        t["contrasting_success"] = result["contrasting_success"].strip()
                    changed = True
                    total_reconciled += 1
            except Exception as exc:
                ctx.audit.failure("reconciliation", exc, paper_id=extraction.paper_id, subject=t["subject"])

        if changed:
            out_path = ctx.path("extracted", "per_paper_json", f"{_safe_paper_id(extraction.paper_id)}.json")
            # Rebuild extraction with updated tuples
            data = model_dump(extraction)
            data["tuples"] = tuples
            updated_extraction = model_validate(PaperExtraction, data)
            write_json(out_path, updated_extraction)
            updated_outputs.append(updated_extraction)
        else:
            updated_outputs.append(extraction)

    append_jsonl(
        ctx.path("extracted", "reconciliation_summary.jsonl"),
        {"timestamp": utc_now_iso(), "candidates": total_candidates, "reconciled": total_reconciled},
    )
    return updated_outputs


def extract_structured_claims(ctx: Any, *, llm_base_url: str | None = None, mock_llm: bool | None = None) -> list[PaperExtraction]:
    ctx.stage_start("extract")
    papers = {p.arxiv_id: p for p in read_manifest(ctx.run_dir)}
    parsed_manifest = load_parsed_manifest(ctx)
    llm = LLMClient(ctx, base_url=llm_base_url, mock=mock_llm)
    outputs: list[PaperExtraction] = []

    for parsed in parsed_manifest:
        paper_meta = papers.get(parsed.paper_id)
        title = paper_meta.title if paper_meta else parsed.title
        text = read_text(parsed.text_path)
        prompt = extraction_prompt(parsed.paper_id, title, text)
        try:
            data, _, _, parsed_path = llm.complete_json(stage="extraction", agent_name="extraction", prompt=prompt, schema_name="PaperExtraction")
            data.setdefault("paper_id", parsed.paper_id)

            valid_relations = {"evaluated_on","improves_over","fails_under","assumes","contradicts","uses_dataset","measured_by","limited_by","addresses","not_addressed_by"}
            all_tuples = data.get("tuples", [])
            verified_tuples = []
            unverified_count = 0

            for t in all_tuples:
                if not isinstance(t, dict):
                    continue
                if t.get("relation") not in valid_relations:
                    continue
                if not t.get("object") or not t.get("evidence_text"):
                    continue
                if str(t.get("subject", "")).strip().lower() in _JUNK_SUBJECTS:
                    continue

                # Drop noise evaluation tuples with no metric AND no dataset
                if t.get("relation") in {"evaluated_on", "uses_dataset", "measured_by"}:
                    if not t.get("metric") and not t.get("dataset"):
                        continue

                # Enforce polarity consistency
                rel = t.get("relation", "")
                if rel == "improves_over" and t.get("polarity") in {"negative", "unknown"}:
                    t["polarity"] = "positive"
                if rel in {"fails_under", "limited_by"} and t.get("polarity") in {"positive", "unknown"}:
                    t["polarity"] = "negative"
                if rel == "assumes" and t.get("polarity") == "unknown":
                    t["polarity"] = "neutral"

                span = t.get("source_span", "")
                ev = t.get("evidence_text", "")
                if _span_in_text(span, text) or _span_in_text(ev, text):
                    verified_tuples.append(t)
                else:
                    unverified_count += 1

            if unverified_count:
                append_jsonl(
                    ctx.path("extracted", "unverified_spans.jsonl"),
                    {"paper_id": parsed.paper_id, "dropped_tuples": unverified_count},
                )

            data["tuples"] = verified_tuples
            data = _clean_extracted_data(data)

            extraction = model_validate(PaperExtraction, data)
            out_path = ctx.path("extracted", "per_paper_json", f"{_safe_paper_id(parsed.paper_id)}.json")
            write_json(out_path, extraction)
            for tup in extraction.tuples:
                row = model_dump(tup)
                row.update({"paper_id": extraction.paper_id, "parsed_response_path": str(parsed_path)})
                append_jsonl(ctx.path("extracted", "all_tuples.jsonl"), row)
            outputs.append(extraction)

        except Exception as exc:
            append_jsonl(
                ctx.path("extracted", "extraction_failures.jsonl"),
                {"timestamp": utc_now_iso(), "paper_id": parsed.paper_id, "error": str(exc)},
            )
            ctx.audit.failure("extract", exc, paper_id=parsed.paper_id)

    # Reconciliation pass: fill in conditions for own-method failures with empty condition
    outputs = _reconcile_failure_conditions(ctx, outputs, parsed_manifest, llm)

    # Rebuild all_extractions.json and all_tuples.jsonl with reconciled data
    write_json(ctx.path("extracted", "all_extractions.json"), [model_dump(o) for o in outputs])
    ctx.stage_end("extract", papers=len(outputs))
    return outputs


def load_extractions(ctx: Any) -> list[PaperExtraction]:
    from .utils import read_json

    data = read_json(ctx.path("extracted", "all_extractions.json"), default=[])
    return [model_validate(PaperExtraction, item) for item in data]


def _safe_paper_id(paper_id: str) -> str:
    return paper_id.replace("/", "_").replace(":", "_")
