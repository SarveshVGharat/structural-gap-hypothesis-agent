# Release Validation Report

Status: PASS for the public staging metadata, artifact bundle, curated paper examples/configs, AI-assistant guidance layer, usability layer, external-user dry run, and post-clone release fix.

## Metadata and Licensing

- `LICENSE`: full Apache-2.0 license text is present.
- `README.md`: public-facing quickstart, local-corpus workflow, license, citation, and artifact/data policy sections are present and dry-run checked.
- `AGENTS.md`: root-level coding-agent guidance is present.
- `CLAUDE.md`: Claude Code-oriented guidance is present.
- `docs/ai_reproduction_guide.md`: offline-safe copy-paste prompts for agent-assisted reproduction are present.
- `paper_artifacts/README.md`: artifact license note and exclusion policy are present.
- `CITATION.cff`: software metadata is present; final arXiv paper title, author list, DOI, repository URL, and arXiv identifier remain TODO placeholders.
- `pyproject.toml`: package metadata, console script, classifiers, and placeholder project URLs are present.
- `.gitignore`: release-safe ignore rules are present for virtualenvs, caches, runtime outputs, raw PDFs/full texts, model artifacts, and credential files.
- `.gitattributes`: LF normalization is enforced for release text artifacts, with common binary-file markers present; Git LFS is not required.

## Paper Artifact Bundle

- `paper_artifacts/release_bundle/`: curated public artifact bundle is present.
- Bundle file count: 295 files.
- Manifest rows: 295, with no MISSING rows.
- Figure artifacts are not part of the current public artifact bundle.
- `paper_examples/`: curated actual generated examples from the paper runs are present for main SGHA, baselines, profile-conditioned generation, and evolutionary exploration.
- `paper_run_configs/`: sanitized YAML templates are present for main domains, profile-conditioned runs, judging, and baselines.
- `main_results/`: compact result CSVs and qualitative example overview are present.
- `profile_conditioned/sanitized_profile_contexts/`: compact public-safe profile context JSON files are present.
- `CHECKSUMS.sha256`: regenerated for 294 LF-normalized bundle files, excluding the checksum file itself, and verified with `sha256sum -c CHECKSUMS.sha256`.
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
- `pytest --collect-only -q`: passed, 21 tests collected.
- `pytest -q`: passed, 21 tests passed.
- `python scripts/audit_release.py`: passed with 0 findings.
- Artifact bundle checksum verification: passed.
- Explicit scan of new `paper_examples/` and `paper_run_configs/` for private paths, private host patterns, key-shaped strings, SSO credential hints, raw PDF filenames, and raw LLM output names: passed with 0 findings.
- Explicit scan of `AGENTS.md`, `CLAUDE.md`, `docs/ai_reproduction_guide.md`, and `README.md` for private paths, key-shaped strings, raw PDF filenames, parsed full-text paths, raw LLM output names, and private host patterns: passed with 0 findings.
- `sgha smoke-test`: passed after refreshing the current editable install to point at the staging repo.
- Fresh temporary clone smoke test: passed with a clean virtualenv install, `sgha smoke-test`, `pytest -q`, `python scripts/audit_release.py`, and `sha256sum -c CHECKSUMS.sha256`.
- Large-file scan with `find . -type f -size +25M`: passed, no files found.
- Cache/raw artifact scan: passed, no `__pycache__`, `.pytest_cache`, raw PDFs, parsed full-text directories, runtime logs, `.env` files, or nested Git directories found in the staging tree.
- In-repository local virtualenv simulation: passed. A fake `.venv/pyvenv.cfg` with a private-looking absolute path was ignored by the release audit and tests, then removed.

## Git Preparation And Push

- The staging directory is a Git repository on branch `main` with `origin` set for the public SGHA repository.
- Release-audit tooling now skips normal local development directories while still rejecting nested Git directories and release-managed raw artifacts.
- The checksum bundle was regenerated after LF normalization fixes.
- The post-clone fix is validated and committed locally for GitHub push.

## Release Audit

- `python scripts/audit_release.py`: passed.
- Findings: 0.
- Report: `RELEASE_AUDIT_REPORT.md`.

## Remaining Blockers

No metadata, artifact-bundle, dry-run, usability, or Git-prep blockers remain for this staging pass. Remaining release decisions are tracked in `TODO_RELEASE.md`.
