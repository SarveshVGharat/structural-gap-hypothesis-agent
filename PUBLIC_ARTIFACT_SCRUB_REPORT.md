# Public Artifact Scrub Report

Date: 2026-08-18

Scope: `paper_artifacts/release_bundle/` in the public SGHA staging repository, with public docs checked for consistency.

This scrub removes staging-only diagnostics, discarded examples, unsuccessful or blocked run rows, internal planning labels, and runtime provenance placeholders from the public artifact bundle. It does not rerun SGHA, change paper score values, call any model/API, download papers, or add raw PDFs/full texts.

## Counts

- Bundle files before scrub: 295
- Bundle files after scrub: 253
- Manifest rows before scrub: 295
- Manifest rows after scrub: 253
- Checksum entries after scrub: 252
- MISSING manifest rows after scrub: 0

## Finding Categories And Actions

| Path or pattern | Category | Reason | Action | Taken |
|---|---|---|---|---|
| `paper_artifacts/release_bundle/tables/markdown/all_results_digest.md` | internal_comment | Draft digest contained planning/status language for results not meant as paper-facing artifacts. | remove | yes |
| `paper_artifacts/release_bundle/tables/markdown/results_master_index.md` | internal_comment | Internal result index/commentary rather than a paper-facing table or artifact. | remove | yes |
| `paper_artifacts/release_bundle/**/*quality_audit.md` | non_paper_artifact | Review/audit scratch files were useful internally but are not paper result artifacts. | remove | yes |
| `paper_artifacts/release_bundle/**/*inspiration_selection_audit.md` | non_paper_artifact | Baseline inspiration-selection audit files are not reported paper artifacts. | remove | yes |
| `paper_artifacts/release_bundle/**/FROZEN_PROMPT_RUBRIC_SCHEMA_AUDIT.md` | non_paper_artifact | Prompt/rubric audit notes are not the public rubric/schema artifacts. | remove | yes |
| `paper_artifacts/release_bundle/**/partial_judge_completion_status.csv` | non_paper_artifact | Partial completion status diagnostics are not paper-facing score tables. | remove | yes |
| `paper_artifacts/release_bundle/**/RESULTS_STATUS_MATRIX.csv and tables/*/results_status_matrix.*` | non_paper_artifact | Staging status matrices duplicated run bookkeeping and included non-paper status rows. | remove | yes |
| `paper_artifacts/release_bundle/tables/latex/all_tables_combined.tex` | non_paper_artifact | Combined draft table file duplicated paper tables and included stale/non-paper rows. | remove | yes |
| `paper_artifacts/release_bundle/profile_conditioned/*summary*.csv` | unsuccessful_run | Profile tables included unreported Sutton/Barto and Yoshua Bengio skipped rows. | sanitize | yes |
| `paper_artifacts/release_bundle/profile_conditioned/*score*.csv and tables/csv/table_d2_personalized_judge_scores.csv` | internal_comment | Score tables included paper-use planning labels rather than public result labels. | sanitize | yes |
| `paper_artifacts/release_bundle/tables/csv/table_a4_baseline_counts_and_status.csv` | unsuccessful_run | Baseline status table included blocked/non-paper attempts; public table now keeps only paper-facing methods. | sanitize | yes |
| `paper_artifacts/release_bundle/candidate_packets/**/*.jsonl and profile_conditioned/candidates/*.jsonl` | private_path | Candidate packets included runtime profile/provenance placeholders rather than public source labels. | sanitize | yes |
| `paper_artifacts/release_bundle/baselines/*/*REPORT.md and judge_scores/**/*.md` | private_path | Reports contained runtime directory pointers, internal endpoint placeholders, or references to removed audit/log files. | sanitize | yes |
| `paper_artifacts/release_bundle/MANIFEST.csv` | internal_comment | Manifest referenced removed files and internal source-description labels. | sanitize | yes |
| `docs/, README.md, TODO_RELEASE.md outside release_bundle` | legitimate_public_text | Terms such as TODO, private, and appendix are release-policy or citation-task text outside the strict artifact bundle. | keep | yes |

## Removed Files

