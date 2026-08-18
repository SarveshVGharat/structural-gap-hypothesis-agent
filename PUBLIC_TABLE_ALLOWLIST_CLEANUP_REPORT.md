# Public Table Allowlist Cleanup Report

Date: 2026-08-18

Scope: public paper table-like files under `paper_artifacts/release_bundle/`, especially `tables/`, `main_results/`, `judge_scores/`, `profile_conditioned/`, `evolutionary/`, and `sensitivity/`.

Policy: keep only canonical paper-facing tables and score aggregates needed to inspect or reproduce reported results. Diagnostic, draft, stale, duplicated, broad-dump, status-matrix, uncertain appendix, and non-paper tables were removed by default. No SGHA runs, LLM calls, OpenRouter calls, paper downloads, raw PDFs, or parsed full texts were used.

## Counts

- Requested full-bundle table-like file count before cleanup: 197
- Requested full-bundle table-like file count after cleanup: 104
- Target-directory inventory count before cleanup: 148
- Target-directory inventory count after cleanup: 57
- Manifest rows before cleanup: 253
- Manifest rows after cleanup: 160
- Checksum entries after cleanup: 159

## Inventory Classification

| Path | Classification | Reason | Action taken |
|---|---|---|---|
| `evolutionary/scores/formulation_only_scores_by_domain.csv` | KEEP_MAIN | Evolutionary formulation/per-domain score aggregate retained for reported results. | keep |
| `evolutionary/scores/formulation_only_scores_by_domain_method.csv` | KEEP_MAIN | Evolutionary formulation/per-domain score aggregate retained for reported results. | keep |
| `evolutionary/scores/formulation_only_scores_by_method.csv` | KEEP_MAIN | Evolutionary formulation/per-domain score aggregate retained for reported results. | keep |
| `evolutionary/scores/formulation_only_scores_unblinded.csv` | KEEP_MAIN | Evolutionary formulation/per-domain score aggregate retained for reported results. | keep |
| `evolutionary/scores/partial_evolutionary_candidate_aggregates.csv` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `evolutionary/scores/partial_evolutionary_scores_by_candidate.csv` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `evolutionary/scores/partial_evolutionary_scores_by_candidate_judge.csv` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `evolutionary/scores/partial_evolutionary_scores_by_domain.csv` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `evolutionary/scores/partial_evolutionary_scores_by_method.csv` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `evolutionary/scores/table_d7_evolutionary_exploration_counts.csv` | REMOVE_NOT_USED | Inspected after the temporary move; this was a legacy optional-branch count table rather than a paper-facing result. | remove |
| `evolutionary/selected_candidates/evolutionary_selected_candidates_index.csv` | KEEP_REPRODUCIBILITY | Paper-facing evolutionary example/index or score summary retained. | keep |
| `evolutionary/selected_candidates/top_evolutionary_example.md` | KEEP_REPRODUCIBILITY | Paper-facing evolutionary example/index or score summary retained. | keep |
| `evolutionary/summaries/FORMULATION_ONLY_EVOLUTIONARY_EXPLORATION_JUDGE_REPORT.md` | KEEP_REPRODUCIBILITY | Paper-facing evolutionary example/index or score summary retained. | keep |
| `evolutionary/summaries/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md` | REMOVE_NOT_USED | Partial evolutionary diagnostic table/report is not in the strict paper-facing allowlist. | remove |
| `judge_scores/README.md` | KEEP_REPRODUCIBILITY | Navigation README for retained main-comparison score aggregates. | sanitize |
| `judge_scores/evolutionary/FORMULATION_ONLY_EVOLUTIONARY_EXPLORATION_JUDGE_REPORT.md` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/formulation_only_scores_by_domain.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/formulation_only_scores_by_domain_method.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/formulation_only_scores_by_method.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/formulation_only_scores_unblinded.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/partial_evolutionary_candidate_aggregates.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/partial_evolutionary_scores_by_candidate.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/partial_evolutionary_scores_by_candidate_judge.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/partial_evolutionary_scores_by_domain.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/evolutionary/partial_evolutionary_scores_by_method.csv` | REMOVE_DUPLICATE | Duplicate evolutionary score table/report; canonical evolutionary/ files are retained. | remove |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_FORMULATION_ONLY_RUBRIC.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_FORMULATION_ONLY_SCORE_SUMMARY.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_all_individual_formulation_scores_readable.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_domain.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_domain_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_unblinded.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_sgha_vs_native_deltas.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_sgha_vs_native_scores.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/claude_opus_FORMULATION_ONLY_CLAUDE_OPUS_BASELINE_JUDGE_REPORT.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_domain.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_domain_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/claude_opus_formulation_only_scores_unblinded.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_BEST_OF_METHOD_4WAY_REPORT.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_candidate_pool_summary.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_criterion_rank_summary.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_domain_winners.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_four_way_judge_summary.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_four_way_results_unblinded.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_mean_rank_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/four_way_win_counts_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_FORMULATION_ONLY_MOOSE_STAR_JUDGE_REPORT.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_PAPER_READY_SGHA_VS_MOOSE_SCORE_TABLE.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_SGHA_VS_MOOSE_STAR_SCORE_SUMMARY.md` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_canonical_sgha_native_moose_scores_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_paper_ready_sgha_vs_moose_score_table.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_sgha_vs_moose_candidate_aggregates.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_sgha_vs_moose_scores_by_domain_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/main_comparison/moose_star_sgha_vs_moose_scores_by_method.csv` | KEEP_REPRODUCIBILITY | Main-comparison score aggregate, rubric, or summary retained for judging reproducibility. | keep |
| `judge_scores/profile_conditioned/PERSONALIZED_PROFILE_ALIGNMENT_JUDGE_REPORT.md` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/paper_ready_personalized_score_table.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/personalized_candidate_aggregates.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/personalized_scores_by_candidate_judge.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/personalized_scores_by_model.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/personalized_scores_by_profile.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/profile_conditioned/recommended_actions_by_candidate.csv` | REMOVE_DUPLICATE | Duplicate profile-conditioned score table/report; canonical profile_conditioned/ files are retained. | remove |
| `judge_scores/sensitivity/table_d3_model_scaling_counts.csv` | REMOVE_DUPLICATE | Duplicate sensitivity table; canonical sensitivity/ files are retained. | remove |
| `judge_scores/sensitivity/table_d4_model_scaling_judge.csv` | REMOVE_DUPLICATE | Duplicate sensitivity table; canonical sensitivity/ files are retained. | remove |
| `judge_scores/sensitivity/table_d5_paper_scaling_counts.csv` | REMOVE_DUPLICATE | Duplicate sensitivity table; canonical sensitivity/ files are retained. | remove |
| `judge_scores/sensitivity/table_d6_paper_scaling_judge.csv` | REMOVE_DUPLICATE | Duplicate sensitivity table; canonical sensitivity/ files are retained. | remove |
| `main_results/README.md` | KEEP_MAIN | Canonical main-result CSV/index file retained by the public allowlist. | keep |
| `main_results/formulation_quality_scores.csv` | KEEP_MAIN | Canonical main-result CSV/index file retained by the public allowlist. | keep |
| `main_results/pipeline_yield.csv` | KEEP_MAIN | Canonical main-result CSV/index file retained by the public allowlist. | keep |
| `main_results/qualitative_example_overview.csv` | KEEP_MAIN | Canonical main-result CSV/index file retained by the public allowlist. | keep |
| `main_results/structural_artifact_coverage.csv` | KEEP_MAIN | Canonical main-result CSV/index file retained by the public allowlist. | keep |
| `profile_conditioned/README.md` | KEEP_MAIN | Canonical profile-conditioned public artifact retained by the allowlist. | keep |
| `profile_conditioned/candidates/michael_jordan_hierarchical_identifiability_example.md` | KEEP_MAIN | Canonical profile-conditioned public artifact retained by the allowlist. | keep |
| `profile_conditioned/profile_pipeline_counts.csv` | KEEP_MAIN | Canonical profile-conditioned public artifact retained by the allowlist. | keep |
| `profile_conditioned/profile_scores.csv` | KEEP_MAIN | Canonical profile-conditioned public artifact retained by the allowlist. | keep |
| `profile_conditioned/profile_summary_table.csv` | KEEP_MAIN | Canonical profile-conditioned public artifact retained by the allowlist. | keep |
| `profile_conditioned/scores/paper_ready_personalized_score_table.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/scores/personalized_candidate_aggregates.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/scores/personalized_scores_by_candidate_judge.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/scores/personalized_scores_by_model.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/scores/personalized_scores_by_profile.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/scores/recommended_actions_by_candidate.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `profile_conditioned/summaries/profile_summary_table.csv` | REMOVE_DUPLICATE | Duplicate profile score/summary table; canonical root profile_conditioned files are retained. | remove |
| `sensitivity/corpus_size/paper_scaling_counts.md` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/corpus_size/paper_scaling_judge.md` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/corpus_size/table_d5_paper_scaling_counts.csv` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/corpus_size/table_d6_paper_scaling_judge.csv` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/model_size/model_scaling_counts.md` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/model_size/model_scaling_judge.md` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/model_size/table_d3_model_scaling_counts.csv` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `sensitivity/model_size/table_d4_model_scaling_judge.csv` | KEEP_MAIN | Canonical model/corpus sensitivity table retained. | keep |
| `tables/README.md` | KEEP_REPRODUCIBILITY | Tables directory retained as a minimal navigation pointer only. | sanitize |
| `tables/csv/table_1_sgha_pipeline_yield.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_2_formulation_quality_main.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_3_structural_artifacts.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_a10_judge_cap_warnings_and_sensitivity.csv` | REMOVE_NOT_USED | Cap-warning sensitivity table is not explicitly in the paper-facing allowlist. | remove |
| `tables/csv/table_a1_full_pipeline_counts.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a2_full_10_criterion_formulation_scores.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a4_baseline_counts_and_status.csv` | REMOVE_UNSUCCESSFUL_OR_BLOCKED | Baseline status/count table is outside the strict public table allowlist. | remove |
| `tables/csv/table_a5_multi_judge_robustness.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a6_best_candidates_by_domain.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a7_per_domain_formulation_scores.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a8_moose_star_baseline_details.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_a9_claude_opus_baseline_details.csv` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/csv/table_d1_personalized_pipeline_counts.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d2_personalized_judge_scores.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d3_model_scaling_counts.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d4_model_scaling_judge.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d5_paper_scaling_counts.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d6_paper_scaling_judge.csv` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/csv/table_d7_evolutionary_exploration_counts.csv` | REMOVE_NOT_USED | Legacy optional-branch count table; removed rather than relocated into the public paper-facing bundle. | remove |
| `tables/latex/table_1_sgha_pipeline_yield.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_2_formulation_quality_main.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_3_structural_artifacts.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_a10_judge_cap_warnings_and_sensitivity.tex` | REMOVE_NOT_USED | Cap-warning sensitivity table is not explicitly in the paper-facing allowlist. | remove |
| `tables/latex/table_a1_full_pipeline_counts.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a2_full_10_criterion_formulation_scores.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a3_structural_artifacts_full.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a4_baseline_counts_and_status.tex` | REMOVE_UNSUCCESSFUL_OR_BLOCKED | Baseline status/count table is outside the strict public table allowlist. | remove |
| `tables/latex/table_a5_multi_judge_robustness.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a6_best_candidates_by_domain.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a7_per_domain_formulation_scores.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a8_moose_star_baseline_details.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_a9_claude_opus_baseline_details.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/latex/table_d1_personalized_pipeline_counts.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d2_personalized_judge_scores.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d3_model_scaling_counts.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d4_model_scaling_judge.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d5_paper_scaling_counts.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d6_paper_scaling_judge.tex` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/latex/table_d7_evolutionary_exploration_counts.tex` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/baseline_counts_and_status.md` | REMOVE_UNSUCCESSFUL_OR_BLOCKED | Baseline status/count table is outside the strict public table allowlist. | remove |
| `tables/markdown/best_candidates_by_domain.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/claude_opus_baseline_details.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/evolutionary_exploration_counts.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/judge_cap_warnings_and_sensitivity.md` | REMOVE_NOT_USED | Cap-warning sensitivity table is not explicitly in the paper-facing allowlist. | remove |
| `tables/markdown/model_scaling_counts.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/model_scaling_judge.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/moose_star_details.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/multi_judge_robustness.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/paper_scaling_counts.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/paper_scaling_judge.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/personalized_judge_scores.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/personalized_pipeline_counts.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |
| `tables/markdown/table_1_sgha_pipeline_yield.md` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/markdown/table_2_formulation_quality_main.md` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/markdown/table_3_structural_artifacts.md` | REMOVE_DUPLICATE | Duplicate broad table-dump copy; canonical section-level table is retained. | remove |
| `tables/markdown/table_a2_full_10_criterion_formulation_scores.md` | UNCERTAIN_REMOVE_BY_DEFAULT | Appendix/draft table was not confirmed as current paper-facing; removed by default. | remove |

