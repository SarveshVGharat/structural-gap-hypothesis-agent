# Using Codex or Claude Code with SGHA

This guide gives copy-paste prompts for using a coding agent with SGHA. The default path is offline and safe: it should not call an LLM, OpenRouter, paper APIs, or external services.

## Prompt A: Understand The Repo

```text
Inspect this SGHA repository without calling external APIs or downloading papers. Summarize the package layout, main CLI commands, examples, docs, and paper artifact bundle. Explain the safe offline workflow, including `sgha smoke-test`, `pytest -q`, `python scripts/audit_release.py`, and checksum verification under `paper_artifacts/release_bundle/`.
```

## Prompt B: Run The Offline Smoke Test

```text
Act as an external user. Create a clean virtual environment, install the repo with `python -m pip install -e ".[dev]"`, then run `sgha smoke-test`, `pytest -q`, `python scripts/audit_release.py`, and `cd paper_artifacts/release_bundle && sha256sum -c CHECKSUMS.sha256`. Do not call an LLM, OpenRouter, paper APIs, or external services. Report each command and whether it passed.
```

## Prompt C: Try The Local Text-Corpus Example

```text
Use only the offline example workflow. Run `sgha init-example ./my_sgha_example`, validate it with `sgha validate-config ./my_sgha_example/config.yaml`, inspect the generated example files, and explain how I would replace the synthetic text files and `papers.jsonl` entries with my own local papers or parsed text. Do not call any model or external API.
```

## Prompt D: Inspect Paper Artifacts

```text
Inspect `paper_artifacts/release_bundle/` without rerunning SGHA or judges. Read the bundle README and MANIFEST, list the main result CSVs, summarize the curated qualitative examples under `paper_examples/`, and verify the checksums with `sha256sum -c CHECKSUMS.sha256`. Do not download papers, call models, or use OpenRouter.
```

## Prompt E: Run With A Local Model Endpoint

This prompt is opt-in and requires a user-provided local OpenAI-compatible endpoint. Do not use it for the default offline smoke test.

```text
I have a local OpenAI-compatible model endpoint. First inspect the SGHA docs and configs. Then explain the commands needed to run SGHA on my local corpus using these placeholders: `SGHA_LLM_BASE_URL` and `SGHA_LLM_MODEL`. Before running any model-backed command, show me exactly which command would call the endpoint and ask for confirmation. Do not use OpenRouter and do not download papers.
```

## Prompt F: Run LLM Judging

This prompt is opt-in and requires a user-provided `OPENROUTER_API_KEY`. It should not be run by default.

```text
I want to rerun the SGHA judging workflow with my own OpenRouter key. Inspect `docs/judging.md` and `paper_artifacts/release_bundle/paper_run_configs/judging/`. Explain the required environment variable `OPENROUTER_API_KEY`, the candidate packets used for judging, the expected outputs, and the risks/costs. Do not print or store my key. Before running any judge command, show me the command and ask for confirmation.
```

## Notes For Agents

- Prefer offline artifact inspection and smoke tests unless the user explicitly asks for model-backed work.
- Do not add secrets, raw papers, parsed full texts, logs, caches, model weights, raw prompts, or raw model responses.
- Keep user-created examples local unless redistribution is permitted.
- Use `AGENTS.md` or `CLAUDE.md` at the repo root for quick operational guidance.
