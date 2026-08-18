# SGHA Paper Artifact Bundle

This bundle contains curated, sanitized artifacts for inspecting and reproducing the SGHA arXiv paper tables and qualitative examples from existing outputs.

## Contents

- `main_sgha/`: final SGHA project families, formal problem statements, final reports, pipeline counts, and qualitative SGHA examples.
- `baselines/`: generated AI-Scientist-v2 Qwen, AI-Scientist-v2 Claude Opus, and MOOSE-Star candidate outputs and summaries.
- `candidate_packets/`: blinded packets and unblinded sanitized packets used for judging.
- `judge_scores/`: retained main-comparison score aggregates, summaries, and judging rubric material.
- `tables/`: a minimal navigation README that points to the canonical section-level table locations.
- `profile_conditioned/`, `evolutionary/`, and `sensitivity/`: focused artifact subsets for those paper sections.
- `paper_examples/`: curated actual generated examples from the paper runs, including SGHA, baseline, profile-conditioned, and evolutionary examples.
- `paper_run_configs/`: sanitized public YAML configs approximating the paper setup without private paths, raw corpora, raw prompts, or credentials.
- `main_results/`: compact copies of the key result CSVs and an index of qualitative examples.

## Quick Checks

From this directory:

```bash
sha256sum -c CHECKSUMS.sha256
```

Use `MANIFEST.csv` as the navigation index. It lists each relative path, artifact type, sanitized source note, and whether the artifact contains generated text, scores, table data, profile artifacts, evolutionary artifacts, or sensitivity artifacts.

## Exclusions

This bundle intentionally excludes figures unless explicitly added later for the camera-ready/arXiv source, raw PDFs, parsed full paper text, raw model responses, runtime LLM call logs, runtime prompt files containing paper text, private logs, environment dumps, caches, profiles, archives, full run directories, nested Git directories, secrets, and private infrastructure details.

## Reproducing Tables

The canonical paper-facing tables are kept near the results they describe: `main_results/`, `profile_conditioned/`, `evolutionary/scores/`, `sensitivity/model_size/`, and `sensitivity/corpus_size/`. Retained main-comparison score aggregates live under `judge_scores/main_comparison/`. The `tables/` directory is only a navigation pointer. To inspect table values, load the retained CSV files with Python, R, or a spreadsheet tool. The bundle itself is artifact-only and should not call LLMs, OpenRouter, paper downloads, or full SGHA runs.

## Inspecting Candidates

Use `paper_examples/` for the easiest reader-facing qualitative examples. Use `candidate_packets/unblinded_sanitized/` for method-labeled candidate text and `candidate_packets/blinded/` for reviewer-facing packets. Toy examples for trying the code live outside this bundle under `examples/local_text_corpus/`.

## Citation

Please cite the accompanying SGHA arXiv paper when final metadata is available. Repository-level citation metadata is tracked in `CITATION.cff`.

## License

Generated tables, candidate packets, score files, and derived summaries in this bundle are intended for research reuse under CC-BY-4.0 unless otherwise specified. Code remains Apache-2.0. Third-party source papers are not redistributed and remain under their original licenses.

## Public scrub note

This bundle is limited to paper-result artifacts: candidate packets, final outputs, canonical score tables, qualitative examples, profile/evolution/sensitivity artifacts, manifests, and checksums.
Discarded examples, non-paper run rows, staging review material, raw logs, raw LLM outputs, raw PDFs, parsed full texts, and runtime path provenance are excluded.
Figures are not included in this artifact bundle unless explicitly added later for the camera-ready or arXiv source.
