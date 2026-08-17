# paper/sgha/domain_batch_downstream_full_comparison_20260713_033820/runs/reasoning_models_test_time_compute — Research Direction Menu

> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides evidence and caveats, but it is not a final scientific judgment. Users should inspect the source papers before deciding what to pursue.

## Executive Summary
- corpus size: **250** papers (seed + retrieved)
- seed papers: **0** | retrieved papers: **250**
- verification-reviewed gaps: **12** | verification-passed gaps: **7** | verification-failed gaps: **5**
- direct formulations: **7**
- direct formulation input: **verification_passed_gaps** | verification-passed only: **True**
- verification gate: **enabled=True**, mode=**survival_score**, threshold=**0.6**
- ambition variants generated: **21**
- critic-passing formulations: **1** | selected formulations: **1**
- final project families: **1**
- generator model: **Qwen/Qwen3.5-9B** | independent-critic model: **Qwen/Qwen3.5-9B**
- final family consolidation: **deterministic (no LLM)**


This is a neutral research menu: candidate directions with their evidence and caveats, to help you
decide what to read and pursue. It does not rank-order winners or prescribe a single answer.

## How This Report Was Generated
1. **Verification-passed gaps** were used for direct formulation: reviewed gaps that passed the configured support/skeptic/feasibility/mechanism/critic gate.
2. **Direct formulation**: one coherent problem per verification-passed gap.
3. **Ambition expansion**: conservative/generalized/bold variants per direct formulation.
4. **Independent critic pass**: a separate judge scored each variant's genuine non-incrementality and flagged inflated ambition.
5. **Soft-cap diversity selection**: a diverse subset selected without deleting critic-approved work.
6. **Strict family consolidation**: variants grouped into project families only on hard anchors, then summarized.
7. **Formal problem formulation**: each project family was stated with variables, observations, assumptions, objectives, targets, and ambiguity flags.
8. **Final neutral rendering** (this report).

No old evolved hypotheses were used; no previous ad-hoc outputs were used; no external search was used;
and **no new hypotheses were generated at report time** — every problem statement and abstract is carried
verbatim from the formulation records.

## Suggested Inspection Order
1. **Most directly aligned directions** — Characterizing the Identifiability Boundary of Bootstrapped Reasoning under Unverifiable Feedback
2. **Strong but source-sensitive directions** — (none)
3. **Caveat-heavy or adjacent directions** — (none)

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
### 1. Characterizing the Identifiability Boundary of Bootstrapped Reasoning under Unverifiable Feedback
- representative formulation: `var:21` | member formulations: ['var:21']
- source verification-passed gaps: ['gap:53c659644ee3bbbe'] | source direct formulations: ['direct:07']

**Problem statement.** Current self-improvement frameworks like STaR collapse when training data contains non-verifiable responses or negative examples, relying on an idealized assumption of ground-truth availability. This reliance prevents the generalization of learned reasoning strategies to out-of-distribution tasks where verification is impossible or ambiguous. The core failure is not merely a lack of robustness but a fundamental breakdown in the learning signal when the verifier itself is absent or unreliable.

**Proposal-style abstract.** This project studies the theoretical limits of bootstrapped reasoning mechanisms when the assumption of verifiable ground truth is relaxed. The central question is identifying the precise boundary conditions under which self-improvement algorithms fail to converge or learn spurious patterns due to unverifiable feedback. A successful outcome would characterize the identifiability regime of reasoning bootstrapping, distinguishing between settings where robust learning is possible versus where it is fundamentally impossible without external verification. This work proposes a new evaluation class for reasoning methods that explicitly tests performance under unverifiable feedback regimes, moving beyond simple robustness checks to define the structural requirements for self-correction.

- core research object / problem class: LLM reasoning bootstrapping with mixed verifiable and non-verifiable few-shot examples including negative samples — Identifiability and convergence of self-supervised reasoning loops under partial observability
- assumption shift: Relaxing the assumption of perfect verifiability to analyze learning under unverifiable feedback
- failure boundary / mechanism: The boundary between convergent bootstrapping and spurious pattern formation when verification is impossible
- possible contribution targets — theorem: Identify the necessary conditions on the verifier function for the bootstrapping process to converge to a correct reasoning policy in the absence of ground truth | algorithm: — | empirical: —
- first supporting papers to inspect: ['openreview:4Po8d9GAfQ', 'openreview:77gQUdQhE7', 'openreview:P6dwZJpJ4m', 'openreview:YUYJsHOf3c']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: moderate | topic alignment: strong
- independent-critic note: The variant successfully elevates the specific STaR robustness gap into a general theoretical problem regarding identifiability under unverifiable feedback, moving beyond mere method evaluation to a fundamental boundary analysis supported by the source evidence.
- main risk: Proving impossibility results requires rigorous formalization of 'verifiability' which may be ambiguous in LLM contexts
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:4Po8d9GAfQ, openreview:77gQUdQhE7, openreview:P6dwZJpJ4m) to confirm the gap is real and not already addressed. Confirm that the target — The boundary between convergent bootstrapping and spurious pattern formation when verification is impossible — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Self-improving reasoning systems (like STaR) fail when they encounter training data containing non-verifiable responses or negative examples because they rely on an assumption that all feedback is ground-truth correct. The problem is to define the precise conditions under which these systems can still learn correctly without external verification, or to prove that learning is impossible in the absence of such verification.

