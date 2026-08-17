#!/usr/bin/env python3
"""Audit the staged SGHA public-release tree for common release blockers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import re
from typing import Iterable


DEFAULT_MAX_BYTES = 5 * 1024 * 1024
PRIVATE_PATH_PATTERNS = ["/" + "users" + "/student/", "/" + "jan" + "aki/"]
PRIVATE_HOST_PATTERNS = ["an" + "andi"]
SECRET_PATTERNS = {
    "openai_or_openrouter_key": re.compile(r"sk(?:-or-v1)?-[A-Za-z0-9_-]{20,}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    "github_token": re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    "huggingface_token": re.compile(r"hf_[A-Za-z0-9]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}
RAW_TEXT_DIR_NAMES = {"parsed_texts", "paper_texts", "parsed_full_texts", "full_texts"}
RAW_LLM_NAMES = {"llm_calls.jsonl", "environment.txt"}
RAW_LLM_DIR_NAMES = {"llm_raw_outputs", "llm_parsed_outputs", "prompts_runtime"}
SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache"}


@dataclass
class Finding:
    kind: str
    path: Path
    reason: str


def iter_paths(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if rel.parts == (".git",):
            continue
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            if path.name in SKIP_DIR_NAMES:
                yield path
            continue
        yield path


def read_text_safely(path: Path) -> str:
    try:
        if path.stat().st_size > DEFAULT_MAX_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def audit(root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> list[Finding]:
    findings: list[Finding] = []
    root = root.resolve()
    for path in iter_paths(root):
        rel = path.relative_to(root)
        rel_text = str(rel)

        if path.is_dir():
            if path.name == ".git" and rel.parts != (".git",):
                findings.append(Finding("nested_git", rel, "nested Git directory"))
            if path.name in RAW_TEXT_DIR_NAMES:
                findings.append(Finding("parsed_full_text", rel, "parsed full-text directory name"))
            if path.name in RAW_LLM_DIR_NAMES:
                findings.append(Finding("raw_llm", rel, "raw LLM output directory name"))
            continue

        if path.name in RAW_LLM_NAMES:
            findings.append(Finding("raw_llm", rel, "runtime environment or LLM call log"))
        if path.suffix.lower() == ".pdf":
            findings.append(Finding("raw_pdf", rel, "PDFs are excluded from the public repo"))
        if path.stat().st_size > max_bytes:
            findings.append(Finding("huge_file", rel, f"file exceeds {max_bytes} bytes"))

        text = read_text_safely(path)
        if not text:
            continue
        for private_path in PRIVATE_PATH_PATTERNS:
            if private_path in text:
                findings.append(Finding("private_path", rel, "private absolute path pattern"))
        for host in PRIVATE_HOST_PATTERNS:
            if host in text:
                findings.append(Finding("private_hostname", rel, "private hostname pattern"))
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(Finding("possible_secret", rel, label))

    return findings


def write_report(path: Path, findings: list[Finding]) -> None:
    lines = ["# Release Audit Report", ""]
    if findings:
        lines.append(f"Status: FAIL ({len(findings)} findings)")
        lines.append("")
        for finding in findings:
            lines.append(f"- `{finding.kind}` in `{finding.path}`: {finding.reason}")
    else:
        lines.append("Status: PASS")
        lines.append("")
        lines.append("No possible secrets, private paths, private hosts, raw PDFs, parsed full-text directories, environment dumps, raw LLM logs, nested Git directories, or oversized files were found.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = args.report or (root / "RELEASE_AUDIT_REPORT.md")
    findings = audit(root, max_bytes=args.max_bytes)
    write_report(report, findings)
    print(f"release audit findings: {len(findings)}")
    print(f"report: {report}")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
