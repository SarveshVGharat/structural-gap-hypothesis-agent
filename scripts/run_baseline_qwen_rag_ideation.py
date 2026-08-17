#!/usr/bin/env python3
"""Local Qwen+RAG ideation baseline for SGHA paper-domain runs.

This baseline builds a deterministic local lexical index over parsed paper text
from the selected corpus. It does not use SGHA extraction tuples, graph/gap/
novelty/verification outputs, final reports, or downstream formulation stages.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_baseline_simple_qwen_ideation import (  # noqa: E402
    BaselineSafetyError,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    FORBIDDEN_INPUT_PARTS,
    approximate_tokens,
    call_local_model,
    create_local_openai_client,
    ensure_safe_output_dir,
    extract_json_payload,
    first_idea_from_payload,
    guard_input_path,
    load_json,
    load_selected_papers,
    load_topic_description,
    repair_json_with_local_model,
    sha256_text,
    truncate_text,
    utc_now_iso,
)


GENERATED_BY = "qwen_rag_ideation"
DEFAULT_OUTPUT_SUBDIR = Path("baselines") / "qwen_rag"

SYSTEM_PROMPT = """You are a careful ML research ideation baseline using local RAG over a selected paper corpus.

Generate one research idea using only the supplied retrieved paper chunks and metadata.

Rules:
- Do not use external search, Semantic Scholar, OpenAlex, WebSearch, Google Scholar, citations, or related-paper expansion.
- Do not run code or experiments.
- Do not claim novelty is proven.
- Ground the idea in the retrieved corpus chunks.
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


IDEA_PROMPT = """{rag_context}

Previously generated baseline ideas:
'''
{previous_ideas}
'''

Generate one new, distinct, source-grounded research idea for this domain using the retrieved local paper chunks.
Return only a JSON object with the required keys.
"""


@dataclass
class RagConfig:
    run_dir: Path
    output_dir: Path | None = None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str = "dummy"
    num_ideas: int = 1
    chunk_source: str = "parsed_text"
    retrieval_method: str = "bm25_or_tfidf"
    top_k: int = 20
    chunk_size: int = 1200
    chunk_overlap: int = 150
    no_external_search: bool = True
    no_experiment_execution: bool = True
    no_generated_code_execution: bool = True
    max_context_chars: int = 30000
    temperature: float = 0.7
    max_tokens: int = 4096
    mock_llm: bool = False


@dataclass
class RagContext:
    text: str
    retrieved_chunks: list[dict[str, Any]]
    all_chunks: list[dict[str, Any]]
    papers: list[dict[str, Any]]
    topic_description: str
    input_files_read: list[str]
    forbidden_inputs_read: list[str]
    approximate_input_tokens: int


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", text.lower()) if len(t) > 2]


def resolve_text_path(path_value: Any, run_dir: Path) -> Path | None:
    if not path_value:
        return None
    path = Path(str(path_value))
    return path if path.is_absolute() else (run_dir / path)


def load_parsed_manifest(run_dir: Path, input_files_read: list[str]) -> list[dict[str, Any]]:
    path = run_dir / "parsed" / "parsed_manifest.json"
    if not path.exists():
        return []
    data = load_json(path, input_files_read)
    return data if isinstance(data, list) else []


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int, str]]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[tuple[int, int, str]] = []
    step = max(1, chunk_size - chunk_overlap)
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append((start, end, text[start:end]))
        if end >= len(text):
            break
        start += step
    return chunks


