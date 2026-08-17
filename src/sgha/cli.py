from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import yaml

from .arxiv_fetcher import fetch_arxiv_corpus
from .config import cli_overrides, deep_merge, load_config
from .evolutionary_refinement import evolve_hypotheses
from .extraction import extract_structured_claims
from .gap_detection import detect_gaps, run_novelty_filter
from .graph_builder import build_knowledge_graph
from .pdf_parser import parse_papers
from .report_builder import build_report
from .run_context import RunContext
from .utils import ensure_dir
from .verification_agents import verify_gaps
from .resolution_extraction import extract_resolution_records
from .counterevidence_linking import discover_counterevidence
from .graph_export import load_graph, export_graph


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sgha", description="Structural Gap Hypothesis Agent")
    p.add_argument("--config", action="append", default=[], help="Additional YAML config overlay.")
    sub = p.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke-test", help="Run a no-network synthetic output-structure demo.")
    smoke.add_argument(
        "--example-config",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "examples" / "local_text_corpus" / "config.yaml",
    )
    smoke.add_argument("--output-dir", type=Path, default=None)

    init_example = sub.add_parser("init-example", help="Copy the offline local-text example into a new directory.")
    init_example.add_argument("output_dir", type=Path)
    init_example.add_argument("--force", action="store_true", help="Allow copying into an existing directory.")

    validate = sub.add_parser("validate-config", help="Validate a public SGHA config without running the pipeline.")
    validate.add_argument("config_path", type=Path)

    summarize = sub.add_parser("summarize-run", help="Summarize available outputs from a complete or partial run.")
    summarize.add_argument("run_dir", type=Path)

    prepare_local = sub.add_parser("prepare-local-corpus", help="Stage a local text corpus for model-backed SGHA stages.")
    prepare_local.add_argument("config_path", type=Path)
    prepare_local.add_argument("--run-id", default=None)
    prepare_local.add_argument("--output-root", type=Path, default=None)

    init = sub.add_parser("init", help="Initialize output and dataset directories.")
    init.add_argument("--project-name", default="structural_gap_hypothesis_agent")
    add_common(init)

    fetch = sub.add_parser("fetch-arxiv", help="Fetch arXiv metadata and PDFs.")
    fetch.add_argument("--query")
    fetch.add_argument("--max-results", type=int)
    fetch.add_argument("--output-dir")
    fetch.add_argument("--run-id")
    fetch.add_argument("--retrieval-config", default=None,
                       help="Path to a retrieval YAML config (e.g. configs/retrieval_bandit_theory.yaml).")
    fetch.add_argument("--llm-base-url")
    add_common(fetch)

    parse = sub.add_parser("parse-papers", help="Parse fetched PDFs.")
    parse.add_argument("--run-id", required=True)
    add_common(parse)

    extract = sub.add_parser("extract", help="Extract structured scientific tuples.")
    extract.add_argument("--run-id", required=True)
    extract.add_argument("--llm-base-url")
    extract.add_argument("--mock-llm", action="store_true")
    add_common(extract)

    graph = sub.add_parser("build-graph", help="Build the knowledge graph.")
    graph.add_argument("--run-id", required=True)
    add_common(graph)

    gaps = sub.add_parser("detect-gaps", help="Detect deterministic structural gap motifs.")
    gaps.add_argument("--run-id", required=True)
    add_common(gaps)

    novelty = sub.add_parser("novelty-filter", help="LLM novelty filter on candidate gaps.")
    novelty.add_argument("--run-id", required=True)
    novelty.add_argument("--llm-base-url")
    add_common(novelty)

    verify = sub.add_parser("verify-gaps", help="Stress-test candidate gaps.")
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--llm-base-url")
    verify.add_argument("--mock-llm", action="store_true")
    verify.add_argument("--skeptic-external-arxiv", action="store_true")
    add_common(verify)

    evolve = sub.add_parser("evolve", help="Evolve hypotheses from verified gaps.")
    evolve.add_argument("--run-id", required=True)
    evolve.add_argument("--generations", type=int)
    evolve.add_argument("--population-size", type=int)
    evolve.add_argument("--llm-base-url")
    add_common(evolve)

    report = sub.add_parser("report", help="Build final Markdown and HTML report.")
    report.add_argument("--run-id", required=True)
    add_common(report)

    resolve = sub.add_parser("resolve-papers", help="Run resolution extraction pass on parsed papers.")
    resolve.add_argument("--run-id", required=True)
    resolve.add_argument("--paper-ids", help="Comma-separated paper IDs to process (default: all).")
    resolve.add_argument("--llm-base-url")
    resolve.add_argument("--min-confidence", type=float, default=0.65)
    resolve.add_argument("--no-resume", action="store_true")
    add_common(resolve)

    discover = sub.add_parser("discover-counterevidence", help="Discover in-corpus counterevidence for gaps.")
    discover.add_argument("--run-id", required=True)
    discover.add_argument("--llm-base-url")
    discover.add_argument("--max-candidates-per-gap", type=int, default=20)
    discover.add_argument("--min-candidate-score", type=float, default=0.20)
    discover.add_argument("--classifier-min-confidence", type=float, default=0.70)
    add_common(discover)

    run_all = sub.add_parser("run-all", help="Run the complete pipeline.")
    run_all.add_argument("--query")
    run_all.add_argument("--retrieval-config", default=None,
                         help="Path to a retrieval YAML config (e.g. configs/retrieval_icl_theory.yaml). "
                              "Query and topic profile are read from this file.")
    run_all.add_argument("--max-results", type=int)
    run_all.add_argument("--generations", type=int)
    run_all.add_argument("--population-size", type=int)
    run_all.add_argument("--llm-base-url")
    run_all.add_argument("--mock-llm", action="store_true")
    run_all.add_argument("--run-id")
    run_all.add_argument("--skeptic-external-arxiv", action="store_true")
    run_all.add_argument("--force", action="store_true", help="Rerun finalization stages even if valid outputs exist.")
    add_common(run_all)

    finalize = sub.add_parser("finalize", help="Run only the finalization path (direct->ambition->family->report).")
    finalize.add_argument("--run-id", required=True)
    finalize.add_argument("--llm-base-url")
    finalize.add_argument("--force", action="store_true")
    add_common(finalize)
    return p


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root")
    parser.add_argument("--dataset-root")


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "smoke-test":
        from .offline_demo import create_mock_run, format_run_summary

        result = create_mock_run(config_path=args.example_config, output_dir=args.output_dir)
        print("offline smoke test ok")
        print(f"mock_run_dir={result['run_dir']}")
        print(format_run_summary(result["summary"]))
        print("Next: inspect the mock output tree, then read docs/run_on_your_own_papers.md.")
        return 0

    if args.command == "init-example":
        source = Path(__file__).resolve().parents[2] / "examples" / "local_text_corpus"
        destination = args.output_dir
        if destination.exists() and not destination.is_dir():
            raise ValueError(f"output path exists and is not a directory: {destination}")
        if destination.exists() and any(destination.iterdir()) and not args.force:
            raise ValueError(f"output directory is not empty: {destination} (use --force to copy anyway)")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        print(f"example project copied to: {destination}")
        print(f"validate it with: sgha validate-config {destination / 'config.yaml'}")
        print(f"try the offline demo with: sgha smoke-test --example-config {destination / 'config.yaml'}")
        return 0

    if args.command == "validate-config":
        from .offline_demo import load_papers_manifest, validate_config_file

        config, errors, warnings = validate_config_file(args.config_path)
        if errors:
            print("config validation failed")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"config ok: {args.config_path}")
        if warnings:
            print("warnings:")
            for warning in warnings:
                print(f"- {warning}")
        if isinstance(config.get("corpus"), dict) and config["corpus"].get("manifest_path"):
            papers = load_papers_manifest(args.config_path, config)
            print(f"papers manifest ok: {len(papers)} records")
        print("Next: run `sgha smoke-test` for an offline output demo, or use model-backed SGHA stages when ready.")
        return 0

    if args.command == "summarize-run":
        from .offline_demo import format_run_summary, summarize_run

        print(format_run_summary(summarize_run(args.run_dir)))
        return 0

    if args.command == "prepare-local-corpus":
        from .offline_demo import prepare_local_corpus

        result = prepare_local_corpus(args.config_path, run_id=args.run_id, output_root=args.output_root)
        print("local corpus prepared")
        print(f"run_id={result['run_id']}")
        print(f"run_dir={result['run_dir']}")
        print(f"papers={result['paper_count']}")
        print("Next model-backed stage example:")
        extract_cmd = f"sgha --config {args.config_path} extract --run-id {result['run_id']}"
        if args.output_root:
            extract_cmd += f" --output-root {args.output_root}"
        print(f"  {extract_cmd}")
        print(f"Then inspect outputs with: sgha summarize-run {result['run_dir']}")
        return 0

    cfg = effective_config(args)
    if args.command == "init":
        ensure_dir(cfg["output_root"])
        ensure_dir(Path(cfg["output_root"]) / "logs")
        ensure_dir(cfg["dataset_root"])
        ensure_dir(Path(cfg["dataset_root"]) / "arxiv" / "downloaded_pdfs")
        print(f"initialized output_root={cfg['output_root']}")
        print(f"initialized dataset_root={cfg['dataset_root']}")
        return 0

    if args.command == "fetch-arxiv":
        retrieval_config_path = getattr(args, "retrieval_config", None)
        if retrieval_config_path:
            cfg["retrieval_config_path"] = retrieval_config_path
        ctx = RunContext(cfg, run_id=args.run_id, create=True)
        _raw_q = cfg.get("query", "")
        _query_str = _raw_q.get("text", "") if isinstance(_raw_q, dict) else _raw_q
        fetch_arxiv_corpus(ctx, query=_query_str, max_results=int(cfg["max_results"]), output_dir=args.output_dir,
                           retrieval_config_path=retrieval_config_path)
        print(ctx.run_id)
        return 0

    ctx = RunContext(cfg, run_id=getattr(args, "run_id", None), create=True)
    if args.command == "parse-papers":
        parse_papers(ctx)
    elif args.command == "extract":
        extract_structured_claims(ctx, llm_base_url=args.llm_base_url, mock_llm=args.mock_llm or None)
    elif args.command == "build-graph":
        build_knowledge_graph(ctx)
    elif args.command == "detect-gaps":
        detect_gaps(ctx)
    elif args.command == "novelty-filter":
        run_novelty_filter(ctx, llm_base_url=args.llm_base_url)
    elif args.command == "verify-gaps":
        verify_gaps(ctx, llm_base_url=args.llm_base_url, mock_llm=args.mock_llm or None, skeptic_external_arxiv=args.skeptic_external_arxiv)
    elif args.command == "evolve":
        evolve_hypotheses(ctx, generations=args.generations, population_size=args.population_size)
    elif args.command == "report":
        build_report(ctx)
    elif args.command == "resolve-papers":
        raw_ids = getattr(args, "paper_ids", None)
        paper_ids_list = [p.strip() for p in raw_ids.split(",")] if raw_ids else None
        records = extract_resolution_records(
            ctx,
            paper_ids=paper_ids_list,
            llm_base_url=args.llm_base_url,
            min_confidence=getattr(args, "min_confidence", 0.65),
            resume=not getattr(args, "no_resume", False),
        )
        print(f"[resolve-papers] Extracted {len(records)} resolution records.")
    elif args.command == "discover-counterevidence":
        import json
        from .utils import read_json
        from .gap_objects import CandidateGap
        from .utils import model_validate
        graph = load_graph(ctx.path("graph", "graph.json"))
        gaps_raw = read_json(ctx.path("gaps", "candidate_gaps.json"), default=[])
        gaps = [model_validate(CandidateGap, g) for g in gaps_raw]
        # Load resolution records
        res_jsonl = ctx.path("resolution_extractions", "all_resolution_records.jsonl")
        from .utils import read_jsonl
        from .resolution_extraction import ResolutionRecord
        res_raw = read_jsonl(res_jsonl)
        records = [model_validate(ResolutionRecord, r) for r in res_raw]
        candidates, edges = discover_counterevidence(
            ctx,
            records,
            graph,
            gaps,
            llm_base_url=args.llm_base_url,
            max_candidates_per_gap=getattr(args, "max_candidates_per_gap", 20),
            min_candidate_score=getattr(args, "min_candidate_score", 0.20),
            classifier_min_confidence=getattr(args, "classifier_min_confidence", 0.70),
        )
        export_graph(graph, ctx.path("graph"))
        print(f"[discover-counterevidence] {len(candidates)} candidates, {len(edges)} edges created.")
    elif args.command == "run-all":
        retrieval_config_path = getattr(args, "retrieval_config", None)
        if retrieval_config_path:
            ctx.config["retrieval_config_path"] = retrieval_config_path
        raw_query = cfg.get("query", "")
        query_str = raw_query.get("text", "") if isinstance(raw_query, dict) else raw_query
        fetch_arxiv_corpus(ctx, query=query_str, max_results=int(cfg["max_results"]),
                           retrieval_config_path=retrieval_config_path)
        parse_papers(ctx)
        extract_structured_claims(ctx, llm_base_url=args.llm_base_url, mock_llm=args.mock_llm or None)
        build_knowledge_graph(ctx)
        detect_gaps(ctx)
        run_novelty_filter(ctx, llm_base_url=args.llm_base_url)
        verify_gaps(ctx, llm_base_url=args.llm_base_url, mock_llm=args.mock_llm or None, skeptic_external_arxiv=args.skeptic_external_arxiv)
        # ---- finalization: config-driven. Default mode == family_report runs the SGHA-native
        # direct_formulations -> ambition_expansion(+critic) -> family_quality -> neutral final report.
        # Legacy evolution path only when finalization.mode == evolution_report (or use_evolution: true).
        fin = (cfg.get("finalization", {}) or {})
        if fin.get("mode", "family_report") == "family_report" and not fin.get("use_evolution", False):
            from .final_family_report import run_finalization
            meta = run_finalization(ctx, llm_base_url=args.llm_base_url, force=bool(getattr(args, "force", False)))
            print(f"run_id={ctx.run_id}")
            print(f"finalization_mode={meta.get('mode')}")
            print(f"final_report_dir={ctx.path(cfg.get('final_report', {}).get('output_dir', 'final_sgha_family_report'))}")
        else:
            evolve_hypotheses(ctx, generations=args.generations, population_size=args.population_size)
            md, html = build_report(ctx)
            print(f"run_id={ctx.run_id}")
            print(f"finalization_mode=evolution_report")
            print(f"report_md={md}")
            print(f"report_html={html}")
    elif args.command == "finalize":
        from .final_family_report import run_finalization
        meta = run_finalization(ctx, llm_base_url=args.llm_base_url, force=bool(getattr(args, "force", False)))
        print(f"run_id={ctx.run_id}")
        print(f"finalization_mode={meta.get('mode')}")
    else:  # pragma: no cover
        raise ValueError(args.command)
    return 0


def effective_config(args: argparse.Namespace) -> dict[str, Any]:
    overrides = cli_overrides(
        query=getattr(args, "query", None),
        max_results=getattr(args, "max_results", None),
        output_root=getattr(args, "output_root", None),
        dataset_root=getattr(args, "dataset_root", None),
        llm_base_url=getattr(args, "llm_base_url", None),
        mock_llm=True if getattr(args, "mock_llm", False) else None,
        generations=getattr(args, "generations", None),
        population_size=getattr(args, "population_size", None),
        skeptic_external_arxiv=True if getattr(args, "skeptic_external_arxiv", False) else None,
    )
    config_paths = list(getattr(args, "config", []) or [])
    retrieval_config = getattr(args, "retrieval_config", None)
    if retrieval_config:
        config_paths.append(retrieval_config)
    cfg = load_config(config_paths, overrides)
    run_id = getattr(args, "run_id", None)
    if run_id:
        run_cfg_path = Path(cfg["output_root"]) / "runs" / run_id / "run_config.yaml"
        if run_cfg_path.exists():
            with run_cfg_path.open("r", encoding="utf-8") as f:
                run_cfg = yaml.safe_load(f) or {}
            cfg = deep_merge(run_cfg, overrides)
    return cfg


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