- `baselines/ai_scientist_v2_claude_opus/bandits_quality_audit.md`
- `baselines/ai_scientist_v2_claude_opus/in_context_learning_quality_audit.md`
- `baselines/ai_scientist_v2_claude_opus/native_ai_scientist_v2_claude_opus_latest_input_audit.csv`
- `baselines/ai_scientist_v2_claude_opus/offline_reinforcement_learning_arxiv_quality_audit.md`
- `baselines/ai_scientist_v2_claude_opus/reasoning_models_test_time_compute_quality_audit.md`
- `baselines/ai_scientist_v2_claude_opus/uncertainty_calibration_conformal_prediction_arxiv_quality_audit.md`
- `baselines/ai_scientist_v2_qwen/bandits_ai_scientist_native_quality_audit.md`
- `baselines/ai_scientist_v2_qwen/in_context_learning_ai_scientist_native_quality_audit.md`
- `baselines/ai_scientist_v2_qwen/offline_reinforcement_learning_arxiv_ai_scientist_native_quality_audit.md`
- `baselines/ai_scientist_v2_qwen/reasoning_models_test_time_compute_ai_scientist_native_quality_audit.md`
- `baselines/ai_scientist_v2_qwen/uncertainty_calibration_conformal_prediction_arxiv_ai_scientist_native_quality_audit.md`
- `baselines/moose_star/bandits_inspiration_selection_audit.md`
- `baselines/moose_star/bandits_quality_audit.md`
- `baselines/moose_star/in_context_learning_inspiration_selection_audit.md`
- `baselines/moose_star/in_context_learning_quality_audit.md`
- `baselines/moose_star/moose_star_baseline_input_audit.csv`
- `baselines/moose_star/offline_reinforcement_learning_arxiv_inspiration_selection_audit.md`
- `baselines/moose_star/offline_reinforcement_learning_arxiv_quality_audit.md`
- `baselines/moose_star/reasoning_models_test_time_compute_inspiration_selection_audit.md`
- `baselines/moose_star/reasoning_models_test_time_compute_quality_audit.md`
- `baselines/moose_star/uncertainty_calibration_conformal_prediction_arxiv_inspiration_selection_audit.md`
- `baselines/moose_star/uncertainty_calibration_conformal_prediction_arxiv_quality_audit.md`
- `evolutionary/scores/partial_judge_completion_status.csv`
- `evolutionary/summaries/FROZEN_PROMPT_RUBRIC_SCHEMA_AUDIT.md`
- `judge_scores/evolutionary/FROZEN_PROMPT_RUBRIC_SCHEMA_AUDIT.md`
- `judge_scores/evolutionary/partial_judge_completion_status.csv`
- `judge_scores/main_comparison/four_way_selection_audit.md`
- `main_sgha/final_project_families/bandits_final_report_quality_audit.md`
- `main_sgha/final_project_families/in_context_learning_final_report_quality_audit.md`
- `main_sgha/final_project_families/offline_reinforcement_learning_arxiv_final_report_quality_audit.md`
- `main_sgha/final_project_families/reasoning_models_test_time_compute_final_report_quality_audit.md`
- `main_sgha/final_project_families/uncertainty_calibration_conformal_prediction_arxiv_final_report_quality_audit.md`
- `main_sgha/pipeline_counts/RESULTS_STATUS_MATRIX.csv`
- `profile_conditioned/summaries/POST_ISSUEFIX_BEST_PERSONALIZED_PROBLEMS.md`
- `profile_conditioned/summaries/POST_ISSUEFIX_PERSONALIZED_PROBLEM_QUALITY_REVIEW.md`
- `profile_conditioned/summaries/personalized_verification_gate_impact.csv`
- `profile_conditioned/summaries/post_issuefix_personalized_quality_scores.csv`
- `tables/csv/results_status_matrix.csv`
- `tables/latex/all_tables_combined.tex`
- `tables/markdown/all_results_digest.md`
- `tables/markdown/results_master_index.md`
- `tables/markdown/results_status_matrix.md`

## Sanitized Files

