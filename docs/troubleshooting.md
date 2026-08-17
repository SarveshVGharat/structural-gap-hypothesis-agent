# Troubleshooting

## Imports fail

Install in editable mode:

```bash
python -m pip install -e ".[test]"
```

The staging package installs both `sgha` and top-level `retrieval` from `src/`.

## A command wants a live model

Use `configs/examples/minimal_mock.yaml` or pass the script's mock option where available. Full model-backed runs require a local or remote OpenAI-compatible endpoint.

## I only want to check the repository

Run:

```bash
python scripts/audit_release.py
python scripts/run_offline_smoke_test.py
python -m pytest -q
```

These checks are designed to be offline.

## The release audit fails

Open `RELEASE_AUDIT_REPORT.md` and remove or sanitize the reported files. Common causes are accidental run outputs, raw PDFs, parsed text folders, nested Git repositories, and private path traces.

## Pytest imports optional packages

The release tests are intentionally minimal. Broader research tests may need optional dependency groups or should be marked as slow/network/LLM tests before final release.
