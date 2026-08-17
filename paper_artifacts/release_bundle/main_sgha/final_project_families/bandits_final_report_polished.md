# paper/sgha/domain_batch_downstream_full_comparison_20260713_033820/runs/bandits — Research Direction Menu

> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides evidence and caveats, but it is not a final scientific judgment. Users should inspect the source papers before deciding what to pursue.

## Executive Summary
- corpus size: **250** papers (seed + retrieved)
- seed papers: **0** | retrieved papers: **250**
- verification-reviewed gaps: **13** | verification-passed gaps: **6** | verification-failed gaps: **7**
- direct formulations: **6**
- direct formulation input: **verification_passed_gaps** | verification-passed only: **True**
- verification gate: **enabled=True**, mode=**survival_score**, threshold=**0.6**
- ambition variants generated: **18**
- critic-passing formulations: **4** | selected formulations: **4**
- final project families: **3**
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
1. **Most directly aligned directions** — Characterizing Identifiability Limits of Structured Bandits Under Piecewise Non-Stationarity, Characterizing the Fundamental Limits of Robust Bayesian Exploration Under Non-Lipschitz Dynamics, Characterizing the Non-Convex Failure Regime of Diffusion-Based Contextual Bandits
2. **Strong but source-sensitive directions** — (none)
3. **Caveat-heavy or adjacent directions** — (none)

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
### 1. Characterizing Identifiability Limits of Structured Bandits Under Piecewise Non-Stationarity
- representative formulation: `var:05` | member formulations: ['var:05', 'var:06']
- source verification-passed gaps: ['gap:ba210076fbccfacb'] | source direct formulations: ['direct:02']

**Problem statement.** Current robust bandit algorithms for structured action sets, such as Network Lasso, rely on the i.i.d. assumption of context generation. This assumption fails in environments with piecewise constant non-stationarity, leading to unbounded regret and failure in identifying optimal arms. The fundamental question is not merely how to fix a specific algorithm, but whether the network structure itself allows for consistent learning under such distributional shifts, or if a fundamental identifiability barrier exists.

**Proposal-style abstract.** This project studies the fundamental limits of learning in contextual bandits with network-structured action sets when the underlying data distribution undergoes piecewise constant shifts. The central question is whether the structural constraints imposed by network regularization are sufficient to guarantee consistent policy identification in non-stationary regimes, or if the combination of structural sparsity and temporal drift creates an inherent identifiability gap. A successful outcome would characterize the precise boundary between learnable and unlearnable regimes for this problem class, providing necessary and sufficient conditions for robustness that are independent of any specific algorithmic implementation. This work moves beyond validating a single method to establishing a theoretical framework for the viability of structured learning under non-stationarity.

- core research object / problem class: Contextual Bandits with Network-Structured Action Sets — Robust Statistical Learning in Non-Stationary Environments with Structural Constraints
- assumption shift: Removal of the i.i.d. assumption; characterization of the minimal requirements for consistency without it
- failure boundary / mechanism: The boundary between regimes where network structure aids robustness versus regimes where structural constraints amplify non-stationarity errors, leading to impossibility
- possible contribution targets — theorem: Necessary and sufficient conditions for identifiability of the optimal arm class under piecewise constant non-stationarity with network constraints | algorithm: — | empirical: —
- first supporting papers to inspect: ['openreview:KWUFlIMn8A', 'openreview:WxW4nZMD3D']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant successfully elevates the specific failure of Network Lasso into a fundamental question about identifiability limits for the entire class of structured bandits under non-stationarity, moving beyond algorithmic repair to theoretical impossibility boundaries.
- main risk: Proving impossibility results requires rigorous mathematical machinery that may be technically demanding and susceptible to counter-examples if the structural assumptions are not precisely defined.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:KWUFlIMn8A, openreview:WxW4nZMD3D) to confirm the gap is real and not already addressed. Confirm that the target — The boundary between regimes where network structure aids robustness versus regimes where structural constraints amplify non-stationarity errors, leading to impossibility — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** We seek to determine if it is theoretically possible to learn the optimal strategy in a sequential decision-making problem where actions are constrained by a network structure, given that the environment's underlying rules change abruptly over time in a piecewise constant manner. Specifically, we ask if the network constraints provide enough information to overcome the lack of independent and identically distributed (i.i.d.) data, or if a fundamental barrier prevents consistent identification of the best action.

