# SGHA Paper Artifact Bundle

This bundle contains curated, sanitized artifacts for inspecting and reproducing the SGHA arXiv paper tables and qualitative examples from existing outputs.

## Contents

- `main_sgha/`: final SGHA project families, formal problem statements, final reports, pipeline counts, and qualitative SGHA examples.
- `baselines/`: generated AI-Scientist-v2 Qwen, AI-Scientist-v2 Claude Opus, and MOOSE-Star candidate outputs and summaries.
- `candidate_packets/`: blinded packets and unblinded sanitized packets used for judging.
- `judge_scores/`: score tables and summaries for main comparison, profile-conditioned generation, evolutionary exploration, and sensitivity analyses.
- `tables/`: paper-ready CSV, LaTeX, and Markdown tables.
- `profile_conditioned/`, `evolutionary/`, and `sensitivity/`: focused artifact subsets for those paper sections.
- `paper_examples/`: curated actual generated examples from the paper runs, including SGHA, baseline, profile-conditioned, and evolutionary examples.
- `paper_run_configs/`: sanitized public YAML configs approximating the paper setup without private paths, raw corpora, raw prompts, or credentials.
- `main_results/`: compact copies of the key result CSVs and an index of qualitative examples.

## Quick Checks

From this directory:

```bash
sha256sum -c CHECKSUMS.sha256
```

Use `MANIFEST.csv` as the navigation index. It lists each relative path, artifact type, paper section, sanitized source note, and whether the artifact contains generated text, scores, or limited third-party text snippets.

## Exclusions

This bundle intentionally excludes figures unless explicitly added later for the camera-ready/arXiv source, raw PDFs, parsed full paper text, raw model responses, runtime LLM call logs, runtime prompt files containing paper text, private logs, environment dumps, caches, profiles, archives, full run directories, nested Git directories, secrets, and private infrastructure details.

## Reproducing Tables

The paper-facing tables are available directly under `tables/csv/`, with matching LaTeX copies under `tables/latex/` when available. To inspect or regenerate table views, load the CSV files with Python, R, a spreadsheet tool, or the paper scripts in the repository. The bundle itself is artifact-only and should not call LLMs, OpenRouter, paper downloads, or full SGHA runs.

## Inspecting Candidates

Use `paper_examples/` for the easiest reader-facing qualitative examples. Use `candidate_packets/unblinded_sanitized/` for method-labeled candidate text and `candidate_packets/blinded/` for reviewer-facing packets. Toy examples for trying the code live outside this bundle under `examples/local_text_corpus/`.

## Citation

Please cite the accompanying SGHA arXiv paper when final metadata is available. Repository-level citation metadata is tracked in `CITATION.cff`.

## License

Generated tables, candidate packets, score files, and derived summaries in this bundle are intended for research reuse under CC-BY-4.0 unless otherwise specified. Code remains Apache-2.0. Third-party source papers are not redistributed and remain under their original licenses.
