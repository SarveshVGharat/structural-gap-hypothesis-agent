#!/usr/bin/env python3
"""Simple local-Qwen ideation baseline for SGHA paper-domain runs.

This baseline is intentionally shallow: it prompts Qwen with selected corpus
metadata only. It does not read SGHA extraction tuples, graph/gap/novelty/
verification outputs, final reports, or any downstream SGHA formulation stages.
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


GENERATED_BY = "simple_qwen_ideation"
DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_BASE_URL = os.environ.get("SGHA_LLM_BASE_URL", "http://localhost:8000/v1")
DEFAULT_OUTPUT_SUBDIR = Path("baselines") / "simple_qwen"

FORBIDDEN_INPUT_PARTS = {
    "final_sgha_family_report",
    "final_report_polished.md",
    "final_project_families.json",
    "stage7_direct_formulations",
    "stage8_ambition_expansion",
    "stage9_family_quality",
    "stage10_formal_problem_formulations",
    "verification",
    "novelty",
    "gaps",
    "graph",
    "comparisons",
    "legacy_evolution_report",
    "final_evolution_report",
}


SYSTEM_PROMPT = """You are a careful ML research ideation baseline.

Generate one research idea using only the supplied paper-corpus metadata.

Rules:
- Do not use external search, Semantic Scholar, OpenAlex, WebSearch, Google Scholar, citations, or related-paper expansion.
- Do not run code or experiments.
- Do not claim novelty is proven.
- Ground the idea in the supplied titles, abstracts, venue/year/source metadata, and topic description.
- Return exactly one JSON object. No Markdown fences.

Required JSON keys:
- "title"
- "problem_statement"
- "motivation"
- "proposed_method_or_direction"
- "expected_contribution"
- "evaluation_plan"
- "risks_or_limitations"
- "top_source_papers_or_context_items"
"""


IDEA_PROMPT = """{corpus_context}

Previously generated baseline ideas:
'''
{previous_ideas}
'''

Generate one new, distinct, source-grounded research idea for this domain.
Return only a JSON object with the required keys.
"""


@dataclass
class BaselineConfig:
    run_dir: Path
    output_dir: Path | None = None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str = "dummy"
    num_ideas: int = 1
    context_mode: str = "titles_and_abstracts"
    no_external_search: bool = True
    no_experiment_execution: bool = True
    no_generated_code_execution: bool = True
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
    topic_description: str
    input_files_read: list[str]
    forbidden_inputs_read: list[str]
    context_mode: str
    approximate_input_tokens: int


class BaselineSafetyError(RuntimeError):
    """Raised when a baseline action would read/write unsafe SGHA artifacts."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approximate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def guard_input_path(path: Path) -> None:
    parts = set(path.resolve().parts) | {path.name}
    forbidden = sorted(parts & FORBIDDEN_INPUT_PARTS)
    if forbidden:
        raise BaselineSafetyError(
            f"Refusing to read forbidden SGHA downstream artifact: {path} "
            f"(matched: {forbidden})"
        )


