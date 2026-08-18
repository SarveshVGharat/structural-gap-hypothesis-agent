# Native AI-Scientist-v2 Qwen Baseline Summary

This report summarizes the paper-facing Native AI-Scientist-v2 Qwen baseline artifacts included in the public bundle.
The original run used an OpenAI-compatible local model endpoint managed by the authors; users should configure their own endpoint when reproducing the baseline.
The public bundle keeps generated candidate artifacts, aggregate counts, and score tables only.

## Counts

| domain | display | requested | generated | kept | truncated | exit_status | audit_status | s2_status | s2_200 | s2_429 | out_dir | ideas_md | ideas_jsonl | audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bandits | Bandits | 3 | 3 | 3 | False | 0 | PASS | rate_limited_only | 0 | 12 |  | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_ideas.md | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_ideas.jsonl |  |
| in_context_learning | In-Context Learning | 4 | 4 | 4 | False | 0 | PASS | rate_limited_only | 0 | 6 |  | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_ideas.md | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_ideas.jsonl |  |
| reasoning_models_test_time_compute | Reasoning Models / Test-Time Compute | 1 | 1 | 1 | False | 0 | PASS | rate_limited_only | 0 | 3 |  | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_ideas.md | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_ideas.jsonl |  |
| offline_reinforcement_learning_arxiv | Offline Reinforcement Learning | 1 | 1 | 1 | False | 0 | PASS | success_with_rate_limits | 1 | 0 |  | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_ideas.md | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_ideas.jsonl |  |
| uncertainty_calibration_conformal_prediction_arxiv | Uncertainty Calibration / Conformal Prediction | 6 | 6 | 6 | False | 0 | PASS | rate_limited_only | 0 | 12 |  | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_ideas.md | public artifact source/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_ideas.jsonl |  |

## Public Bundle Contents

- Candidate outputs are included as JSONL/Markdown artifacts under this baseline directory and in `candidate_packets/`.
- Runtime paths, local endpoint details, raw model responses, logs, audit scratch files, and command traces are excluded.
- Score summaries and judge tables are included under `judge_scores/` and `tables/`.