**Formal problem statement.** Let $\mathcal{A}$ be a set of actions constrained by a network structure $\mathcal{G}$. Let $\mathcal{D}_t$ denote the distribution of contexts at time $t$. The environment exhibits piecewise constant non-stationarity, meaning $\mathcal{D}_t = \mathcal{D}_{k}$ for $t \in [t_k, t_{k+1})$. The question is whether there exists a sequence of policies $\pi_t$ such that the regret $R_T$ grows sublinearly with time $T$ (or equivalently, whether the optimal arm class is identifiable) solely based on the structural constraints of $\mathcal{G}$, without assuming $\mathcal{D}_t$ is i.i.d. across time.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{A}$ | Set of available actions | set | introduced for formalization |
| $\mathcal{G}$ | Network structure constraining action sets | set | introduced for formalization |
| $\mathcal{D}_t$ | Distribution of contexts at time $t$ | distribution | from evidence |
| $t_k$ | Time points where the distribution shifts | scalar | introduced for formalization |
| $\pi_t$ | Policy at time $t$ | function | introduced for formalization |
| $R_T$ | Cumulative regret up to time $T$ | scalar | from evidence |

- entities: ['Contextual Bandit with Network-Structured Action Sets', 'Piecewise Constant Non-Stationary Environment', 'Network Constraints', 'Identifiability Regime']
- feedback or observation model: The feedback model is unclear; the evidence mentions 'unbounded regret' and 'failure in identifying optimal arms' but does not specify the reward function form or the exact mechanism of the distribution shift beyond 'piecewise constant'.
- decision variables / outputs: The output is a theoretical characterization (necessary and sufficient conditions) regarding the existence of a consistent learning policy.
- objective: Characterize the necessary and sufficient conditions for consistent learning (identifiability) in network-structured bandits under piecewise constant non-stationarity.
- constraints: The action selection must respect the network structure $\mathcal{G}$.
- success criterion: Establishing a precise boundary between regimes where network structure aids robustness versus regimes where structural constraints amplify non-stationarity errors, leading to impossibility.

**Assumptions.**
- Network Structure Constraint (kept): Actions are not chosen freely but are constrained by a specific network topology.
- Piecewise Constant Non-Stationarity (kept): The underlying data distribution changes abruptly at specific time points and remains constant between them.
- i.i.d. Context Generation (removed): The assumption that contexts are generated independently and identically distributed over time.
- Existence of Consistent Learning (questioned): The hypothesis that consistent learning might be possible under these conditions.

**Open question.** Does the combination of structural sparsity (network constraints) and temporal drift (piecewise non-stationarity) create an inherent identifiability gap that makes consistent learning impossible, regardless of the algorithm used?

- possible theorem target: Necessary and sufficient conditions for identifiability of the optimal arm class under piecewise constant non-stationarity with network constraints.
- possible algorithm target: —
- possible empirical / benchmark target: —
- evaluation protocol: Theoretical derivation of bounds or impossibility proofs based on the defined structural and temporal constraints.
- formalization confidence: medium | requires human definition: True
- formalization risk: Some terms may remain under-specified until the source papers are read.

