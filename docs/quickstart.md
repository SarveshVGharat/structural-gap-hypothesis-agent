# Quickstart

This path is offline-safe. It does not call an LLM, OpenRouter, paper APIs, or the network.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run the Offline Smoke Test

```bash
sgha smoke-test
```

The command loads `examples/local_text_corpus/config.yaml`, validates the tiny synthetic corpus, writes a mock SGHA output tree under a temporary directory, and prints a summary.

Equivalent script form:

```bash
python scripts/run_offline_smoke_test.py
```

## Copy the Example Project

```bash
sgha init-example ./my_sgha_example
sgha validate-config ./my_sgha_example/config.yaml
sgha smoke-test --example-config ./my_sgha_example/config.yaml
```

Replace the synthetic files in `./my_sgha_example/papers/` with local text extracted from papers you are allowed to use, then edit `papers.jsonl`.

## Inspect Outputs

```bash
sgha summarize-run /path/to/mock_or_real_run
python scripts/summarize_run_outputs.py --run-dir /path/to/mock_or_real_run
```

See `docs/output_structure.md` for the expected stage directories and common files.

## Stage Local Text for Model-Backed SGHA

After replacing the synthetic files with your own local paper text, prepare a run directory without calling a model:

```bash
sgha prepare-local-corpus ./my_sgha_example/config.yaml --run-id my_local_run --output-root ./my_sgha_example/sgha_outputs
```

This writes `./my_sgha_example/sgha_outputs/runs/my_local_run/`. Run model-backed stages only after you have configured your own local endpoint. See `docs/run_on_your_own_papers.md`.

## Next

- Run on local papers: `docs/run_on_your_own_papers.md`
- Configure SGHA: `docs/configuration.md`
- Reproduce paper artifacts: `docs/reproducing_paper_results.md`
