# Structural Gap Hypothesis Agent

Structural Gap Hypothesis Agent (SGHA) is an auditable pipeline for turning a scientific paper corpus into structured claims, evidence graphs, candidate research gaps, verified gap families, and formal problem formulations.

## What SGHA Produces

- paper-level extractions and scientific tuples
- graph artifacts linking methods, assumptions, limitations, tasks, datasets, and evidence
- candidate structural gaps and verification records
- direct and expanded research-problem formulations
- final SGHA family reports and formal problem JSON
- curated paper-result artifacts for inspecting the accompanying paper

## Quickstart

These commands are offline-safe: they do not call an LLM, OpenRouter, paper APIs, or the network.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
sgha smoke-test
```

The smoke test loads `examples/local_text_corpus/config.yaml`, validates a tiny synthetic corpus, writes a temporary mock output tree, and prints where it was created.

Useful next commands:

```bash
sgha init-example ./my_sgha_example
sgha validate-config ./my_sgha_example/config.yaml
sgha smoke-test --example-config ./my_sgha_example/config.yaml
sgha prepare-local-corpus ./my_sgha_example/config.yaml --run-id my_local_run --output-root ./my_sgha_example/sgha_outputs
sgha summarize-run ./my_sgha_example/sgha_outputs/runs/my_local_run
```

## Run on Your Own Papers

Start with the synthetic local corpus under `examples/local_text_corpus/`. Replace the text files with your own local paper text, edit `papers.jsonl`, and validate the config:

```bash
sgha validate-config examples/local_text_corpus/config.yaml
```

For model-backed SGHA stages, point the config to your own OpenAI-compatible endpoint:

```bash
export SGHA_LLM_BASE_URL=http://localhost:8000/v1
export SGHA_LLM_MODEL=your-local-model-name
export SGHA_LLM_API_KEY=EMPTY
```

Detailed workflow: `docs/run_on_your_own_papers.md`.

## Using An AI Coding Assistant

You can ask Codex, Claude Code, or a similar coding assistant to inspect the repo, run the offline smoke test, inspect paper artifacts, or prepare a local-corpus config. Start with `AGENTS.md` for general agent guidance, `CLAUDE.md` for Claude Code-oriented notes, and `docs/ai_reproduction_guide.md` for copy-paste prompts. The default assistant workflow should stay offline-safe; model-backed SGHA stages and LLM judging require explicit user-provided endpoints or API keys.

## Main Commands

```bash
sgha --help
sgha smoke-test --help
sgha init-example --help
sgha validate-config --help
sgha prepare-local-corpus --help
sgha summarize-run --help
python scripts/summarize_run_outputs.py --help
```

The full research pipeline commands are also exposed through `sgha --help`. Commands such as retrieval, parsing, extraction, verification, finalization, and `run-all` may require local models, network access, or user-provided corpora depending on configuration.

## Paper Artifacts

The curated artifact bundle is in `paper_artifacts/release_bundle/`. It contains paper-result artifacts such as candidate packets, final outputs, score tables, CSV/LaTeX tables, qualitative examples, manifests, source notes, and checksums.

For paper inspection, start with `paper_artifacts/release_bundle/main_results/` for key CSVs, `paper_artifacts/release_bundle/paper_examples/` for actual generated examples used in the paper, and `paper_artifacts/release_bundle/paper_run_configs/` for sanitized paper-run config templates. The toy corpus under `examples/local_text_corpus/` is only for trying the code offline.

Figures are not included in this artifact bundle unless explicitly added later for the camera-ready or arXiv source. Raw PDFs, parsed full texts, model weights, private logs, secrets, caches, and full run directories are not redistributed.

Artifact reproduction: `docs/reproducing_paper_results.md`.

## Docs

- `docs/quickstart.md`
- `docs/ai_reproduction_guide.md`
- `docs/run_on_your_own_papers.md`
- `docs/output_structure.md`
- `docs/configuration.md`
- `docs/pipeline.md`
- `docs/baselines.md`
- `docs/judging.md`
- `docs/data_and_artifacts.md`
- `docs/reproducing_paper_results.md`
- `docs/troubleshooting.md`

## Release Audit

Before publishing or committing new artifacts, run:

```bash
python scripts/audit_release.py
python -m pytest -q
```

The release audit checks for common blockers such as possible secrets, private paths, private hostnames, raw PDFs, parsed full-text directories, environment dumps, raw LLM logs, nested Git directories, and oversized files.

## Citation

Citation metadata is in `CITATION.cff`. Final arXiv details, author list, and DOI/arXiv identifiers are pending and marked with TODO placeholders.

## License

Code in this repository is released under Apache-2.0. Generated paper tables, figures if later added, candidate packets, score files, and derived summaries are intended for research reuse under CC-BY-4.0 unless otherwise specified in `paper_artifacts/README.md`. Third-party papers, PDFs, and full texts are not redistributed.