**Ambiguity flags / terms needing definition.**
- Network Structure: The specific type of network (e.g., graph topology, sparsity pattern) and how it mathematically constrains the action set are not explicitly defined in the evidence. User must define: The precise mathematical definition of the action set $\mathcal{A}$ and the constraint function imposed by $\mathcal{G}$.
- Piecewise Constant Non-Stationarity: The evidence does not specify the magnitude of the shift, the frequency of shifts, or the relationship between the shift and the network structure. User must define: The formal definition of the shift function and the bounds on the distributional change.
- Feedback Model: The specific reward function and the exact nature of the observation process are not detailed. User must define: The reward function $r(a, c)$ and the observation distribution.
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.
### 2. Characterizing the Fundamental Limits of Robust Bayesian Exploration Under Non-Lipschitz Dynamics
- representative formulation: `var:03` | member formulations: ['var:03']
- source verification-passed gaps: ['gap:ef3ea35e2e975d35'] | source direct formulations: ['direct:01']

**Problem statement.** Standard Bayesian exploration mechanisms, such as Thompson Sampling, fundamentally rely on the stability of posterior updates, which is guaranteed by Lipschitz continuity and Gaussian priors. In environments where reward dynamics are non-Lipschitz or subject to adversarial poisoning, these stability guarantees collapse, rendering standard Bayesian updates arbitrary and ineffective. The central challenge is not merely to design a robust algorithm, but to characterize the precise boundary where Bayesian exploration becomes information-theoretically impossible or fundamentally unstable under such violations.

**Proposal-style abstract.** This project studies the fundamental limits of Bayesian exploration mechanisms when core regularity assumptions, specifically Lipschitz continuity and Gaussian prior stability, are systematically violated by non-Lipschitz dynamics or adversarial perturbations. The central question is to identify the phase transition between regimes where robust identification is possible and those where it is information-theoretically impossible, regardless of the specific algorithmic instantiation. A successful outcome would establish a rigorous impossibility boundary characterizing the failure regime of posterior-based exploration under distributional shifts that break standard statistical assumptions. This work proposes a new evaluation framework for the identifiability of optimal actions in non-stable environments, moving beyond the validation of specific robust heuristics to define the theoretical capacity of the Bayesian paradigm itself under adversarial and non-smooth conditions.

- core research object / problem class: Contextual bandits with partial feedback under adversarial reward poisoning and non-Lipschitz dynamics — Fundamental limits of Bayesian inference and exploration under distributional instability
- assumption shift: Removal of the Lipschitz continuity assumption and the implicit stability of Gaussian posteriors
- failure boundary / mechanism: The phase transition between identifiable and unidentifiable regimes in non-smooth, adversarially perturbed environments
- possible contribution targets — theorem: Establish a lower bound on the minimax regret or a necessary condition for identifiability in non-Lipschitz bandit settings | algorithm: — | empirical: —
- first supporting papers to inspect: ['openreview:0Fi3u4RCyU', 'openreview:0TUMAAb3of', 'openreview:0bcUyy2vdY', 'openreview:0oWGVvC6oq', 'openreview:5q4U5gnU1g']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: moderate | topic alignment: strong
- independent-critic note: The variant successfully shifts the scientific object from designing a specific robust algorithm to characterizing fundamental information-theoretic limits, which is a distinct and higher-level contribution than the source's algorithmic modification. The source evidence regarding the collapse of stability guarantees under non-Lipschitz dynamics provides strong grounding for investigating these impossibility boundaries.
- main risk: The mathematical complexity of defining and proving boundaries for non-Lipschitz dynamics may be intractable without simplifying assumptions that defeat the purpose.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:0Fi3u4RCyU, openreview:0TUMAAb3of, openreview:0bcUyy2vdY) to confirm the gap is real and not already addressed. Confirm that the target — The phase transition between identifiable and unidentifiable regimes in non-smooth, adversarially perturbed environments — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Standard Bayesian exploration methods fail when the environment's reward dynamics are non-smooth (non-Lipschitz) or when rewards are adversarially poisoned. The goal is to mathematically define the exact boundary where it becomes information-theoretically impossible to identify the optimal action, rather than just designing a robust algorithm.

