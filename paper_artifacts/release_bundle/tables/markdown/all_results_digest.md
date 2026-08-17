# All Results Digest

Generated: 20260726_175918

## Main Claims Supported by Current Results

1. Across five 250-paper domains, SGHA selected 1,250 papers, extracted structured content from 1,044 papers, produced 39 hard verification-passed gaps, and finalized 15 formalized project families.
2. In formulation-quality judging over the common five-judge panel, SGHA has the highest mean overall formulation quality among the four tabled methods: SGHA 5.99, AI-Scientist-v2 + Qwen 4.55, AI-Scientist-v2 + Claude Opus 5.84, and MOOSE-Star 2.00.
3. SGHA has complete structural research-problem artifacts for 15/15 candidates; the baselines provide source-grounded ideas but do not include SGHA-style formal problems, ambiguity flags, or complete research-problem objects.

## Main Paper Tables

- Table 1: SGHA pipeline yield across the five domains.
- Table 2: Four-method formulation-quality comparison.
- Table 3: Structural artifact completeness comparison.

## Appendix and Diagnostics

Appendix tables include full 10-criterion scores, baseline status, robustness checks, best-candidate diagnostics, MOOSE-Star and Claude Opus details, and cap-warning sensitivity. Diagnostic tables include personalization, model scaling, paper-count scaling, and legacy evolution availability.

## What Is Missing or Not Yet Judged

- Simple Qwen and Qwen+RAG baseline artifacts exist but are not included in the main four-method formulation-quality score table.
- GPT-5.5 Native AI-Scientist-v2 generated no valid candidate set because compute-node OpenRouter generation was blocked.
- 4B model-scaling output has no final families, so no formulation score is available.
- Evolutionary exploration artifacts are legacy/optional and not LLM-judge scored.

## Recommended Placement

- Main: Tables 1-3.
- Appendix: Tables A1-A10.
- Diagnostic/omit unless needed: D1-D7, blocked network attempts, legacy evolution.
