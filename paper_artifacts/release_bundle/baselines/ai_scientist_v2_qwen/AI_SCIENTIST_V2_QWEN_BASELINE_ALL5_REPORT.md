# Native AI-Scientist-v2 Baseline All-Five Report

- created_at: 2026-07-21T08:25:52
- output_root: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline
- native_entrypoint: [ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/perform_ideation_temp_free.py
- model: Qwen/Qwen3.5-9B
- endpoint: http://[SANITIZED_INTERNAL_HOST]:8000/v1
- vllm_job_id: 15267
- client_job_id: 15272
- first_attempt_cancelled_due_to_unbounded_s2_rate_limit: 15271
- S2_API_KEY_present: false
- Semantic Scholar enabled: true
- external literature search enabled: true
- OpenAlex used: false
- full AI-Scientist-v2 pipeline used: false
- generated-code execution used: false
- experiment execution used: false
- plotting used: false
- paper writing used: false
- review loop used: false

## Native Entrypoint Inspection

- Exact command format: `python ai_scientist/perform_ideation_temp_free.py --workshop-file <topic.md> --model Qwen/Qwen3.5-9B --max-num-generations <N> --num-reflections 5`.
- Topic markdown format follows the native README/example: `# Title`, `## Keywords`, `## TL;DR`, and `## Abstract`; these files also include selected corpus metadata signals from titles/abstracts only.
- Model restrictions are enforced by `AVAILABLE_LLMS` in `ai_scientist/llm.py` and by the argparse `choices=AVAILABLE_LLMS` in `perform_ideation_temp_free.py`.
- Local Qwen endpoint support required a minimal `llm.py` patch to create an OpenAI-compatible client using `AI_SCIENTIST_OPENAI_BASE_URL` and `AI_SCIENTIST_OPENAI_API_KEY`.
- Semantic Scholar is enabled by default: `perform_ideation_temp_free.py` constructs `SemanticScholarSearchTool()` and includes `SearchSemanticScholar` in the native tool list.
- The full pipeline is avoided by not running `launch_scientist_bfts.py`; only `perform_ideation_temp_free.py` was executed.

## Patches

- `[ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/llm.py`: Added Qwen/Qwen3.5-9B to AVAILABLE_LLMS and routed Qwen/* to local OpenAI-compatible endpoint via AI_SCIENTIST_OPENAI_BASE_URL.
- `[ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/tools/semantic_scholar.py`: Bound Semantic Scholar backoff to max_tries=3 so unauthenticated 429s are recorded and ideation continues.

## Patch Backups

- [ORIGINAL_RESEARCH_REPO]/external_baselines/backups/native_ai_scientist_v2_qwen_patch_20260721_075951/manifest.json
- [ORIGINAL_RESEARCH_REPO]/external_baselines/backups/native_ai_scientist_v2_s2_retry_patch_20260721_080503/manifest.json

## Counts and Semantic Scholar Status

| Domain | Requested | Generated | Kept | Truncated | Audit | Semantic Scholar status | S2 200 | S2 429 |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| Bandits | 3 | 3 | 3 | False | PASS | rate_limited_only | 0 | 12 |
| In-Context Learning | 4 | 4 | 4 | False | PASS | rate_limited_only | 0 | 6 |
| Reasoning Models / Test-Time Compute | 1 | 1 | 1 | False | PASS | rate_limited_only | 0 | 3 |
| Offline Reinforcement Learning | 1 | 1 | 1 | False | PASS | success_with_rate_limits | 1 | 0 |
| Uncertainty Calibration / Conformal Prediction | 6 | 6 | 6 | False | PASS | rate_limited_only | 0 | 12 |

## Output Paths

### Bandits

- output_dir: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits
- ai_scientist_native_ideas.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_ideas.md
- ai_scientist_native_ideas.jsonl: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_ideas.jsonl
- ai_scientist_native_ideas.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_ideas.json
- ai_scientist_native_run_metadata.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_run_metadata.json
- ai_scientist_native_quality_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/ai_scientist_native_quality_audit.md
- semantic_scholar_usage_log.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/semantic_scholar_usage_log.md
- raw_stdout_stderr.log: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/bandits/raw_stdout_stderr.log
- comparison_packet: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/bandits/family_vs_native_ai_scientist_v2
- blinded_review_packet.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/bandits/family_vs_native_ai_scientist_v2/blinded_review_packet.md
- unblinded_side_by_side.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/bandits/family_vs_native_ai_scientist_v2/unblinded_side_by_side.md
- comparison_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/bandits/family_vs_native_ai_scientist_v2/comparison_audit.md

### In-Context Learning

- output_dir: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning
- ai_scientist_native_ideas.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_ideas.md
- ai_scientist_native_ideas.jsonl: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_ideas.jsonl
- ai_scientist_native_ideas.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_ideas.json
- ai_scientist_native_run_metadata.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_run_metadata.json
- ai_scientist_native_quality_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/ai_scientist_native_quality_audit.md
- semantic_scholar_usage_log.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/semantic_scholar_usage_log.md
- raw_stdout_stderr.log: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/in_context_learning/raw_stdout_stderr.log
- comparison_packet: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/in_context_learning/family_vs_native_ai_scientist_v2
- blinded_review_packet.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/in_context_learning/family_vs_native_ai_scientist_v2/blinded_review_packet.md
- unblinded_side_by_side.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/in_context_learning/family_vs_native_ai_scientist_v2/unblinded_side_by_side.md
- comparison_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/in_context_learning/family_vs_native_ai_scientist_v2/comparison_audit.md

### Reasoning Models / Test-Time Compute

- output_dir: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute
- ai_scientist_native_ideas.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_ideas.md
- ai_scientist_native_ideas.jsonl: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_ideas.jsonl
- ai_scientist_native_ideas.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_ideas.json
- ai_scientist_native_run_metadata.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_run_metadata.json
- ai_scientist_native_quality_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/ai_scientist_native_quality_audit.md
- semantic_scholar_usage_log.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/semantic_scholar_usage_log.md
- raw_stdout_stderr.log: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/reasoning_models_test_time_compute/raw_stdout_stderr.log
- comparison_packet: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/reasoning_models_test_time_compute/family_vs_native_ai_scientist_v2
- blinded_review_packet.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/reasoning_models_test_time_compute/family_vs_native_ai_scientist_v2/blinded_review_packet.md
- unblinded_side_by_side.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/reasoning_models_test_time_compute/family_vs_native_ai_scientist_v2/unblinded_side_by_side.md
- comparison_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/reasoning_models_test_time_compute/family_vs_native_ai_scientist_v2/comparison_audit.md

### Offline Reinforcement Learning

- output_dir: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv
- ai_scientist_native_ideas.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_ideas.md
- ai_scientist_native_ideas.jsonl: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_ideas.jsonl
- ai_scientist_native_ideas.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_ideas.json
- ai_scientist_native_run_metadata.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_run_metadata.json
- ai_scientist_native_quality_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/ai_scientist_native_quality_audit.md
- semantic_scholar_usage_log.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/semantic_scholar_usage_log.md
- raw_stdout_stderr.log: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/offline_reinforcement_learning_arxiv/raw_stdout_stderr.log
- comparison_packet: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/offline_reinforcement_learning_arxiv/family_vs_native_ai_scientist_v2
- blinded_review_packet.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/offline_reinforcement_learning_arxiv/family_vs_native_ai_scientist_v2/blinded_review_packet.md
- unblinded_side_by_side.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/offline_reinforcement_learning_arxiv/family_vs_native_ai_scientist_v2/unblinded_side_by_side.md
- comparison_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/offline_reinforcement_learning_arxiv/family_vs_native_ai_scientist_v2/comparison_audit.md

### Uncertainty Calibration / Conformal Prediction

- output_dir: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv
- ai_scientist_native_ideas.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_ideas.md
- ai_scientist_native_ideas.jsonl: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_ideas.jsonl
- ai_scientist_native_ideas.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_ideas.json
- ai_scientist_native_run_metadata.json: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_run_metadata.json
- ai_scientist_native_quality_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/ai_scientist_native_quality_audit.md
- semantic_scholar_usage_log.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/semantic_scholar_usage_log.md
- raw_stdout_stderr.log: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/outputs/uncertainty_calibration_conformal_prediction_arxiv/raw_stdout_stderr.log
- comparison_packet: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/uncertainty_calibration_conformal_prediction_arxiv/family_vs_native_ai_scientist_v2
- blinded_review_packet.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/uncertainty_calibration_conformal_prediction_arxiv/family_vs_native_ai_scientist_v2/blinded_review_packet.md
- unblinded_side_by_side.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/uncertainty_calibration_conformal_prediction_arxiv/family_vs_native_ai_scientist_v2/unblinded_side_by_side.md
- comparison_audit.md: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/comparisons/uncertainty_calibration_conformal_prediction_arxiv/family_vs_native_ai_scientist_v2/comparison_audit.md

## Comparison Framing

- This baseline is native AI-Scientist-v2 ideation with Semantic Scholar/literature tools enabled.
- It is not same-corpus-only: the native tool can query Semantic Scholar when not rate-limited.
- It is not information-matched: SGHA uses graph/gap/verification/family/formalization machinery, while AI-Scientist-v2 uses its native ideation loop and literature tool.
- It is not compute-matched.
- It is output-count matched to repaired SGHA final family counts.

## Caveats

- `S2_API_KEY` was not present. Semantic Scholar was enabled, but unauthenticated rate limits occurred in four domains; Offline RL recorded one successful Semantic Scholar response.
- A bounded-retry patch was needed because native Semantic Scholar backoff otherwise kept retrying 429s without a practical cap.
- The native ideation output sometimes references literature names from its own model memory or failed literature searches; this should be treated as baseline behavior, not verified literature grounding.
- No external OpenAlex/WebSearch/Google Scholar path was used.

## Recommended Paper Wording

Use wording like: “We compare against native AI-Scientist-v2 ideation using its `perform_ideation_temp_free.py` entrypoint with Semantic Scholar literature-search tooling enabled and local Qwen/Qwen3.5-9B as the LLM. This baseline is output-count matched to SGHA but is not same-corpus-only, information-matched, or compute-matched.”

## Summary Files

- native_ai_scientist_v2_all5_summary.csv: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/native_ai_scientist_v2_all5_summary.csv
- native_ai_scientist_v2_comparison_summary.csv: [MAIN_PAPER_RUN_NAMESPACE]/native_ai_scientist_v2_ideation_baseline/native_ai_scientist_v2_comparison_summary.csv
