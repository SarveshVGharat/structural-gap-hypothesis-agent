# paper/sgha/domain_batch_downstream_full_comparison_20260713_033820/runs/in_context_learning — Research Direction Menu

> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides evidence and caveats, but it is not a final scientific judgment. Users should inspect the source papers before deciding what to pursue.

## Executive Summary
- corpus size: **250** papers (seed + retrieved)
- seed papers: **0** | retrieved papers: **250**
- verification-reviewed gaps: **16** | verification-passed gaps: **12** | verification-failed gaps: **4**
- direct formulations: **12**
- direct formulation input: **verification_passed_gaps** | verification-passed only: **True**
- verification gate: **enabled=True**, mode=**survival_score**, threshold=**0.6**
- ambition variants generated: **36**
- critic-passing formulations: **4** | selected formulations: **4**
- final project families: **4**
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
1. **Most directly aligned directions** — Characterizing the Depth-Window Phase Transition in Linear Attention Mechanisms, Characterizing the Fundamental Robustness Boundary of Autoregressive and Masked In-Context Learning, Robustness Phase Transitions in In-Context Learning Under Adversarial Feedback
2. **Strong but source-sensitive directions** — Characterizing the Failure Regime of Linear Intervention Methods Under Neural Superposition
3. **Caveat-heavy or adjacent directions** — (none)

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
### 1. Characterizing the Depth-Window Phase Transition in Linear Attention Mechanisms
- representative formulation: `var:27` | member formulations: ['var:27']
- source verification-passed gaps: ['gap:1f032c8842a6a531'] | source direct formulations: ['direct:09']

**Problem statement.** Current empirical studies on Linear Attention mechanisms focus on shallow architectures, leaving the fundamental limits of information propagation in deep networks unquantified. Specifically, it remains unknown if and where the performance degradation occurs as depth increases beyond two layers or when attention windows are fixed, suggesting a potential phase transition rather than a smooth decline. This project aims to map the precise boundary conditions under which Linear Attention fails to support in-context learning, distinguishing between architectural depth limits and window adaptability constraints.

**Proposal-style abstract.** This project studies the fundamental failure regimes of Linear Attention mechanisms in deep architectures, moving beyond shallow empirical validation to characterize a potential phase transition in information propagation. The central question is whether the inability to adapt attention windows in deep networks represents a hard boundary or a gradual degradation dependent on task complexity. A successful outcome would define the critical depth and window size thresholds where Linear Attention becomes provably insufficient for in-context learning, providing a unified explanation for observed performance drops across diverse tasks. This work proposes a systematic evaluation protocol to expose the general failure modes of the Linear Attention class, rather than validating a single method in a specific setting.

- core research object / problem class: Few-shot in-context learning with Linear Attention mechanisms in architectures deeper than two layers — Information propagation limits and capacity constraints in deep transformer-like architectures
- assumption shift: Relaxes the assumption that Linear Attention is universally viable by characterizing the specific structural conditions (depth/window) where it becomes ineffective
- failure boundary / mechanism: The critical depth and window size thresholds where Linear Attention transitions from functional to non-functional in in-context learning tasks
- possible contribution targets — theorem: — | algorithm: — | empirical: Mapping the phase transition boundary between successful and failed in-context learning under depth and window constraints
- first supporting papers to inspect: ['openreview:AC9FsaVIpk', 'openreview:kZbTkpnafR', 'openreview:lYPAYmfQqm', 'openreview:lYongcxaNz', 'openreview:lfxIASyLxB']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant elevates the scope from a generic validation of failure modes to a rigorous characterization of phase transitions and boundary conditions, directly addressing the specific gap regarding depth and window limits identified in the source without merely relabeling the problem.
- main risk: The phase transition may be gradual rather than sharp, complicating the definition of a clear boundary
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:AC9FsaVIpk, openreview:kZbTkpnafR, openreview:lYPAYmfQqm) to confirm the gap is real and not already addressed. Confirm that the target — The critical depth and window size thresholds where Linear Attention transitions from functional to non-functional in in-context learning tasks — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** We need to determine the specific conditions (specifically network depth and attention window size) under which Linear Attention mechanisms fail to support few-shot in-context learning. The goal is to map the boundary between a functional regime and a non-functional regime, characterizing whether the failure is a sharp phase transition or a gradual degradation.

