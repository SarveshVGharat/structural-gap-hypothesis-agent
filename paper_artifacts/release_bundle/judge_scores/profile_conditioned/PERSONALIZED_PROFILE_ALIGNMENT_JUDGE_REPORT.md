# Personalized Profile Alignment Judge Report

## Setup

- scoring mode: `personalized_formulation_10pt`
- pairwise comparison: disabled
- weighted composite: not computed
- external search: not used

## Profile Context Source

- Profile context cards were built from sanitized profile summaries and paper-facing generated artifacts.
- Profile names were visible to the judge; method labels were hidden.

## Candidates Scored

- geoffrey_hinton:family:01 / Geoffrey Hinton: Characterizing the Convergence Failure Regime of Stochastic Gradient Approximations in Deep Generative Models
- michael_i_jordan:family:01 / Michael I. Jordan: Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices
- michael_i_jordan:family:02 / Michael I. Jordan: Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation
- yann_lecun:family:01 / Yann LeCun: Characterizing the Fundamental Limits of Partition Function Approximation in High-Dimensional EBMs

## Calibration Status

- Calibration passed: yes

## Results

- Geoffrey Hinton / Characterizing the Convergence Failure Regime of Stochastic Gradient Approximations in Deep Generative Models: formulation=5.6667, personalization=7.1667, alignment=8.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=reported_profile_result
- Michael I. Jordan / Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices: formulation=6.0, personalization=6.3333, alignment=6.5, action=PROMISING_NEEDS_REFINEMENT, paper_use=reported_profile_result
- Michael I. Jordan / Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation: formulation=6.0, personalization=7.0, alignment=8.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=reported_profile_result
- Yann LeCun / Characterizing the Fundamental Limits of Partition Function Approximation in High-Dimensional EBMs: formulation=6.1667, personalization=5.3333, alignment=7.0, action=PROMISING_NEEDS_REFINEMENT, paper_use=reported_profile_result

## Paper-Use Recommendation

- Michael I. Jordan: Identifiability Boundaries of Filtering-Clustering Under Rank-Deficient Design Matrices (reported_profile_result)
- Michael I. Jordan: Characterizing Hierarchical Identifiability Limits in Variational Protein Annotation (reported_profile_result)

## Caveats

- The public profile set contains 3 scored profiles producing 4 candidates.
- Profile alignment was judged only from provided profile cards; no external profile knowledge or novelty search was used.
- Use the per-candidate `n_judges` field when quoting means.
