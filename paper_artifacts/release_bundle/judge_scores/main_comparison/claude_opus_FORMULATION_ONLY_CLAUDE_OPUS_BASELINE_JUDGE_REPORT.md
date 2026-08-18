# Formulation-Only Judge Report: Claude Opus Latest Native AI-Scientist-v2 Baseline

## Setup Recap
- baseline: Native AI-Scientist-v2 Claude Opus Latest
- model_id: `~anthropic/claude-opus-latest`
- resolved_model_id: `anthropic/claude-opus-5` where observed in generation metadata
- candidates scored: 15
- scoring mode: formulation-only 10-point rubric
- pairwise comparison: disabled
- weighted composite score: not computed
- SGHA was not re-scored; existing SGHA scores were reused for comparison.

## Candidate Counts

|domain|candidates|
|---|---|
|bandits|3|
|in_context_learning|4|
|offline_reinforcement_learning_arxiv|1|
|reasoning_models_test_time_compute|1|
|uncertainty_calibration_conformal_prediction_arxiv|6|

## Judge Models

|judge_model|scores|parse_errors|
|---|---|---|
|anthropic/claude-sonnet-4|15|0|
|openai/gpt-5.6-sol-pro|15|0|
|x-ai/grok-4.5|15|0|
|moonshotai/kimi-k3|15|0|
|google/gemini-3.6-flash|15|0|

## Claude Opus Baseline Scores

|method|candidates|judge_models|mean_problem_definition_clarity_10|mean_technical_specificity_10|mean_well_posedness_10|mean_assumption_boundary_clarity_10|mean_formalizability_10|mean_nontriviality_10|mean_scope_control_10|mean_source_grounded_specificity_10|mean_ambiguity_hygiene_10|mean_overall_formulation_quality_10|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|15|5|7.1467|6.9467|4.88|4.7467|5.2133|6.88|6.1867|2.9733|3.5733|5.84|

## Same-Provider Sensitivity

|method|candidates|judge_models|mean_problem_definition_clarity_10|mean_technical_specificity_10|mean_well_posedness_10|mean_assumption_boundary_clarity_10|mean_formalizability_10|mean_nontriviality_10|mean_scope_control_10|mean_source_grounded_specificity_10|mean_ambiguity_hygiene_10|mean_overall_formulation_quality_10|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|15|4|7.15|6.7833|4.9|4.8333|5.2167|6.65|6.0333|2.9667|3.4667|5.8333|

## Three-Method Comparison

|method|candidates|judge_models|mean_problem_definition_clarity_10|mean_technical_specificity_10|mean_well_posedness_10|mean_assumption_boundary_clarity_10|mean_formalizability_10|mean_nontriviality_10|mean_scope_control_10|mean_source_grounded_specificity_10|mean_ambiguity_hygiene_10|mean_overall_formulation_quality_10|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|15|5|7.1467|6.9467|4.88|4.7467|5.2133|6.88|6.1867|2.9733|3.5733|5.84|
|NATIVE_AI_SCIENTIST_V2_QWEN|15|5|5.5867|4.72|3.5333|3.6133|3.68|5.2667|5.7333|5.1067|2.8133|4.5467|
|SGHA_FULL|15|5|6.7733|5.8933|5.7733|6.4533|5.5067|6.3867|5.36|7.4267|7.6133|5.9867|

## Criteria Winners

|criterion|winning_method|winning_mean|SGHA_FULL_mean|NATIVE_AI_SCIENTIST_V2_QWEN_mean|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST_mean|
|---|---|---|---|---|---|
|problem_definition_clarity_10|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|7.1467|6.7733|5.5867|7.1467|
|technical_specificity_10|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|6.9467|5.8933|4.72|6.9467|
|well_posedness_10|SGHA_FULL|5.7733|5.7733|3.5333|4.88|
|assumption_boundary_clarity_10|SGHA_FULL|6.4533|6.4533|3.6133|4.7467|
|formalizability_10|SGHA_FULL|5.5067|5.5067|3.68|5.2133|
|nontriviality_10|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|6.88|6.3867|5.2667|6.88|
|scope_control_10|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|6.1867|5.36|5.7333|6.1867|
|source_grounded_specificity_10|SGHA_FULL|7.4267|7.4267|5.1067|2.9733|
|ambiguity_hygiene_10|SGHA_FULL|7.6133|7.6133|2.8133|3.5733|
|overall_formulation_quality_10|SGHA_FULL|5.9867|5.9867|4.5467|5.84|

## Structural Metrics

|method|candidates|source_grounding_present|formal_problem_statement_present|assumptions_setup_present|ambiguity_flags_present|evaluation_plan_present|risks_caveats_present|complete_research_problem_object_count|
|---|---|---|---|---|---|---|---|---|
|SGHA_FULL|15|15|15|15|15|15|15|15|
|NATIVE_AI_SCIENTIST_V2_QWEN|15|15|0|0|0|15|15|0|
|NATIVE_AI_SCIENTIST_V2_CLAUDE_OPUS_LATEST|15|15|0|0|0|15|15|0|

## Validation Summary

- all five requested judge models completed: true
- candidates scored per judge: 15
- total Claude Opus baseline score rows: 75
- parse errors: 0
- method labels hidden during scoring: true
- blinding key read only during postprocess: true
- pairwise comparison disabled: true
- weighted composite score avoided: true
- secret leakage check: PASS

## Caveats
- LLM-judge scores are descriptive and do not establish external novelty.
- The Claude Opus Latest Native AI-Scientist-v2 baseline is output-count matched, not compute- or information-matched.
- Method labels were hidden during scoring; blinding keys were read only during postprocess.
- Kimi required sharded completion after a provider stall; the final Kimi directory contains all 15 scores and records the shard trail.

## Recommended Paper Use
- Use the three-method score table for appendix or supporting analysis.
- Use the structural completeness table in the main paper only if the text clearly distinguishes completeness from formulation quality.
- Include the Anthropic-judge exclusion sensitivity when discussing Claude Opus Latest results.