**Formal problem statement.** Let D be the depth of a transformer-like architecture and W be the fixed attention window size. Let P(D, W) be the performance of a Linear Attention mechanism on a class of in-context learning tasks. The problem is to identify the critical thresholds (D*, W*) such that for D > D* or W < W*, the mechanism P(D, W) falls below a functional threshold, thereby characterizing the depth-window phase transition.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| D | Architectural depth of the network | scalar | from evidence |
| W | Fixed attention window size | scalar | from evidence |
| P | Performance metric for in-context learning | scalar | from evidence |
| T | Set of in-context learning tasks | set | from evidence |
| D* | Critical depth threshold | scalar | introduced for formalization |
| W* | Critical window size threshold | scalar | introduced for formalization |

- entities: ['Linear Attention Mechanism', 'Deep Transformer Architecture', 'In-Context Learning Task', 'Information Propagation Metric']
- feedback or observation model: The feedback model is the observed performance P(D, W) on task T, which is currently unquantified regarding the specific boundary conditions for failure.
- decision variables / outputs: The estimated critical thresholds D* and W* that delineate the functional and non-functional regimes.
- objective: To empirically map the boundary conditions (D*, W*) where Linear Attention transitions from supporting to failing in-context learning.
- constraints: The analysis is restricted to Linear Attention mechanisms and architectures deeper than two layers.
- success criterion: A unified characterization of the failure regime that distinguishes between architectural depth limits and window adaptability constraints.

**Assumptions.**
- Phase Transition Existence (questioned): The performance degradation follows a phase transition (sharp boundary) rather than a smooth decline.
- Depth Limitation (kept): Linear Attention fails to adapt attention windows and degrades performance in architectures with depth greater than two layers.
- Window Adaptability (relaxed): The inability to adapt attention windows in deep networks represents a hard boundary or a gradual degradation dependent on task complexity.

**Open question.** Whether the inability to adapt attention windows in deep networks represents a hard boundary or a gradual degradation dependent on task complexity.

- possible theorem target: A possible theorem would characterize the critical depth and window size thresholds where Linear Attention becomes provably insufficient for in-context learning.
- possible algorithm target: A systematic evaluation protocol to expose the general failure modes of the Linear Attention class.
- possible empirical / benchmark target: Mapping the phase transition boundary between successful and failed in-context learning under depth and window constraints.
- evaluation protocol: A systematic evaluation protocol to expose the general failure modes of the Linear Attention class, rather than validating a single method in a specific setting.
- formalization confidence: medium | requires human definition: True
- formalization risk: The phase transition may be gradual rather than sharp, complicating the definition of a clear boundary.

**Ambiguity flags / terms needing definition.**
- Functional vs. Non-functional: The specific performance threshold that defines the transition from functional to non-functional is not explicitly defined in the source evidence. User must define: The quantitative metric or threshold value that constitutes 'failure' in the in-context learning context.
- Task Complexity: The relationship between task complexity and the phase transition is mentioned but not formalized. User must define: The specific definition of task complexity and how it interacts with depth and window constraints.
### 2. Characterizing the Fundamental Robustness Boundary of Autoregressive and Masked In-Context Learning
- representative formulation: `var:12` | member formulations: ['var:12']
- source verification-passed gaps: ['gap:81ede26b259172dd'] | source direct formulations: ['direct:04']

**Problem statement.** Prior research incorrectly assumes that in-context learning (ICL) is unique to causal language models, systematically excluding masked models from robustness analyses. This bias obscures whether the failure modes of ICL under distributional shift are architectural artifacts or universal properties of the in-context mechanism itself. The central problem is establishing the fundamental boundary between architectures that can generalize from context and those that cannot, specifically under adversarial or shifted conditions.

**Proposal-style abstract.** This project studies the fundamental limits of in-context learning by characterizing the robustness failure regimes of both autoregressive and masked language model classes. The central question is whether the exclusion of masked models from robustness literature masks a universal fragility in the ICL mechanism or if architectures possess distinct, irreducible boundaries of generalization. A successful outcome would define a precise boundary condition separating architectures capable of robust few-shot adaptation from those that fail systematically under distributional shift. This work proposes a unified evaluation protocol designed to expose these class-level failure modes rather than validating specific instances. By treating ICL as a mechanism shared across architectural families, the project aims to derive structural constraints on when context-based generalization is possible, moving beyond empirical comparisons of specific models to a theoretical understanding of the ICL capability class.

