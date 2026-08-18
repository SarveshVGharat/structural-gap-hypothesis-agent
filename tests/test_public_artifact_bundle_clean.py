from __future__ import annotations

from pathlib import Path

from scripts.audit_release import audit


ROOT = Path(__file__).resolve().parents[1]


def test_public_artifact_bundle_has_no_internal_notes() -> None:
    findings = [
        finding
        for finding in audit(ROOT)
        if finding.kind in {"internal_bundle_note", "table_allowlist_note"}
    ]
    assert findings == []


def test_audit_rejects_internal_notes_inside_release_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "paper_artifacts" / "release_bundle"
    bundle.mkdir(parents=True)
    (bundle / "example.md").write_text(
        "coauthor note: do not show this bad example\nsutton_barto_rl\n",
        encoding="utf-8",
    )

    findings = audit(tmp_path)

    assert any(finding.kind == "internal_bundle_note" for finding in findings)


def test_audit_scopes_internal_note_check_to_release_bundle(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "release_process.md").write_text(
        "Internal review note: do not show rejected artifacts in the bundle.\n",
        encoding="utf-8",
    )

    findings = audit(tmp_path)

    assert [finding for finding in findings if finding.kind == "internal_bundle_note"] == []


def test_audit_rejects_table_allowlist_notes_inside_release_bundle(tmp_path: Path) -> None:
    table_dir = tmp_path / "paper_artifacts" / "release_bundle" / "main_results"
    table_dir.mkdir(parents=True)
    (table_dir / "pipeline_yield.csv").write_text(
        "domain,status\nexample,blocked clean later\n",
        encoding="utf-8",
    )

    findings = audit(tmp_path)

    assert any(finding.kind == "table_allowlist_note" for finding in findings)
