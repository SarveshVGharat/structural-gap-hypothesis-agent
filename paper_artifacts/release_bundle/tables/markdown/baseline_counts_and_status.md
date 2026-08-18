# Baseline Counts And Status

| method | generator_model | trained_or_training_free | inference_mode | output_count | candidate_count_valid | domains_completed | status | judge_scores_available | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SGHA_FULL | Qwen/Qwen3.5-9B | training-free generation pipeline | verified SGHA family-report pipeline | 15 | 15 | 5/5 | PASS | yes | Main system outputs; verified gate and formal problem stage included. |
| Native AI-Scientist-v2 Qwen | Qwen/Qwen3.5-9B | training-free baseline | native AI-Scientist-v2 ideation-only / local Qwen | 15 | 15 | 5/5 | PASS | yes | No experiment execution, code execution, paper writing, or review loop. |
| Native AI-Scientist-v2 Claude Opus | ~anthropic/claude-opus-latest (resolved anthropic/claude-opus-5 observed) | training-free frontier generator | native AI-Scientist-v2 ideation-only via OpenRouter | 15 | 15 | 5/5 | PASS | yes | Output-count matched; not compute/information matched; Semantic Scholar native path enabled. |
| MOOSE-Star | ZonglinY/MOOSE-Star-HC-R1D-7B | released trained public model | HC_ONLY | 15 | 15 | 5/5 | PASS | yes | No additional training/fine-tuning; deterministic inspiration selection. |
