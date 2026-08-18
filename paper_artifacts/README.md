# Paper Artifacts

This directory contains the curated public artifact bundle for reproducing paper tables and inspecting examples:

```text
release_bundle/
```

Raw PDFs, parsed full texts, model weights, runtime path provenance, staging review notes, blocked or skipped run rows, private logs, and secrets are excluded from this repository and from the artifact bundle.

Generated canonical paper tables, candidate packets, score files, and derived summaries are intended for research reuse under CC-BY-4.0 unless otherwise specified.

Figures are not included in this artifact bundle unless explicitly added later for the camera-ready/arXiv source.

Third-party source papers remain under their original licenses and are not redistributed here.

Start with `release_bundle/README.md`, `release_bundle/MANIFEST.csv`, `release_bundle/CHECKSUMS.sha256`, and `release_bundle/SECRET_LEAKAGE_CHECK.md`.

Inside the bundle, `paper_examples/` contains actual generated examples used in the paper, `paper_run_configs/` contains sanitized public configs approximating the paper setup, and `main_results/` collects the key result CSVs in one place. The broad table-export directories have been pruned in favor of canonical section-level tables. Toy examples for trying the code are separate and live under `examples/local_text_corpus/`.
