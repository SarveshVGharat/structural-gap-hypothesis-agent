# Native AI-Scientist-v2 Ideation Quality Audit

- status: PASS
- domain: offline_reinforcement_learning_arxiv
- entrypoint_used: [ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/perform_ideation_temp_free.py
- native_perform_ideation_temp_free_used: true
- ai_scientist_v2_source_patched: true
- patched_files: ['[ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/llm.py', '[ORIGINAL_RESEARCH_REPO]/external_baselines/AI-Scientist-v2/ai_scientist/tools/semantic_scholar.py']
- patch_backup_manifests: ['[ORIGINAL_RESEARCH_REPO]/external_baselines/backups/native_ai_scientist_v2_qwen_patch_20260721_075951/manifest.json', '[ORIGINAL_RESEARCH_REPO]/external_baselines/backups/native_ai_scientist_v2_s2_retry_patch_20260721_080503/manifest.json']
- model: Qwen/Qwen3.5-9B
- endpoint: http://[SANITIZED_INTERNAL_HOST]:8000/v1
- s2_api_key_present: false
- semantic_scholar_enabled: true
- external_literature_search_enabled: true
- openalex_used: false
- full_pipeline_used: false
- launch_scientist_bfts_used: false
- code_execution_used: false
- generated_code_execution_used: false
- experiment_execution_used: false
- plotting_used: false
- paper_writing_used: false
- review_loop_used: false
- num_ideas_requested: 1
- num_ideas_generated: 1
- num_ideas_kept: 1
- top_n_truncation_used: false
- semantic_scholar_status: success_with_rate_limits
- semantic_scholar_200_count: 1
- semantic_scholar_429_count: 0
- native_parse_failure_count: 0
- full_pipeline_outputs_detected_under_native_root: 0

## Warnings

- none
