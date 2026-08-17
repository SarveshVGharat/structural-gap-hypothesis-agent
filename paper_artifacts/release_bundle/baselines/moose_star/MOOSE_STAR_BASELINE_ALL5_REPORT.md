# MOOSE-Star Public-Model Baseline: All Five SGHA Domains

## Setup summary

- Baseline namespace: `[MAIN_PAPER_RUN_NAMESPACE]/baselines/moose_star_public_models_20260726_005146`
- Public MOOSE-Star repo: `[ORIGINAL_RESEARCH_REPO]/external_baselines/MOOSE-Star`
- Repo commit: `41a90cc94cc4d162c2cffc9d3d4db93571158f99`
- Public model used: `ZonglinY/MOOSE-Star-HC-R1D-7B`
- Local model path: `[SANITIZED_PRIVATE_PATH]
- Inference mode: `HC_ONLY`
- SLURM job: `16428`
- Training/fine-tuning run: no
- OpenRouter used: no
- SGHA graph/gap/verification/direct/final/formal artifacts used as input: no

## Inference mode used

This run uses the public MOOSE-Star Hypothesis Composition model with the official HC prompt template from `utils/prompt_store.py`. It does not use the IR model because the IR path requires SGLang service orchestration and MOOSE-Star hierarchical search tree artifacts that were not present for these SGHA ML-domain corpora.

Each generated candidate receives:

- a domain research question;
- a background survey built from selected-paper metadata only;
- `No previous hypothesis.`;
- one deterministic inspiration title/abstract pair from the selected-paper manifest.

## Domains and output counts

| Domain | Expected | Actual | Parse issues | Model | Inference mode |
|---|---:|---:|---:|---|---|
| bandits | 3 | 3 | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY |
| in_context_learning | 4 | 4 | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY |
| reasoning_models_test_time_compute | 1 | 1 | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY |
| offline_reinforcement_learning_arxiv | 1 | 1 | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY |
| uncertainty_calibration_conformal_prediction_arxiv | 6 | 6 | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY |

Total MOOSE-Star candidates: 15.

## Validation

Validation report:

`[MAIN_PAPER_RUN_NAMESPACE]/baselines/moose_star_public_models_20260726_005146/outputs/MOOSE_STAR_BASELINE_VALIDATION.md`

Counts table:

`[MAIN_PAPER_RUN_NAMESPACE]/baselines/moose_star_public_models_20260726_005146/outputs/moose_star_baseline_counts.csv`

Input audit:

`[MAIN_PAPER_RUN_NAMESPACE]/baselines/moose_star_public_models_20260726_005146/outputs/moose_star_baseline_input_audit.csv`

Validation passed with zero count errors and zero parse issues after reparsing preserved raw outputs to clean tokenizer artifacts.

## Output files

For each domain, the public bundle keeps:

- `moose_star_ideas.jsonl`
- `moose_star_ideas.md`
- `quality_audit.md`
- `inspiration_selection_audit.md`

Runtime outputs, local run metadata, command traces, and raw model-output files are intentionally excluded from the public bundle.

## Comparison package

SGHA-vs-MOOSE-Star comparison package:

`[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538`

Key files:

- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/candidates/sgha_vs_moose_candidates_unblinded.jsonl`
- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/candidates/sgha_vs_moose_candidates_blinded.jsonl`
- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/candidates/blinding_key.json`
- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/structural_metrics/structural_completeness_by_method.csv`
- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/structural_metrics/STRUCTURAL_COMPLETENESS_SUMMARY.md`
- `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/paper_framing/MOOSE_STAR_BASELINE_FRAMING.md`

## Caveats

- This is an adapted public-model baseline, not full native MOOSE-Star hierarchical search.
- The released MOOSE-Star public models are trained on TOMATO-Star biomedical-style scientific data, while these five domains are ML research domains.
- The baseline is output-count matched but not an SGHA ablation: SGHA uses its extraction/graph/verification/formalization pipeline, while MOOSE-Star receives metadata and deterministic inspiration title/abstract pairs.
- MOOSE-Star outputs do not provide SGHA-style formal problem statements, assumptions/setup objects, ambiguity flags, evaluation plans, or risk fields unless explicitly present in generated text. Missing normalized fields are marked `not provided`.

## Recommended next step

Run the existing formulation-only blinded LLM judge on `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/candidates/sgha_vs_moose_candidates_blinded.jsonl` using the same rubric as the SGHA-vs-Native AI-Scientist-v2 evaluation.
