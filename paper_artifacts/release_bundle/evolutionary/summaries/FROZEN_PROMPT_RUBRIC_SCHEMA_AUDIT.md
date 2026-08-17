# Frozen Prompt/Rubric/Schema Audit

The evolutionary exploration branch is scored with the existing `formulation_only_10pt` judge mode and the frozen formulation-only criteria/cap rules from the SGHA-vs-Native evaluation. No source prompt, rubric, schema, or response format files were modified for this evaluation.

- candidate packet: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/candidates/evolutionary_candidates_blinded.jsonl`
- blinding key: `[MAIN_PAPER_RUN_NAMESPACE]/evolutionary_exploration_formulation_judge_20260801_165429/candidates/evolutionary_blinding_key.json`

## Hashes

| Artifact | Path | sha256 |
|---|---|---|
| FROZEN_FORMULATION_ONLY_RUBRIC.md | `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/prompt_freeze/FROZEN_FORMULATION_ONLY_RUBRIC.md` | `bc354c8d7b370a94e3c9f5930402b381cc37c20f1a40efdbe5efb0ede05558b0` |
| FROZEN_FORMULATION_ONLY_SCHEMA.md | `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/prompt_freeze/FROZEN_FORMULATION_ONLY_SCHEMA.md` | `99c8d342ab8dc2cd7acb39f13b23fb4716575814cb03cd351cbc89c073360a96` |
| FROZEN_FORMULATION_ONLY_SYSTEM_PROMPT.md | `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/prompt_freeze/FROZEN_FORMULATION_ONLY_SYSTEM_PROMPT.md` | `7c50f624d187899b22b76cacf204401834cc36dda06cbfb67c17ca97067d543d` |
| FROZEN_FORMULATION_ONLY_USER_PROMPT_TEMPLATE.md | `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/prompt_freeze/FROZEN_FORMULATION_ONLY_USER_PROMPT_TEMPLATE.md` | `1c5c02c14cd453cd57f4a8c7e63984a665858f3a450a76d908be1c6ffefff948` |
| FROZEN_PROMPT_HASHES.json | `[MAIN_PAPER_RUN_NAMESPACE]/sgha_vs_native_ai_scientist_v2_final_comparison/openai_gemini_judge_prompt_frozen_repair_20260723_054649/prompt_freeze/FROZEN_PROMPT_HASHES.json` | `5bccbdba2c7ae1ec928e8705fe1ee56ffbae35a79119b2d370fbf418eda2f880` |
| openrouter_llm_judge.yaml | `[ORIGINAL_RESEARCH_REPO]/configs/judging/openrouter_llm_judge.yaml` | `2ac305d15e138f28b8c09412f508eabe4cd7f971e14587b33e3527b6fb6054e5` |

## Confirmations

- prompt unchanged: yes
- rubric unchanged: yes
- JSON schema unchanged: yes
- cap rules unchanged: yes
- scoring criteria unchanged: yes
- no pairwise comparison: yes
- no weighted composite score: yes
