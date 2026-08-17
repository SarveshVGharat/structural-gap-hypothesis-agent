from __future__ import annotations

from pathlib import Path

from sgha.offline_demo import (
    DEFAULT_EXAMPLE_CONFIG,
    STAGE_DIRS,
    create_mock_run,
    load_papers_manifest,
    prepare_local_corpus,
    summarize_run,
    validate_config_file,
)


def test_local_text_example_config_validates() -> None:
    config, errors, _warnings = validate_config_file(DEFAULT_EXAMPLE_CONFIG, require_mock_llm=True)
    assert errors == []
    papers = load_papers_manifest(DEFAULT_EXAMPLE_CONFIG, config)
    assert len(papers) == 3
    assert {paper["paper_id"] for paper in papers} == {"toy-001", "toy-002", "toy-003"}


def test_create_mock_run_writes_expected_shape(tmp_path: Path) -> None:
    result = create_mock_run(DEFAULT_EXAMPLE_CONFIG, tmp_path / "mock_run")
    run_dir = result["run_dir"]

    for stage in STAGE_DIRS:
        assert (run_dir / stage).is_dir()
    assert (run_dir / "final_sgha_family_report" / "final_project_families.json").exists()
    assert (run_dir / "stage10_formal_problem_formulations" / "formal_problem_formulations.jsonl").exists()

    summary = summarize_run(run_dir)
    assert summary["extracted_paper_count"] == 3
    assert summary["tuple_count"] == 3
    assert summary["candidate_gap_count"] == 2
    assert summary["verified_gap_count"] == 2
    assert summary["direct_formulation_count"] == 1
    assert summary["final_family_count"] == 1
    assert summary["formal_problem_count"] == 1
    assert summary["final_report_path"]


def test_prepare_local_corpus_writes_pipeline_manifests(tmp_path: Path) -> None:
    result = prepare_local_corpus(DEFAULT_EXAMPLE_CONFIG, run_id="test_local", output_root=tmp_path / "out")
    run_dir = result["run_dir"]

    assert result["paper_count"] == 3
    assert (run_dir / "arxiv" / "papers_manifest.json").exists()
    assert (run_dir / "parsed" / "parsed_manifest.json").exists()
    assert (run_dir / "LOCAL_CORPUS_PREPARED.md").exists()


def test_summarize_run_handles_partial_missing_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "partial_run"
    run_dir.mkdir()

    summary = summarize_run(run_dir)
    assert summary["run_dir_exists"] is True
    assert summary["candidate_gap_count"] == 0
    assert summary["final_report_path"] is None


def test_summarize_script_prints_partial_summary(tmp_path: Path, capsys) -> None:
    from scripts.summarize_run_outputs import main

    run_dir = tmp_path / "partial_run"
    run_dir.mkdir()
    assert main(["--run-dir", str(run_dir)]) == 0
    captured = capsys.readouterr()
    assert "Candidate gaps: 0" in captured.out
    assert "Final report: not found" in captured.out


def test_cli_offline_commands(tmp_path: Path, capsys) -> None:
    from sgha.cli import main

    copied = tmp_path / "copied_example"
    run_dir = tmp_path / "cli_mock_run"

    assert main(["init-example", str(copied)]) == 0
    assert (copied / "config.yaml").exists()
    assert main(["validate-config", str(copied / "config.yaml")]) == 0
    assert main(["smoke-test", "--example-config", str(copied / "config.yaml"), "--output-dir", str(run_dir)]) == 0
    assert main(["prepare-local-corpus", str(copied / "config.yaml"), "--run-id", "cli_local", "--output-root", str(tmp_path / "out")]) == 0
    assert main(["summarize-run", str(run_dir)]) == 0

    captured = capsys.readouterr()
    assert "offline smoke test ok" in captured.out
    assert "local corpus prepared" in captured.out
    assert "Final families: 1" in captured.out
