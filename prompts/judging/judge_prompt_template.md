# Judge Prompt Template

Purpose: evaluate blinded candidate research problems using explicit rubric criteria.

Inputs:

- blinded candidate packet
- rubric and scoring mode
- calibration sentinels when enabled

Output: strict JSON scores, rationales, strengths, weaknesses, confidence, and cap-rule diagnostics.

Implementation: `scripts/run_llm_judge_openrouter.py`.
