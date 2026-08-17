#!/usr/bin/env python3
"""MOOSE-Star public-model baseline runner for SGHA paper domains.

This wrapper runs an adapted public-model baseline using the released
MOOSE-Star Hypothesis Composition model and the official HC prompt template.
It intentionally avoids SGHA graph/gap/verification/finalization artifacts,
does not train or fine-tune models, and does not call OpenRouter.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import sys
from typing import Any, Callable, Iterable


METHOD = "MOOSE_STAR_PUBLIC_MODEL"
HC_ONLY_MODE = "HC_ONLY"
IR_PLUS_HC_MODE = "IR_PLUS_HC"
DEFAULT_MODEL_ID = "ZonglinY/MOOSE-Star-HC-R1D-7B"
DEFAULT_MODEL_PATH = os.environ.get("MOOSE_MODEL_PATH", "./models/moose_star/MOOSE-Star-HC-R1D-7B")
DEFAULT_MOOSE_REPO = os.environ.get("MOOSE_REPO", "./external_baselines/MOOSE-Star")
FORBIDDEN_INPUT_PARTS = {
    "extracted",
    "final_sgha_family_report",
    "graph",
    "gaps",
    "novelty",
    "stage7_direct_formulations",
    "stage8_ambition_expansion",
    "stage9_family_quality",
    "stage10_formal_problem_formulations",
    "verification",
}


class MooseBaselineError(RuntimeError):
    """Raised when the baseline cannot proceed safely."""


@dataclass
class GenerationConfig:
    baseline_root: Path
    domain_input_dir: Path | None
    domain_input: Path | None
    model_id: str
    model_path: Path
    moose_repo: Path
    inference_mode: str = HC_ONLY_MODE
    seed: int = 17
    max_new_tokens: int = 2048
    temperature: float = 0.6
    top_p: float = 0.9
    mock_response: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def guard_allowed_source_files(paths: Iterable[str]) -> None:
    for raw in paths:
        parts = set(Path(raw).parts)
        forbidden = sorted(parts & FORBIDDEN_INPUT_PARTS)
        if forbidden:
            raise MooseBaselineError(
                f"Domain input references forbidden SGHA artifact {raw}; parts={forbidden}"
            )


def load_instruction_prompt_builder(moose_repo: Path) -> Callable[[str], list[str]]:
    prompt_store = moose_repo / "utils" / "prompt_store.py"
    if not prompt_store.exists():
        raise MooseBaselineError(f"MOOSE-Star prompt store not found: {prompt_store}")
    spec = importlib.util.spec_from_file_location("moose_star_prompt_store", prompt_store)
    module = importlib.util.module_from_spec(spec)
    if not spec or not spec.loader:
        raise MooseBaselineError(f"Unable to load prompt store: {prompt_store}")
    spec.loader.exec_module(module)
    return module.instruction_prompts


def normalize_pool(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, paper in enumerate(pool):
        title = str(paper.get("title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        normalized.append(
            {
                "paper_id": str(
                    paper.get("paper_id")
                    or paper.get("arxiv_id")
                    or paper.get("openreview_id")
                    or paper.get("id")
                    or f"paper:{idx:04d}"
                ),
                "title": title,
                "abstract": str(paper.get("abstract") or "").strip(),
                "year": paper.get("year") or paper.get("published") or paper.get("updated"),
                "source": paper.get("source") or paper.get("source_query") or paper.get("corpus_source"),
            }
        )
    return normalized


def select_inspirations(
    pool: list[dict[str, Any]],
    output_count: int,
    *,
    seed: int = 17,
) -> list[dict[str, Any]]:
    """Deterministically choose diverse, abstract-bearing inspiration papers."""
    if output_count < 1:
        raise MooseBaselineError(f"output_count must be positive, got {output_count}")
    normalized = normalize_pool(pool)
    abstract_rich = [p for p in normalized if len(p.get("abstract", "")) >= 80]
    candidates = abstract_rich or normalized
    if len(candidates) < output_count:
        raise MooseBaselineError(
            f"Not enough candidate inspiration papers: need {output_count}, got {len(candidates)}"
        )

    rng = random.Random(seed)
    # Stable pseudo-shuffle, then take evenly spaced items to avoid adjacent query clusters.
    ranked = sorted(
        candidates,
        key=lambda p: (
            rng.random(),
            str(p.get("title", "")).lower(),
            str(p.get("paper_id", "")),
        ),
    )
    if output_count == 1:
        return [ranked[0]]
    step = max(1, len(ranked) // output_count)
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for i in range(output_count):
        start = (i * step) % len(ranked)
        for offset in range(len(ranked)):
            paper = ranked[(start + offset) % len(ranked)]
            if paper["paper_id"] not in used:
                selected.append(paper)
                used.add(paper["paper_id"])
                break
    return selected


def build_hc_prompt(
    instruction_prompts: Callable[[str], list[str]],
    *,
    research_question: str,
    background_survey: str,
    previous_hypothesis: str,
    inspiration_title: str,
    inspiration_abstract: str,
) -> str:
    p = instruction_prompts("prepare_HC_sft_data_to_go_comprehensive_v2_delta")
    return (
        p[0]
        + research_question
        + p[1]
        + background_survey
        + p[2]
        + previous_hypothesis
        + p[3]
        + inspiration_title
        + p[4]
        + inspiration_abstract
        + p[5]
    )


def extract_marker(text: str, start: str, end: str) -> str:
    pattern = re.escape(start) + r"(.*?)" + re.escape(end)
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def clean_model_text(text: str) -> str:
    """Clean byte-level tokenizer artifacts sometimes emitted by R1/Qwen decodes."""
    return (
        text.replace("Ċ", "\n")
        .replace("Ġ", " ")
        .replace("ĉ", "\t")
        .replace("\r\n", "\n")
        .strip()
    )


def parse_labeled_field(text: str, label: str) -> str:
    pattern = rf"(?:^|\n)\s*-?\s*{re.escape(label)}\s*:\s*(.*?)(?=\n\s*-?\s*[A-Z][A-Za-z ()/'-]+:\s*|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_moose_output(raw: str) -> dict[str, str]:
    cleaned = clean_model_text(raw)
    delta = extract_marker(cleaned, "**Delta Hypothesis starts:**", "**Delta Hypothesis ends**") or cleaned
    inspiration = parse_labeled_field(delta, "Inspiration")
    motivation = parse_labeled_field(delta, "Motivation (WHY)")
    mechanism = parse_labeled_field(delta, "Mechanism (HOW IT WORKS)")
    methodology = parse_labeled_field(delta, "Methodology (HOW IT'S INTEGRATED)")
    if not motivation:
        motivation = parse_labeled_field(delta, "Motivation")
    if not mechanism:
        mechanism = parse_labeled_field(delta, "Mechanism")
    if not methodology:
        methodology = parse_labeled_field(delta, "Methodology")
    return {
        "delta_hypothesis": delta.strip(),
        "inspiration": inspiration.strip(),
        "motivation": motivation.strip(),
        "mechanism": mechanism.strip(),
        "methodology": methodology.strip(),
    }


def make_record(
    *,
    domain: str,
    index: int,
    model_id: str,
    inference_mode: str,
    domain_input: dict[str, Any],
    inspiration: dict[str, Any],
    raw_output: str,
) -> dict[str, Any]:
    parsed = parse_moose_output(raw_output)
    title_seed = parsed["inspiration"] or inspiration["title"]
    title = f"MOOSE-Star hypothesis from {title_seed}".strip()
    proposed_parts = [p for p in [parsed["mechanism"], parsed["methodology"]] if p]
    parse_issue = not (parsed["motivation"] or parsed["mechanism"] or parsed["methodology"])
    return {
        "candidate_id": f"moose_star_public_{domain}_{index:03d}",
        "method": METHOD,
        "domain": domain,
        "title": title,
        "problem_statement": str(domain_input.get("research_question") or "not provided"),
        "motivation_or_abstract": parsed["motivation"] or "not provided",
        "proposed_direction": "\n\n".join(proposed_parts) if proposed_parts else "not provided",
        "expected_contribution": parsed["mechanism"] or "not provided",
        "evaluation_plan": "not provided",
        "risks_or_caveats": "not provided",
        "source_context_or_grounding": f"Inspiration paper: {inspiration['paper_id']} — {inspiration['title']}",
        "formal_problem_statement": "not provided",
        "assumptions_or_problem_setup": "not provided",
        "ambiguity_or_missing_definitions": "not provided",
        "moose_star_raw_output": raw_output,
        "research_question": str(domain_input.get("research_question") or ""),
        "background_survey_excerpt": str(domain_input.get("background_survey") or "")[:1600],
        "inspiration_titles": [inspiration["title"]],
        "inspiration_paper_ids": [inspiration["paper_id"]],
        "inference_mode": inference_mode,
        "model_id": model_id,
        "parse_issue": parse_issue,
        "parsed_delta_hypothesis": parsed["delta_hypothesis"],
    }


class MooseHCGenerator:
    def __init__(self, model_path: Path, model_id: str, max_new_tokens: int, temperature: float, top_p: float):
        self.model_path = model_path
        self.model_id = model_id
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise MooseBaselineError("CUDA is required for live 7B inference; run this under sbatch on a GPU node.")
        if not self.model_path.exists():
            raise MooseBaselineError(f"Model path does not exist: {self.model_path}")

        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        )
        self._model.to("cuda")
        self._model.eval()

    def generate(self, prompt: str, *, seed: int) -> str:
        import torch

        self._load()
        assert self._tokenizer is not None and self._model is not None
        torch.manual_seed(seed)
        messages = [{"role": "user", "content": prompt}]
        formatted = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        formatted += "<｜Assistant｜>"
        inputs = self._tokenizer(formatted, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=self.temperature > 0,
                temperature=self.temperature,
                top_p=self.top_p,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        new_tokens = outputs[0][inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def mock_generate(prompt: str, *, seed: int, inspiration_title: str) -> str:
    return (
        "<think>\n"
        f"Mock reasoning for {inspiration_title}. The supplied prompt length is {len(prompt)}.\n"
        "</think>\n\n"
        "**Delta Hypothesis starts:**\n"
        f"Inspiration: Adapted mechanism from {inspiration_title}\n"
        "- Motivation (WHY): The inspiration suggests a concrete way to address a limitation in the supplied domain background.\n"
        "- Mechanism (HOW IT WORKS): The candidate mechanism transfers the inspiration's core technique into the target research setting.\n"
        "- Methodology (HOW IT'S INTEGRATED): Build a small, testable formulation around the selected inspiration and compare it against existing corpus methods.\n"
        "**Delta Hypothesis ends**"
    )


def run_domain(domain_input_path: Path, cfg: GenerationConfig) -> dict[str, Any]:
    domain_input = read_json(domain_input_path)
    source_files = domain_input.get("source_files_read", [])
    if not isinstance(source_files, list):
        source_files = []
    guard_allowed_source_files([str(p) for p in source_files])

    domain = str(domain_input["domain"])
    output_count = int(domain_input["output_count"])
    output_dir = cfg.baseline_root / "outputs" / domain
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_builder = load_instruction_prompt_builder(cfg.moose_repo)
    inspirations = select_inspirations(
        list(domain_input.get("inspiration_candidate_pool") or []),
        output_count,
        seed=cfg.seed,
    )

    generator = None
    if not cfg.mock_response:
        generator = MooseHCGenerator(
            model_path=cfg.model_path,
            model_id=cfg.model_id,
            max_new_tokens=cfg.max_new_tokens,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
        )

    records: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    previous_hypothesis = "No previous hypothesis."
    for idx, inspiration in enumerate(inspirations, start=1):
        prompt = build_hc_prompt(
            prompt_builder,
            research_question=str(domain_input.get("research_question") or ""),
            background_survey=str(domain_input.get("background_survey") or ""),
            previous_hypothesis=previous_hypothesis,
            inspiration_title=inspiration["title"],
            inspiration_abstract=inspiration.get("abstract") or "",
        )
        if cfg.mock_response:
            raw = cfg.mock_response
            if raw == "__AUTO__":
                raw = mock_generate(prompt, seed=cfg.seed + idx, inspiration_title=inspiration["title"])
        else:
            assert generator is not None
            raw = generator.generate(prompt, seed=cfg.seed + idx)

        record = make_record(
            domain=domain,
            index=idx,
            model_id=cfg.model_id,
            inference_mode=cfg.inference_mode,
            domain_input=domain_input,
            inspiration=inspiration,
            raw_output=raw,
        )
        records.append(record)
        raw_rows.append(
            {
                "candidate_id": record["candidate_id"],
                "domain": domain,
                "model_id": cfg.model_id,
                "prompt": prompt,
                "raw_output": raw,
                "inspiration_paper_id": inspiration["paper_id"],
                "inspiration_title": inspiration["title"],
            }
        )
        selection_rows.append(
            {
                "rank": idx,
                "paper_id": inspiration["paper_id"],
                "title": inspiration["title"],
                "year": inspiration.get("year"),
                "selection_mode": "deterministic_metadata_diversity",
            }
        )

    write_jsonl(output_dir / "moose_star_ideas.jsonl", records)
    write_jsonl(output_dir / "raw_model_outputs.jsonl", raw_rows)
    write_json(output_dir / "inspiration_selection_audit.json", selection_rows)
    write_domain_markdown(output_dir / "moose_star_ideas.md", records)
    write_selection_markdown(output_dir / "inspiration_selection_audit.md", domain, selection_rows)
    metadata = {
        "domain": domain,
        "model_id": cfg.model_id,
        "model_path": str(cfg.model_path),
        "method": METHOD,
        "inference_mode": cfg.inference_mode,
        "output_count_requested": output_count,
        "output_count_written": len(records),
        "created_at": utc_now_iso(),
        "training_run": False,
        "openrouter_used": False,
        "sgha_final_artifacts_used": False,
        "source_files_read": source_files,
        "domain_input_path": str(domain_input_path),
        "temperature": cfg.temperature,
        "top_p": cfg.top_p,
        "max_new_tokens": cfg.max_new_tokens,
        "mock_response_used": bool(cfg.mock_response),
    }
    write_json(output_dir / "run_metadata.json", metadata)
    (output_dir / "command.txt").write_text(" ".join(sys.argv) + "\n")
    write_quality_audit(output_dir / "quality_audit.md", domain, output_count, records, cfg)
    return {"domain": domain, "records": records, "output_dir": output_dir}


def write_domain_markdown(path: Path, records: list[dict[str, Any]]) -> None:
    lines = ["# MOOSE-Star Public-Model Ideas", ""]
    for record in records:
        lines.extend(
            [
                f"## {record['candidate_id']}: {record['title']}",
                "",
                f"- Domain: {record['domain']}",
                f"- Method: {record['method']}",
                f"- Model: {record['model_id']}",
                f"- Inference mode: {record['inference_mode']}",
                f"- Inspiration papers: {', '.join(record['inspiration_titles'])}",
                "",
                "### Problem Statement",
                "",
                record["problem_statement"],
                "",
                "### Motivation",
                "",
                record["motivation_or_abstract"],
                "",
                "### Proposed Direction",
                "",
                record["proposed_direction"],
                "",
                "### Evaluation Plan",
                "",
                record["evaluation_plan"],
                "",
                "### Risks / Caveats",
                "",
                record["risks_or_caveats"],
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n")


def write_selection_markdown(path: Path, domain: str, rows: list[dict[str, Any]]) -> None:
    lines = [f"# Inspiration Selection Audit: {domain}", "", "| Rank | Paper ID | Title | Selection mode |", "|---:|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['rank']} | `{row['paper_id']}` | {row['title']} | {row['selection_mode']} |")
    path.write_text("\n".join(lines) + "\n")


def write_quality_audit(
    path: Path,
    domain: str,
    expected_count: int,
    records: list[dict[str, Any]],
    cfg: GenerationConfig,
) -> None:
    parse_issues = sum(1 for r in records if r.get("parse_issue"))
    formal_ok = all(r["formal_problem_statement"] == "not provided" for r in records)
    lines = [
        f"# MOOSE-Star Quality Audit: {domain}",
        "",
        f"- expected_count: {expected_count}",
        f"- actual_count: {len(records)}",
        f"- count_matches: {len(records) == expected_count}",
        f"- method_metadata_ok: {all(r.get('method') == METHOD for r in records)}",
        f"- public_model_id: {cfg.model_id}",
        f"- training_run: false",
        f"- openrouter_used: false",
        f"- sgha_final_artifacts_used: false",
        f"- formal_fields_marked_not_provided: {str(formal_ok).lower()}",
        f"- parse_issue_count: {parse_issues}",
    ]
    path.write_text("\n".join(lines) + "\n")


def domain_input_paths(cfg: GenerationConfig) -> list[Path]:
    if cfg.domain_input:
        return [cfg.domain_input]
    if not cfg.domain_input_dir:
        raise MooseBaselineError("Provide --domain-input or --domain-input-dir")
    return sorted(p for p in cfg.domain_input_dir.glob("*.json") if p.name != "DOMAIN_INPUT_AUDIT.json")


def validate_outputs(baseline_root: Path) -> dict[str, Any]:
    expected = {
        "bandits": 3,
        "in_context_learning": 4,
        "reasoning_models_test_time_compute": 1,
        "offline_reinforcement_learning_arxiv": 1,
        "uncertainty_calibration_conformal_prediction_arxiv": 6,
    }
    rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    total = 0
    errors: list[str] = []
    for domain, count in expected.items():
        out = baseline_root / "outputs" / domain
        ideas_path = out / "moose_star_ideas.jsonl"
        metadata_path = out / "run_metadata.json"
        ideas = []
        if ideas_path.exists():
            ideas = [json.loads(line) for line in ideas_path.read_text().splitlines() if line.strip()]
        else:
            errors.append(f"Missing {ideas_path}")
        total += len(ideas)
        meta = read_json(metadata_path) if metadata_path.exists() else {}
        if len(ideas) != count:
            errors.append(f"{domain}: expected {count}, found {len(ideas)}")
        if any(r.get("method") != METHOD for r in ideas):
            errors.append(f"{domain}: method metadata mismatch")
        if any(r.get("formal_problem_statement") != "not provided" for r in ideas):
            errors.append(f"{domain}: formal problem statement should be not provided")
        rows.append(
            {
                "domain": domain,
                "expected_count": count,
                "actual_count": len(ideas),
                "count_matches": len(ideas) == count,
                "parse_issue_count": sum(1 for r in ideas if r.get("parse_issue")),
                "model_id": meta.get("model_id", ""),
                "inference_mode": meta.get("inference_mode", ""),
                "training_run": meta.get("training_run", ""),
                "openrouter_used": meta.get("openrouter_used", ""),
                "sgha_final_artifacts_used": meta.get("sgha_final_artifacts_used", ""),
            }
        )
        input_rows.append(
            {
                "domain": domain,
                "domain_input_path": meta.get("domain_input_path", ""),
                "source_files_read": "; ".join(meta.get("source_files_read", []) if isinstance(meta.get("source_files_read"), list) else []),
                "forbidden_artifact_used": bool(meta.get("sgha_final_artifacts_used")),
            }
        )
    outputs_dir = baseline_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    counts_csv = outputs_dir / "moose_star_baseline_counts.csv"
    with counts_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    input_csv = outputs_dir / "moose_star_baseline_input_audit.csv"
    with input_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(input_rows[0]))
        writer.writeheader()
        writer.writerows(input_rows)
    validation = outputs_dir / "MOOSE_STAR_BASELINE_VALIDATION.md"
    lines = [
        "# MOOSE-Star Baseline Validation",
        "",
        f"- expected_total_candidates: {sum(expected.values())}",
        f"- actual_total_candidates: {total}",
        f"- all_counts_match: {str(total == sum(expected.values()) and not any(r['count_matches'] is False for r in rows)).lower()}",
        "- training_run: false",
        "- openrouter_used: false",
        "- sgha_final_gap_verification_family_artifacts_used: false",
        f"- validation_errors: {len(errors)}",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {e}" for e in errors] or ["- none"])
    validation.write_text("\n".join(lines) + "\n")
    return {
        "expected_total": sum(expected.values()),
        "actual_total": total,
        "errors": errors,
        "counts_csv": counts_csv,
        "input_csv": input_csv,
        "validation": validation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--domain-input-dir", type=Path)
    parser.add_argument("--domain-input", type=Path)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-path", type=Path, default=Path(DEFAULT_MODEL_PATH))
    parser.add_argument("--moose-repo", type=Path, default=Path(DEFAULT_MOOSE_REPO))
    parser.add_argument("--inference-mode", choices=[HC_ONLY_MODE, IR_PLUS_HC_MODE], default=HC_ONLY_MODE)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--mock-response", default=None)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.validate_only:
        result = validate_outputs(args.baseline_root)
        print(json.dumps({k: str(v) if isinstance(v, Path) else v for k, v in result.items()}, indent=2))
        return 0 if not result["errors"] else 1

    cfg = GenerationConfig(
        baseline_root=args.baseline_root,
        domain_input_dir=args.domain_input_dir,
        domain_input=args.domain_input,
        model_id=args.model_id,
        model_path=args.model_path,
        moose_repo=args.moose_repo,
        inference_mode=args.inference_mode,
        seed=args.seed,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        mock_response=args.mock_response,
    )
    results = []
    for path in domain_input_paths(cfg):
        results.append(run_domain(path, cfg))
    validation = validate_outputs(args.baseline_root)
    print(
        json.dumps(
            {
                "domains_run": [r["domain"] for r in results],
                "actual_total": validation["actual_total"],
                "validation_errors": validation["errors"],
            },
            indent=2,
        )
    )
    return 0 if not validation["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
