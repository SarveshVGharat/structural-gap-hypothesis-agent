# Profile-Conditioned Artifacts

This directory collects public-safe profile-conditioned artifacts for the paper.

- `profile_summary_table.csv` gives profile-level pipeline counts and status.
- `profile_scores.csv` gives paper-ready personalized judge scores by candidate.
- `profile_pipeline_counts.csv` mirrors the personalized pipeline-count table.
- `sanitized_profile_contexts/` contains compact JSON contexts for Yann LeCun, Geoffrey Hinton, and Michael I. Jordan.
- `candidates/` and `scores/` retain the original sanitized candidate packet and score tables.

The context JSON files include only counts, high-level generated profile descriptors, seed-paper title/ID samples, and aggregate score metadata. Cached profile pages, raw PDFs, parsed full texts, raw prompts, raw model responses, logs, caches, private paths, and credentials are excluded.
