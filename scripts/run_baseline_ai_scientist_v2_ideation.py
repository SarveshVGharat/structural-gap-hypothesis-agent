#!/usr/bin/env python3
"""Ideation-only AI-Scientist-v2-style baseline for SGHA runs.

This wrapper intentionally does not import or run AI-Scientist-v2 tree search,
experiment execution, plotting, writeup, review, generated-code execution, or
Semantic Scholar tooling. It reuses the AI-Scientist-v2 ideation prompt shape
with the external-search tool removed, then calls a local OpenAI-compatible
endpoint.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable


GENERATED_BY = "ai_scientist_v2_ideation_qwen"
DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_BASE_URL = os.environ.get("SGHA_LLM_BASE_URL", "http://localhost:8000/v1")
DEFAULT_OUTPUT_SUBDIR = Path("baselines") / "ai_scientist_v2_ideation_qwen"
FORBIDDEN_INPUT_PARTS = {
    "final",
    "final_sgha_family_report",
    "stage7_direct_formulations",
    "stage7_direct_formulations_qwen",
    "stage8_ambition_expansion",
    "stage9_family_quality",
    "stage10_formal_problem_formulations",
}


AI_SCIENTIST_V2_REUSE_NOTE = (
    "Prompt adapted from AI-Scientist-v2 perform_ideation_temp_free.py: "
    "experienced AI researcher, proposal-style ideation, previous proposal "
    "archive, and finalized structured idea fields. Semantic Scholar and all "
    "execution/writeup/review paths are removed."
)


BASELINE_SYSTEM_PROMPT = """You are an experienced AI researcher who aims to propose high-impact research ideas resembling exciting grant proposals. Feel free to propose novel ideas or experiments, but keep them feasible for an academic lab. Each proposal should stem from a simple and elegant question, observation, or hypothesis about the provided topic and paper corpus.

Safety and scope rules:
- Do not use Semantic Scholar.
- Do not request or perform external literature search.
- Do not run code.
- Do not propose that this baseline execute experiments.
- Do not write a paper, review a paper, or generate plots.
- Use only the supplied corpus context.
- Return exactly one JSON object for one finalized idea.

The JSON object must include:
- "Name": short lowercase identifier with underscores
- "Title": proposal title
- "Short Hypothesis": concise research question or hypothesis
- "Related Work": source-grounded motivation from the supplied corpus only
- "Abstract": proposal-style abstract
- "Experiments": conceptual evaluation plan, not executable instructions
- "Risk Factors and Limitations": risks and limitations
- "Expected Contribution": expected scientific contribution
- "Proposed Method or Direction": proposed method, theorem, benchmark, or conceptual direction
"""


IDEA_GENERATION_PROMPT = """{workshop_description}

Here are the proposals that you have already generated:

'''
{prev_ideas_string}
'''

Generate exactly one new high-level research proposal that differs from previous proposals.

Return only JSON. Do not include Markdown fences. Do not include ACTION/ARGUMENTS. Do not use tools.
"""


@dataclass
class BaselineConfig:
    run_dir: Path
    output_dir: Path | None = None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str = "dummy"
    num_ideas: int = 8
    corpus_context_mode: str = "titles_and_abstracts"
    no_semantic_scholar: bool = True
    no_experiment_execution: bool = True
    max_papers: int = 80
    max_abstract_chars: int = 900
    max_context_chars: int = 28000
    temperature: float = 0.7
    max_tokens: int = 4096
    mock_llm: bool = False


@dataclass
class CorpusContext:
    text: str
    papers: list[dict[str, Any]]
    source_files_read: list[str]
    forbidden_input_paths_read: list[str]
    mode: str
    topic_description: str


class BaselineSafetyError(RuntimeError):
    """Raised when a requested baseline action would break safety constraints."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path, *, source_files_read: list[str], run_dir: Path) -> Any:
    guard_input_path(path, run_dir)
    source_files_read.append(str(path))
    return json.loads(path.read_text())


def load_jsonl(path: Path, *, source_files_read: list[str], run_dir: Path) -> list[dict[str, Any]]:
    guard_input_path(path, run_dir)
    source_files_read.append(str(path))
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def guard_input_path(path: Path, run_dir: Path) -> None:
    try:
        relative = path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        relative = path.resolve()
    parts = set(relative.parts)
    forbidden = sorted(parts & FORBIDDEN_INPUT_PARTS)
    if forbidden:
        raise BaselineSafetyError(
            f"Refusing to read SGHA-generated finalization artifact as baseline input: {path} "
            f"(forbidden path parts: {forbidden})"
        )


