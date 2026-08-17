# Data and Artifacts

This repository does not redistribute raw papers or full parsed text. Users should obtain papers from their original sources and respect the applicable licenses and terms.

The curated paper artifact bundle is available under `paper_artifacts/release_bundle/` and contains only release-safe, derived artifacts.

Do not commit:

- raw PDFs
- parsed full paper text
- downloaded paper caches
- full run directories
- raw prompts or raw model responses
- environment dumps
- model weights
- private source path traces

Public paper artifacts under `paper_artifacts/release_bundle/` include:

- CSV and TeX tables
- candidate packets
- score files
- markdown summaries
- curated actual generated examples from the paper runs
- sanitized paper-run config templates
- compact main-result CSV copies
- manifests
- checksums
- high-level status matrices
- small source identifiers such as paper IDs when allowed

Figures are not included in this artifact bundle unless explicitly added later for the camera-ready/arXiv source.

Generated tables, candidate packets, score files, and derived summaries are intended for research reuse under CC-BY-4.0 unless otherwise specified in `paper_artifacts/README.md`. Third-party source papers remain under their original licenses and are not redistributed here.

The release audit script checks for common forbidden artifact classes.

Artifact-only reproduction should not call LLMs, download papers, or run the full SGHA pipeline. It should verify checksums and inspect or regenerate table views from curated CSV and summary files.

For a no-network usability path, use `examples/local_text_corpus/` and `sgha smoke-test`. That example contains only short synthetic text files and writes a mock output tree for learning SGHA's stage layout. For local user corpora, provide your own `papers.jsonl` with `text_path` entries and keep source papers outside public commits unless redistribution is permitted.

Toy examples are for trying the code. `paper_artifacts/release_bundle/paper_examples/` contains actual generated examples from the paper runs, while `paper_artifacts/release_bundle/paper_run_configs/` contains sanitized documentation configs for reproducing the setup with user-managed corpora and model endpoints.
