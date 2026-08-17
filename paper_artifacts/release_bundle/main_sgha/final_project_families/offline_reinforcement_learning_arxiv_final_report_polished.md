# paper/sgha/domain_batch_two_more_topics_comparison_20260714_022034/runs/offline_reinforcement_learning_arxiv — Research Direction Menu

> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides evidence and caveats, but it is not a final scientific judgment. Users should inspect the source papers before deciding what to pursue.

## Executive Summary
- corpus size: **250** papers (seed + retrieved)
- seed papers: **0** | retrieved papers: **250**
- verification-reviewed gaps: **8** | verification-passed gaps: **2** | verification-failed gaps: **6**
- direct formulations: **2**
- direct formulation input: **verification_passed_gaps** | verification-passed only: **True**
- verification gate: **enabled=True**, mode=**survival_score**, threshold=**0.6**
- ambition variants generated: **6**
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
1. **Most directly aligned directions** — Characterizing the Failure Regime of Q-Learning in Offline RL via Distributional Shift
2. **Strong but source-sensitive directions** — (none)
3. **Caveat-heavy or adjacent directions** — (none)

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
### 1. Characterizing the Failure Regime of Q-Learning in Offline RL via Distributional Shift
- representative formulation: `var:01` | member formulations: ['var:01']
- source verification-passed gaps: ['gap:e197e76f293f8374'] | source direct formulations: ['direct:01']

**Problem statement.** Existing literature treats Q-learning as a monolithic baseline in offline reinforcement learning, failing to distinguish between its successes and catastrophic failures across diverse data distributions. This lack of granular empirical validation obscures the specific structural conditions under which Q-learning's implicit regularization breaks down. Consequently, the field lacks a standardized understanding of the boundary between safe exploration and distributional collapse in offline settings.

**Proposal-style abstract.** This project studies the fundamental failure regimes of Q-learning within the offline reinforcement learning setting by moving beyond binary success/failure metrics. The central question is to characterize the precise distributional shift conditions that trigger catastrophic overestimation in Q-learning algorithms. A successful outcome would establish a rigorous benchmark suite that maps algorithmic performance to specific statistical properties of the offline data, such as support mismatch or reward density variance. This work aims to define the boundary where Q-learning transitions from a viable baseline to a source of severe bias, providing a constructive explanation for its instability rather than merely reporting isolated performance drops.

- core research object / problem class: Offline Reinforcement Learning — The problem of distributional shift-induced instability in model-free offline learning algorithms
- assumption shift: Relaxation of the implicit assumption that standard Q-learning is robust to arbitrary offline data distributions
- failure boundary / mechanism: The boundary condition between stable Q-learning convergence and catastrophic overestimation driven by support mismatch
- possible contribution targets — theorem: Characterization of the support mismatch threshold triggering Q-learning divergence | algorithm: — | empirical: A multi-dataset benchmark suite quantifying Q-learning failure modes across varying distributional shifts
- first supporting papers to inspect: ['2005.01643v3', '2305.13804v2', '2308.11336v1', '2310.00678v1', '2402.05876v1']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant successfully reframes the generic 'sparse evaluation' gap into a specific scientific object (the failure regime boundary) and a broader problem class (distributional shift), moving beyond mere relabeling to define a distinct investigative scope.
- main risk: Difficulty in isolating specific distributional shift metrics that causally lead to failure without confounding factors.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2005.01643v3, 2305.13804v2, 2308.11336v1) to confirm the gap is real and not already addressed. Confirm that the target — The boundary condition between stable Q-learning convergence and catastrophic overestimation driven by support mismatch — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** In offline reinforcement learning, Q-learning is often treated as a robust baseline, yet it frequently fails catastrophically when the data distribution differs significantly from the training support. The problem is to rigorously define the specific conditions of distributional shift (e.g., support mismatch) that cause this failure, and to create a benchmark suite that maps these conditions to algorithmic performance.

**Formal problem statement.** Let D be a dataset of transitions sampled from an unknown distribution D_0. Let Q be a Q-function estimator initialized to zero. The problem is to characterize the set of distributions D_0 such that the limit of Q as iterations approach infinity diverges to infinity (catastrophic overestimation) or converges to a suboptimal value, specifically identifying the threshold of support mismatch between D_0 and the support of the behavior policy that triggers this instability.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| D | The finite set of transitions available in the offline dataset | set | introduced for formalization |
| D_0 | The true probability distribution generating the offline data | distribution | introduced for formalization |
| Q | The Q-function value estimate produced by the algorithm | function | introduced for formalization |
| S_pi | The support of the behavior policy used to collect data | set | introduced for formalization |
| S_D | The support of the true data distribution D_0 | set | introduced for formalization |
| delta | A metric quantifying the distance or mismatch between S_pi and S_D | scalar | introduced for formalization |
| theta | The threshold value of delta above which Q-learning exhibits catastrophic failure | scalar | introduced for formalization |

- entities: ['Offline dataset D', 'True transition distribution D_0', 'Q-learning estimator Q', 'Behavior policy support S_pi', 'Target support S_D', 'Support mismatch metric delta']
- feedback or observation model: The feedback is the final value of Q(s,a) for states (s,a) in the support of D_0. The measurement of success is the convergence of Q to the optimal Q* or its divergence to infinity.
- decision variables / outputs: The output is the characterization of the failure boundary (theta) and the empirical mapping of delta to performance metrics.
- objective: To identify the critical threshold theta such that for all delta > theta, the algorithm Q diverges or fails to converge to the optimal policy, and for delta < theta, Q converges stably.
- constraints: The analysis must be performed within the offline setting where no new data can be collected after D is observed.
- success criterion: A formal definition of the failure regime boundary and a validated benchmark suite demonstrating the correlation between delta and Q-learning performance.

**Assumptions.**
- Standard Q-learning update rule (kept): The algorithm follows the standard Bellman update using the offline dataset.
- Existence of a failure boundary (relaxed): There exists a specific structural condition (support mismatch) that separates stable convergence from catastrophic failure.
- Robustness to arbitrary distributions (questioned): The implicit assumption that Q-learning is robust to arbitrary offline data distributions is questioned.

**Open question.** What is the precise mathematical form of the support mismatch metric delta that causally triggers the divergence of Q-learning in offline settings?

- possible theorem target: A characterization of the support mismatch threshold triggering Q-learning divergence.
- possible algorithm target: None specified; the focus is on characterization rather than a new algorithm.
- possible empirical / benchmark target: A multi-dataset benchmark suite quantifying Q-learning failure modes across varying distributional shifts.
- evaluation protocol: The problem is evaluated by constructing a suite of synthetic and real-world datasets with controlled variations in support mismatch and measuring the resulting Q-function values to validate the proposed threshold.
- formalization confidence: medium | requires human definition: True
- formalization risk: Difficulty in isolating specific distributional shift metrics that causally lead to failure without confounding factors.

**Ambiguity flags / terms needing definition.**
- Catastrophic overestimation: The term implies divergence to infinity but could also refer to severe bias without divergence; the exact mathematical definition of 'catastrophic' is not provided. User must define: Define the specific metric or threshold that constitutes 'catastrophic' failure (e.g., value exceeding a safety bound or diverging to infinity).
- Support mismatch: While intuitively understood as the difference between behavior and data supports, the specific metric (e.g., KL divergence, set difference measure) is not defined. User must define: Specify the mathematical metric used to quantify the distance between the behavior policy support and the data distribution support.
- mismatch: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.

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
