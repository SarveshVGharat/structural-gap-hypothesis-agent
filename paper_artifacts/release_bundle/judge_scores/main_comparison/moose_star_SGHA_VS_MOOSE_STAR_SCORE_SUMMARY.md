# SGHA vs MOOSE-Star Formulation-Only Score Summary

- evaluation_dir: `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_moose_star_public_model_comparison_20260726_012538/formulation_only_llm_judge_20260726_013946`
- judge models: five main OpenRouter judges from different providers
- candidates: 15 SGHA + 15 MOOSE-Star, scored independently by each judge
- weighted composite: not computed
- pairwise comparison: not run
- external novelty check: not run

## Aggregate Means Across Five Judges

| method | n candidate-judge scores | overall_formulation_quality_10 | problem_definition_clarity_10 | technical_specificity_10 | formalizability_10 | source_grounded_specificity_10 | ambiguity_hygiene_10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SGHA_FULL | 75 | 5.5467 | 6.44 | 5.48 | 5.08 | 5.2667 | 7.6533 |
| MOOSE_STAR_PUBLIC_MODEL | 75 | 2.0 | 1.8533 | 2.5067 | 1.5067 | 3.7467 | 1.48 |

## Judge-Level Overall Scores

| judge | SGHA | MOOSE-Star | delta |
|---|---:|---:|---:|
| anthropic/claude-sonnet-4 | 5.6 | 2.0 | 3.6 |
| openai/gpt-5.6-sol-pro | 5.2667 | 2.0 | 3.2667 |
| x-ai/grok-4.5 | 5.5333 | 2.3333 | 3.2 |
| moonshotai/kimi-k3 | 5.6667 | 2.4667 | 3.2 |
| google/gemini-3.6-flash | 5.6667 | 1.2 | 4.4667 |

## Validation Notes

- All five main judges produced 30/30 active scores after one targeted Claude schema repair for candidate_21.
- Active unresolved parse errors: 0.
- Claude initial parse error is preserved under `model_runs/anthropic_claude_sonnet_4/repairs/`.
- The scoring packet redacted method labels from wrapper text only; original candidate files remain unchanged.
