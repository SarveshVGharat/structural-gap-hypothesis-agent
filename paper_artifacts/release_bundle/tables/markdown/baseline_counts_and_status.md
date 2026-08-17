# Baseline Counts and Status

|method|generator_model|trained_or_training_free|inference_mode|output_count|candidate_count_valid|domains_completed|status|judge_scores_available|notes|
|---|---|---|---|---|---|---|---|---|---|
|SGHA_FULL|Qwen/Qwen3.5-9B|training-free generation pipeline|verified SGHA family-report pipeline|15|15|5/5|PASS|yes|Main system outputs; verified gate and formal problem stage included.|
|Native AI-Scientist-v2 Qwen|Qwen/Qwen3.5-9B|training-free baseline|native AI-Scientist-v2 ideation-only / local Qwen|15|15|5/5|PASS|yes|No experiment execution, code execution, paper writing, or review loop.|
|Native AI-Scientist-v2 Claude Opus|~anthropic/claude-opus-latest (resolved anthropic/claude-opus-5 observed)|training-free frontier generator|native AI-Scientist-v2 ideation-only via OpenRouter|15|15|5/5|PASS|yes|Output-count matched; not compute/information matched; Semantic Scholar native path enabled.|
|MOOSE-Star|ZonglinY/MOOSE-Star-HC-R1D-7B|released trained public model|HC_ONLY|15|15|5/5|PASS|yes|No additional training/fine-tuning; deterministic inspiration selection.|
|Simple Qwen|Qwen/Qwen3.5-9B|training-free baseline|simple_qwen|15|15|5/5|PASS|not in main four-method table|Baseline artifacts exist; formulation-only score status outside main table is not included here.|
|Qwen+RAG|Qwen/Qwen3.5-9B|training-free baseline|qwen_rag|15|15|5/5|PASS|not in main four-method table|Baseline artifacts exist; formulation-only score status outside main table is not included here.|
|Native AI-Scientist-v2 GPT-5.5 attempted|openai/gpt-5.5|training-free frontier generator|native AI-Scientist-v2 via OpenRouter|0|0|0/5|BLOCKED_NETWORK_UNREACHABLE|no|Model/probe succeeded; full compute-node generation failed with network unreachable.|
|Native AI-Scientist-v2 Claude Opus blocked attempt|~anthropic/claude-opus-latest|training-free frontier generator|native AI-Scientist-v2 via OpenRouter|0|0|0/5|BLOCKED_NETWORK_UNREACHABLE|no|Superseded by SSO-authenticated successful attempt; no candidate set produced in blocked namespace.|
