#!/usr/bin/env python3
"""Summarize SGHA evidence and graph counts for supplementary tables.

This script reads existing SGHA run artifacts only. It does not call any LLM,
external service, or pipeline stage.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence


NOT_AVAILABLE = "NOT_AVAILABLE"

DEFAULT_OUTPUT_PARENT = Path(os.environ.get("SGHA_ARTIFACT_OUTPUT_PARENT", "./paper_artifacts/generated"))

DOMAIN_RUNS: Mapping[str, Path] = {
    "bandits": Path(os.environ.get("SGHA_RUN_BANDITS", "./paper_artifacts/source_runs/bandits")),
    "in_context_learning": Path(os.environ.get("SGHA_RUN_ICL", "./paper_artifacts/source_runs/in_context_learning")),
    "reasoning_models_test_time_compute": Path(
        os.environ.get("SGHA_RUN_TEST_TIME_COMPUTE", "./paper_artifacts/source_runs/reasoning_models_test_time_compute")
    ),
    "offline_reinforcement_learning_arxiv": Path(
        os.environ.get("SGHA_RUN_OFFLINE_RL", "./paper_artifacts/source_runs/offline_reinforcement_learning_arxiv")
    ),
    "uncertainty_calibration_conformal_prediction_arxiv": Path(
        os.environ.get("SGHA_RUN_UNCERTAINTY_CALIBRATION", "./paper_artifacts/source_runs/uncertainty_calibration_conformal_prediction_arxiv")
    ),
}

PAPER_OBJECT_FIELDS = [
    "methods",
    "tasks",
    "datasets",
    "metrics",
    "assumptions",
    "results",
    "limitations",
    "failure_conditions",
    "claims",
    "contradictions_or_tensions",
    "future_work",
]

RELATION_PRIORITY = [
    "assumes",
    "fails_under",
    "limited_by",
    "addresses",
    "not_addressed_by",
    "contradicts",
    "improves_over",
    "evaluated_on",
    "uses_dataset",
    "measured_by",
]

CLAIM_TYPE_PRIORITY = [
    "assumption",
    "comparison",
    "limitation",
    "evaluation",
    "result",
    "failure",
    "hypothesis",
    "method",
    "unknown",
]

EVIDENCE_TYPE_PRIORITY = [
    "theoretical",
    "empirical",
    "ablation",
    "qualitative",
    "assumption",
    "citation",
    "benchmark",
    "unknown",
]

NODE_TYPE_PRIORITY = [
    "Paper",
    "Method",
    "Task",
    "Dataset",
    "Metric",
    "Assumption",
    "Result",
    "Limitation",
    "FailureCondition",
    "Claim",
    "Gap",
    "Hypothesis",
]

EDGE_TYPE_PRIORITY = [
    "mentions",
    "assumes",
    "fails_under",
    "limited_by",
    "addresses",
    "not_addressed_by",
    "contradicts",
    "improves_over",
    "evaluated_on",
    "uses_dataset",
    "measured_by",
    "supports_gap",
    "weakens_gap",
    "counterevidence_for",
    "partially_addresses_gap",
]

MOTIF_TYPE_PRIORITY = [
    "assumption_mismatch",
    "shared_failure_condition",
    "repeated_unaddressed_limitation",
    "conflicting_claims",
    "sparse_evaluation",
    "unrealistic_assumption",
    "theory_practice_gap",
    "missing_stress_test",
    "shared_unrealistic_assumption",
    "unresolved_tradeoff",
    "transfer_solution_gap",
    "claim_without_measurement",
    "missing_baseline_comparison",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def normalize_missing(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        return value if value else default
    return str(value)


def order_columns(observed: Iterable[str], priority: Sequence[str]) -> List[str]:
    observed_set = {x for x in observed if x}
    ordered = [x for x in priority if x in observed_set]
    ordered.extend(sorted(observed_set - set(ordered)))
    return ordered


def count_list_json(path: Path) -> int:
    if not path.exists():
        return 0
    data = read_json(path)
    return len(data) if isinstance(data, list) else 0


def selected_papers(root: Path) -> int:
    manifest = root / "arxiv" / "papers_manifest.json"
    if manifest.exists():
        data = read_json(manifest)
        if isinstance(data, list):
            return len(data)
    selected = root / "arxiv" / "selected_before_download.json"
    if selected.exists():
        data = read_json(selected)
        if isinstance(data, list):
            return len(data)
    return 0


def parsed_papers(root: Path) -> int:
    manifest = root / "parsed" / "parsed_manifest.json"
    if manifest.exists():
        data = read_json(manifest)
        if isinstance(data, list):
            return len(data)
    return len(list((root / "parsed" / "paper_texts").glob("*.txt")))


def extracted_records(root: Path) -> List[Dict[str, Any]]:
    path = root / "extracted" / "all_extractions.json"
    if path.exists():
        data = read_json(path)
        if isinstance(data, list):
            return data
    return []


def all_tuples(root: Path) -> List[Dict[str, Any]]:
    return read_jsonl(root / "extracted" / "all_tuples.jsonl")


def final_metadata(root: Path) -> Dict[str, Any]:
    path = root / "final_sgha_family_report" / "run_metadata.json"
    if path.exists():
        data = read_json(path)
        if isinstance(data, dict):
            return data
    final_json = root / "final_sgha_family_report" / "final_project_families.json"
    if final_json.exists():
        data = read_json(final_json)
        if isinstance(data, dict):
            return data.get("verification_gate", {})
    return {}


def final_families(root: Path) -> int:
    path = root / "final_sgha_family_report" / "final_project_families.json"
    if path.exists():
        data = read_json(path)
        if isinstance(data, dict) and isinstance(data.get("families"), list):
            return len(data["families"])
    return 0


def graph_counts(root: Path) -> tuple[int, int, Counter[str], Counter[str]]:
    graph_path = root / "graph" / "graph.json"
    if not graph_path.exists():
        return 0, 0, Counter(), Counter()
    graph = read_json(graph_path)
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    node_types = Counter(normalize_missing(n.get("type")) for n in nodes if isinstance(n, dict))
    edge_types = Counter(normalize_missing(e.get("relation")) for e in edges if isinstance(e, dict))
    return len(nodes), len(edges), node_types, edge_types


def motif_counts(root: Path) -> Counter[str]:
    path = root / "motifs" / "motif_hits.json"
    if not path.exists():
        return Counter()
    data = read_json(path)
    if not isinstance(data, list):
        return Counter()
    return Counter(normalize_missing(row.get("motif_type")) for row in data if isinstance(row, dict))


def extraction_validation_counts(root: Path, selected: int, parsed: int, extracted: int) -> Dict[str, Any]:
    failed = 0
    error_count = 0
    for status_path in sorted((root / "extractions").glob("shard_*/extraction_status.json")):
        status = read_json(status_path)
        if isinstance(status, dict):
            failed += int(status.get("total_failed") or len(status.get("failed", [])) or 0)
            errors = status.get("errors", {})
            error_count += len(errors) if isinstance(errors, dict) else 0

    unverified_rows = 0
    dropped_tuples = 0
    unverified_available = False
    for spans_path in sorted((root / "extractions").glob("shard_*/unverified_spans.jsonl")):
        unverified_available = True
        for row in read_jsonl(spans_path):
            unverified_rows += 1
            try:
                dropped_tuples += int(row.get("dropped_tuples", 0) or 0)
            except (TypeError, ValueError):
                pass

    malformed = NOT_AVAILABLE
    if failed and error_count:
        malformed = NOT_AVAILABLE

    notes = []
    if malformed == NOT_AVAILABLE:
        notes.append("malformed extraction count not logged separately")
    if unverified_available:
        notes.append("span validation/drop counts from extractions/shard_*/unverified_spans.jsonl")
    else:
        notes.append("unverified span artifact not found")

    return {
        "extraction_failures": failed,
        "malformed_extractions": malformed,
        "span_validation_failures": dropped_tuples if unverified_available else NOT_AVAILABLE,
        "dropped_tuples_if_available": dropped_tuples if unverified_available else NOT_AVAILABLE,
        "unverified_spans_if_available": unverified_rows if unverified_available else NOT_AVAILABLE,
        "parsed_but_not_extracted": max(parsed - extracted, 0),
        "notes": "; ".join(notes),
    }


def build_rows() -> Dict[str, Any]:
    overview = []
    paper_objects = []
    relation_counts: Dict[str, Counter[str]] = {}
    claim_counts: Dict[str, Counter[str]] = {}
    evidence_counts: Dict[str, Counter[str]] = {}
    metadata_rows = []
    node_counts: Dict[str, Counter[str]] = {}
    edge_counts: Dict[str, Counter[str]] = {}
    motif_by_domain: Dict[str, Counter[str]] = {}
    validation_rows = []
    source_paths: Dict[str, Dict[str, Path]] = {}

    for domain, root in DOMAIN_RUNS.items():
        tuple_rows = all_tuples(root)
        extraction_rows = extracted_records(root)
        metadata = final_metadata(root)
        graph_nodes, graph_edges, graph_node_types, graph_edge_types = graph_counts(root)
        motifs = motif_counts(root)

        selected = selected_papers(root)
        parsed = parsed_papers(root)
        extracted = len(extraction_rows)
        tuple_count = len(tuple_rows)
        novelty_survivors = count_list_json(root / "gaps" / "candidate_gaps.json")

        overview.append(
            {
                "domain": domain,
                "selected_papers": selected,
                "parsed_papers": parsed,
                "extracted_papers": extracted,
                "tuple_count": tuple_count,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "motif_hits": sum(motifs.values()),
                "novelty_survivors": novelty_survivors,
                "reviewed_gaps": metadata.get("verification_reviewed_count", NOT_AVAILABLE),
                "verified_gaps": metadata.get("verification_passed_count", NOT_AVAILABLE),
                "direct_formulations": count_jsonl(
                    root / "stage7_direct_formulations" / "direct_formulations.jsonl"
                ),
                "critic_passing_variants": count_jsonl(
                    root / "stage8_ambition_expansion" / "critic_passing_formulations.jsonl"
                ),
                "project_families": final_families(root),
                "formal_problem_statements": count_jsonl(
                    root
                    / "stage10_formal_problem_formulations"
                    / "formal_problem_formulations.jsonl"
                ),
            }
        )

        object_counts = {field: 0 for field in PAPER_OBJECT_FIELDS}
        for record in extraction_rows:
            for field in PAPER_OBJECT_FIELDS:
                value = record.get(field, [])
                if isinstance(value, list):
                    object_counts[field] += len(value)
        paper_objects.append(
            {
                "domain": domain,
                "extracted_papers": extracted,
                **object_counts,
                "total_paper_level_objects": sum(object_counts.values()),
            }
        )

        relation_counts[domain] = Counter(
            normalize_missing(row.get("relation")) for row in tuple_rows
        )
        claim_counts[domain] = Counter(
            normalize_missing(row.get("claim_type")) for row in tuple_rows
        )
        evidence_counts[domain] = Counter(
            normalize_missing(row.get("evidence_type")) for row in tuple_rows
        )

        metadata_counter = Counter()
        for row in tuple_rows:
            for field in ["condition", "task", "dataset", "model", "metric"]:
                if nonempty(row.get(field)):
                    metadata_counter[f"nonempty_{field}"] += 1

            polarity = normalize_missing(row.get("polarity"))
            if polarity in {"positive", "negative", "neutral", "mixed"}:
                metadata_counter[f"polarity_{polarity}"] += 1
            else:
                metadata_counter["polarity_unknown"] += 1

            scope = normalize_missing(row.get("subject_scope"))
            if scope in {"own_method", "prior_work", "general"}:
                metadata_counter[f"subject_scope_{scope}"] += 1
            else:
                metadata_counter["subject_scope_unknown_or_missing"] += 1

            if row.get("resolved_by_paper") is True:
                metadata_counter["resolved_by_paper_true"] += 1
            else:
                metadata_counter["resolved_by_paper_false"] += 1

            if row.get("in_related_work") is True:
                metadata_counter["in_related_work_true"] += 1
            else:
                metadata_counter["in_related_work_false"] += 1

        metadata_rows.append(
            {
                "domain": domain,
                "tuple_count": tuple_count,
                "nonempty_condition": metadata_counter["nonempty_condition"],
                "nonempty_task": metadata_counter["nonempty_task"],
                "nonempty_dataset": metadata_counter["nonempty_dataset"],
                "nonempty_model": metadata_counter["nonempty_model"],
                "nonempty_metric": metadata_counter["nonempty_metric"],
                "polarity_positive": metadata_counter["polarity_positive"],
                "polarity_negative": metadata_counter["polarity_negative"],
                "polarity_neutral": metadata_counter["polarity_neutral"],
                "polarity_mixed": metadata_counter["polarity_mixed"],
                "polarity_unknown": metadata_counter["polarity_unknown"],
                "subject_scope_own_method": metadata_counter["subject_scope_own_method"],
                "subject_scope_prior_work": metadata_counter["subject_scope_prior_work"],
                "subject_scope_general": metadata_counter["subject_scope_general"],
                "subject_scope_unknown_or_missing": metadata_counter[
                    "subject_scope_unknown_or_missing"
                ],
                "resolved_by_paper_true": metadata_counter["resolved_by_paper_true"],
                "resolved_by_paper_false": metadata_counter["resolved_by_paper_false"],
                "in_related_work_true": metadata_counter["in_related_work_true"],
                "in_related_work_false": metadata_counter["in_related_work_false"],
            }
        )

        node_counts[domain] = graph_node_types
        edge_counts[domain] = graph_edge_types
        motif_by_domain[domain] = motifs
        validation_rows.append(
            {"domain": domain, **extraction_validation_counts(root, selected, parsed, extracted)}
        )
        source_paths[domain] = {
            "run_dir": root,
            "papers_manifest": root / "arxiv" / "papers_manifest.json",
            "parsed_manifest": root / "parsed" / "parsed_manifest.json",
            "all_extractions": root / "extracted" / "all_extractions.json",
            "all_tuples": root / "extracted" / "all_tuples.jsonl",
            "graph": root / "graph" / "graph.json",
            "motif_hits": root / "motifs" / "motif_hits.json",
            "candidate_gaps": root / "gaps" / "candidate_gaps.json",
            "novelty_verdicts": root / "gaps" / "novelty_filter_verdicts.jsonl",
            "verification_summary": root / "verification" / "verification_summary.json",
            "final_metadata": root / "final_sgha_family_report" / "run_metadata.json",
            "direct_formulations": root / "stage7_direct_formulations" / "direct_formulations.jsonl",
            "critic_passing": root
            / "stage8_ambition_expansion"
            / "critic_passing_formulations.jsonl",
            "final_families": root / "final_sgha_family_report" / "final_project_families.json",
            "formal_problems": root
            / "stage10_formal_problem_formulations"
            / "formal_problem_formulations.jsonl",
            "extraction_summary": root / "extractions" / "extraction_summary.json",
            "unverified_spans": root / "extractions" / "shard_*/unverified_spans.jsonl",
        }

    return {
        "overview": overview,
        "paper_objects": paper_objects,
        "relation_counts": relation_counts,
        "claim_counts": claim_counts,
        "evidence_counts": evidence_counts,
        "metadata_rows": metadata_rows,
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "motif_counts": motif_by_domain,
        "validation_rows": validation_rows,
        "source_paths": source_paths,
    }


def add_total_row(rows: List[Dict[str, Any]], first_col: str = "domain") -> List[Dict[str, Any]]:
    if not rows:
        return rows
    out = list(rows)
    total: Dict[str, Any] = {first_col: "TOTAL"}
    for col in rows[0]:
        if col == first_col:
            continue
        values = [row.get(col) for row in rows]
        if all(isinstance(v, (int, float)) for v in values):
            total[col] = sum(values)
        elif all(isinstance(v, int) or (isinstance(v, str) and v.isdigit()) for v in values):
            total[col] = sum(int(v) for v in values)
        else:
            total[col] = NOT_AVAILABLE if any(v == NOT_AVAILABLE for v in values) else ""
    out.append(total)
    return out


def counter_rows(
    counters: Mapping[str, Counter[str]], priority: Sequence[str], include_total: bool = True
) -> tuple[List[Dict[str, Any]], List[str]]:
    columns = order_columns((key for counter in counters.values() for key in counter), priority)
    rows: List[Dict[str, Any]] = []
    total = Counter()
    for domain in DOMAIN_RUNS:
        counter = counters.get(domain, Counter())
        total.update(counter)
        rows.append({"domain": domain, **{col: counter.get(col, 0) for col in columns}})
    if include_total:
        rows.append({"domain": "TOTAL", **{col: total.get(col, 0) for col in columns}})
    return rows, ["domain", *columns]


def write_csv(path: Path, rows: List[Dict[str, Any]], columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def write_latex(path: Path, rows: List[Dict[str, Any]], columns: Sequence[str], caption: str, label: str) -> None:
    align = "l" + "r" * (len(columns) - 1)
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\scriptsize",
        rf"\caption{{{latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        r"\resizebox{\textwidth}{!}{%",
        rf"\begin{{tabular}}{{{align}}}",
        r"\toprule",
        " & ".join(latex_escape(col) for col in columns) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(latex_escape(row.get(col, "")) for col in columns) + r" \\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            r"\end{table*}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_source_paths(path: Path, source_paths: Mapping[str, Mapping[str, Path]]) -> None:
    lines = [
        "# Source Paths For Evidence Count Tables",
        "",
        "All counts are derived from the existing artifacts below. Missing glob-style paths are marked as pattern references.",
        "",
    ]
    for domain, paths in source_paths.items():
        lines.append(f"## {domain}")
        lines.append("")
        lines.append("| artifact | status | path |")
        lines.append("|---|---|---|")
        for name, p in paths.items():
            if "*" in str(p):
                status = "PATTERN"
            else:
                status = "FOUND" if p.exists() else "MISSING"
            lines.append(f"| `{name}` | {status} | `{p}` |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_readme(path: Path, output_dir: Path, rows: Dict[str, Any]) -> None:
    overview = rows["overview"]
    totals = add_total_row(overview)[-1]
    lines = [
        "# SGHA Supplement Evidence Counts",
        "",
        f"- Created at: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        f"- Output directory: `{output_dir}`",
        "- Scope: main five-domain repaired SGHA runs.",
        "- Procedure: read-only aggregation over existing JSON, JSONL, CSV, and Markdown metadata artifacts.",
        "- No SGHA stages, LLM calls, OpenRouter calls, or external searches were run.",
        "",
        "## Counting Notes",
        "",
        "- `selected_papers` is the length of `arxiv/papers_manifest.json`.",
        "- `parsed_papers` is the length of `parsed/parsed_manifest.json`.",
        "- `extracted_papers` is the length of `extracted/all_extractions.json`.",
        "- `tuple_count` is the number of nonempty JSONL records in `extracted/all_tuples.jsonl`.",
        "- `novelty_survivors` is the length of `gaps/candidate_gaps.json`; across these runs this is the post-novelty candidate-gap set.",
        "- `reviewed_gaps` and `verified_gaps` come from `final_sgha_family_report/run_metadata.json`, which records the repaired hard verification gate counts.",
        "- `formal_problem_statements` is the number of Stage 10 JSONL records.",
        "- `span_validation_failures` and `dropped_tuples_if_available` are summed from `extractions/shard_*/unverified_spans.jsonl` where that artifact logs `dropped_tuples` per paper.",
        "- `malformed_extractions` is `NOT_AVAILABLE` because these runs do not log a separate malformed-extraction count distinct from extraction failures/errors.",
        "",
        "## Five-Domain Totals",
        "",
        f"- selected papers: `{totals['selected_papers']}`",
        f"- parsed papers: `{totals['parsed_papers']}`",
        f"- extracted papers: `{totals['extracted_papers']}`",
        f"- evidence tuples: `{totals['tuple_count']}`",
        f"- graph nodes: `{totals['graph_nodes']}`",
        f"- graph edges: `{totals['graph_edges']}`",
        f"- motif hits: `{totals['motif_hits']}`",
        f"- novelty survivors: `{totals['novelty_survivors']}`",
        f"- reviewed gaps: `{totals['reviewed_gaps']}`",
        f"- verified gaps: `{totals['verified_gaps']}`",
        f"- project families: `{totals['project_families']}`",
        f"- formal problem statements: `{totals['formal_problem_statements']}`",
        "",
        "## Tables",
        "",
    ]
    for name in [
        "evidence_count_overview",
        "paper_level_object_counts_by_domain",
        "tuple_relation_counts_by_domain",
        "tuple_claim_type_counts_by_domain",
        "tuple_evidence_type_counts_by_domain",
        "tuple_metadata_counts_by_domain",
        "graph_node_counts_by_domain",
        "graph_edge_counts_by_domain",
        "motif_counts_by_domain",
        "extraction_validation_counts_by_domain",
    ]:
        lines.append(f"- `{name}.csv` and `{name}.tex`")
    lines.append("- `source_paths_for_counts.md`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.output_dir is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT_PARENT / f"supplement_evidence_counts_{stamp}"
    else:
        output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=False)

    rows = build_rows()

    overview_rows = add_total_row(rows["overview"])
    overview_cols = list(rows["overview"][0].keys())
    write_csv(output_dir / "evidence_count_overview.csv", overview_rows, overview_cols)
    write_latex(
        output_dir / "evidence_count_overview.tex",
        overview_rows,
        overview_cols,
        "SGHA evidence and finalization count overview across five domains.",
        "tab:sgha-evidence-count-overview",
    )

    paper_object_rows = add_total_row(rows["paper_objects"])
    paper_object_cols = list(rows["paper_objects"][0].keys())
    write_csv(
        output_dir / "paper_level_object_counts_by_domain.csv",
        paper_object_rows,
        paper_object_cols,
    )
    write_latex(
        output_dir / "paper_level_object_counts_by_domain.tex",
        paper_object_rows,
        paper_object_cols,
        "Paper-level extraction object counts by domain.",
        "tab:sgha-paper-level-object-counts",
    )

    table_specs = [
        (
            "tuple_relation_counts_by_domain",
            rows["relation_counts"],
            RELATION_PRIORITY,
            "Evidence tuple relation counts by domain.",
            "tab:sgha-tuple-relation-counts",
        ),
        (
            "tuple_claim_type_counts_by_domain",
            rows["claim_counts"],
            CLAIM_TYPE_PRIORITY,
            "Evidence tuple claim-type counts by domain.",
            "tab:sgha-tuple-claim-type-counts",
        ),
        (
            "tuple_evidence_type_counts_by_domain",
            rows["evidence_counts"],
            EVIDENCE_TYPE_PRIORITY,
            "Evidence tuple evidence-type counts by domain.",
            "tab:sgha-tuple-evidence-type-counts",
        ),
        (
            "graph_node_counts_by_domain",
            rows["node_counts"],
            NODE_TYPE_PRIORITY,
            "Graph node type counts by domain.",
            "tab:sgha-graph-node-counts",
        ),
        (
            "graph_edge_counts_by_domain",
            rows["edge_counts"],
            EDGE_TYPE_PRIORITY,
            "Graph edge relation counts by domain.",
            "tab:sgha-graph-edge-counts",
        ),
        (
            "motif_counts_by_domain",
            rows["motif_counts"],
            MOTIF_TYPE_PRIORITY,
            "Structural motif hit counts by domain.",
            "tab:sgha-motif-counts",
        ),
    ]
    for name, counters, priority, caption, label in table_specs:
        c_rows, c_cols = counter_rows(counters, priority)
        write_csv(output_dir / f"{name}.csv", c_rows, c_cols)
        write_latex(output_dir / f"{name}.tex", c_rows, c_cols, caption, label)

    metadata_cols = list(rows["metadata_rows"][0].keys())
    metadata_rows = add_total_row(rows["metadata_rows"])
    write_csv(output_dir / "tuple_metadata_counts_by_domain.csv", metadata_rows, metadata_cols)
    write_latex(
        output_dir / "tuple_metadata_counts_by_domain.tex",
        metadata_rows,
        metadata_cols,
        "Evidence tuple metadata coverage counts by domain.",
        "tab:sgha-tuple-metadata-counts",
    )

    validation_cols = list(rows["validation_rows"][0].keys())
    validation_rows = add_total_row(rows["validation_rows"])
    write_csv(
        output_dir / "extraction_validation_counts_by_domain.csv",
        validation_rows,
        validation_cols,
    )
    write_latex(
        output_dir / "extraction_validation_counts_by_domain.tex",
        validation_rows,
        validation_cols,
        "Extraction validation and failure counts by domain.",
        "tab:sgha-extraction-validation-counts",
    )

    write_source_paths(output_dir / "source_paths_for_counts.md", rows["source_paths"])
    write_readme(output_dir / "EVIDENCE_COUNTS_README.md", output_dir, rows)

    print(output_dir)


if __name__ == "__main__":
    main()