## Removed Files

- `evolutionary/scores/table_d7_evolutionary_exploration_counts.csv`
- `main_sgha/pipeline_counts/table_1_sgha_pipeline_yield.csv`
- `main_sgha/pipeline_counts/table_3_structural_artifacts.csv`
- `evolutionary/scores/partial_evolutionary_candidate_aggregates.csv`
- `evolutionary/scores/partial_evolutionary_scores_by_candidate.csv`
- `evolutionary/scores/partial_evolutionary_scores_by_candidate_judge.csv`
- `evolutionary/scores/partial_evolutionary_scores_by_domain.csv`
- `evolutionary/scores/partial_evolutionary_scores_by_method.csv`
- `evolutionary/summaries/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md`
- `judge_scores/evolutionary/FORMULATION_ONLY_EVOLUTIONARY_EXPLORATION_JUDGE_REPORT.md`
- `judge_scores/evolutionary/PARTIAL_EVOLUTIONARY_SCORE_RESULTS.md`
- `judge_scores/evolutionary/formulation_only_scores_by_domain.csv`
- `judge_scores/evolutionary/formulation_only_scores_by_domain_method.csv`
- `judge_scores/evolutionary/formulation_only_scores_by_method.csv`
- `judge_scores/evolutionary/formulation_only_scores_unblinded.csv`
- `judge_scores/evolutionary/partial_evolutionary_candidate_aggregates.csv`
- `judge_scores/evolutionary/partial_evolutionary_scores_by_candidate.csv`
- `judge_scores/evolutionary/partial_evolutionary_scores_by_candidate_judge.csv`
- `judge_scores/evolutionary/partial_evolutionary_scores_by_domain.csv`
- `judge_scores/evolutionary/partial_evolutionary_scores_by_method.csv`
- `judge_scores/profile_conditioned/PERSONALIZED_PROFILE_ALIGNMENT_JUDGE_REPORT.md`
- `judge_scores/profile_conditioned/paper_ready_personalized_score_table.csv`
- `judge_scores/profile_conditioned/personalized_candidate_aggregates.csv`
- `judge_scores/profile_conditioned/personalized_scores_by_candidate_judge.csv`
- `judge_scores/profile_conditioned/personalized_scores_by_model.csv`
- `judge_scores/profile_conditioned/personalized_scores_by_profile.csv`
- `judge_scores/profile_conditioned/recommended_actions_by_candidate.csv`
- `judge_scores/sensitivity/table_d3_model_scaling_counts.csv`
- `judge_scores/sensitivity/table_d4_model_scaling_judge.csv`
- `judge_scores/sensitivity/table_d5_paper_scaling_counts.csv`
- `judge_scores/sensitivity/table_d6_paper_scaling_judge.csv`
- `profile_conditioned/scores/paper_ready_personalized_score_table.csv`
- `profile_conditioned/scores/personalized_candidate_aggregates.csv`
- `profile_conditioned/scores/personalized_scores_by_candidate_judge.csv`
- `profile_conditioned/scores/personalized_scores_by_model.csv`
- `profile_conditioned/scores/personalized_scores_by_profile.csv`
- `profile_conditioned/scores/recommended_actions_by_candidate.csv`
- `profile_conditioned/summaries/profile_summary_table.csv`
- `tables/csv/table_1_sgha_pipeline_yield.csv`
- `tables/csv/table_2_formulation_quality_main.csv`
- `tables/csv/table_3_structural_artifacts.csv`
- `tables/csv/table_a10_judge_cap_warnings_and_sensitivity.csv`
- `tables/csv/table_a1_full_pipeline_counts.csv`
- `tables/csv/table_a2_full_10_criterion_formulation_scores.csv`
- `tables/csv/table_a4_baseline_counts_and_status.csv`
- `tables/csv/table_a5_multi_judge_robustness.csv`
- `tables/csv/table_a6_best_candidates_by_domain.csv`
- `tables/csv/table_a7_per_domain_formulation_scores.csv`
- `tables/csv/table_a8_moose_star_baseline_details.csv`
- `tables/csv/table_a9_claude_opus_baseline_details.csv`
- `tables/csv/table_d1_personalized_pipeline_counts.csv`
- `tables/csv/table_d2_personalized_judge_scores.csv`
- `tables/csv/table_d3_model_scaling_counts.csv`
- `tables/csv/table_d4_model_scaling_judge.csv`
- `tables/csv/table_d5_paper_scaling_counts.csv`
- `tables/csv/table_d6_paper_scaling_judge.csv`
- `tables/csv/table_d7_evolutionary_exploration_counts.csv`
- `tables/latex/table_1_sgha_pipeline_yield.tex`
- `tables/latex/table_2_formulation_quality_main.tex`
- `tables/latex/table_3_structural_artifacts.tex`
- `tables/latex/table_a10_judge_cap_warnings_and_sensitivity.tex`
- `tables/latex/table_a1_full_pipeline_counts.tex`
- `tables/latex/table_a2_full_10_criterion_formulation_scores.tex`
- `tables/latex/table_a3_structural_artifacts_full.tex`
- `tables/latex/table_a4_baseline_counts_and_status.tex`
- `tables/latex/table_a5_multi_judge_robustness.tex`
- `tables/latex/table_a6_best_candidates_by_domain.tex`
- `tables/latex/table_a7_per_domain_formulation_scores.tex`
- `tables/latex/table_a8_moose_star_baseline_details.tex`
- `tables/latex/table_a9_claude_opus_baseline_details.tex`
- `tables/latex/table_d1_personalized_pipeline_counts.tex`
- `tables/latex/table_d2_personalized_judge_scores.tex`
- `tables/latex/table_d3_model_scaling_counts.tex`
- `tables/latex/table_d4_model_scaling_judge.tex`
- `tables/latex/table_d5_paper_scaling_counts.tex`
- `tables/latex/table_d6_paper_scaling_judge.tex`
- `tables/latex/table_d7_evolutionary_exploration_counts.tex`
- `tables/markdown/baseline_counts_and_status.md`
- `tables/markdown/best_candidates_by_domain.md`
- `tables/markdown/claude_opus_baseline_details.md`
- `tables/markdown/evolutionary_exploration_counts.md`
- `tables/markdown/judge_cap_warnings_and_sensitivity.md`
- `tables/markdown/model_scaling_counts.md`
- `tables/markdown/model_scaling_judge.md`
- `tables/markdown/moose_star_details.md`
- `tables/markdown/multi_judge_robustness.md`
- `tables/markdown/paper_scaling_counts.md`
- `tables/markdown/paper_scaling_judge.md`
- `tables/markdown/personalized_judge_scores.md`
- `tables/markdown/personalized_pipeline_counts.md`
- `tables/markdown/table_1_sgha_pipeline_yield.md`
- `tables/markdown/table_2_formulation_quality_main.md`
- `tables/markdown/table_3_structural_artifacts.md`
- `tables/markdown/table_a2_full_10_criterion_formulation_scores.md`

