# MOOSE-Star Public-Model Baseline Summary

This report summarizes the paper-facing MOOSE-Star public-model baseline artifacts included in the public bundle.
The baseline uses the public `ZonglinY/MOOSE-Star-HC-R1D-7B` model in hypothesis-composition mode; users are responsible for obtaining and running any upstream model dependencies.
The public bundle keeps generated candidate artifacts, aggregate counts, and score tables only.

## Counts

| domain | expected_count | actual_count | count_matches | parse_issue_count | model_id | inference_mode | training_run | openrouter_used | sgha_final_artifacts_used |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bandits | 3 | 3 | True | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY | False | False | False |
| in_context_learning | 4 | 4 | True | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY | False | False | False |
| reasoning_models_test_time_compute | 1 | 1 | True | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY | False | False | False |
| offline_reinforcement_learning_arxiv | 1 | 1 | True | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY | False | False | False |
| uncertainty_calibration_conformal_prediction_arxiv | 6 | 6 | True | 0 | ZonglinY/MOOSE-Star-HC-R1D-7B | HC_ONLY | False | False | False |

## Public Bundle Contents

- Candidate outputs are included as JSONL/Markdown artifacts under this baseline directory and in `candidate_packets/`.
- Runtime paths, local endpoint details, raw model responses, logs, audit scratch files, and command traces are excluded.
- Score summaries and judge tables are included under `judge_scores/` and `tables/`.
