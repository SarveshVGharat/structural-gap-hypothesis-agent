from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXAMPLE_CONFIG = REPO_ROOT / "examples" / "local_text_corpus" / "config.yaml"

STAGE_DIRS = [
    "extracted",
    "graph",
    "gaps",
    "verification",
    "stage7_direct_formulations",
    "stage8_ambition_expansion",
    "stage9_family_quality",
    "stage10_formal_problem_formulations",
    "final_sgha_family_report",
]

PRIVATE_TEXT_PATTERNS = [
    "/" + "users" + "/student/",
    "/" + "jan" + "aki/",
    "an" + "andi",
]
SECRET_PATTERNS = [
    re.compile(r"sk(?:-or-v1)?-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
]


def read_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config must be a YAML mapping: {config_path}")
    return data


def validate_config_file(path: str | Path, *, require_mock_llm: bool = False) -> tuple[dict[str, Any], list[str], list[str]]:
    config_path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, [f"could not read config: {exc}"], warnings

    for pattern in PRIVATE_TEXT_PATTERNS:
        if pattern in text:
            errors.append("config contains a private path or hostname pattern")
            break
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append("config contains a possible API token; use environment variables instead")

    try:
        config = read_yaml(config_path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        return {}, [str(exc)], warnings

    for key in ["output_root", "dataset_root"]:
        if not config.get(key):
            warnings.append(f"`{key}` is not set; SGHA will rely on defaults or command-line overrides")

    llm = config.get("llm")
    if not isinstance(llm, dict):
        warnings.append("`llm` section is missing")
    else:
        if require_mock_llm and llm.get("mock") is not True:
            errors.append("offline smoke test requires `llm.mock: true`")
        if not llm.get("base_url"):
            warnings.append("`llm.base_url` is not set")
        if not llm.get("model"):
            warnings.append("`llm.model` is not set")
        api_key = str(llm.get("api_key", "")).strip()
        if api_key and "$" not in api_key and api_key.upper() not in {"EMPTY", "NONE", "TODO"}:
            warnings.append("`llm.api_key` appears to be set directly; prefer an environment variable")

    retrieval = config.get("retrieval")
    if isinstance(retrieval, dict) and retrieval.get("enabled"):
        warnings.append("retrieval is enabled; full retrieval commands may call external services or download papers")

    corpus = config.get("corpus")
    if corpus is not None and not isinstance(corpus, dict):
        errors.append("`corpus` must be a mapping when provided")
    elif isinstance(corpus, dict):
        manifest = corpus.get("manifest_path")
        if manifest:
            manifest_path = resolve_config_path(config_path, manifest)
            if not manifest_path.exists():
                errors.append(f"corpus manifest does not exist: {manifest}")

    return config, errors, warnings


def resolve_config_path(config_path: str | Path, value: str | Path) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate
    return (Path(config_path).resolve().parent / candidate).resolve()


def papers_manifest_path(config_path: str | Path, config: dict[str, Any]) -> Path:
    corpus = config.get("corpus") if isinstance(config.get("corpus"), dict) else {}
    manifest = corpus.get("manifest_path") or config.get("papers_manifest") or config.get("papers_jsonl")
    if manifest:
        return resolve_config_path(config_path, manifest)
    default_manifest = Path(config_path).resolve().parent / "papers.jsonl"
    if default_manifest.exists():
        return default_manifest
    raise ValueError("no papers manifest found; set `corpus.manifest_path` or place papers.jsonl next to the config")


def load_papers_manifest(config_path: str | Path, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config_data = config or read_yaml(config_path)
    manifest_path = papers_manifest_path(config_path, config_data)
    papers: list[dict[str, Any]] = []
    for line_no, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{manifest_path}:{line_no}: invalid JSON: {exc}") from exc
        missing = [field for field in ["paper_id", "title", "authors", "year", "source"] if field not in record]
        if missing:
            raise ValueError(f"{manifest_path}:{line_no}: missing fields: {', '.join(missing)}")
        if "text_path" not in record and "pdf_path" not in record:
            raise ValueError(f"{manifest_path}:{line_no}: expected text_path or pdf_path")
        if "text_path" in record:
            text_path = Path(str(record["text_path"]))
            resolved = text_path if text_path.is_absolute() else (manifest_path.parent / text_path).resolve()
            if not resolved.exists():
                raise ValueError(f"{manifest_path}:{line_no}: text_path does not exist: {record['text_path']}")
        papers.append(record)
    if not papers:
        raise ValueError(f"papers manifest is empty: {manifest_path}")
    return papers


def build_synthetic_objects() -> dict[str, Any]:
    from retrieval.models import CandidatePaper, RetrievalFacet, RetrievalPlan, ScoredPaper

    from .extraction_schemas import PaperExtraction, ScientificTuple
    from .gap_objects import CandidateGap, VerificationResult

    paper = CandidatePaper(
        arxiv_id="synthetic:001",
        title="Synthetic Offline SGHA Smoke Test",
        abstract="A tiny synthetic record used only to validate public-release imports.",
    )
    scored = ScoredPaper(**paper.model_dump(), metadata_score=1.0, final_score=1.0)
    plan = RetrievalPlan(
        original_query="synthetic smoke test",
        facets=[
            RetrievalFacet(
                facet_id="facet_001",
                label="offline synthetic validation",
                keywords=["synthetic", "validation"],
            )
        ],
    )
    tup = ScientificTuple(
        subject="SyntheticMethod",
        relation="fails_under",
        object="distribution shift",
        evidence_text="synthetic evidence only",
        confidence=0.8,
        claim_type="failure",
        polarity="negative",
    )
    extraction = PaperExtraction(
        paper_id="synthetic:001",
        claims=["synthetic claim"],
        limitations=["synthetic limitation"],
        failure_conditions=["distribution shift"],
        tuples=[tup],
    )
    gap = CandidateGap(
        gap_id="gap_synthetic_001",
        gap="Synthetic methods need validation under distribution shift.",
        target="distribution shift",
        motif_type="synthetic_smoke",
        overall_score=0.5,
        paper_ids=["synthetic:001"],
    )
    verification = VerificationResult(
        gap_id=gap.gap_id,
        agent_name="support_agent",
        summary="Synthetic verification object for offline smoke testing.",
        confidence=0.75,
    )
    return {
        "retrieval_plan": plan.model_dump(),
        "candidate_paper": scored.model_dump(),
        "paper_extraction": extraction.model_dump(),
        "candidate_gap": gap.model_dump(),
        "verification": verification.model_dump(),
    }


def create_mock_run(config_path: str | Path = DEFAULT_EXAMPLE_CONFIG, output_dir: str | Path | None = None) -> dict[str, Any]:
    config, errors, warnings = validate_config_file(config_path, require_mock_llm=True)
    if errors:
        raise ValueError("; ".join(errors))
    papers = load_papers_manifest(config_path, config)

    run_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="sgha_offline_demo_"))
    run_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGE_DIRS:
        (run_dir / stage).mkdir(parents=True, exist_ok=True)

    extractions = []
    tuples = []
    manifest_path = papers_manifest_path(config_path, config)
    for index, paper in enumerate(papers, start=1):
        text_path = manifest_path.parent / str(paper.get("text_path", ""))
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        snippet = " ".join(text.split())[:260]
        paper_id = str(paper["paper_id"])
        tuple_record = {
            "paper_id": paper_id,
            "subject": f"{paper_id}_toy_method",
            "relation": "limited_by",
            "object": "small distribution shifts",
            "evidence_text": snippet,
            "confidence": round(0.72 + (index * 0.03), 2),
            "claim_type": "limitation",
            "polarity": "negative",
        }
        tuples.append(tuple_record)
        extractions.append(
            {
                "paper_id": paper_id,
                "title": paper["title"],
                "claims": [f"{paper['title']} studies a synthetic toy robustness setting."],
                "limitations": ["Synthetic smoke-test limitation; not a scientific result."],
                "failure_conditions": ["small distribution shifts"],
                "tuples": [tuple_record],
            }
        )

    gaps = [
        {
            "gap_id": "mock_gap_001",
            "gap": "Toy adaptation methods lack a shared stress test for shift-aware calibration.",
            "target": "shift-aware calibration",
            "motif_type": "missing_bridge",
            "overall_score": 0.61,
            "paper_ids": [str(p["paper_id"]) for p in papers],
            "offline_demo": True,
        },
        {
            "gap_id": "mock_gap_002",
            "gap": "Synthetic retrieval examples do not compare memory budgets and feedback frequency.",
            "target": "memory-budgeted retrieval",
            "motif_type": "unresolved_tradeoff",
            "overall_score": 0.54,
            "paper_ids": [str(p["paper_id"]) for p in papers[:2]],
            "offline_demo": True,
        },
    ]
    verification_rows = [
        {
            "gap_id": gap["gap_id"],
            "agent_name": "support_agent",
            "summary": "Offline mock verification only; no model or network call was made.",
            "confidence": 0.7,
        }
        for gap in gaps
    ]
    direct_formulations = [
        {
            "formulation_id": "mock_direct_001",
            "gap_id": "mock_gap_001",
            "problem": "Design a tiny benchmark for calibration under controlled synthetic shifts.",
            "offline_demo": True,
        }
    ]
    expanded_formulations = [
        {
            "formulation_id": "mock_expanded_001",
            "parent_id": "mock_direct_001",
            "problem": "Compare confidence calibration, retrieval refresh rate, and memory limits in a toy setting.",
            "offline_demo": True,
        }
    ]
    formal_problems = [
        {
            "problem_id": "mock_formal_problem_001",
            "family_id": "mock_family_001",
            "title": "Synthetic Shift Calibration Under Memory Limits",
            "inputs": ["three synthetic text records", "toy shift labels"],
            "objective": "Minimize calibration error while limiting retrieval refreshes.",
            "constraints": ["offline demo only", "not a scientific claim"],
        }
    ]
    families = [
        {
            "family_id": "mock_family_001",
            "title": "Toy Robustness and Calibration",
            "gap_ids": ["mock_gap_001", "mock_gap_002"],
            "formal_problem_ids": ["mock_formal_problem_001"],
            "summary": "A mock family showing the shape of SGHA final outputs.",
            "offline_demo": True,
        }
    ]

    write_json(run_dir / "extracted" / "all_extractions.json", extractions)
    write_jsonl(run_dir / "extracted" / "all_tuples.jsonl", tuples)
    write_json(
        run_dir / "graph" / "graph_summary.json",
        {"paper_count": len(papers), "tuple_count": len(tuples), "offline_demo": True},
    )
    write_json(
        run_dir / "graph" / "graph.json",
        {
            "nodes": [{"id": item["paper_id"], "type": "paper", "label": item["title"]} for item in papers],
            "edges": [{"source": row["paper_id"], "target": row["object"], "relation": row["relation"]} for row in tuples],
        },
    )
    write_json(run_dir / "gaps" / "candidate_gaps.json", gaps)
    write_jsonl(run_dir / "verification" / "verification_results.jsonl", verification_rows)
    write_json(run_dir / "verification" / "verified_gaps.json", gaps)
    write_jsonl(run_dir / "stage7_direct_formulations" / "direct_formulations.jsonl", direct_formulations)
    write_jsonl(run_dir / "stage8_ambition_expansion" / "expanded_formulations.jsonl", expanded_formulations)
    write_json(run_dir / "stage9_family_quality" / "family_quality_scores.json", {"families": families, "offline_demo": True})
    write_jsonl(run_dir / "stage10_formal_problem_formulations" / "formal_problem_formulations.jsonl", formal_problems)
    write_json(run_dir / "final_sgha_family_report" / "final_project_families.json", {"families": families})
    write_json(run_dir / "final_sgha_family_report" / "formal_problem_statements.json", formal_problems)
    write_text(
        run_dir / "final_sgha_family_report" / "final_report.md",
        "# Offline SGHA Smoke-Test Report\n\n"
        "This mock report demonstrates the public output structure only. "
        "It was generated from tiny synthetic text and did not call an LLM or any network service.\n",
    )

    summary = summarize_run(run_dir)
    write_json(
        run_dir / "RUN_SUMMARY.json",
        {
            "status": "ok",
            "config": str(config_path),
            "warnings": warnings,
            "summary": summary,
            "synthetic_objects": build_synthetic_objects(),
        },
    )
    return {"run_dir": run_dir, "summary": summary, "warnings": warnings}


def prepare_local_corpus(
    config_path: str | Path,
    *,
    run_id: str | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    config, errors, warnings = validate_config_file(config_path)
    if errors:
        raise ValueError("; ".join(errors))
    papers = load_papers_manifest(config_path, config)
    manifest_path = papers_manifest_path(config_path, config)

    configured_output = output_root or config.get("output_root") or "./runs"
    configured_output_text = str(configured_output)
    if "${" in configured_output_text:
        raise ValueError("output_root uses an environment placeholder; pass --output-root for local corpus prep")
    output_root_path = Path(configured_output_text).resolve()
    run_name = run_id or f"local_corpus_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = output_root_path / "runs" / run_name

    (run_dir / "arxiv").mkdir(parents=True, exist_ok=True)
    (run_dir / "parsed" / "paper_sections").mkdir(parents=True, exist_ok=True)

    paper_manifest = []
    parsed_manifest = []
    for paper in papers:
        paper_id = str(paper["paper_id"])
        title = str(paper.get("title", paper_id))
        authors = paper.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]
        text_path = _resolve_manifest_member(manifest_path, paper.get("text_path"))
        text = text_path.read_text(encoding="utf-8")
        safe_id = _safe_file_stem(paper_id)
        sections_path = run_dir / "parsed" / "paper_sections" / f"{safe_id}.json"
        write_json(
            sections_path,
            {
                "full_text": {
                    "start_char": 0,
                    "end_char": len(text),
                    "text_preview": " ".join(text.split())[:500],
                }
            },
        )
        paper_manifest.append(
            {
                "arxiv_id": paper_id,
                "title": title,
                "authors": authors,
                "abstract": str(paper.get("abstract", "")),
                "categories": [],
                "published": str(paper.get("year", "")),
                "updated": "",
                "pdf_url": "",
                "local_pdf_path": str(paper.get("pdf_path", "")),
                "download_status": "local_text_provided",
                "sha256": "",
                "source_query": str(paper.get("source", "local")),
            }
        )
        parsed_manifest.append(
            {
                "paper_id": paper_id,
                "arxiv_id": paper_id,
                "title": title,
                "text_path": str(text_path),
                "sections_path": str(sections_path),
                "parser": "local_text_manifest",
                "full_text_chars": len(text),
                "pages": 0,
                "quality": {"status": "ok", "source": "local_text", "synthetic": paper.get("source") == "synthetic_example"},
            }
        )

    write_json(run_dir / "arxiv" / "papers_manifest.json", paper_manifest)
    write_json(run_dir / "parsed" / "parsed_manifest.json", parsed_manifest)
    write_text(
        run_dir / "LOCAL_CORPUS_PREPARED.md",
        "# Local Corpus Prepared\n\n"
        "This run directory was prepared from a local `papers.jsonl` manifest. "
        "No LLM, OpenRouter, paper API, or network call was used during preparation.\n",
    )
    write_json(
        run_dir / "local_corpus_prep_summary.json",
        {
            "run_id": run_name,
            "paper_count": len(papers),
            "config": str(config_path),
            "manifest": str(manifest_path),
            "warnings": warnings,
        },
    )
    return {"run_id": run_name, "run_dir": run_dir, "paper_count": len(papers), "warnings": warnings}


def summarize_run(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    extracted = _read_json(root / "extracted" / "all_extractions.json")
    tuple_count = _count_jsonl(root / "extracted" / "all_tuples.jsonl")
    if tuple_count == 0 and isinstance(extracted, list):
        tuple_count = sum(len(item.get("tuples", [])) for item in extracted if isinstance(item, dict))

    candidate_gaps = _read_json(root / "gaps" / "candidate_gaps.json")
    verified_gaps = _read_json(root / "verification" / "verified_gaps.json")
    direct_count = _count_jsonl(root / "stage7_direct_formulations" / "direct_formulations.jsonl")
    formal_count = _count_jsonl(root / "stage10_formal_problem_formulations" / "formal_problem_formulations.jsonl")
    if formal_count == 0:
        formal_count = _count_items(_read_json(root / "final_sgha_family_report" / "formal_problem_statements.json"))
    families = _read_json(root / "final_sgha_family_report" / "final_project_families.json")
    final_report = _first_existing(
        [
            root / "final_sgha_family_report" / "final_report.md",
            root / "final_sgha_family_report" / "final_report_polished.md",
            root / "final_sgha_family_report" / "report.md",
            root / "final_sgha_family_report" / "final_report.html",
        ]
    )

    return {
        "run_dir": str(root),
        "run_dir_exists": root.exists(),
        "extracted_paper_count": _count_items(extracted),
        "tuple_count": tuple_count,
        "candidate_gap_count": _count_items(candidate_gaps),
        "verified_gap_count": _count_items(verified_gaps),
        "direct_formulation_count": direct_count,
        "final_family_count": _count_items(families),
        "formal_problem_count": formal_count,
        "final_report_path": str(final_report) if final_report else None,
    }


def format_run_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Run directory: {summary.get('run_dir')}",
        f"Run directory exists: {summary.get('run_dir_exists')}",
        f"Extracted papers: {summary.get('extracted_paper_count', 0)}",
        f"Scientific tuples: {summary.get('tuple_count', 0)}",
        f"Candidate gaps: {summary.get('candidate_gap_count', 0)}",
        f"Verified gaps: {summary.get('verified_gap_count', 0)}",
        f"Direct formulations: {summary.get('direct_formulation_count', 0)}",
        f"Final families: {summary.get('final_family_count', 0)}",
        f"Formal problems: {summary.get('formal_problem_count', 0)}",
    ]
    final_report = summary.get("final_report_path")
    lines.append(f"Final report: {final_report if final_report else 'not found'}")
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _count_items(data: Any) -> int:
    if data is None:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ["families", "items", "records", "gaps", "problems", "papers", "extractions"]:
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        if data:
            return 1
    return 0


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _resolve_manifest_member(manifest_path: Path, value: Any) -> Path:
    if not value:
        raise ValueError("local corpus prep requires text_path for each paper")
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else (manifest_path.parent / candidate).resolve()


def _safe_file_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "paper"