- `MANIFEST.csv`
- `README.md`
- `SOURCE_NOTES_SANITIZED.md`
- `baselines/ai_scientist_v2_claude_opus/bandits_best_example.md`
- `baselines/ai_scientist_v2_claude_opus/native_ai_scientist_v2_claude_opus_latest_counts.csv`
- `baselines/ai_scientist_v2_qwen/AI_SCIENTIST_V2_QWEN_BASELINE_ALL5_REPORT.md`
- `baselines/ai_scientist_v2_qwen/bandits_ai_scientist_native_ideas.jsonl`
- `baselines/ai_scientist_v2_qwen/in_context_learning_ai_scientist_native_ideas.jsonl`
- `baselines/ai_scientist_v2_qwen/native_ai_scientist_v2_all5_summary.csv`
- `baselines/ai_scientist_v2_qwen/native_ai_scientist_v2_comparison_summary.csv`
- `baselines/ai_scientist_v2_qwen/offline_reinforcement_learning_arxiv_ai_scientist_native_ideas.jsonl`
- `baselines/ai_scientist_v2_qwen/reasoning_models_test_time_compute_ai_scientist_native_ideas.jsonl`
- `baselines/ai_scientist_v2_qwen/uncertainty_calibration_conformal_prediction_arxiv_ai_scientist_native_ideas.jsonl`
- `baselines/moose_star/MOOSE_STAR_BASELINE_ALL5_REPORT.md`
- `candidate_packets/blinded/profile_conditioned_candidates_blinded.jsonl`
- `candidate_packets/unblinded_sanitized/ai_scientist_v2_claude_opus_candidates_unblinded_sanitized.jsonl`
- `candidate_packets/unblinded_sanitized/profile_conditioned_candidates_unblinded_sanitized.jsonl`
- `evolutionary/summaries/FORMULATION_ONLY_EVOLUTIONARY_EXPLORATION_JUDGE_REPORT.md`
- `evolutionary/summaries/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md`
- `judge_scores/evolutionary/FORMULATION_ONLY_EVOLUTIONARY_EXPLORATION_JUDGE_REPORT.md`
- `judge_scores/evolutionary/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_FORMULATION_ONLY_SCORE_SUMMARY.md`
- `judge_scores/main_comparison/claude_opus_FORMULATION_ONLY_CLAUDE_OPUS_BASELINE_JUDGE_REPORT.md`
- `judge_scores/main_comparison/four_way_BEST_OF_METHOD_4WAY_REPORT.md`
- `judge_scores/main_comparison/four_way_candidate_pool_summary.md`
- `judge_scores/main_comparison/moose_star_FORMULATION_ONLY_MOOSE_STAR_JUDGE_REPORT.md`
- `judge_scores/main_comparison/moose_star_SGHA_VS_MOOSE_STAR_SCORE_SUMMARY.md`
- `judge_scores/profile_conditioned/PERSONALIZED_PROFILE_ALIGNMENT_JUDGE_REPORT.md`
- `judge_scores/profile_conditioned/paper_ready_personalized_score_table.csv`
- `paper_examples/profile_conditioned/michael_jordan_hierarchical_identifiability_example.md`
- `profile_conditioned/candidates/profile_conditioned_candidates_unblinded_sanitized.jsonl`
- `profile_conditioned/profile_pipeline_counts.csv`
- `profile_conditioned/profile_scores.csv`
- `profile_conditioned/profile_summary_table.csv`
- `profile_conditioned/scores/paper_ready_personalized_score_table.csv`
- `profile_conditioned/summaries/profile_summary_table.csv`
- `tables/csv/table_a4_baseline_counts_and_status.csv`
- `tables/csv/table_d1_personalized_pipeline_counts.csv`
- `tables/csv/table_d2_personalized_judge_scores.csv`
- `tables/latex/table_a4_baseline_counts_and_status.tex`
- `tables/latex/table_d1_personalized_pipeline_counts.tex`
- `tables/latex/table_d2_personalized_judge_scores.tex`
- `tables/latex/table_d7_evolutionary_exploration_counts.tex`
- `tables/markdown/baseline_counts_and_status.md`
- `tables/markdown/personalized_judge_scores.md`
- `tables/markdown/personalized_pipeline_counts.md`

## Row-Level Changes

- `profile_conditioned/profile_pipeline_counts.csv`: 2 profile rows removed: Sutton/Barto RL and Yoshua Bengio skipped/no-run profiles.
- `profile_conditioned/profile_summary_table.csv`: 2 profile rows removed and runtime report-path cells blanked.
- `profile_conditioned/summaries/profile_summary_table.csv`: 2 profile rows removed and runtime report-path cells blanked.
- `tables/csv/table_d1_personalized_pipeline_counts.csv`: 2 profile rows removed: only Yann LeCun, Geoffrey Hinton, and Michael I. Jordan remain.
- `profile_conditioned/profile_scores.csv`: 4 paper-use planning labels replaced with public result labels; numeric scores unchanged.
- `profile_conditioned/scores/paper_ready_personalized_score_table.csv`: 4 paper-use planning labels replaced with public result labels; numeric scores unchanged.
- `tables/csv/table_d2_personalized_judge_scores.csv`: 4 paper-use planning labels replaced with public result labels; numeric scores unchanged.
- `tables/csv/table_a4_baseline_counts_and_status.csv`: 4 non-paper/blocked baseline-attempt rows removed; reported paper-facing methods remain.

## Public Bundle Policy After Scrub

- Included: paper-result artifacts such as candidate packets, final outputs, score tables, paper tables, qualitative examples, profile/evolution/sensitivity artifacts, sanitized paper-run configs, manifests, and checksums.
- Excluded: discarded examples, unsuccessful internal run rows, staging status matrices, review/audit scratch files, raw logs, raw model responses, raw PDFs, parsed full texts, runtime path provenance, and non-paper baseline attempts.
- Figures remain excluded unless explicitly added later for camera-ready or arXiv source distribution.

## Consistency Notes

- Main result values were not recomputed or changed; the scrub removed non-paper rows and stale duplicate/status artifacts only.
- The public paper-facing profile set is Yann LeCun, Geoffrey Hinton, and Michael I. Jordan.
- The public paper-facing baseline bundle keeps Native AI-Scientist-v2 and MOOSE-Star artifacts alongside SGHA outputs; blocked or exploratory baseline attempts are excluded.
- Broad terms such as `TODO`, `private`, and `appendix` remain only where they are legitimate public documentation or release-task language outside the release bundle.
