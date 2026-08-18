# Formulation-Only Score Summary

- created_at_utc: 2026-07-22T19:44:01.014726+00:00
- OpenRouter model: `anthropic/claude-sonnet-4`
- candidates scored: 30
- SGHA_FULL candidates: 15
- NATIVE_AI_SCIENTIST_V2 candidates: 15
- calibration passed: True
- parse errors: 0
- raw model responses: 46
- remaining cap violation count: 4
- pairwise comparison disabled: True
- weighted composite avoided: True
- formulation quality only: True

## Overall Means

| method | n | mean overall_formulation_quality_10 | cap violations |
|---|---:|---:|---:|
| SGHA_FULL | 15 | 6.4 | 2 |
| NATIVE_AI_SCIENTIST_V2 | 15 | 4.9333 | 2 |

## Criteria Won

- SGHA_FULL: 9 criteria: problem_definition_clarity_10, technical_specificity_10, well_posedness_10, assumption_boundary_clarity_10, formalizability_10, nontriviality_10, source_grounded_specificity_10, ambiguity_hygiene_10, overall_formulation_quality_10
- NATIVE_AI_SCIENTIST_V2: 1 criteria: scope_control_10

## Recommended Actions

| method | action | count |
|---|---|---:|
| NATIVE_AI_SCIENTIST_V2 | PROMISING_NEEDS_REFINEMENT | 15 |
| SGHA_FULL | PROMISING_NEEDS_REFINEMENT | 15 |

## Files


## Caveats

- Scores judge formulation quality only from provided text; no external novelty check was performed.
- Native records with missing formal/setup/ambiguity fields were shown as `not provided` rather than filled in.
- Remaining cap-violation flags are retained in score records and audits.