**Formal problem statement.** Let $\mathcal{A}$ be the set of actions and $\mathcal{X}$ be the context space. We consider a sequence of rounds $t=1, \dots, T$. At each round, a context $x_t \in \mathcal{X}$ is drawn. The agent selects an action $a_t \in \mathcal{A}$. The reward $r_t$ is generated by a function $f: \mathcal{X} \times \mathcal{A} \to \mathbb{R}$ that is non-Lipschitz continuous, potentially perturbed by an adversary $\mathcal{D}$ (adversarial poisoning). Standard Bayesian updates rely on the stability of the posterior $\pi_t(a|x_t)$, which is guaranteed under Lipschitz continuity and Gaussian priors. We seek to characterize the phase transition between regimes where the optimal action $a^* = \arg\max_a \mathbb{E}[f(x, a)]$ is identifiable and regimes where it is information-theoretically unidentifiable due to the violation of regularity assumptions.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $x_t$ | Context observed at round t | vector | from evidence |
| $a_t$ | Action selected by the agent at round t | scalar | from evidence |
| $r_t$ | Observed reward at round t (potentially poisoned) | scalar | from evidence |
| $f$ | Underlying reward dynamics function | function | from evidence |
| $\pi_t$ | Posterior belief distribution over actions | distribution | from evidence |
| $\mathcal{D}$ | Adversarial mechanism or poisoning process | process | from evidence |
| $R_T$ | Cumulative regret over T rounds | scalar | introduced for formalization |
| $\mathcal{L}$ | Lipschitz constant (assumed to be 0 or undefined) | scalar | introduced for formalization |

- entities: ['Context space $\\mathcal{X}$', 'Action space $\\mathcal{A}$', 'Reward function $f$ (non-Lipschitz)', 'Adversarial perturbation process $\\mathcal{D}$', 'Posterior distribution $\\pi_t$', 'Optimal action $a^*$', 'Minimax regret $R_T$ or Identifiability condition $\\mathcal{I}$']
- feedback or observation model: Partial feedback: The agent observes the reward only for the selected action $a_t$. The measurement model is corrupted by non-Lipschitz dynamics and adversarial perturbations, breaking the standard Gaussian conjugacy required for stable Bayesian updates.
- decision variables / outputs: The agent's policy $\pi(a|x)$ determines the action selection. The theoretical output is a characterization of the set of functions $f$ and adversaries $\mathcal{D}$ for which $a^*$ is unidentifiable.
- objective: Establish a lower bound on the minimax regret $R_T$ or a necessary condition for identifiability in settings where $f$ is non-Lipschitz and $\mathcal{D}$ is adversarial.
- constraints: The environment dynamics $f$ must be non-Lipschitz. The adversary $\mathcal{D}$ may perturb rewards within a bounded or unbounded set (depending on the specific variant of poisoning).
- success criterion: Derivation of a phase transition threshold (e.g., a bound on the magnitude of non-Lipschitz discontinuity or adversarial budget) below which identification is possible and above which it is impossible.

**Assumptions.**
- Lipschitz Continuity (removed): The standard assumption that reward functions are Lipschitz continuous, ensuring stable posterior updates.
- Gaussian Prior Stability (removed): The assumption that Gaussian priors maintain stability under updates, which relies on Lipschitz dynamics.
- Adversarial Poisoning (kept): The presence of an adversary that can manipulate reward observations.

**Open question.** What is the precise mathematical boundary (in terms of the modulus of continuity or adversarial budget) separating the regime where Bayesian exploration can robustly identify the optimal action from the regime where it is information-theoretically impossible?

- possible theorem target: A lower bound on the minimax regret or a necessary condition for identifiability in non-Lipschitz bandit settings.
- possible algorithm target: None specified; the focus is on fundamental limits.
- possible empirical / benchmark target: None specified; the focus is on theoretical characterization.
- evaluation protocol: Theoretical proof of impossibility results or lower bounds on regret under the specified violation of assumptions.
- formalization confidence: medium | requires human definition: True
- formalization risk: Some terms may remain under-specified until the source papers are read.