**Formal problem statement.** We seek to characterize the identifiability boundary of bootstrapped reasoning mechanisms operating under partial observability. Specifically, we aim to determine the necessary and sufficient conditions on the verifier function and the distribution of training examples such that the self-supervised bootstrapping process converges to a correct reasoning policy, distinguishing between regimes where robust learning is possible and those where it is fundamentally impossible due to unverifiable feedback.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| π | The reasoning policy being learned | process | introduced for formalization |
| V | The verifier function mapping responses to correctness labels | function | from evidence |
| D | The distribution of training examples (queries and responses) | distribution | from evidence |
| y | The feedback signal generated by V | scalar | from evidence |
| y* | The ground truth correctness label | scalar | from evidence |
| P | The target correct reasoning policy | process | introduced for formalization |

- entities: ['Reasoning Policy', 'Verifier Function', 'Training Data Distribution', 'Feedback Signal', 'Ground Truth']
- feedback or observation model: The feedback model is defined by the verifier V. The measurement is y = V(response). The model is partial because y* (ground truth) is not always observable or verifiable by V.
- decision variables / outputs: The policy π is updated based on the feedback y to minimize the divergence from the target policy P.
- objective: To identify the set of conditions C such that if (V, D) satisfies C, then the bootstrapping process converges to P; otherwise, the process converges to a spurious pattern or fails.
- constraints: The system operates without access to y* for a subset of the data distribution.
- success criterion: Convergence of π to P in the limit, or a formal proof of impossibility (non-convergence to P) for specific configurations of V and D.

**Assumptions.**
- Verifiability of Training Data (relaxed): The assumption that all training responses are verifiably correct.
- Existence of Ground Truth (kept): The existence of a unique ground truth y* for every query.
- Convergence of Bootstrapping (questioned): The assumption that the iterative process will eventually stabilize.

**Open question.** What are the necessary conditions on the verifier function V and the data distribution D that guarantee the identifiability of the correct reasoning policy P in the absence of direct ground truth access?

- possible theorem target: A characterization of the identifiability boundary separating convergent bootstrapping from spurious pattern formation.
- possible algorithm target: A modified bootstrapping algorithm robust to unverifiable feedback (not explicitly targeted in the source evidence).
- possible empirical / benchmark target: A new evaluation class for reasoning methods testing performance under unverifiable feedback regimes.
- evaluation protocol: Theoretical analysis of the convergence properties of the bootstrapping loop under varying degrees of verifier reliability and data ambiguity.
- formalization confidence: medium | requires human definition: True
- formalization risk: Proving impossibility results requires rigorous formalization of 'verifiability' which may be ambiguous in LLM contexts.

**Ambiguity flags / terms needing definition.**
- Unverifiable Feedback: The term is used to describe both the absence of a verifier and the presence of a verifier that is unreliable or ambiguous. User must define: The precise mathematical definition of 'unverifiable' (e.g., probability of error > 0, or complete absence of V).
- Spurious Pattern: The source evidence mentions learning spurious patterns but does not define the structural properties of these patterns. User must define: A formal definition of what constitutes a 'spurious pattern' in the context of reasoning policies.
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.

## Directions Requiring Extra Source Validation
(none)

## Caveat-Heavy or Adjacent Directions
(none)

## Full Provenance and Artifacts
- direct formulations: `stage7_direct_formulations/direct_formulations.jsonl`
- ambition expansion: `stage8_ambition_expansion/` (variants, critic-passing pool, selected)
- family consolidation: `stage9_family_quality/project_families.json`
- formal problem formulations: `stage10_formal_problem_formulations/formal_problem_formulations.jsonl`
- this report: `final_sgha_family_report/`
- generator + critic: Qwen/Qwen3.5-9B; family consolidation: deterministic (no LLM)

## Limitations
- Novelty / non-incrementality were judged by the generator + an independent critic, **not** by external
  literature verification — some directions may already exist in the literature.
- Evidence grounding is measured against the local corpus only; no external/citation search was performed.
- "Topic alignment" is measured against this run's own declared topic; an adjacent-area direction is
  flagged, not deleted — judge it yourself.
- These are candidate directions, not results. Inspect the cited papers before committing.
