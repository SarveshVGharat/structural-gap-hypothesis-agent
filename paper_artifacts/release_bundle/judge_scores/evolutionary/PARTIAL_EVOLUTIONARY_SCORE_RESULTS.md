# Partial Evolutionary Exploration Judge Results

Live scoring was stopped early at user request. These are partial results from completed/written score files only.

## Judge Completion

| Judge model | Scores written | Parse errors | Status |
|---|---:|---:|---|
| anthropic/claude-sonnet-4 | 15 | 0 | complete |
| openai/gpt-5.6-sol-pro | 15 | 0 | complete |
| x-ai/grok-4.5 | 15 | 0 | complete |
| moonshotai/kimi-k3 | 10 | 0 | interrupted_or_unknown |
| google/gemini-3.6-flash | 0 | 0 | not_started |

## Selected Candidate Counts

| Domain | Selected candidates |
|---|---:|
| bandits | 3 |
| in_context_learning | 4 |
| reasoning_models_test_time_compute | 1 |
| offline_reinforcement_learning_arxiv | 1 |
| uncertainty_calibration_conformal_prediction_arxiv | 6 |

## Partial Method-Level Means

| Criterion | Mean |
|---|---:|
| problem_definition_clarity_10 | 4.1091 |
| technical_specificity_10 | 4.0909 |
| well_posedness_10 | 2.8 |
| assumption_boundary_clarity_10 | 3.4182 |
| formalizability_10 | 2.6364 |
| nontriviality_10 | 5.0545 |
| scope_control_10 | 4.3818 |
| source_grounded_specificity_10 | 5.4 |
| ambiguity_hygiene_10 | 2.2 |
| overall_formulation_quality_10 | 3.8182 |

## Partial Domain Overall Means

| Domain | Scored rows | Mean overall |
|---|---:|---:|
| bandits | 12 | 3.75 |
| in_context_learning | 14 | 3.6429 |
| reasoning_models_test_time_compute | 4 | 4.5 |
| offline_reinforcement_learning_arxiv | 4 | 3.75 |
| uncertainty_calibration_conformal_prediction_arxiv | 21 | 3.8571 |

## Best Candidate So Far

- evolutionary_reasoning_models_test_time_compute_rank01_hypothesis_8c830430218e7a3d (reasoning_models_test_time_compute): mean overall 4.5 across 4 judge(s); max overall 5.0
- title: Self-verification mechanisms within test-time compute scaling frameworks.

## Diagnostics

- total score rows: 55
- parse errors: 0
- cap warnings/violations recorded: 0
- recommended actions: {'NEEDS_REFRAMING': 53, 'PROMISING_NEEDS_REFINEMENT': 2}

## Paths

- partial score rows: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/postprocess/partial_evolutionary_scores_by_candidate_judge.csv`
- partial method means: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/postprocess/partial_evolutionary_scores_by_method.csv`
- partial domain means: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/postprocess/partial_evolutionary_scores_by_domain.csv`
- candidate aggregates: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/postprocess/partial_evolutionary_candidate_aggregates.csv`