**Ambiguity flags / terms needing definition.**
- Non-Lipschitz dynamics: The term covers a wide range of discontinuities and singularities; the specific class of functions (e.g., Hölder continuous with $\alpha < 1$, step functions, etc.) is not defined. User must define: The specific regularity class or modulus of continuity that defines the 'non-Lipschitz' regime.
- Adversarial poisoning: The strength and budget of the adversary are not specified. User must define: Whether the adversary has full knowledge of the algorithm, a budget on total perturbation, or constraints on the perturbation magnitude.
- Information-theoretically impossible: Requires a formal definition of the information-theoretic metric (e.g., Fano's inequality application, mutual information bounds). User must define: The specific information-theoretic criterion used to declare unidentifiability.
- dynamic: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
### 3. Characterizing the Non-Convex Failure Regime of Diffusion-Based Contextual Bandits
- representative formulation: `var:09` | member formulations: ['var:09']
- source verification-passed gaps: ['gap:5b3e0ad02d0b1944'] | source direct formulations: ['direct:03']

**Problem statement.** Diffusion-based contextual bandit algorithms like dTS rely on Gaussian posterior approximations derived from linear link functions. This assumption breaks down when score functions are non-linear, causing the posterior to diverge from the true reward distribution. The central problem is not merely fixing dTS for non-linearities, but characterizing the fundamental boundary where diffusion-based inference fails to identify optimal policies due to non-convexity in the score landscape.

**Proposal-style abstract.** This project studies the fundamental limits of diffusion-based inference in sequential decision-making when the underlying reward structure violates linearity. The central question is identifying the precise geometric and topological conditions under which the Gaussian approximation inherent to diffusion models becomes a catastrophic failure mode, leading to unbounded regret. A successful outcome would establish a rigorous impossibility boundary defining the class of non-linear score functions for which no diffusion-based algorithm can guarantee sublinear regret without explicit non-linearity correction. This work moves beyond algorithmic patching to define the structural prerequisites for the validity of diffusion priors in bandit settings.

- core research object / problem class: Contextual Bandits with Non-Linear Score Functions — Bayesian Inference in Non-Convex High-Dimensional Spaces under Sequential Constraints
- assumption shift: Removal of the linear link function assumption to expose the non-convex failure regime
- failure boundary / mechanism: The phase transition between regimes where Gaussian approximation yields valid regret bounds versus regimes where it leads to systematic identification failure
- possible contribution targets — theorem: A necessary condition on the curvature and convexity of the score function class required for diffusion-based posterior concentration | algorithm: — | empirical: —
- first supporting papers to inspect: ['openreview:GGAG3wFEKv', 'openreview:nEnazjpwOx']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts the objective from fixing a specific algorithm (dTS) to characterizing a fundamental phase transition in a broader class of diffusion-based inference, moving beyond simple validation to theoretical boundary analysis.
- main risk: The boundary might be too narrow or trivial if non-linearities are mild; the result could be that 'only linear works' without interesting intermediate regimes.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:GGAG3wFEKv, openreview:nEnazjpwOx) to confirm the gap is real and not already addressed. Confirm that the target — The phase transition between regimes where Gaussian approximation yields valid regret bounds versus regimes where it leads to systematic identification failure — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Diffusion-based algorithms for contextual bandits (like dTS) assume a linear relationship between context features and rewards to maintain tractable Gaussian posterior approximations. When the true reward structure is non-linear, these approximations fail, potentially leading to unbounded regret. The problem is to rigorously characterize the geometric and topological boundary separating regimes where these algorithms succeed from those where they fundamentally fail to identify optimal policies.

