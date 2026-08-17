# Release Staging Manifest

Created as a first public-release staging copy from the SGHA research repository.

Included:

- `src/sgha/`: core SGHA package, without caches or generated package metadata.
- `src/retrieval/`: retrieval package staged under `src/` so it can be installed as top-level `retrieval`.
- `scripts/`: selected public-facing baseline, judge, supplement-summary, and release-audit scripts.
- `configs/`: sanitized default and example configs.
- `docs/`: public-facing documentation placeholders.
- `prompts/`: prompt inventory and safe template excerpts.
- `schemas/`: schema inventory and lightweight JSON-schema artifacts.
- `tests/`: minimal offline release tests.

Excluded:

- raw PDFs
- parsed full paper text
- archives and profile caches
- full run directories
- raw prompts and raw LLM outputs
- environment dumps and LLM call logs
- model weights
- nested Git directories
- private cluster files
- third-party baseline repositories copied wholesale
