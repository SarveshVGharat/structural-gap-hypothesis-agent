# Claude Code Guidance for SGHA

This repository contains Structural Gap Hypothesis Agent (SGHA), an auditable pipeline for converting scientific paper corpora into evidence graphs, research-gap candidates, final problem families, and formal problem statements.

## Recommended First Commands

```bash
python -m pip install -e ".[dev]"
sgha smoke-test
pytest -q
python scripts/audit_release.py
cd paper_artifacts/release_bundle && sha256sum -c CHECKSUMS.sha256
```

The default workflow is offline-safe. Do not call an LLM, OpenRouter, paper APIs, or external services unless the user explicitly asks for that behavior and provides the needed endpoint or key.

## Repo Map

- `src/sgha/`: main SGHA code, CLI commands, offline demo utilities, prompts, schemas, and stage modules.
- `src/retrieval/`: retrieval/query utilities and backend adapters.
- `configs/` and `configs/examples/`: configuration examples.
- `examples/local_text_corpus/`: tiny synthetic corpus for smoke tests.
- `docs/`: quickstart, pipeline, configuration, artifact, baseline, judging, and troubleshooting docs.
- `paper_artifacts/release_bundle/`: sanitized paper artifacts, including result CSVs, candidate packets, curated examples, score tables, manifests, and checksums.

## Common Tasks

- Understand the repo: inspect `README.md`, `docs/quickstart.md`, `docs/run_on_your_own_papers.md`, and this file.
- Run the offline demo: `sgha smoke-test`.
- Create a local example: `sgha init-example ./my_sgha_example`.
- Validate a config: `sgha validate-config ./my_sgha_example/config.yaml`.
- Summarize a run: `sgha summarize-run <run_dir>`.
- Inspect paper artifacts: start with `paper_artifacts/release_bundle/README.md` and `MANIFEST.csv`.

## Safety Constraints

- Do not add secrets, API keys, auth dumps, or `.env` files.
- Do not commit raw PDFs, parsed full texts, logs, caches, model weights, raw prompts, or raw model responses.
- Do not download papers by default.
- Do not run full SGHA or LLM judging unless the user explicitly requests it and supplies a local model endpoint or API key.
- Keep examples synthetic/offline unless the user provides local data.

## Avoiding Accidental API Calls

Prefer `sgha smoke-test`, `sgha init-example`, `sgha validate-config`, and artifact inspection commands for default tasks. Treat model-backed pipeline stages and judge scripts as opt-in. If a command requires `SGHA_LLM_BASE_URL`, `SGHA_LLM_MODEL`, or `OPENROUTER_API_KEY`, explain the requirement before running it.
