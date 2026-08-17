# Personalized Profile Alignment Judge Report

## Setup

- evaluation directory: `[PROFILE_CONDITIONED_RUN_NAMESPACE]/llm_judge/personalized_profile_alignment_judge_20260724_104911`
- repaired personalized namespace: `[PROFILE_CONDITIONED_RUN_NAMESPACE]/`
- original repaired batch: `[SANITIZED_PRIVATE_PATH]
- scoring mode: `personalized_formulation_10pt`
- pairwise comparison: disabled
- weighted composite: not computed
- external search: not used

## Profile Context Source

- Profile context cards were built from seed audits, topic inference audits, run summaries, final families, Stage 10 formalizations, and final report audits.
- Profile names were visible to the judge; method labels were hidden.

## Candidates Scored

- geoffrey_hinton:family:01 / Geoffrey Hinton: Characterizing the Convergence Failure Regime of Stochastic Gradient Approximations in Deep Generative Models
- michael_i_jordan:family:01 / Michael I. Jordan: Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices
- michael_i_jordan:family:02 / Michael I. Jordan: Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation
- yann_lecun:family:01 / Yann LeCun: Characterizing the Fundamental Limits of Partition Function Approximation in High-Dimensional EBMs

## Judge Models

- `anthropic/claude-sonnet-4`: PASS (scores=4, parse_errors=0)
- `anthropic/claude-fable-5`: FAILED_PARTIAL (scores=3, parse_errors=1)
- `x-ai/grok-4.5`: PASS (scores=4, parse_errors=0)
- `moonshotai/kimi-k3`: PASS (scores=4, parse_errors=0)
- `openai/gpt-5.6-sol-pro`: PASS (scores=4, parse_errors=0)
- `google/gemini-3.6-flash`: FAILED_PARTIAL (scores=3, parse_errors=1)

## Calibration Status

- Calibration passed: yes
- details: `[PROFILE_CONDITIONED_RUN_NAMESPACE]/llm_judge/personalized_profile_alignment_judge_20260724_104911/calibration/CALIBRATION_STATUS.md`

## Results

- Geoffrey Hinton / Characterizing the Convergence Failure Regime of Stochastic Gradient Approximations in Deep Generative Models: formulation=5.6667, personalization=7.1667, alignment=8.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=do_not_use_as_strong_example
- Michael I. Jordan / Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices: formulation=6.0, personalization=6.3333, alignment=6.5, action=PROMISING_NEEDS_REFINEMENT, paper_use=appendix_or_qualitative_discussion
- Michael I. Jordan / Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation: formulation=6.0, personalization=7.0, alignment=8.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=appendix_or_qualitative_discussion
- Yann LeCun / Characterizing the Fundamental Limits of Partition Function Approximation in High-Dimensional EBMs: formulation=6.1667, personalization=5.3333, alignment=7.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=do_not_use_as_strong_example

## Skipped Profiles

- Sutton-Barto RL profile: skipped, no usable verification artifacts.
- Yoshua Bengio: skipped, no usable verification artifacts.

## Paper-Use Recommendation

- Michael I. Jordan: Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices (appendix_or_qualitative_discussion)
- Michael I. Jordan: Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation (appendix_or_qualitative_discussion)

## Caveats

- Only 3 repaired profiles were scoreable, producing 4 candidates.
- Claude Fable and Gemini were partial model runs with one parse error each.
- Profile alignment was judged only from provided profile cards; no external profile knowledge or novelty search was used.
- Use the per-candidate `n_judges` field when quoting means.