- core research object / problem class: Few-shot in-context learning evaluation under distributional shift across autoregressive and masked model classes — The fundamental limits of generalization from context in neural sequence models
- assumption shift: Relaxes the assumption that ICL is unique to causal models to treat it as a shared mechanism with potential universal failure modes.
- failure boundary / mechanism: The boundary between architectures that can robustly generalize from context and those that fail systematically under distributional shift
- possible contribution targets — theorem: Structural conditions under which in-context learning fails to generalize under distributional shift for a class of architectures | algorithm: — | empirical: A unified evaluation suite exposing class-level failure modes in ICL robustness
- first supporting papers to inspect: ['openreview:BCA9NMZkLS', 'openreview:Dj9wssUmLn']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant successfully elevates the scope from a specific validation of a misconception to a fundamental characterization of architectural boundaries under distributional shift, moving beyond mere relabeling. While the source evidence supports the existence of the gap, the claim of a 'fundamental boundary' is an ambitious extrapolation that requires rigorous proof beyond the initial verification of the bias.
- main risk: The hypothesis that masked models share identical failure modes may be false, requiring a complex redefinition of the boundary.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:BCA9NMZkLS, openreview:Dj9wssUmLn) to confirm the gap is real and not already addressed. Confirm that the target — The boundary between architectures that can robustly generalize from context and those that fail systematically under distributional shift — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Prior research assumes in-context learning (ICL) is unique to causal (autoregressive) models, excluding masked models from robustness analysis. This project seeks to determine if the failure modes of ICL under distributional shift are specific to architecture or universal to the mechanism. The goal is to define the fundamental boundary separating architectures that can robustly generalize from context from those that fail systematically.

**Formal problem statement.** Let M be the class of neural sequence models partitioned into autoregressive (AR) and masked (MASK) architectures. Let D be a distribution over input contexts and tasks. The problem is to characterize the set of conditions C under which the in-context learning mechanism fails to generalize for a model M in M under a shifted distribution D'. Specifically, we seek to identify if the failure boundary is shared across M (universal fragility) or distinct for subsets of M (architectural artifacts).

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| M_AR | Set of autoregressive language model architectures | set | introduced for formalization |
| M_MASK | Set of masked language model architectures | set | introduced for formalization |
| D | Base distribution over contexts and tasks | distribution | introduced for formalization |
| D' | Shifted or adversarial distribution | distribution | introduced for formalization |
| ICL(M, D) | Performance of model M using in-context learning on distribution D | function | introduced for formalization |
| B | The fundamental robustness boundary separating generalizable from non-generalizable architectures | set | introduced for formalization |

- entities: ['Neural sequence model classes (Autoregressive, Masked)', 'Input contexts and task definitions', 'Distributional shifts (adversarial or natural)', 'In-context learning mechanism', 'Generalization performance metric']
- feedback or observation model: The measurement model is the observed generalization gap between training distribution D and shifted distribution D'. The feedback loop involves comparing failure modes across M_AR and M_MASK to infer the structure of B.
- decision variables / outputs: The identification of the boundary B and the classification of architectures as robust or fragile under shift.
- objective: To derive structural conditions defining the boundary B such that for any M in M, M generalizes under D' if and only if M is in B, and to determine if B = M_AR U M_MASK (universal) or B is a proper subset.
- constraints: Evaluation must be conducted under distributional shift; comparisons must control for task difficulty and context length.
- success criterion: A precise characterization of the failure boundary B that distinguishes between architectural artifacts and universal ICL fragility.

**Assumptions.**
- ICL Mechanism Universality (relaxed): The in-context learning mechanism is a shared property across both autoregressive and masked architectures, despite differences in generation direction.
- Architectural Distinction (kept): Autoregressive and masked models represent distinct classes with potentially different failure modes.

**Open question.** Whether the failure modes of ICL under distributional shift are architectural artifacts specific to autoregressive or masked models, or universal properties of the in-context mechanism itself.

- possible theorem target: Structural conditions under which in-context learning fails to generalize under distributional shift for a class of architectures.
- possible algorithm target: —
- possible empirical / benchmark target: A unified evaluation suite exposing class-level failure modes in ICL robustness.
- evaluation protocol: A unified evaluation protocol designed to expose class-level failure modes rather than validating specific instances, treating ICL as a mechanism shared across architectural families.
- formalization confidence: medium | requires human definition: True
- formalization risk: The hypothesis that masked models share identical failure modes may be false, requiring a complex redefinition of the boundary.

