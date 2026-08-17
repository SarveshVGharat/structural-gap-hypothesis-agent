# Candidate Packets

This directory contains sanitized candidate packets used for judging and inspection.

- `blinded/` keeps reviewer-facing packets where method labels were hidden by the original packet builder.
- `unblinded_sanitized/` keeps method labels and generated candidate text while removing private paths and raw-source fields.

Included candidate families:

- SGHA final candidates.
- AI-Scientist-v2 with Qwen candidates.
- AI-Scientist-v2 with Claude Opus candidates.
- MOOSE-Star public-model candidates.
- Profile-conditioned candidates.
- Evolutionary exploration candidates.

Raw model responses, runtime prompts, private paths, full run directories, raw PDFs, and parsed full texts are not included.
