# Reproducing Paper Results

The public staging copy includes a curated paper artifact bundle under `paper_artifacts/release_bundle/`. Reproduction has two tracks.

The bundle includes canonical generated tables, candidate packets, manifests, checksums, score outputs, curated qualitative examples, and summaries. It does not include figures unless explicitly added later for the camera-ready/arXiv source, raw PDFs, parsed full texts, model weights, raw prompts, raw responses, runtime path provenance, staging review notes, discarded examples, non-paper run rows, broad duplicate table dumps, private logs, secrets, or full run directories.

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

Paper-facing tables are under canonical section directories: `paper_artifacts/release_bundle/main_results/`, `paper_artifacts/release_bundle/profile_conditioned/`, `paper_artifacts/release_bundle/evolutionary/scores/`, `paper_artifacts/release_bundle/sensitivity/model_size/`, and `paper_artifacts/release_bundle/sensitivity/corpus_size/`. Retained main-comparison judging aggregates are under `paper_artifacts/release_bundle/judge_scores/main_comparison/`. The `tables/` directory is only a navigation pointer. Candidate packets are under `paper_artifacts/release_bundle/candidate_packets/`, and curated actual generated examples are under `paper_artifacts/release_bundle/paper_examples/`.

## Full Pipeline Reproduction

This path may require network access, paper downloads, an OpenAI-compatible model endpoint, and substantial compute. It should be documented separately from the artifact-only path.

Sanitized paper-run config templates are provided under `paper_artifacts/release_bundle/paper_run_configs/`. They document domain budgets, model placeholders, enabled stages, verification gates, baseline modes, and judge settings without private paths. The paper-facing baseline artifacts in this bundle cover SGHA, Native AI-Scientist-v2, and MOOSE-Star comparisons. Before final release, add exact upstream baseline install details, expected runtime, dependency extras, and known nondeterminism notes.

## Usability Smoke Test

The offline smoke test is separate from paper-result reproduction. It uses `examples/local_text_corpus/`, writes synthetic mock outputs, and is meant only to teach the output structure:

```bash
sgha smoke-test
sgha summarize-run /path/printed/by/smoke-test
```

See `docs/quickstart.md` and `docs/output_structure.md`.