**Ambiguity flags / terms needing definition.**
- Fundamental Robustness Boundary: The term implies a precise mathematical or structural limit, but the evidence suggests this is an ambitious extrapolation requiring rigorous proof. User must define: The specific mathematical or structural definition of the boundary (e.g., capacity constraints, attention patterns, or loss landscape properties).
- Distributional Shift: The evidence mentions 'adversarial or shifted conditions' but does not specify the types of shifts (covariate, concept, or task shift). User must define: The specific nature of the distributional shifts to be tested in the unified evaluation suite.
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
### 3. Robustness Phase Transitions in In-Context Learning Under Adversarial Feedback
- representative formulation: `var:17` | member formulations: ['var:17']
- source verification-passed gaps: ['gap:58c15de0e11db764'] | source direct formulations: ['direct:06']

**Problem statement.** Current empirical studies on in-context learning (ICL) treat noise and counterfactual feedback as static perturbations, failing to characterize how these adversarial conditions interact with prompt length and model capacity to induce catastrophic failure. There is no unified framework to identify the boundary conditions where ICL transitions from robust generalization to systematic hallucination under adversarial data regimes.

**Proposal-style abstract.** This project studies the phase transition boundaries of in-context learning when subjected to noisy annotations and counterfactual feedback. The central question is how the interaction between prompt length, model architecture, and the density of adversarial examples determines the robustness regime of few-shot learners. A successful outcome would establish a generalized failure map that identifies the critical thresholds where theoretical guarantees break down, moving beyond isolated robustness tests to a comprehensive characterization of ICL instability across method families.

- core research object / problem class: In-context learning with few-shot prompting under adversarial data conditions — Robustness and generalization limits of non-parametric learning under adversarial perturbations
- assumption shift: Relaxes the assumption of independent, additive noise to coupled, synergistic adversarial feedback.
- failure boundary / mechanism: The critical threshold where ICL transitions from robust generalization to systematic hallucination under coupled adversarial conditions.
- possible contribution targets — theorem: — | algorithm: — | empirical: A generalized failure map quantifying robustness thresholds across model architectures and prompt lengths.
- first supporting papers to inspect: ['openreview:00uVk06eVK', 'openreview:7H1jbTaOIn', 'openreview:BNAvYSCrLD', 'openreview:CCUrU4A92S', 'openreview:FxLxbJTm7F']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts the scientific object from static noise validation to dynamic phase transitions and synergistic feedback regimes, moving beyond the source's narrow benchmark gap to a fundamental characterization of failure boundaries.
- main risk: High computational cost of evaluating phase transitions across diverse model families and prompt lengths.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (openreview:00uVk06eVK, openreview:7H1jbTaOIn, openreview:BNAvYSCrLD) to confirm the gap is real and not already addressed. Confirm that the target — The critical threshold where ICL transitions from robust generalization to systematic hallucination under coupled adversarial conditions — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Current studies on in-context learning (ICL) treat noise and counterfactual feedback as independent, static disturbances. This project seeks to formalize the problem of identifying the specific boundary conditions where the interaction between prompt length, model capacity, and coupled adversarial feedback causes a phase transition from robust generalization to systematic hallucination.

**Formal problem statement.** Let \( \mathcal{M} \) be a family of in-context learning models parameterized by capacity \( C \). Let \( L \) denote the prompt length. Let \( \mathcal{D}_{adv} \) be a data distribution containing coupled noisy annotations and counterfactual feedback. The problem is to characterize the function \( \Phi: \mathcal{M} \times \mathbb{N} \times \mathcal{D}_{adv} \to \{\text{robust}, \text{hallucination}\} \) that identifies the critical threshold \( (C^*, L^*) \) where the system transitions from robust generalization to systematic failure.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| C | Model capacity parameter | scalar | introduced for formalization |
| L | Prompt length | scalar | from evidence |
| \mathcal{D}_{adv} | Distribution of data with coupled noisy and counterfactual feedback | distribution | from evidence |
| \Phi | Mapping from model, prompt, and data to failure regime | function | introduced for formalization |
| \theta | Model parameters | vector | introduced for formalization |
| y_{true} | Ground truth label | scalar | introduced for formalization |
| y_{obs} | Observed label (potentially noisy or counterfactual) | scalar | introduced for formalization |

