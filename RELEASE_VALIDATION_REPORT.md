# Release Validation Report

Status: PASS for the public staging metadata, artifact bundle, usability layer, external-user dry run, and private GitHub pre-push preparation.

## Metadata and Licensing

- `LICENSE`: full Apache-2.0 license text is present.
- `README.md`: public-facing quickstart, local-corpus workflow, license, citation, and artifact/data policy sections are present and dry-run checked.
- `paper_artifacts/README.md`: artifact license note and exclusion policy are present.
- `CITATION.cff`: software metadata is present; final arXiv paper title, author list, DOI, repository URL, and arXiv identifier remain TODO placeholders.
- `pyproject.toml`: package metadata, console script, classifiers, and placeholder project URLs are present.
- `.gitignore`: release-safe ignore rules are present for caches, runtime outputs, raw PDFs/full texts, model artifacts, and credential files.
- `.gitattributes`: text normalization and common binary-file markers are present; Git LFS is not required.

## Paper Artifact Bundle

- `paper_artifacts/release_bundle/`: curated public artifact bundle is present.
- Bundle file count: 260 files.
- Manifest rows: 260, with no MISSING rows.
- Figure artifacts are not part of the current public artifact bundle.
- `CHECKSUMS.sha256`: generated for 259 bundle files, excluding the checksum file itself, and verified with `sha256sum -c CHECKSUMS.sha256`.
- `SECRET_LEAKAGE_CHECK.md`: passed with no findings.
- Source-paper PDFs, parsed full texts, generated figure files, raw model responses, private logs, secrets, caches, and full run directories are excluded.

## Usability Layer

- Fresh external-user editable install in a temporary directory: passed.
- Fresh external-user `.[dev]` editable install in a separate temporary directory: passed.
- `sgha smoke-test`: passed using the synthetic local text corpus and wrote a mock stage output tree to a temporary directory.
- `sgha init-example`: passed by copying the offline example project to a temporary directory.
- `sgha validate-config`: passed for the copied offline example config.
- `sgha prepare-local-corpus`: passed by staging local text metadata into SGHA manifest files without LLM, OpenRouter, paper API, or network calls.
- `sgha summarize-run`: passed on a mock run directory.
- `python scripts/run_offline_smoke_test.py`: passed.
- `python scripts/summarize_run_outputs.py --run-dir <tmp>`: passed.
- CLI help checks passed for `sgha`, `smoke-test`, `init-example`, `validate-config`, `prepare-local-corpus`, `summarize-run`, model-backed stage help commands, all public scripts under `scripts/`, and the artifact summary helper.
- `sgha summarize-run` on a missing run directory returned a graceful zero-count summary.
- `sgha init-example` on an existing non-empty directory returned a clean CLI error without a traceback.

Model-backed SGHA stage examples in the docs were not executed because they require a user-provided OpenAI-compatible endpoint and may call the configured model.

## Static and Test Checks

- `python -m py_compile` on all staged Python files: passed.
- `pytest --collect-only -q`: passed, 18 tests collected.
- `pytest -q`: passed, 18 tests passed.
- `python scripts/audit_release.py`: passed with 0 findings.
- Artifact bundle checksum verification: passed.
- Large-file scan with `find . -type f -size +25M`: passed, no files found.
- Cache/raw artifact scan: passed, no `__pycache__`, `.pytest_cache`, raw PDFs, parsed full-text directories, runtime logs, `.env` files, or nested Git directories found in the staging tree.

## Git Preparation

- A fresh Git repository was initialized in the staging directory on branch `main` without importing original research history.
- Release-ready files were staged for the initial commit after checking staged names and diff stats.
- The staged set contains 388 files, including sanitized source, docs, tests, configs, prompts, schemas, and the curated artifact bundle.
- The initial commit is pending local Git `user.name` and `user.email`; no author identity was invented during validation.
- No remote push was performed during validation.

## Release Audit

- `python scripts/audit_release.py`: passed.
- Findings: 0.
- Report: `RELEASE_AUDIT_REPORT.md`.

## Remaining Blockers

No metadata, artifact-bundle, dry-run, usability, or Git-prep blockers remain for this staging pass. Remaining release decisions are tracked in `TODO_RELEASE.md`.
