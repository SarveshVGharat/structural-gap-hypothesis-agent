# Pipeline

SGHA is organized as staged, auditable transformations:

1. Retrieve candidate papers or load a curated corpus.
2. Parse paper PDFs or user-provided text.
3. Extract structured scientific claims and evidence tuples.
4. Build an evidence graph.
5. Detect structural gap motifs.
6. Verify candidate gaps with role-based critics and counterevidence checks.
7. Convert surviving gaps into direct formulations.
8. Expand, critique, and consolidate formulations into project families.
9. Optionally formalize research problems.
10. Generate final reports and paper tables.

The public quickstart should use mock/offline settings first:

```bash
sgha smoke-test
python scripts/run_offline_smoke_test.py
```

The smoke test uses `examples/local_text_corpus/` and writes synthetic mock outputs only. Full runs may require network access, paper downloads, model serving, and substantial compute.

Runtime outputs are intentionally ignored by Git. Do not commit run directories, raw prompts, raw responses, environment dumps, parsed full texts, or downloaded PDFs.

Prefer individual `sgha` stage commands while learning the system. `sgha run-all` is an advanced command because it can invoke retrieval, parsing, and live model-backed stages.

Use `sgha summarize-run /path/to/run_dir` or `python scripts/summarize_run_outputs.py --run-dir /path/to/run_dir` to inspect available outputs after a mock, partial, or complete run.

For user-provided local text, `sgha prepare-local-corpus <config.yaml> --run-id <name>` creates the `arxiv/papers_manifest.json` and `parsed/parsed_manifest.json` files expected by the model-backed extraction stage.
