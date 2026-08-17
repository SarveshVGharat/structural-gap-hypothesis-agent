# Agent Guidance for SGHA

Structural Gap Hypothesis Agent (SGHA) is an auditable research pipeline for turning a paper corpus into structured claims, evidence graphs, candidate research gaps, verified gap families, and formal problem formulations.

## Safe First Commands

Run these before making changes:

```bash
python -m pip install -e ".[dev]"
sgha smoke-test
pytest -q
python scripts/audit_release.py
cd paper_artifacts/release_bundle && sha256sum -c CHECKSUMS.sha256
```

These commands are offline-safe and should not call an LLM, OpenRouter, paper APIs, or external services.

## Repo Map

- `src/sgha/`: SGHA pipeline modules, CLI, offline demo helpers, schemas, prompts, and stage implementations.
- `src/retrieval/`: retrieval backends and query/planning utilities.
- `configs/` and `configs/examples/`: runtime and example configuration files.
- `prompts/`: prompt templates where present.
- `schemas/`: structured output schemas where present.
- `examples/local_text_corpus/`: tiny synthetic offline corpus for smoke tests and user onboarding.
- `docs/`: user documentation, reproduction notes, baseline/judge notes, and troubleshooting.
- `paper_artifacts/release_bundle/`: sanitized paper-result artifacts, candidate packets, score tables, examples, manifests, and checksums.

## Safety Rules

- Do not call external APIs unless the user explicitly asks.
- Do not download papers by default.
- Do not add secrets or real API keys.
- Do not commit `.env`, raw PDFs, parsed full texts, logs, caches, model weights, raw prompts, or raw model responses.
- Keep examples synthetic/offline unless the user provides their own data.
- Keep generated paper artifacts sanitized: no private paths, internal hosts, full run directories, or hidden secret values.

## Paper Artifact Inspection

Start at `paper_artifacts/release_bundle/README.md`. Use `MANIFEST.csv` to navigate the bundle, `main_results/` for key CSVs, `paper_examples/` for curated generated examples, and `paper_run_configs/` for sanitized paper-run config templates. Verify integrity from the bundle directory with:

```bash
sha256sum -c CHECKSUMS.sha256
```

Do not rerun SGHA or judges when the task is only to inspect paper artifacts.

## Run Summaries

To summarize an existing or partial run directory, use:

```bash
sgha summarize-run <run_dir>
```

The command handles missing stage files gracefully and prints counts plus the final-report path when available.