## Moved Files

- None. The potential evolutionary count table was inspected after the move and removed because it described a legacy optional branch rather than a paper-facing result.

## Retained Tables By Section

### Main pipeline yield
- `main_results/pipeline_yield.csv` (present)

### Formulation-quality comparison
- `main_results/formulation_quality_scores.csv` (present)
- `judge_scores/main_comparison/ai_scientist_v2_qwen_FORMULATION_ONLY_RUBRIC.md`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_FORMULATION_ONLY_SCORE_SUMMARY.md`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_all_individual_formulation_scores_readable.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_domain.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_domain_method.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_by_method.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_scores_unblinded.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_sgha_vs_native_deltas.csv`
- `judge_scores/main_comparison/ai_scientist_v2_qwen_formulation_only_sgha_vs_native_scores.csv`
- `judge_scores/main_comparison/claude_opus_FORMULATION_ONLY_CLAUDE_OPUS_BASELINE_JUDGE_REPORT.md`
- `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_domain.csv`
- `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_domain_method.csv`
- `judge_scores/main_comparison/claude_opus_formulation_only_scores_by_method.csv`
- `judge_scores/main_comparison/claude_opus_formulation_only_scores_unblinded.csv`
- `judge_scores/main_comparison/four_way_BEST_OF_METHOD_4WAY_REPORT.md`
- `judge_scores/main_comparison/four_way_candidate_pool_summary.md`
- `judge_scores/main_comparison/four_way_criterion_rank_summary.csv`
- `judge_scores/main_comparison/four_way_domain_winners.csv`
- `judge_scores/main_comparison/four_way_four_way_judge_summary.md`
- `judge_scores/main_comparison/four_way_four_way_results_unblinded.csv`
- `judge_scores/main_comparison/four_way_mean_rank_by_method.csv`
- `judge_scores/main_comparison/four_way_win_counts_by_method.csv`
- `judge_scores/main_comparison/moose_star_FORMULATION_ONLY_MOOSE_STAR_JUDGE_REPORT.md`
- `judge_scores/main_comparison/moose_star_PAPER_READY_SGHA_VS_MOOSE_SCORE_TABLE.md`
- `judge_scores/main_comparison/moose_star_SGHA_VS_MOOSE_STAR_SCORE_SUMMARY.md`
- `judge_scores/main_comparison/moose_star_canonical_sgha_native_moose_scores_by_method.csv`
- `judge_scores/main_comparison/moose_star_paper_ready_sgha_vs_moose_score_table.csv`
- `judge_scores/main_comparison/moose_star_sgha_vs_moose_candidate_aggregates.csv`
- `judge_scores/main_comparison/moose_star_sgha_vs_moose_scores_by_domain_method.csv`
- `judge_scores/main_comparison/moose_star_sgha_vs_moose_scores_by_method.csv`