def ensure_safe_output_dir(run_dir: Path, output_dir: Path | None) -> Path:
    out = output_dir or (run_dir / DEFAULT_OUTPUT_SUBDIR)
    out = out.resolve()
    if "baselines" not in out.parts and not any("baseline" in part for part in out.parts):
        raise BaselineSafetyError(
            f"Baseline output directory must be under a baseline/baselines path segment: {out}"
        )
    forbidden_output_parts = FORBIDDEN_INPUT_PARTS - {"final"}
    if set(out.parts) & forbidden_output_parts:
        raise BaselineSafetyError(f"Refusing to write baseline output into SGHA stage/final dirs: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _paper_id(paper: dict[str, Any], idx: int) -> str:
    for key in ("paper_id", "arxiv_id", "id", "openreview_id"):
        value = paper.get(key)
        if value:
            return str(value)
    return f"paper:{idx:03d}"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def normalize_paper_record(paper: dict[str, Any], idx: int) -> dict[str, Any]:
    return {
        "paper_id": _paper_id(paper, idx),
        "title": str(paper.get("title") or paper.get("paper_title") or "Untitled paper"),
        "abstract": str(paper.get("abstract") or paper.get("summary") or ""),
        "authors": _string_list(paper.get("authors")),
        "year": paper.get("year") or paper.get("published") or paper.get("updated"),
        "venue": paper.get("venue") or paper.get("source_query"),
        "categories": _string_list(paper.get("categories")),
    }


def load_topic_description(run_dir: Path, source_files_read: list[str]) -> str:
    query_path = run_dir / "arxiv" / "query.json"
    if query_path.exists():
        data = load_json(query_path, source_files_read=source_files_read, run_dir=run_dir)
        if isinstance(data, dict):
            if data.get("topic_description"):
                return str(data["topic_description"]).strip()
            queries = data.get("queries") or []
            if queries:
                return "Topic queries: " + "; ".join(str(q) for q in queries)
    return "SGHA corpus topic inferred from selected paper titles and abstracts."


def load_corpus_papers(run_dir: Path, mode: str) -> CorpusContext:
    run_dir = run_dir.resolve()
    source_files_read: list[str] = []
    forbidden_input_paths_read: list[str] = []

    if mode == "final_report_context":
        raise BaselineSafetyError(
            "final_report_context is disabled for this baseline because it would expose SGHA-generated "
            "hypotheses/families to the external ideation baseline."
        )
    if mode not in {"titles_and_abstracts", "top_paper_summaries"}:
        raise ValueError(f"Unsupported corpus context mode: {mode}")

    topic_description = load_topic_description(run_dir, source_files_read)
    candidates = [
        run_dir / "corpus" / "selected_papers.jsonl",
        run_dir / "corpus" / "selected_papers.json",
        run_dir / "arxiv" / "papers_manifest.json",
        run_dir / "arxiv" / "selected_before_download.json",
        run_dir / "profile" / "seed_papers.jsonl",
    ]

    raw_papers: list[dict[str, Any]] = []
    selected_source: Path | None = None
    for path in candidates:
        if not path.exists():
            continue
        selected_source = path
        if path.suffix == ".jsonl":
            raw_papers = load_jsonl(path, source_files_read=source_files_read, run_dir=run_dir)
        else:
            data = load_json(path, source_files_read=source_files_read, run_dir=run_dir)
            if isinstance(data, dict):
                raw_papers = data.get("papers") or data.get("selected_papers") or []
            elif isinstance(data, list):
                raw_papers = data
            else:
                raw_papers = []
        if raw_papers:
            break

    if not raw_papers:
        raise FileNotFoundError(
            f"No selected corpus metadata found under {run_dir}; checked {[str(p) for p in candidates]}"
        )

    papers = [normalize_paper_record(p, idx + 1) for idx, p in enumerate(raw_papers)]
    context_text = build_prompt_context(
        papers=papers,
        topic_description=topic_description,
        mode=mode,
        max_papers=80,
        max_abstract_chars=900,
        max_context_chars=28000,
        selected_source=selected_source,
    )
    return CorpusContext(
        text=context_text,
        papers=papers,
        source_files_read=source_files_read,
        forbidden_input_paths_read=forbidden_input_paths_read,
        mode=mode,
        topic_description=topic_description,
    )


def truncate_text(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def build_prompt_context(
    *,
    papers: list[dict[str, Any]],
    topic_description: str,
    mode: str,
    max_papers: int,
    max_abstract_chars: int,
    max_context_chars: int,
    selected_source: Path | None,
) -> str:
    lines = [
        "# Title: SGHA Corpus Ideation Baseline",
        "",
        "## Keywords",
        "structural gap hypothesis, research ideation baseline, local corpus",
        "",
        "## TL;DR",
        "Generate research ideas using only the supplied SGHA selected-corpus context.",
        "",
        "## Abstract",
        topic_description.strip(),
        "",
        "## Baseline Input Rules",
        "- Use only the corpus context below.",
        "- Do not use SGHA final reports, Stage 7/8/9 outputs, or final project families.",
        "- Do not use Semantic Scholar or external literature search.",
        "- Do not run code or experiments.",
        "",
        "## Corpus Context",
        f"Context mode: {mode}",
        f"Corpus source file: {selected_source if selected_source else 'unknown'}",
        f"Number of selected paper records available: {len(papers)}",
        f"Number of paper records shown: {min(len(papers), max_papers)}",
        "",
    ]
    for idx, paper in enumerate(papers[:max_papers], 1):
        abstract = truncate_text(paper.get("abstract", ""), max_abstract_chars)
        authors = ", ".join(paper.get("authors") or [])
        cats = ", ".join(paper.get("categories") or [])
        lines.extend(
            [
                f"### Paper {idx}: {paper.get('title')}",
                f"- paper_id: {paper.get('paper_id')}",
                f"- year: {paper.get('year') or ''}",
                f"- venue/source: {paper.get('venue') or ''}",
                f"- authors: {authors}",
                f"- categories: {cats}",
                f"- abstract: {abstract}",
                "",
            ]
        )
        if sum(len(line) + 1 for line in lines) >= max_context_chars:
            lines.append("Context truncated deterministically at max_context_chars.")
            break
    text = "\n".join(lines).rstrip() + "\n"
    if len(text) > max_context_chars:
        text = text[:max_context_chars].rstrip() + "\n\nContext truncated deterministically at max_context_chars.\n"
    return text


def create_local_openai_client(*, base_url: str, api_key: str) -> Any:
    import openai

    return openai.OpenAI(base_url=base_url, api_key=api_key)


def _message_content(response: Any) -> str:
    msg = response.choices[0].message
    content = getattr(msg, "content", None)
    if content:
        return str(content)
    # Qwen served through vLLM with a reasoning parser can put the whole
    # response in `reasoning` if thinking is not disabled or if generation
    # stops before the final answer. Returning this lets callers include the
    # raw response in diagnostics rather than collapsing to the string "None".
    reasoning = ""
    model_extra = getattr(msg, "model_extra", None) or {}
    if isinstance(model_extra, dict):
        reasoning = model_extra.get("reasoning") or ""
    reasoning = reasoning or getattr(msg, "reasoning", "") or ""
    return str(reasoning)


def call_local_model(
    *,
    client: Any,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    content = _message_content(response).strip()
    if content:
        return content
    retry = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return strict JSON only. No markdown fences. Do not think step by step."},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return _message_content(retry).strip()


def extract_json_payload(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty LLM response")
    try:
        from sgha.json_repair import parse_json_with_repair

        parsed = parse_json_with_repair(text)
        if parsed not in (None, "", {}, []):
            return parsed
    except Exception:
        pass
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(f.strip() for f in fenced)
    first_obj = text.find("{")
    last_obj = text.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        candidates.append(text[first_obj : last_obj + 1])
    first_arr = text.find("[")
    last_arr = text.rfind("]")
    if first_arr >= 0 and last_arr > first_arr:
        candidates.append(text[first_arr : last_arr + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"Could not parse JSON from model response: {text[:500]}")


def repair_json_with_local_model(
    *,
    client: Any,
    model: str,
    malformed_text: str,
    temperature: float,
    max_tokens: int,
) -> str:
    prompt = """Repair the following malformed JSON-like research idea into exactly one valid JSON object.

Rules:
- Preserve the idea content as much as possible.
- Do not add external facts.
- Do not use Semantic Scholar.
- Do not run code.
- Return only JSON. No markdown fences.
- Include these keys if possible: Name, Title, Short Hypothesis, Related Work, Abstract, Experiments, Risk Factors and Limitations, Expected Contribution, Proposed Method or Direction.

Malformed JSON-like text:
""" + malformed_text
    return call_local_model(
        client=client,
        model=model,
        system_prompt="You repair malformed JSON into strict JSON only. No markdown fences.",
        user_prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def first_idea_from_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        if not payload:
            raise ValueError("model returned empty idea list")
        payload = payload[0]
    if isinstance(payload, dict) and "idea" in payload and isinstance(payload["idea"], dict):
        payload = payload["idea"]
    if isinstance(payload, dict) and "ideas" in payload and isinstance(payload["ideas"], list):
        if not payload["ideas"]:
            raise ValueError("model returned empty ideas list")
        payload = payload["ideas"][0]
    if not isinstance(payload, dict):
        raise ValueError(f"model response did not contain an idea object: {type(payload).__name__}")
    return payload


def _get_any(record: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            value = record[key]
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
    return default


def normalize_idea(
    raw: dict[str, Any],
    *,
    idx: int,
    model: str,
    context: CorpusContext,
) -> dict[str, Any]:
    title = _get_any(raw, ["Title", "title"], default=f"Baseline idea {idx}")
    source_context_used = {
        "corpus_context_mode": context.mode,
        "paper_count_available": len(context.papers),
        "paper_ids_shown": [p.get("paper_id") for p in context.papers[:80]],
        "source_files_read": context.source_files_read,
        "forbidden_input_paths_read": context.forbidden_input_paths_read,
        "context_sha256": sha256_text(context.text),
    }
    return {
        "idea_id": f"baseline_ai_scientist_v2_qwen_{idx:03d}",
        "title": title,
        "problem_statement": _get_any(raw, ["Problem Statement", "problem_statement", "Short Hypothesis", "short_hypothesis"]),
        "motivation": _get_any(raw, ["Motivation", "motivation", "Related Work", "related_work"]),
        "proposed_method_or_direction": _get_any(
            raw,
            ["Proposed Method or Direction", "proposed_method_or_direction", "Method", "method", "Experiments"],
        ),
        "expected_contribution": _get_any(raw, ["Expected Contribution", "expected_contribution", "Contribution", "Abstract"]),
        "evaluation_plan": _get_any(raw, ["Evaluation Plan", "evaluation_plan", "Experiments", "experiments"]),
        "risks_or_limitations": _get_any(
            raw,
            ["Risk Factors and Limitations", "risks_or_limitations", "Risks", "Limitations"],
        ),
        "source_context_used": source_context_used,
        "model": model,
        "generated_by": GENERATED_BY,
        "raw_ai_scientist_v2_style_idea": raw,
    }


def mock_idea_payload(idx: int) -> dict[str, Any]:
    return {
        "Name": f"mock_safe_idea_{idx:03d}",
        "Title": f"Mock Safe Baseline Idea {idx}",
        "Short Hypothesis": "A local-corpus-only hypothesis can be generated without external search or code execution.",
        "Related Work": "Grounded only in the supplied tiny corpus context.",
        "Abstract": "This mock idea exists to validate baseline artifact writing and safety metadata.",
        "Experiments": "Inspect the generated JSONL and audit files; do not execute experiments.",
        "Risk Factors and Limitations": "Mock output is not a scientific result.",
        "Expected Contribution": "A deterministic smoke-test artifact.",
        "Proposed Method or Direction": "Use a mocked local ideation response.",
    }


def generate_ideas(
    *,
    config: BaselineConfig,
    context: CorpusContext,
    client_factory: Callable[..., Any] = create_local_openai_client,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_events: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    client = None
    if not config.mock_llm:
        client = client_factory(base_url=config.base_url, api_key=config.api_key)

    for idx in range(1, config.num_ideas + 1):
        prev_ideas_string = "\n\n".join(json.dumps(i["raw_ai_scientist_v2_style_idea"], ensure_ascii=False) for i in ideas)
        prompt = IDEA_GENERATION_PROMPT.format(
            workshop_description=context.text,
            prev_ideas_string=prev_ideas_string or "No previous proposals.",
        )
        if config.mock_llm:
            raw = mock_idea_payload(idx)
            raw_text = json.dumps(raw)
        else:
            raw_text = call_local_model(
                client=client,
                model=config.model,
                system_prompt=BASELINE_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            repair_used = False
            parse_error = ""
            try:
                raw = first_idea_from_payload(extract_json_payload(raw_text))
            except Exception as exc:
                parse_error = str(exc)
                repaired_text = repair_json_with_local_model(
                    client=client,
                    model=config.model,
                    malformed_text=raw_text,
                    temperature=0.0,
                    max_tokens=config.max_tokens,
                )
                repair_used = True
                raw = first_idea_from_payload(extract_json_payload(repaired_text))
                raw_events.append(
                    {
                        "idea_index": idx,
                        "raw_response": raw_text,
                        "parse_error": parse_error,
                        "repair_used": repair_used,
                        "repair_response": repaired_text,
                    }
                )
                ideas.append(normalize_idea(raw, idx=idx, model=config.model, context=context))
                continue
        raw_events.append({"idea_index": idx, "raw_response": raw_text, "repair_used": False})
        ideas.append(normalize_idea(raw, idx=idx, model=config.model, context=context))
    return ideas, raw_events


def write_outputs(
    *,
    output_dir: Path,
    config: BaselineConfig,
    context: CorpusContext,
    ideas: list[dict[str, Any]],
    raw_events: list[dict[str, Any]],
) -> dict[str, Path]:
    jsonl_path = output_dir / "baseline_ideas.jsonl"
    md_path = output_dir / "baseline_ideas.md"
    context_path = output_dir / "baseline_prompt_context.md"
    metadata_path = output_dir / "baseline_run_metadata.json"
    audit_path = output_dir / "baseline_quality_audit.md"

    jsonl_path.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in ideas) + ("\n" if ideas else ""))
    context_path.write_text(context.text)

    md_lines = ["# AI-Scientist-v2 Ideation Baseline Ideas", ""]
    for idea in ideas:
        md_lines.extend(
            [
                f"## {idea['idea_id']}: {idea['title']}",
                "",
                f"- model: {idea['model']}",
                f"- generated_by: {idea['generated_by']}",
                "",
                "### Problem Statement",
                "",
                idea.get("problem_statement", ""),
                "",
                "### Motivation",
                "",
                idea.get("motivation", ""),
                "",
                "### Proposed Method or Direction",
                "",
                idea.get("proposed_method_or_direction", ""),
                "",
                "### Expected Contribution",
                "",
                idea.get("expected_contribution", ""),
                "",
                "### Evaluation Plan",
                "",
                idea.get("evaluation_plan", ""),
                "",
                "### Risks or Limitations",
                "",
                idea.get("risks_or_limitations", ""),
                "",
            ]
        )
    md_path.write_text("\n".join(md_lines).rstrip() + "\n")

    metadata = {
        "generated_by": GENERATED_BY,
        "created_at": utc_now_iso(),
        "run_dir": str(config.run_dir.resolve()),
        "output_dir": str(output_dir),
        "model": config.model,
        "base_url": config.base_url,
        "num_ideas_requested": config.num_ideas,
        "num_ideas_written": len(ideas),
        "corpus_context_mode": config.corpus_context_mode,
        "semantic_scholar_enabled": False,
        "experiment_execution_enabled": False,
        "generated_code_execution_enabled": False,
        "plotting_enabled": False,
        "writeup_enabled": False,
        "review_enabled": False,
        "output_count_matched": True,
        "information_matched": False,
        "compute_matched": False,
        "same_model": True,
        "same_corpus_metadata_source": True,
        "full_ai_scientist_pipeline_used": False,
        "ai_scientist_ideation_only": True,
        "ai_scientist_v2_clone_path": str((Path(__file__).resolve().parents[1] / "external_baselines" / "AI-Scientist-v2").resolve()),
        "ai_scientist_v2_reuse_note": AI_SCIENTIST_V2_REUSE_NOTE,
        "source_files_read": context.source_files_read,
        "forbidden_input_paths_read": context.forbidden_input_paths_read,
        "prompt_context_sha256": sha256_text(context.text),
        "raw_generation_events": raw_events,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    status = "PASS"
    warnings: list[str] = []
    if not ideas:
        status = "FAIL"
        warnings.append("no ideas generated")
    if context.forbidden_input_paths_read:
        status = "FAIL"
        warnings.append("forbidden SGHA finalization inputs were read")
    missing_required = [
        idea["idea_id"]
        for idea in ideas
        if not all(idea.get(k) for k in ["title", "problem_statement", "evaluation_plan", "model", "generated_by"])
    ]
    if missing_required:
        status = "WARN" if status == "PASS" else status
        warnings.append(f"ideas with missing recommended fields: {missing_required}")

    audit_lines = [
        "# AI-Scientist-v2 Ideation Baseline Quality Audit",
        "",
        f"- status: {status}",
        f"- ideas_written: {len(ideas)}",
        f"- semantic_scholar_enabled: false",
        f"- experiment_execution_enabled: false",
        f"- generated_code_execution_enabled: false",
        f"- plotting_enabled: false",
        f"- writeup_enabled: false",
        f"- review_enabled: false",
        f"- forbidden_input_paths_read: {len(context.forbidden_input_paths_read)}",
        f"- output_under_baseline_path: {'baselines' in output_dir.parts or any('baseline' in part for part in output_dir.parts)}",
        "- output_count_matched: true",
        "- information_matched: false",
        "- compute_matched: false",
        "- same_model: true",
        "- same_corpus_metadata_source: true",
        "- full_ai_scientist_pipeline_used: false",
        "- ai_scientist_ideation_only: true",
        f"- model: {config.model}",
        f"- base_url: {config.base_url}",
        "",
        "## Warnings",
        "",
    ]
    audit_lines.extend(f"- {w}" for w in warnings)
    if not warnings:
        audit_lines.append("- none")
    audit_path.write_text("\n".join(audit_lines).rstrip() + "\n")

    return {
        "jsonl": jsonl_path,
        "markdown": md_path,
        "context": context_path,
        "metadata": metadata_path,
        "audit": audit_path,
    }


def run_baseline(
    config: BaselineConfig,
    *,
    client_factory: Callable[..., Any] = create_local_openai_client,
) -> dict[str, Any]:
    if not config.no_semantic_scholar:
        raise BaselineSafetyError("Semantic Scholar must remain disabled for this baseline.")
    if not config.no_experiment_execution:
        raise BaselineSafetyError("Experiment execution must remain disabled for this baseline.")

    output_dir = ensure_safe_output_dir(config.run_dir, config.output_dir)
    context = load_corpus_papers(config.run_dir, config.corpus_context_mode)
    context.text = build_prompt_context(
        papers=context.papers,
        topic_description=context.topic_description,
        mode=config.corpus_context_mode,
        max_papers=config.max_papers,
        max_abstract_chars=config.max_abstract_chars,
        max_context_chars=config.max_context_chars,
        selected_source=Path(context.source_files_read[-1]) if context.source_files_read else None,
    )
    ideas, raw_events = generate_ideas(config=config, context=context, client_factory=client_factory)
    paths = write_outputs(output_dir=output_dir, config=config, context=context, ideas=ideas, raw_events=raw_events)
    return {
        "output_dir": output_dir,
        "ideas": ideas,
        "paths": paths,
        "context": context,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an ideation-only AI-Scientist-v2-style baseline on an SGHA corpus.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--num-ideas", type=int, default=8)
    parser.add_argument(
        "--corpus-context-mode",
        choices=["titles_and_abstracts", "final_report_context", "top_paper_summaries"],
        default="titles_and_abstracts",
    )
    parser.add_argument("--no-semantic-scholar", action="store_true", default=True)
    parser.add_argument("--no-experiment-execution", action="store_true", default=True)
    parser.add_argument("--max-papers", type=int, default=80)
    parser.add_argument("--max-abstract-chars", type=int, default=900)
    parser.add_argument("--max-context-chars", type=int, default=28000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--mock-llm", action="store_true", help="Use deterministic mock ideas instead of calling vLLM.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = BaselineConfig(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        num_ideas=args.num_ideas,
        corpus_context_mode=args.corpus_context_mode,
        no_semantic_scholar=True,
        no_experiment_execution=True,
        max_papers=args.max_papers,
        max_abstract_chars=args.max_abstract_chars,
        max_context_chars=args.max_context_chars,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        mock_llm=args.mock_llm,
    )
    result = run_baseline(config)
    print(f"Baseline output directory: {result['output_dir']}")
    for name, path in result["paths"].items():
        print(f"{name}: {path}")
    print(f"Ideas written: {len(result['ideas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