**Formal problem statement.** Let $\mathcal{F}$ be a class of score functions mapping contexts to rewards. The problem is to determine the necessary conditions on the curvature and convexity of functions in $\mathcal{F}$ such that diffusion-based inference (relying on Gaussian posterior approximations) guarantees sublinear regret. Specifically, we seek to identify the phase transition boundary where the Gaussian approximation diverges from the true reward distribution due to non-convexity in the score landscape, rendering the algorithm incapable of identifying the optimal policy.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{F}$ | Class of score functions mapping contexts to rewards | set | introduced for formalization |
| $\pi_{diff}$ | Diffusion-based inference algorithm relying on Gaussian approximation | process | introduced for formalization |
| $\mathcal{R}_{true}$ | True reward distribution induced by the score function | distribution | introduced for formalization |
| $\mathcal{R}_{approx}$ | Approximated reward distribution derived from Gaussian posterior | distribution | introduced for formalization |
| $\mathcal{L}(f)$ | Score landscape associated with score function $f$ | function | introduced for formalization |
| $\mathcal{R}_T$ | Cumulative regret over time horizon $T$ | scalar | introduced for formalization |

- entities: ['Contextual Bandit Environment', 'Score Function Class', 'Diffusion-Based Inference Algorithm', 'Gaussian Posterior Approximation', 'Regret Metric', 'Score Landscape']
- feedback or observation model: The feedback is the realized reward $r_t = f(x_t)$ where $f \in \mathcal{F}$. The measurement of success is the cumulative regret $\mathcal{R}_T$. The validity of the inference is measured by the divergence between $\mathcal{R}_{true}$ and $\mathcal{R}_{approx}$.
- decision variables / outputs: The algorithm outputs a sequence of actions $a_t$ based on the posterior approximation. The theoretical output of interest is the characterization of the set $\mathcal{F}_{valid} \subseteq \mathcal{F}$.
- objective: Characterize the boundary conditions on $\mathcal{F}$ such that $\lim_{T \to \infty} \mathcal{R}_T / T = 0$ holds for $\pi_{diff}$, and identify the conditions under which this limit is non-zero or unbounded due to non-convexity.
- constraints: The algorithm $\pi_{diff}$ is constrained to use Gaussian posterior approximations derived from linear link functions.
- success criterion: Establishing a rigorous impossibility boundary defining the class of non-linear score functions for which no diffusion-based algorithm can guarantee sublinear regret without explicit non-linearity correction.

**Assumptions.**
- Linear Link Function Assumption (relaxed): The standard dTS algorithm assumes a linear relationship between context and score to derive tractable bounds.
- Gaussian Posterior Approximation (kept): The inference mechanism relies on approximating the posterior with a Gaussian distribution.
- Sequential Decision Constraints (kept): The problem occurs in a sequential setting where actions affect future information.

**Open question.** What are the precise geometric and topological conditions on the score function class $\mathcal{F}$ that constitute the phase transition between valid regret bounds and systematic identification failure?

- possible theorem target: A necessary condition on the curvature and convexity of the score function class required for diffusion-based posterior concentration.
- possible algorithm target: —
- possible empirical / benchmark target: —
- evaluation protocol: Theoretical derivation of conditions on $\mathcal{F}$; potential experimental validation by testing algorithms on functions near the hypothesized boundary.
- formalization confidence: medium | requires human definition: True
- formalization risk: The boundary might be too narrow or trivial if non-linearities are mild; the result could be that 'only linear works' without interesting intermediate regimes.

**Ambiguity flags / terms needing definition.**
- Non-convexity in the score landscape: The specific definition of non-convexity (e.g., non-convex loss, non-convex domain, or non-convex posterior geometry) is not explicitly defined in the source evidence. User must define: The precise mathematical definition of the non-convexity that causes the failure.
- Systematic identification failure: The threshold for 'failure' (e.g., linear regret vs. exponential regret vs. divergence) is not quantified. User must define: The specific regret growth rate that defines the failure regime.
- failure: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.

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
