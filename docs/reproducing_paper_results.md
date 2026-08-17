# Reproducing Paper Results

The public staging copy includes a curated paper artifact bundle under `paper_artifacts/release_bundle/`. Reproduction has two tracks.

The bundle includes generated tables, candidate packets, manifests, checksums, score outputs, and summaries. It does not include figures unless explicitly added later for the camera-ready/arXiv source, raw PDFs, parsed full texts, model weights, raw prompts, raw responses, private logs, secrets, or full run directories.

Generated tables, candidate packets, score files, and derived summaries are intended for research reuse under CC-BY-4.0 unless otherwise specified in `paper_artifacts/README.md`. Third-party source papers remain under their original licenses and are not redistributed here.

## Artifact-only Reproduction

This path should not call LLMs, download papers, or run the SGHA pipeline. It should verify checksums and inspect or regenerate table views from the curated bundle.

Useful commands:

```bash
python scripts/audit_release.py
cd paper_artifacts/release_bundle
sha256sum -c CHECKSUMS.sha256
cd ../..
python scripts/summarize_sgha_evidence_counts_for_supplement.py --help
```

Paper-ready CSV tables are under `paper_artifacts/release_bundle/tables/csv/`. Matching LaTeX tables are under `paper_artifacts/release_bundle/tables/latex/` where available, and candidate packets are under `paper_artifacts/release_bundle/candidate_packets/`.

## Full Pipeline Reproduction

This path may require network access, paper downloads, an OpenAI-compatible model endpoint, and substantial compute. It should be documented separately from the artifact-only path.

Before final release, add exact commands, expected runtime, model versions, dependency extras, and known nondeterminism notes.

## Usability Smoke Test

The offline smoke test is separate from paper-result reproduction. It uses `examples/local_text_corpus/`, writes synthetic mock outputs, and is meant only to teach the output structure:

```bash
sgha smoke-test
sgha summarize-run /path/printed/by/smoke-test
```

See `docs/quickstart.md` and `docs/output_structure.md`.
