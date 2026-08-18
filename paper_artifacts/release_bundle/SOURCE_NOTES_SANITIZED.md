# Sanitized Source Notes

This bundle was assembled from existing SGHA paper outputs, canonical paper-facing result tables, profile-conditioned outputs, evolutionary exploration outputs, and sensitivity artifacts.

The source locations were private research run namespaces and local artifact directories. Public files in this bundle use sanitized source descriptions only; private absolute paths, internal hostnames, launch details, logs, caches, and raw model-response files are not included.

High-level source groups:

- Main five-domain SGHA runs for final project families, formal problem statements, final reports, pipeline counts, and paper-facing qualitative examples.
- Canonical paper-facing table artifacts in `main_results/`, `profile_conditioned/`, `evolutionary/scores/`, and `sensitivity/`.
- Native AI-Scientist-v2/Qwen comparison outputs for candidate packets and formulation-quality scores.
- AI-Scientist-v2 Claude Opus comparison outputs for candidate packets and formulation-quality scores.
- MOOSE-Star public-model comparison outputs for candidate packets and formulation-quality scores.
- Profile-conditioned outputs for profile-level and candidate-level scores.
- Evolutionary exploration outputs for selected candidates and aggregate scores.
- Curated `paper_examples/` files assembled from existing sanitized final-family JSON, formal-problem JSONL, baseline examples, profile-conditioned candidate packets, evolutionary selected candidates, and paper score tables.
- Sanitized `paper_run_configs/` files created as public documentation templates; they preserve run-level settings such as domains, paper budgets, model placeholders, stages, verification gates, baseline modes, and judge rubric names while excluding raw runtime configuration paths.
- Compact `main_results/` CSVs copied or indexed from the existing paper-ready table sources. Broad duplicate table dumps are intentionally omitted.

Figures are not included in this artifact bundle unless explicitly added later for the camera-ready/arXiv source. No figure-related placeholder rows are kept in `MANIFEST.csv`.

The toy corpus under `examples/local_text_corpus/` is separate from this bundle and is only for offline usability testing.

Discarded examples, non-paper run rows, staging review material, and broad duplicate table dumps are intentionally excluded from the public bundle.