def build_chunks(
    *,
    run_dir: Path,
    papers: list[dict[str, Any]],
    parsed_manifest: list[dict[str, Any]],
    input_files_read: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    paper_meta = {p.get("paper_id"): p for p in papers}
    chunks: list[dict[str, Any]] = []
    for parsed in parsed_manifest:
        paper_id = str(parsed.get("paper_id") or parsed.get("arxiv_id") or "")
        text_path = resolve_text_path(parsed.get("text_path"), run_dir)
        if not text_path or not text_path.exists():
            continue
        guard_input_path(text_path)
        input_files_read.append(str(text_path))
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        meta = paper_meta.get(paper_id, {})
        title = str(meta.get("title") or parsed.get("title") or paper_id or "Untitled paper")
        for local_idx, (start, end, excerpt) in enumerate(
            chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            1,
        ):
            chunks.append(
                {
                    "context_id": f"chunk:{len(chunks) + 1:06d}",
                    "paper_id": paper_id or f"paper_unknown:{len(chunks) + 1}",
                    "title": title,
                    "year": meta.get("year") or parsed.get("year"),
                    "venue": meta.get("venue") or parsed.get("venue"),
                    "source_text_path": str(text_path),
                    "local_chunk_index": local_idx,
                    "char_start": start,
                    "char_end": end,
                    "text": excerpt,
                }
            )
    if chunks:
        return chunks

    # Fallback to abstracts if parsed text is unavailable. This keeps the RAG
    # baseline runnable while recording that no parsed chunks were found.
    for idx, paper in enumerate(papers, 1):
        text = " ".join(str(paper.get(k) or "") for k in ["title", "abstract"])
        if not text.strip():
            continue
        chunks.append(
            {
                "context_id": f"abstract:{idx:06d}",
                "paper_id": paper.get("paper_id") or f"paper:{idx:03d}",
                "title": paper.get("title") or "Untitled paper",
                "year": paper.get("year"),
                "venue": paper.get("venue"),
                "source_text_path": "abstract_metadata_fallback",
                "local_chunk_index": 1,
                "char_start": 0,
                "char_end": len(text),
                "text": truncate_text(text, chunk_size),
            }
        )
    return chunks


def retrieve_chunks(
    *,
    chunks: list[dict[str, Any]],
    topic_description: str,
    top_k: int,
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    query_text = (
        topic_description
        + " research gap limitation assumption failure mode open problem benchmark evaluation theoretical guarantee robustness"
    )
    query_terms = tokenize(query_text)
    query_counts = Counter(query_terms)
    chunk_terms = [tokenize(str(c.get("title", "")) + " " + str(c.get("text", ""))) for c in chunks]
    doc_freq: Counter[str] = Counter()
    for terms in chunk_terms:
        doc_freq.update(set(terms))
    n_docs = len(chunks)
    avg_len = sum(len(t) for t in chunk_terms) / max(1, n_docs)
    k1 = 1.5
    b = 0.75
    scores: list[tuple[float, int]] = []
    for idx, terms in enumerate(chunk_terms):
        if not terms:
            continue
        counts = Counter(terms)
        dl = len(terms)
        score = 0.0
        for term, qtf in query_counts.items():
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = tf + k1 * (1 - b + b * dl / max(avg_len, 1.0))
            score += qtf * idf * (tf * (k1 + 1)) / denom
        if score > 0:
            scores.append((score, idx))
    if not scores:
        scores = [(1.0 / (idx + 1), idx) for idx in range(min(len(chunks), top_k))]
    scores.sort(key=lambda x: (-x[0], x[1]))
    retrieved: list[dict[str, Any]] = []
    seen_papers: defaultdict[str, int] = defaultdict(int)
    for score, idx in scores:
        row = dict(chunks[idx])
        pid = str(row.get("paper_id"))
        if seen_papers[pid] >= 3:
            continue
        seen_papers[pid] += 1
        row["retrieval_score"] = round(score, 6)
        retrieved.append(row)
        if len(retrieved) >= top_k:
            break
    return retrieved


def build_rag_prompt_context(
    *,
    topic_description: str,
    retrieved_chunks: list[dict[str, Any]],
    all_chunks: list[dict[str, Any]],
    config: RagConfig,
) -> str:
    lines = [
        "# Qwen+RAG Paper Ideation Baseline",
        "",
        "## Topic Description",
        topic_description.strip(),
        "",
        "## Input Rules",
        "- Use only the retrieved local paper chunks below.",
        "- Do not use SGHA extraction tuples, graph, gap, novelty, verification, direct formulation, ambition, family, formal-problem, final-report, comparison, or evolution outputs.",
        "- Do not use external search, citation crawling, generated-code execution, plotting, paper writing, or review loops.",
        "",
        "## Retrieval Metadata",
        f"- chunk_source: {config.chunk_source}",
        f"- retrieval_method: {config.retrieval_method}",
        f"- top_k: {config.top_k}",
        f"- chunk_size: {config.chunk_size}",
        f"- chunk_overlap: {config.chunk_overlap}",
        f"- total_chunks_indexed: {len(all_chunks)}",
        f"- retrieved_chunks_shown: {len(retrieved_chunks)}",
        "",
        "## Retrieved Corpus Chunks",
        "",
    ]
    for chunk in retrieved_chunks:
        lines.extend(
            [
                f"### {chunk['context_id']}: {chunk.get('title')}",
                f"- paper_id: {chunk.get('paper_id')}",
                f"- year: {chunk.get('year') or ''}",
                f"- venue/source: {chunk.get('venue') or ''}",
                f"- retrieval_score: {chunk.get('retrieval_score')}",
                f"- excerpt: {truncate_text(chunk.get('text', ''), config.chunk_size)}",
                "",
            ]
        )
        if sum(len(line) + 1 for line in lines) >= config.max_context_chars:
            lines.append("Retrieved context truncated deterministically at max_context_chars.")
            break
    text = "\n".join(lines).rstrip() + "\n"
    if len(text) > config.max_context_chars:
        text = text[: config.max_context_chars].rstrip() + "\n\nRetrieved context truncated deterministically at max_context_chars.\n"
    return text


def load_rag_context(config: RagConfig) -> RagContext:
    if config.chunk_source != "parsed_text":
        raise ValueError(f"Unsupported chunk source: {config.chunk_source}")
    if config.retrieval_method != "bm25_or_tfidf":
        raise ValueError(f"Unsupported retrieval method: {config.retrieval_method}")
    input_files_read: list[str] = []
    run_dir = config.run_dir.resolve()
    topic_description = load_topic_description(run_dir, input_files_read)
    papers, _ = load_selected_papers(run_dir, input_files_read)
    parsed_manifest = load_parsed_manifest(run_dir, input_files_read)
    chunks = build_chunks(
        run_dir=run_dir,
        papers=papers,
        parsed_manifest=parsed_manifest,
        input_files_read=input_files_read,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    retrieved = retrieve_chunks(chunks=chunks, topic_description=topic_description, top_k=config.top_k)
    text = build_rag_prompt_context(
        topic_description=topic_description,
        retrieved_chunks=retrieved,
        all_chunks=chunks,
        config=config,
    )
    return RagContext(
        text=text,
        retrieved_chunks=retrieved,
        all_chunks=chunks,
        papers=papers,
        topic_description=topic_description,
        input_files_read=input_files_read,
        forbidden_inputs_read=[],
        approximate_input_tokens=approximate_tokens(text),
    )


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
        "title": f"Mock Qwen RAG Idea {idx}",
        "problem_statement": "A local parsed-paper RAG baseline can propose a research direction without downstream SGHA artifacts.",
        "motivation": "This mock idea is grounded only in retrieved local paper chunks.",
        "proposed_method_or_direction": "Define a lightweight study over retrieved corpus chunks.",
        "expected_contribution": "A deterministic smoke-test RAG baseline artifact.",
        "evaluation_plan": "Validate retrieved context JSONL, ideas JSONL, metadata, and audit files.",
        "risks_or_limitations": "Mock output is not a scientific result.",
        "top_source_papers_or_context_items": [f"mock_retrieved_context_{idx}"],
    }


def normalize_idea(raw: dict[str, Any], *, idx: int, config: RagConfig, context: RagContext) -> dict[str, Any]:
    retrieved_ids = [str(c.get("context_id")) for c in context.retrieved_chunks]
    source_context_used = {
        "context_mode": "parsed_paper_rag",
        "paper_count_available": len(context.papers),
        "chunk_count": len(context.all_chunks),
        "retrieved_context_ids": retrieved_ids,
        "input_files_read_count": len(context.input_files_read),
        "prompt_context_sha256": sha256_text(context.text),
    }
    return {
        "idea_id": f"qwen_rag_{idx:03d}",
        "title": _get_any(raw, ["title", "Title"], f"Qwen RAG idea {idx}"),
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
            retrieved_ids[:5],
        ),
        "retrieved_context_ids": retrieved_ids,
        "source_context_used": source_context_used,
        "model": config.model,
        "generated_by": GENERATED_BY,
        "context_mode": "parsed_paper_rag",
        "output_count_matched": True,
        "external_search_used": False,
        "code_execution_used": False,
        "raw_qwen_rag_idea": raw,
    }


def generate_ideas(
    *,
    config: RagConfig,
    context: RagContext,
    client_factory: Callable[..., Any] = create_local_openai_client,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    client = None if config.mock_llm else client_factory(base_url=config.base_url, api_key=config.api_key)
    ideas: list[dict[str, Any]] = []
    raw_events: list[dict[str, Any]] = []
    llm_call_count = 0
    output_token_estimate = 0
    for idx in range(1, config.num_ideas + 1):
        previous = "\n\n".join(json.dumps(i["raw_qwen_rag_idea"], ensure_ascii=False) for i in ideas)
        prompt = IDEA_PROMPT.format(rag_context=context.text, previous_ideas=previous or "No previous ideas.")
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
    config: RagConfig,
    context: RagContext,
    ideas: list[dict[str, Any]],
    raw_events: list[dict[str, Any]],
    llm_call_count: int,
    approximate_output_tokens: int,
) -> dict[str, Path]:
    jsonl_path = output_dir / "baseline_ideas.jsonl"
    md_path = output_dir / "baseline_ideas.md"
    context_path = output_dir / "baseline_prompt_context.md"
    retrieved_path = output_dir / "baseline_retrieved_context.jsonl"
    metadata_path = output_dir / "baseline_run_metadata.json"
    audit_path = output_dir / "baseline_quality_audit.md"

    jsonl_path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in ideas), encoding="utf-8")
    context_path.write_text(context.text, encoding="utf-8")
    retrieved_path.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in context.retrieved_chunks),
        encoding="utf-8",
    )

    md_lines = ["# Qwen+RAG Ideation Baseline Ideas", ""]
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
                "### Retrieved Context IDs",
                "",
                "\n".join(f"- {x}" for x in idea.get("retrieved_context_ids", [])),
                "",
            ]
        )
    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    output_count_matched = len(ideas) == config.num_ideas
    metadata = {
        "baseline_name": "Qwen+RAG ideation",
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
        "same_corpus_source": True,
        "information_matching_level": "local_parsed_paper_rag",
        "compute_matched": False,
        "retrieval_method": config.retrieval_method,
        "top_k": config.top_k,
        "chunk_source": config.chunk_source,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "chunk_count": len(context.all_chunks),
        "retrieved_context_count": len(context.retrieved_chunks),
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
    if not context.retrieved_chunks:
        status = "FAIL"
        warnings.append("no retrieved context chunks were available")
    missing_required = [
        idea["idea_id"]
        for idea in ideas
        if not all(idea.get(k) for k in ["title", "problem_statement", "evaluation_plan", "model"])
    ]
    if missing_required:
        status = "WARN" if status == "PASS" else status
        warnings.append(f"ideas with missing recommended fields: {missing_required}")

    audit_lines = [
        "# Qwen+RAG Ideation Baseline Quality Audit",
        "",
        f"- status: {status}",
        f"- ideas_written: {len(ideas)}",
        f"- output_count_matched: {str(output_count_matched).lower()}",
        f"- same_model: {str(metadata['same_model']).lower()}",
        "- same_corpus_source: true",
        "- information_matching_level: local_parsed_paper_rag",
        "- compute_matched: false",
        f"- retrieval_method: {config.retrieval_method}",
        f"- top_k: {config.top_k}",
        f"- chunk_count: {len(context.all_chunks)}",
        f"- retrieved_context_count: {len(context.retrieved_chunks)}",
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
        "retrieved_context": retrieved_path,
        "metadata": metadata_path,
        "audit": audit_path,
    }


def run_baseline(
    config: RagConfig,
    *,
    client_factory: Callable[..., Any] = create_local_openai_client,
) -> dict[str, Any]:
    if not config.no_external_search:
        raise BaselineSafetyError("External search must remain disabled for Qwen+RAG baseline.")
    if not config.no_experiment_execution:
        raise BaselineSafetyError("Experiment execution must remain disabled for Qwen+RAG baseline.")
    if not config.no_generated_code_execution:
        raise BaselineSafetyError("Generated-code execution must remain disabled for Qwen+RAG baseline.")
    output_dir = ensure_safe_output_dir(config.run_dir, config.output_dir or (config.run_dir / DEFAULT_OUTPUT_SUBDIR))
    context = load_rag_context(config)
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
    parser = argparse.ArgumentParser(description="Run Qwen+RAG ideation baseline on SGHA parsed paper text.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--num-ideas", type=int, required=True)
    parser.add_argument("--chunk-source", choices=["parsed_text"], default="parsed_text")
    parser.add_argument("--retrieval-method", choices=["bm25_or_tfidf"], default="bm25_or_tfidf")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--no-external-search", action="store_true", default=True)
    parser.add_argument("--no-experiment-execution", action="store_true", default=True)
    parser.add_argument("--no-generated-code-execution", action="store_true", default=True)
    parser.add_argument("--max-context-chars", type=int, default=30000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--mock-llm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_baseline(
        RagConfig(
            run_dir=args.run_dir,
            output_dir=args.output_dir,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            num_ideas=args.num_ideas,
            chunk_source=args.chunk_source,
            retrieval_method=args.retrieval_method,
            top_k=args.top_k,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            no_external_search=True,
            no_experiment_execution=True,
            no_generated_code_execution=True,
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
    print(f"Chunks indexed: {len(result['context'].all_chunks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