def ensure_safe_output_dir(run_dir: Path, output_dir: Path | None) -> Path:
    out = output_dir or (run_dir / DEFAULT_OUTPUT_SUBDIR)
    out = out.resolve()
    if "baselines" not in out.parts and not any("baseline" in part for part in out.parts):
        raise BaselineSafetyError(
            f"Baseline output directory must include a baseline/baselines path segment: {out}"
        )
    forbidden = sorted((set(out.parts) | {out.name}) & FORBIDDEN_INPUT_PARTS)
    if forbidden:
        raise BaselineSafetyError(f"Refusing to write baseline outputs under forbidden SGHA paths: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_json(path: Path, input_files_read: list[str]) -> Any:
    guard_input_path(path)
    input_files_read.append(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path, input_files_read: list[str]) -> list[dict[str, Any]]:
    guard_input_path(path)
    input_files_read.append(str(path))
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _paper_id(paper: dict[str, Any], idx: int) -> str:
    for key in ("paper_id", "arxiv_id", "openreview_id", "id"):
        value = paper.get(key)
        if value:
            return str(value)
    return f"paper:{idx:03d}"


def normalize_paper_record(paper: dict[str, Any], idx: int) -> dict[str, Any]:
    return {
        "paper_id": _paper_id(paper, idx),
        "title": str(paper.get("title") or paper.get("paper_title") or "Untitled paper"),
        "abstract": str(paper.get("abstract") or paper.get("summary") or ""),
        "authors": _string_list(paper.get("authors")),
        "year": paper.get("year") or paper.get("published") or paper.get("updated"),
        "venue": paper.get("venue") or paper.get("source_query") or paper.get("source"),
        "categories": _string_list(paper.get("categories")),
    }


def load_topic_description(run_dir: Path, input_files_read: list[str]) -> str:
    query_path = run_dir / "arxiv" / "query.json"
    if query_path.exists():
        data = load_json(query_path, input_files_read)
        if isinstance(data, dict):
            if data.get("topic_description"):
                return str(data["topic_description"]).strip()
            queries = data.get("queries") or []
            if queries:
                return "Topic queries: " + "; ".join(str(q) for q in queries)
    return "Research topic inferred from selected corpus metadata."


def load_selected_papers(run_dir: Path, input_files_read: list[str]) -> tuple[list[dict[str, Any]], Path]:
    candidates = [
        run_dir / "corpus" / "selected_papers.jsonl",
        run_dir / "corpus" / "selected_papers.json",
        run_dir / "arxiv" / "papers_manifest.json",
        run_dir / "arxiv" / "selected_before_download.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            rows = load_jsonl(path, input_files_read)
        else:
            data = load_json(path, input_files_read)
            if isinstance(data, dict):
                rows = data.get("papers") or data.get("selected_papers") or []
            elif isinstance(data, list):
                rows = data
            else:
                rows = []
        if rows:
            return [normalize_paper_record(p, idx + 1) for idx, p in enumerate(rows)], path
    raise FileNotFoundError(f"No selected corpus metadata found under {run_dir}")


def truncate_text(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def build_prompt_context(
    *,
    papers: list[dict[str, Any]],
    topic_description: str,
    context_mode: str,
    selected_source: Path,
    max_papers: int,
    max_abstract_chars: int,
    max_context_chars: int,
) -> str:
    lines = [
        "# Simple Qwen Corpus Ideation Baseline",
        "",
        "## Topic Description",
        topic_description.strip(),
        "",
        "## Input Rules",
        "- Use only the selected-corpus metadata below.",
        "- Do not use SGHA graph, gap, novelty, verification, direct formulation, ambition, family, formal-problem, final-report, or evolution outputs.",
        "- Do not use external search or citation crawling.",
        "",
        "## Corpus Metadata",
        f"- context_mode: {context_mode}",
        f"- selected_source_file: {selected_source}",
        f"- selected_papers_available: {len(papers)}",
        f"- selected_papers_shown: {min(len(papers), max_papers)}",
        "",
    ]
    for idx, paper in enumerate(papers[:max_papers], 1):
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
                f"- abstract: {truncate_text(paper.get('abstract', ''), max_abstract_chars)}",
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


def load_corpus_context(config: BaselineConfig) -> CorpusContext:
    if config.context_mode != "titles_and_abstracts":
        raise ValueError(f"Unsupported Simple Qwen context mode: {config.context_mode}")
    input_files_read: list[str] = []
    run_dir = config.run_dir.resolve()
    topic_description = load_topic_description(run_dir, input_files_read)
    papers, selected_source = load_selected_papers(run_dir, input_files_read)
    text = build_prompt_context(
        papers=papers,
        topic_description=topic_description,
        context_mode=config.context_mode,
        selected_source=selected_source,
        max_papers=config.max_papers,
        max_abstract_chars=config.max_abstract_chars,
        max_context_chars=config.max_context_chars,
    )
    return CorpusContext(
        text=text,
        papers=papers,
        topic_description=topic_description,
        input_files_read=input_files_read,
        forbidden_inputs_read=[],
        context_mode=config.context_mode,
        approximate_input_tokens=approximate_tokens(text),
    )


def create_local_openai_client(*, base_url: str, api_key: str) -> Any:
    import openai

    return openai.OpenAI(base_url=base_url, api_key=api_key)


def _message_content(response: Any) -> str:
    msg = response.choices[0].message
    content = getattr(msg, "content", None)
    if content:
        return str(content)
    model_extra = getattr(msg, "model_extra", None) or {}
    reasoning = model_extra.get("reasoning") if isinstance(model_extra, dict) else ""
    return str(reasoning or getattr(msg, "reasoning", "") or "")


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
            {"role": "system", "content": "Return strict JSON only. No markdown fences."},
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
    candidates.extend(m.strip() for m in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.I | re.S))
    first_obj, last_obj = text.find("{"), text.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        candidates.append(text[first_obj : last_obj + 1])
    first_arr, last_arr = text.find("["), text.rfind("]")
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
    prompt = """Repair this malformed JSON-like research idea into exactly one valid JSON object.

Preserve the idea content. Do not add external facts. Return only JSON.

Malformed response:
""" + malformed_text
    return call_local_model(
        client=client,
        model=model,
        system_prompt="You repair malformed JSON into strict JSON only.",
        user_prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def first_idea_from_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        if not payload:
            raise ValueError("model returned an empty idea list")
        payload = payload[0]
    if isinstance(payload, dict) and isinstance(payload.get("idea"), dict):
        payload = payload["idea"]
    if isinstance(payload, dict) and isinstance(payload.get("ideas"), list):
        if not payload["ideas"]:
            raise ValueError("model returned an empty ideas list")
        payload = payload["ideas"][0]
    if not isinstance(payload, dict):
        raise ValueError(f"model response did not contain an idea object: {type(payload).__name__}")
    return payload


def _get_any(record: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
    return default


def _get_list(record: dict[str, Any], keys: list[str], default: list[str]) -> list[str]:
    for key in keys:
        value = record.get(key)
        if isinstance(value, list) and value:
            return [str(v) for v in value]
        if value not in (None, "", [], {}):
            return [str(value)]
    return default


def mock_idea_payload(idx: int) -> dict[str, Any]:
    return {
        "title": f"Mock Simple Qwen Idea {idx}",
        "problem_statement": "A corpus-only baseline can propose a research direction without downstream SGHA artifacts.",
        "motivation": "This mock idea is grounded only in the supplied selected-paper metadata.",
        "proposed_method_or_direction": "Define a lightweight study over the provided corpus context.",
        "expected_contribution": "A deterministic smoke-test baseline artifact.",
        "evaluation_plan": "Validate that the JSONL, metadata, and audit files are written.",
        "risks_or_limitations": "Mock output is not a scientific result.",
        "top_source_papers_or_context_items": [f"mock_context_item_{idx}"],
    }


def normalize_idea(
    raw: dict[str, Any],
    *,
    idx: int,
    config: BaselineConfig,
    context: CorpusContext,
) -> dict[str, Any]:
    default_sources = [str(p.get("paper_id")) for p in context.papers[:5]]
    source_context_used = {
        "context_mode": context.context_mode,
        "paper_count_available": len(context.papers),
        "paper_ids_shown": [p.get("paper_id") for p in context.papers[: config.max_papers]],
        "input_files_read": context.input_files_read,
        "context_sha256": sha256_text(context.text),
    }
    return {
        "idea_id": f"simple_qwen_{idx:03d}",
        "title": _get_any(raw, ["title", "Title"], f"Simple Qwen idea {idx}"),
        "problem_statement": _get_any(raw, ["problem_statement", "Problem Statement", "Short Hypothesis"]),
        "motivation": _get_any(raw, ["motivation", "Motivation", "Related Work"]),
        "proposed_method_or_direction": _get_any(
            raw,
            ["proposed_method_or_direction", "Proposed Method or Direction", "Method", "Experiments"],
        ),
        "expected_contribution": _get_any(raw, ["expected_contribution", "Expected Contribution", "Abstract"]),
        "evaluation_plan": _get_any(raw, ["evaluation_plan", "Evaluation Plan", "Experiments"]),
        "risks_or_limitations": _get_any(raw, ["risks_or_limitations", "Risk Factors and Limitations", "Risks"]),
        "top_source_papers_or_context_items": _get_list(
            raw,
            ["top_source_papers_or_context_items", "Top Source Papers or Context Items", "source_papers"],
            default_sources,
        ),
        "source_context_used": source_context_used,
        "model": config.model,
        "generated_by": GENERATED_BY,
        "context_mode": config.context_mode,
        "output_count_matched": True,
        "external_search_used": False,
        "code_execution_used": False,
        "raw_simple_qwen_idea": raw,
    }


def generate_ideas(
    *,
    config: BaselineConfig,
    context: CorpusContext,
    client_factory: Callable[..., Any] = create_local_openai_client,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    client = None if config.mock_llm else client_factory(base_url=config.base_url, api_key=config.api_key)
    ideas: list[dict[str, Any]] = []
    raw_events: list[dict[str, Any]] = []
    llm_call_count = 0
    output_token_estimate = 0
    for idx in range(1, config.num_ideas + 1):
        previous = "\n\n".join(json.dumps(i["raw_simple_qwen_idea"], ensure_ascii=False) for i in ideas)
        prompt = IDEA_PROMPT.format(corpus_context=context.text, previous_ideas=previous or "No previous ideas.")
        repair_used = False
        parse_error = ""
        if config.mock_llm:
            raw_text = json.dumps(mock_idea_payload(idx))
        else:
            raw_text = call_local_model(
                client=client,
                model=config.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            llm_call_count += 1
        try:
            raw = first_idea_from_payload(extract_json_payload(raw_text))
        except Exception as exc:
            if config.mock_llm:
                raise
            parse_error = str(exc)
            repaired_text = repair_json_with_local_model(
                client=client,
                model=config.model,
                malformed_text=raw_text,
                temperature=0.0,
                max_tokens=config.max_tokens,
            )
            llm_call_count += 1
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
        else:
            raw_events.append({"idea_index": idx, "raw_response": raw_text, "repair_used": repair_used})
        output_token_estimate += approximate_tokens(raw_text)
        ideas.append(normalize_idea(raw, idx=idx, config=config, context=context))
    return ideas, raw_events, llm_call_count, output_token_estimate


def write_outputs(
    *,
    output_dir: Path,
    config: BaselineConfig,
    context: CorpusContext,
    ideas: list[dict[str, Any]],
    raw_events: list[dict[str, Any]],
    llm_call_count: int,
    approximate_output_tokens: int,
) -> dict[str, Path]:
    jsonl_path = output_dir / "baseline_ideas.jsonl"
    md_path = output_dir / "baseline_ideas.md"
    context_path = output_dir / "baseline_prompt_context.md"
    metadata_path = output_dir / "baseline_run_metadata.json"
    audit_path = output_dir / "baseline_quality_audit.md"

    jsonl_path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in ideas), encoding="utf-8")
    context_path.write_text(context.text, encoding="utf-8")

    md_lines = ["# Simple Qwen Ideation Baseline Ideas", ""]
    for idea in ideas:
        md_lines.extend(
            [
                f"## {idea['idea_id']}: {idea['title']}",
                "",
                f"- model: {idea['model']}",
                f"- generated_by: {idea['generated_by']}",
                f"- context_mode: {idea['context_mode']}",
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
                "### Top Source Papers or Context Items",
                "",
                "\n".join(f"- {x}" for x in idea.get("top_source_papers_or_context_items", [])),
                "",
            ]
        )
    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    output_count_matched = len(ideas) == config.num_ideas
    metadata = {
        "baseline_name": "Simple Qwen ideation",
        "generated_by": GENERATED_BY,
        "created_at": utc_now_iso(),
        "run_dir": str(config.run_dir.resolve()),
        "output_dir": str(output_dir),
        "model": config.model,
        "base_url": config.base_url,
        "num_ideas_requested": config.num_ideas,
        "num_ideas_generated": len(ideas),
        "output_count_matched": output_count_matched,
        "same_model": config.model == DEFAULT_MODEL,
        "same_corpus_metadata_source": True,
        "information_matched": False,
        "compute_matched": False,
        "context_mode": config.context_mode,
        "input_files_read": context.input_files_read,
        "forbidden_inputs_checked": sorted(FORBIDDEN_INPUT_PARTS),
        "forbidden_inputs_read": context.forbidden_inputs_read,
        "forbidden_inputs_not_used": len(context.forbidden_inputs_read) == 0,
        "external_search_used": False,
        "semantic_scholar_used": False,
        "openalex_used": False,
        "websearch_used": False,
        "google_scholar_used": False,
        "citation_crawling_used": False,
        "experiment_execution_used": False,
        "generated_code_execution_used": False,
        "code_execution_used": False,
        "llm_call_count": llm_call_count,
        "approximate_input_tokens": context.approximate_input_tokens,
        "approximate_output_tokens": approximate_output_tokens,
        "raw_generation_events": raw_events,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    status = "PASS"
    warnings: list[str] = []
    if not output_count_matched:
        status = "FAIL"
        warnings.append("generated idea count does not match requested output count")
    if context.forbidden_inputs_read:
        status = "FAIL"
        warnings.append(f"forbidden inputs were read: {context.forbidden_inputs_read}")
    missing_required = [
        idea["idea_id"]
        for idea in ideas
        if not all(idea.get(k) for k in ["title", "problem_statement", "evaluation_plan", "model"])
    ]
    if missing_required:
        status = "WARN" if status == "PASS" else status
        warnings.append(f"ideas with missing recommended fields: {missing_required}")

    audit_lines = [
        "# Simple Qwen Ideation Baseline Quality Audit",
        "",
        f"- status: {status}",
        f"- ideas_written: {len(ideas)}",
        f"- output_count_matched: {str(output_count_matched).lower()}",
        f"- same_model: {str(metadata['same_model']).lower()}",
        "- same_corpus_metadata_source: true",
        "- information_matched: false",
        "- compute_matched: false",
        f"- context_mode: {config.context_mode}",
        "- external_search_used: false",
        "- semantic_scholar_used: false",
        "- openalex_used: false",
        "- websearch_used: false",
        "- google_scholar_used: false",
        "- citation_crawling_used: false",
        "- experiment_execution_used: false",
        "- generated_code_execution_used: false",
        "- code_execution_used: false",
        f"- forbidden_inputs_checked: {len(FORBIDDEN_INPUT_PARTS)}",
        f"- forbidden_inputs_not_used: {str(metadata['forbidden_inputs_not_used']).lower()}",
        f"- forbidden_inputs_read: {len(context.forbidden_inputs_read)}",
        f"- llm_call_count: {llm_call_count}",
        f"- approximate_input_tokens: {context.approximate_input_tokens}",
        f"- approximate_output_tokens: {approximate_output_tokens}",
        "",
        "## Warnings",
        "",
    ]
    audit_lines.extend(f"- {w}" for w in warnings)
    if not warnings:
        audit_lines.append("- none")
    audit_path.write_text("\n".join(audit_lines).rstrip() + "\n", encoding="utf-8")

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
    if not config.no_external_search:
        raise BaselineSafetyError("External search must remain disabled for Simple Qwen baseline.")
    if not config.no_experiment_execution:
        raise BaselineSafetyError("Experiment execution must remain disabled for Simple Qwen baseline.")
    if not config.no_generated_code_execution:
        raise BaselineSafetyError("Generated-code execution must remain disabled for Simple Qwen baseline.")
    output_dir = ensure_safe_output_dir(config.run_dir, config.output_dir)
    context = load_corpus_context(config)
    ideas, raw_events, llm_call_count, approximate_output_tokens = generate_ideas(
        config=config,
        context=context,
        client_factory=client_factory,
    )
    paths = write_outputs(
        output_dir=output_dir,
        config=config,
        context=context,
        ideas=ideas,
        raw_events=raw_events,
        llm_call_count=llm_call_count,
        approximate_output_tokens=approximate_output_tokens,
    )
    return {"output_dir": output_dir, "ideas": ideas, "paths": paths, "context": context}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Simple Qwen ideation baseline on SGHA corpus metadata.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--num-ideas", type=int, required=True)
    parser.add_argument("--context-mode", choices=["titles_and_abstracts"], default="titles_and_abstracts")
    parser.add_argument("--no-external-search", action="store_true", default=True)
    parser.add_argument("--no-experiment-execution", action="store_true", default=True)
    parser.add_argument("--no-generated-code-execution", action="store_true", default=True)
    parser.add_argument("--max-papers", type=int, default=80)
    parser.add_argument("--max-abstract-chars", type=int, default=900)
    parser.add_argument("--max-context-chars", type=int, default=28000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--mock-llm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_baseline(
        BaselineConfig(
            run_dir=args.run_dir,
            output_dir=args.output_dir,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            num_ideas=args.num_ideas,
            context_mode=args.context_mode,
            no_external_search=True,
            no_experiment_execution=True,
            no_generated_code_execution=True,
            max_papers=args.max_papers,
            max_abstract_chars=args.max_abstract_chars,
            max_context_chars=args.max_context_chars,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            mock_llm=args.mock_llm,
        )
    )
    print(f"Baseline output directory: {result['output_dir']}")
    for name, path in result["paths"].items():
        print(f"{name}: {path}")
    print(f"Ideas written: {len(result['ideas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
