# Sanitized Source Notes

This bundle was assembled from existing SGHA paper outputs, paper-ready result tables, profile-conditioned judge outputs, and evolutionary exploration outputs.

The source locations were private research run namespaces and local artifact directories. Public files in this bundle use sanitized source descriptions only; private absolute paths, internal hostnames, launch details, logs, caches, and raw model-response files are not included.

High-level source groups:

- Main five-domain SGHA runs for final project families, formal problem statements, final reports, pipeline counts, and paper-facing qualitative examples.
- Paper-ready result table packet for paper-ready CSV, LaTeX, and Markdown tables.
- Native AI-Scientist-v2/Qwen comparison outputs for candidate packets and formulation-quality scores.
- AI-Scientist-v2 Claude Opus comparison outputs for candidate packets and formulation-quality scores.
- MOOSE-Star public-model comparison outputs for candidate packets and formulation-quality scores.
- Profile-conditioned personalization judge outputs for profile-level and candidate-level scores.
- Evolutionary exploration judge outputs for selected candidates and aggregate scores.
- Curated `paper_examples/` files assembled from existing sanitized final-family JSON, formal-problem JSONL, baseline examples, profile-conditioned candidate packets, evolutionary selected candidates, and paper score tables.
- Sanitized `paper_run_configs/` files created as public documentation templates; they preserve run-level settings such as domains, paper budgets, model placeholders, stages, verification gates, baseline modes, and judge rubric names while excluding raw runtime configuration paths.
- Compact `main_results/` CSVs copied or indexed from the existing paper-ready table sources.

Figures are not included in this artifact bundle unless explicitly added later for the camera-ready/arXiv source. No figure-related placeholder rows are kept in `MANIFEST.csv`.

The toy corpus under `examples/local_text_corpus/` is separate from this bundle and is only for offline usability testing.

Discarded examples, unsuccessful internal runs, staging status matrices, and review-note artifacts are intentionally excluded from the public bundle.