### Structural artifact coverage
- `main_results/structural_artifact_coverage.csv` (present)

### Qualitative example overview
- `main_results/qualitative_example_overview.csv` (present)

### Profile-conditioned generation
- `profile_conditioned/profile_pipeline_counts.csv` (present)
- `profile_conditioned/profile_scores.csv` (present)
- `profile_conditioned/profile_summary_table.csv` (present)

### Evolutionary exploration
- No retained artifact-count table; the only available count table was marked as a legacy optional branch and was removed.
- `evolutionary/scores/formulation_only_scores_by_method.csv` (present)
- `evolutionary/scores/formulation_only_scores_by_domain.csv` (present)
- `evolutionary/scores/formulation_only_scores_by_domain_method.csv` (present)
- `evolutionary/scores/formulation_only_scores_unblinded.csv` (present)

### Model/corpus sensitivity
- `sensitivity/model_size/table_d3_model_scaling_counts.csv` (present)
- `sensitivity/model_size/table_d4_model_scaling_judge.csv` (present)
- `sensitivity/corpus_size/table_d5_paper_scaling_counts.csv` (present)
- `sensitivity/corpus_size/table_d6_paper_scaling_judge.csv` (present)

### Appendix tables
- `main_sgha/pipeline_counts/table_a1_full_pipeline_counts.csv` (present)
