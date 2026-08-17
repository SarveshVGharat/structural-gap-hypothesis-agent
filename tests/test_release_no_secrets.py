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
