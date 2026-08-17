from __future__ import annotations

from pathlib import Path

from scripts.audit_release import audit


ROOT = Path(__file__).resolve().parents[1]


def test_release_audit_has_no_findings() -> None:
    findings = audit(ROOT)
    assert findings == []


def test_forbidden_runtime_files_absent() -> None:
    forbidden_names = {"environment.txt", "llm_calls.jsonl"}
    assert not [p for p in ROOT.rglob("*") if p.name in forbidden_names]


def test_no_nested_git_directories() -> None:
    assert not [p for p in ROOT.rglob(".git") if p.is_dir() and p != ROOT / ".git"]


def test_no_raw_pdfs_or_parsed_full_text_dirs() -> None:
    parsed_names = {"parsed_texts", "paper_texts", "parsed_full_texts", "full_texts"}
    assert not [p for p in ROOT.rglob("*.pdf")]
    assert not [p for p in ROOT.rglob("*") if p.is_dir() and p.name in parsed_names]


def test_audit_ignores_local_virtualenv_dirs(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()
    private_home = "/" + "users" + "/student/example/python"
    (venv / "pyvenv.cfg").write_text(f"home = {private_home}\n", encoding="utf-8")

    findings = audit(tmp_path)
    assert findings == []


def test_audit_rejects_nested_git_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "vendor" / ".git"
    nested.mkdir(parents=True)

    findings = audit(tmp_path)
    assert any(finding.kind == "nested_git" for finding in findings)


def test_audit_rejects_env_files(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("PLACEHOLDER=1\n", encoding="utf-8")

    findings = audit(tmp_path)
    assert any(finding.kind == "env_file" for finding in findings)
