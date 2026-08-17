# Formulation-Only MOOSE-Star Judge Report

- created_at: `2026-07-25T21:47:02.876961+00:00`
- evaluation_dir: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946`
- candidate packet: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/candidates/sgha_vs_moose_candidates_blinded.jsonl`
- unblinded source packet: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/candidates/sgha_vs_moose_candidates_unblinded.jsonl`
- scoring mode: `formulation_only_10pt`
- weighted composite: not computed
- pairwise comparison: not run
- external novelty check: not run

## Model Run Status

| judge | active scores | unresolved parse errors | cap warnings | repair used |
|---|---:|---:|---:|---|
| anthropic/claude-sonnet-4 | 30 | 0 | 2 | True |
| openai/gpt-5.6-sol-pro | 30 | 0 | 0 | False |
| x-ai/grok-4.5 | 30 | 0 | 0 | False |
| moonshotai/kimi-k3 | 30 | 0 | 0 | False |
| google/gemini-3.6-flash | 30 | 0 | 0 | False |

## Main SGHA vs MOOSE-Star Score Table

# Paper-Ready SGHA vs MOOSE-Star Formulation-Only Score Table

Scores are descriptive OpenRouter LLM-judge formulation-only assessments on a 0-10 rubric. No external novelty check, weighted composite, or pairwise preference is used.

| judge model | SGHA overall formulation quality | MOOSE-Star overall formulation quality | SGHA - MOOSE | criteria won by SGHA | criteria won by MOOSE | ties |
|---|---:|---:|---:|---:|---:|---:|
| anthropic/claude-sonnet-4 | 5.6 | 2.0 | 3.6 | 10 | 0 | 0 |
| openai/gpt-5.6-sol-pro | 5.2667 | 2.0 | 3.2667 | 10 | 0 | 0 |
| x-ai/grok-4.5 | 5.5333 | 2.3333 | 3.2 | 10 | 0 | 0 |
| moonshotai/kimi-k3 | 5.6667 | 2.4667 | 3.2 | 10 | 0 | 0 |
| google/gemini-3.6-flash | 5.6667 | 1.2 | 4.4667 | 10 | 0 | 0 |

## Across-Judge Aggregate

| method | candidate-judge scores | mean overall formulation quality | mean source-grounded specificity | mean formalizability |
|---|---:|---:|---:|---:|
| SGHA_FULL | 75 | 5.5467 | 5.2667 | 5.08 |
| MOOSE_STAR_PUBLIC_MODEL | 75 | 2.0 | 3.7467 | 1.5067 |


## Three-Method Summary

# Three-Method Formulation-Only Comparison Summary

- SGHA/MOOSE evaluation: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946`
- Native source evaluation: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/postprocess`
- main judges: anthropic/claude-sonnet-4, openai/gpt-5.6-sol-pro, x-ai/grok-4.5, moonshotai/kimi-k3, google/gemini-3.6-flash
- excluded from main table: anthropic/claude-fable-5
- weighted composite: not computed
- pairwise comparison: not run

## Across-Judge Method Means

| method | n | overall | formalizability | source-grounding | complete-problem interpretation |
|---|---:|---:|---:|---:|---|
| SGHA_FULL | 75 | 5.5467 | 5.08 | 5.2667 | Verification-backed formal research-problem families with explicit formal/problem fields. |
| NATIVE_AI_SCIENTIST_V2 | 75 | 4.5467 | 3.68 | 5.1067 | Native ideation outputs with proposal text, evaluation plans, and risks but no SGHA-style formal object. |
| MOOSE_STAR_PUBLIC_MODEL | 75 | 2.0 | 1.5067 | 3.7467 | Public-model MOOSE-Star hypothesis outputs with source inspirations but generally missing formal/setup/ambiguity fields. |


## Key Artifacts

- SGHA vs MOOSE candidate/judge scores: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/postprocess/sgha_vs_moose_scores_by_candidate_judge.csv`
- SGHA vs MOOSE by-method scores: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/postprocess/sgha_vs_moose_scores_by_method.csv`
- paper-ready SGHA vs MOOSE CSV: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/postprocess/paper_ready_sgha_vs_moose_score_table.csv`
- combined three-method by-method scores: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/postprocess/combined_three_method_scores_by_method.csv`
- combined three-method structure metrics: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946/postprocess/combined_three_method_structural_metrics.csv`