- entities: ['In-context learning model \\( \\mathcal{M} \\)', 'Prompt length \\( L \\)', 'Adversarial data distribution \\( \\mathcal{D}_{adv} \\)', 'Robustness regime \\( \\mathcal{R}_{robust} \\)', 'Hallucination regime \\( \\mathcal{R}_{hall} \\)', 'Phase transition boundary \\( \\partial \\mathcal{R} \\)']
- feedback or observation model: The feedback mechanism is defined by the adversarial perturbation process \( \epsilon \) applied to ground truth, resulting in \( y_{obs} = y_{true} + \epsilon \), where \( \epsilon \) exhibits synergistic coupling between noise and counterfactual components.
- decision variables / outputs: The output is the predicted label \( \hat{y} \) generated by the model \( \mathcal{M} \) given the prompt and context.
- objective: To identify the critical thresholds \( C^* \) and \( L^* \) such that for \( C < C^* \) or \( L > L^* \), the probability of systematic hallucination exceeds a failure tolerance \( \delta \).
- constraints: The analysis must account for the coupled nature of adversarial perturbations, relaxing the assumption of independent additive noise.
- success criterion: Construction of a generalized failure map that quantifies robustness thresholds across model architectures and prompt lengths.

**Assumptions.**
- Independent Noise Assumption (relaxed): The assumption that noise and counterfactual feedback are independent, additive perturbations.
- Static Perturbation Assumption (relaxed): The assumption that adversarial conditions are static rather than interacting dynamically with prompt length and capacity.
- Existence of Phase Transition (kept): The assumption that a sharp boundary exists between robust generalization and systematic hallucination.

**Open question.** How the interaction between prompt length, model architecture, and the density of adversarial examples determines the robustness regime of few-shot learners.

- possible theorem target: A characterization of the critical thresholds \( (C^*, L^*) \) defining the phase transition boundary.
- possible algorithm target: A method for estimating the failure boundary from empirical data.
- possible empirical / benchmark target: A generalized failure map quantifying robustness thresholds across model architectures and prompt lengths.
- evaluation protocol: Empirical evaluation across diverse model families and prompt lengths to map the region of systematic hallucination.
- formalization confidence: medium | requires human definition: True
- formalization risk: High computational cost of evaluating phase transitions across diverse model families and prompt lengths; potential ambiguity in defining 'systematic hallucination' quantitatively.

**Ambiguity flags / terms needing definition.**
- Systematic hallucination: The term is used to describe catastrophic failure but lacks a precise quantitative definition in the source evidence. User must define: A specific metric or threshold for output divergence from ground truth that qualifies as 'systematic'.
- Coupled adversarial feedback: The specific mathematical form of the coupling between noise and counterfactuals is not specified. User must define: The functional relationship or dependency structure between the noise component and the counterfactual component.
- robust: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.

## Directions Requiring Extra Source Validation
### 1. Characterizing the Failure Regime of Linear Intervention Methods Under Neural Superposition
- representative formulation: `var:35` | member formulations: ['var:35']
- source verification-passed gaps: ['gap:c7dff43244739c0d'] | source direct formulations: ['direct:12']

**Problem statement.** Mechanistic interpretability relies on intervention methods like TaRot that assume attention heads operate as independent, low-dimensional linear units. However, neural superposition causes token associations to entangle within single heads, violating these independence assumptions. This project characterizes the specific boundary where such linear interventions fail, moving beyond validating a single tool to defining the structural limits of the entire class of linear intervention mechanisms.

**Proposal-style abstract.** This project studies the fundamental limits of mechanistic editing methods that rely on linear independence assumptions in neural networks. The central question is identifying the precise structural conditions under which the entanglement of representations in attention heads renders linear interventions ineffective. A successful outcome would establish a rigorous failure regime for the class of linear intervention methods, providing a theoretical boundary that distinguishes editable circuits from entangled superpositions. This work proposes a new evaluation protocol to map the transition from robust editing to catastrophic disruption as superposition density increases, thereby redefining the scope of applicability for current interpretability tools.

- core research object / problem class: Mechanistic interpretability of Transformer attention heads under neural superposition — The structural identifiability and editability of neural circuits in the presence of representation superposition
- assumption shift: Relaxing the assumption of independent, low-dimensional linear operations to characterize the failure of this entire class under entanglement
- failure boundary / mechanism: The phase transition where linear interventions shift from precise editing to disruptive noise due to entangled circuits
- possible contribution targets — theorem: A structural threshold for the efficacy of linear interventions based on superposition density | algorithm: — | empirical: —
- first supporting papers to inspect: ['openreview:iZI1vCiTTA']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: moderate
- independent-critic note: The variant successfully generalizes from a specific critique of TaRot to a systematic characterization of the failure regime for an entire class of linear intervention methods, directly addressing the identified gap in superposition robustness without merely relabeling the original problem.
- main risk: Difficulty in quantifying 'entanglement' density in high-dimensional spaces without introducing its own strong assumptions
- caveats: Only partially overlaps this run's core topic.
- **What to verify before pursuing.** Read the first supporting papers (openreview:iZI1vCiTTA) to confirm the gap is real and not already addressed. Confirm that the target — The phase transition where linear interventions shift from precise editing to disruptive noise due to entangled circuits — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Mechanistic interpretability tools like TaRot assume that attention heads in Transformer models operate as independent, low-dimensional linear units. However, neural superposition causes multiple token associations to entangle within single heads, violating this independence. The problem is to characterize the specific structural boundary where these linear intervention methods fail, shifting from precise editing to disruptive noise, and to define the limits of the entire class of such linear intervention mechanisms.

**Formal problem statement.** Let $\mathcal{H}$ be the set of attention heads in a Transformer model. Let $\mathcal{S}$ be the set of token associations (superpositions) within these heads. The problem is to identify the structural conditions on $\mathcal{S}$ such that a linear intervention operator $\mathcal{I}$, designed to isolate and modify a specific association $s \in \mathcal{S}$, fails to produce the intended edit without disrupting other associations $s' \in \mathcal{S}$. Specifically, we seek a threshold or boundary in the space of superposition densities where the efficacy of $\mathcal{I}$ transitions from robust editing to catastrophic disruption.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{H}$ | Set of attention heads in the model | set | introduced for formalization |
| $\mathcal{S}$ | Set of token associations (superpositions) within heads | set | introduced for formalization |
| $\mathcal{I}$ | Linear intervention operator acting on a head | function | introduced for formalization |
| $\rho$ | Superposition density (measure of entanglement) | scalar | introduced for formalization |
| $E_{edit}$ | Efficacy of the intervention in achieving the target edit | scalar | introduced for formalization |
| $D_{noise}$ | Disruption noise affecting non-target associations | scalar | introduced for formalization |

- entities: ['Attention heads', 'Token associations', 'Linear intervention operators', 'Superposition density', 'Entanglement structure']
- feedback or observation model: The measurement model is unclear. The evidence suggests measuring 'efficacy' and 'disruption' but does not specify the exact metric (e.g., change in loss, correlation with target concept, or specific output divergence).
- decision variables / outputs: The structural threshold or boundary condition defining the failure regime.
- objective: To characterize the boundary where $E_{edit}$ drops below a critical threshold or $D_{noise}$ exceeds a tolerance level as a function of superposition density $\rho$.
- constraints: The intervention $\mathcal{I}$ must be linear and low-dimensional, consistent with the class of methods being analyzed.
- success criterion: Establishing a rigorous structural threshold that distinguishes editable circuits from entangled superpositions.

**Assumptions.**
- Linear Independence Assumption (relaxed): Attention heads operate as independent, low-dimensional linear units.
- Existence of Superposition (kept): Neural superposition causes token associations to entangle within single heads.
- Class Generalization (kept): The failure of TaRot implies the failure of the entire class of linear intervention mechanisms.

**Open question.** What is the precise structural condition (e.g., a specific density threshold or geometric property of the entanglement) that marks the transition from effective editing to disruptive noise?

- possible theorem target: A structural threshold for the efficacy of linear interventions based on superposition density.
- possible algorithm target: —
- possible empirical / benchmark target: A new evaluation protocol to map the transition from robust editing to catastrophic disruption as superposition density increases.
- evaluation protocol: The evidence proposes a new evaluation protocol but does not detail the specific steps, metrics, or datasets required to execute it. The protocol must be defined to map the transition from robust editing to catastrophic disruption.
- formalization confidence: medium | requires human definition: True
- formalization risk: The problem relies on quantifying 'entanglement' in high-dimensional spaces, which may require introducing strong assumptions that contradict the goal of characterizing the failure of such assumptions. Additionally, the measurement model for 'efficacy' and 'disruption' is not fully specified in the source evidence.

**Ambiguity flags / terms needing definition.**
- Entanglement density: The main risk identified is the difficulty in quantifying 'entanglement' density in high-dimensional spaces without introducing its own strong assumptions. User must define: A rigorous, assumption-minimal definition or metric for quantifying the degree of superposition/entanglement in attention heads.
- Efficacy vs. Disruption: The feedback/measurement model is unclear regarding how to precisely measure 'efficacy' of the edit versus 'disruption' of other circuits. User must define: Specific quantitative metrics for 'precise editing' and 'catastrophic disruption' to operationalize the failure boundary.
- failure: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.

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
