# paper/sgha/domain_batch_two_more_topics_comparison_20260714_022034/runs/uncertainty_calibration_conformal_prediction_arxiv — Research Direction Menu

> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides evidence and caveats, but it is not a final scientific judgment. Users should inspect the source papers before deciding what to pursue.

## Executive Summary
- corpus size: **250** papers (seed + retrieved)
- seed papers: **0** | retrieved papers: **250**
- verification-reviewed gaps: **15** | verification-passed gaps: **12** | verification-failed gaps: **3**
- direct formulations: **12**
- direct formulation input: **verification_passed_gaps** | verification-passed only: **True**
- verification gate: **enabled=True**, mode=**survival_score**, threshold=**0.6**
- ambition variants generated: **36**
- critic-passing formulations: **9** | selected formulations: **8**
- final project families: **6**
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
1. **Most directly aligned directions** — Calibrating Conformal Prediction Under Arbitrary Covariate Shift via Invariant Coverage Mechanisms, Characterizing the Fundamental Limits of Data-Adaptive Uncertainty Calibration, Characterizing the Fundamental Limits of Calibration Under Extreme Non-Exchangeable Shifts, Characterizing Calibration Collapse in Federated Conformal Prediction Under Arbitrary Heterogeneity, Calibration-Optimal Single-Pass Uncertainty via Structural Mismatch Bounds
2. **Strong but source-sensitive directions** — (none)
3. **Caveat-heavy or adjacent directions** — Characterizing the Fragility Boundary of Distribution-Free Conformal Prediction Under Extreme Label Shift

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
### 1. Calibrating Conformal Prediction Under Arbitrary Covariate Shift via Invariant Coverage Mechanisms
- representative formulation: `var:10` | member formulations: ['var:10', 'var:11']
- source verification-passed gaps: ['gap:a45116748c5f1c8a'] | source direct formulations: ['direct:04']

**Problem statement.** Conformal prediction guarantees valid coverage under the i.i.d. assumption, which breaks catastrophically under dataset shift. Existing literature acknowledges this failure but lacks a rigorous framework to characterize the precise conditions under which coverage degrades or to construct methods that maintain validity without i.i.d. assumptions. The current gap is not merely a lack of benchmarks, but a missing theoretical characterization of the failure regime and a constructive mechanism for invariant coverage.

**Proposal-style abstract.** This project studies the fundamental limits of uncertainty quantification when the i.i.d. assumption is violated by arbitrary covariate shifts. The central question is how to characterize the boundary between regimes where standard conformal prediction fails and those where modified mechanisms can restore validity. A successful outcome would provide a rigorous impossibility boundary demonstrating which shift types are inherently incompatible with finite-sample coverage guarantees without additional structural assumptions. Furthermore, it proposes a constructive mechanism class based on distributionally robust optimization that ensures coverage validity by explicitly accounting for the worst-case shift within a defined ambiguity set, rather than relying on historical data averages. This work moves beyond empirical validation to establish a new evaluation class for robust uncertainty quantification.

- core research object / problem class: Conformal prediction under arbitrary covariate shift — Robust Uncertainty Quantification under Distributional Shift
- assumption shift: Relaxes the i.i.d. assumption to allow for arbitrary covariate shift, requiring a new structural condition for validity.
- failure boundary / mechanism: Characterizes the boundary where exchangeability fails and coverage guarantees become invalid, identifying the specific shift characteristics that cause this.
- possible contribution targets — theorem: An impossibility theorem characterizing the necessary structural conditions (e.g., invariance) required to maintain coverage under arbitrary shifts. | algorithm: A distributionally robust calibration algorithm that minimizes coverage error over an ambiguity set of shifted distributions. | empirical: A systematic evaluation of the proposed robust mechanism class against standard conformal methods across diverse shift types.
- first supporting papers to inspect: ['2010.03039v2', '2112.09196v2']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts the scientific object from building a validation benchmark (source) to characterizing the theoretical failure boundary and constructing invariant mechanisms (variant), representing a genuine non-incremental leap in scope and ambition. While the source evidence only supports the existence of the gap, the proposed contribution type is specific and not merely a relabeling of the validation task.
- main risk: The derived ambiguity set for the distributionally robust mechanism may be too conservative, leading to vacuous coverage guarantees in practice.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2010.03039v2, 2112.09196v2) to confirm the gap is real and not already addressed. Confirm that the target — Characterizes the boundary where exchangeability fails and coverage guarantees become invalid, identifying the specific shift characteristics that cause this — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Standard conformal prediction methods guarantee valid uncertainty estimates only when data is independent and identically distributed (i.i.d.). When the data distribution shifts arbitrarily (covariate shift), these guarantees fail. The problem is to rigorously characterize the specific conditions under which this failure occurs (the impossibility boundary) and to construct a new class of algorithms that maintains valid coverage by explicitly accounting for the worst-case distributional shift within a defined ambiguity set.

**Formal problem statement.** The question is whether one can characterize the precise structural conditions on the covariate shift distribution that render standard exchangeability-based conformal prediction invalid, and if so, construct a distributionally robust calibration mechanism that guarantees coverage validity under arbitrary shifts by optimizing over an ambiguity set of possible shifted distributions.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| P_train | The probability distribution of the training data | distribution | from evidence |
| P_test | The probability distribution of the test data under shift | distribution | from evidence |
| A | The set of candidate distributions representing the worst-case shift | set | introduced for formalization |
| C | The coverage guarantee level (e.g., 1-alpha) | scalar | introduced for formalization |
| S | The transformation mapping training distribution to test distribution | function | introduced for formalization |

- entities: ['Training data distribution P_train', 'Test data distribution P_test', 'Ambiguity set A', 'Coverage guarantee function C', 'Shift operator S']
- feedback or observation model: The feedback is binary: whether the true label falls within the predicted set. The measurement model is unclear regarding the exact statistical properties of the shift S.
- decision variables / outputs: The choice of the ambiguity set A and the calibration threshold q.
- objective: Minimize the coverage error over the worst-case distribution in A while ensuring the coverage probability is at least C.
- constraints: The method must maintain validity for all distributions in the ambiguity set A.
- success criterion: Derivation of an impossibility theorem defining the boundary where coverage fails, and construction of an algorithm where the coverage error is bounded by the size of the ambiguity set.

**Assumptions.**
- Exchangeability under i.i.d. (relaxed): Standard conformal prediction assumes data points are exchangeable.
- Existence of Ambiguity Set (kept): There exists a well-defined set of distributions A that captures the worst-case shift.
- Finite Sample Regime (kept): The analysis focuses on finite-sample coverage guarantees.

**Open question.** What specific structural properties of the covariate shift S allow for the construction of a valid ambiguity set A that is not vacuous?

- possible theorem target: An impossibility theorem characterizing the necessary structural conditions (e.g., invariance) required to maintain coverage under arbitrary shifts.
- possible algorithm target: A distributionally robust calibration algorithm that minimizes coverage error over an ambiguity set of shifted distributions.
- possible empirical / benchmark target: A systematic evaluation of the proposed robust mechanism class against standard conformal methods across diverse shift types.
- evaluation protocol: Systematic evaluation of the proposed robust mechanism class against standard conformal methods across diverse shift types to verify coverage validity.
- formalization confidence: medium | requires human definition: True
- formalization risk: The derived ambiguity set for the distributionally robust mechanism may be too conservative, leading to vacuous coverage guarantees in practice.

**Ambiguity flags / terms needing definition.**
- Arbitrary covariate shift: The term 'arbitrary' implies no structure, but the proposed solution requires a defined ambiguity set, suggesting some structure is assumed or constructed. User must define: The specific class of distributions or the metric defining the distance between P_train and P_test.
- Vacuous coverage guarantees: This refers to a set A so large that the only valid prediction set is the entire space. User must define: The quantitative threshold for what constitutes a 'vacuous' set in the context of the ambiguity set construction.
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.
### 2. Characterizing the Fundamental Limits of Data-Adaptive Uncertainty Calibration
- representative formulation: `var:27` | member formulations: ['var:27']
- source verification-passed gaps: ['gap:22d6aa79790b1d2e'] | source direct formulations: ['direct:09']

**Problem statement.** Monte Carlo Dropout and similar stochastic approximation methods rely on fixed hyperparameters to estimate uncertainty, failing when training data distributions shift or contain outliers. Current literature treats the optimal dropout rate as a static parameter or a simple schedule, ignoring the theoretical constraints on how much data statistics can influence uncertainty calibration without compromising model integrity. This project investigates the fundamental boundary between data-adaptive uncertainty estimation and overfitting, asking how much a model's uncertainty can depend on training data statistics before the estimation becomes statistically impossible.

**Proposal-style abstract.** This project studies the theoretical limits of adaptive uncertainty calibration in deep neural networks, moving beyond empirical tuning of dropout rates to characterize the conditions under which data-dependent uncertainty estimates are valid. The central question is to identify the boundary between beneficial adaptation to data distribution shifts and the failure modes where adaptive mechanisms induce severe overfitting or calibration collapse. A successful outcome would establish a rigorous impossibility boundary or lower bound on the variance of uncertainty estimators that are conditioned on training data statistics, providing a principled framework for when adaptive methods are theoretically justified versus when they are inherently unstable. This work proposes a new evaluation protocol to expose failure regimes across a family of adaptive uncertainty methods, rather than validating a single algorithm.

- core research object / problem class: Deep Neural Networks with Stochastic Approximation for Uncertainty Quantification — Fundamental limits of statistical learning under distributional shift and the identifiability of uncertainty in stochastic models.
- assumption shift: Relaxes the assumption that uncertainty estimation requires fixed hyperparameters; instead, it characterizes the necessary conditions for any data-dependent estimator to exist.
- failure boundary / mechanism: The phase transition point where the dependence of the uncertainty estimator on training data statistics causes the estimator to lose consistency or calibration properties.
- possible contribution targets — theorem: A necessary condition for the existence of a consistent uncertainty estimator that depends on training data statistics, showing that beyond a specific dependence on data moments, calibration error diverges. | algorithm: — | empirical: —
- first supporting papers to inspect: ['2110.06427v1', '2202.12369v2', '2206.02152v2', '2210.09909v1', '2302.11874v1']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant successfully shifts from a specific engineering fix for MC-Dropout to a fundamental theoretical investigation of identifiability limits under distributional shift, moving beyond the source's narrow validation of adaptive schedules.
- main risk: The mathematical derivation of the impossibility boundary may be intractable for high-dimensional neural network architectures without simplifying assumptions that reduce practical relevance.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2110.06427v1, 2202.12369v2, 2206.02152v2) to confirm the gap is real and not already addressed. Confirm that the target — The phase transition point where the dependence of the uncertainty estimator on training data statistics causes the estimator to lose consistency or calibration properties — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Monte Carlo Dropout and similar methods use fixed hyperparameters to estimate uncertainty, which fails when training data distributions shift. This project seeks to define the theoretical boundary where adapting these hyperparameters to training data statistics becomes statistically impossible due to overfitting or loss of calibration.

**Formal problem statement.** Let $\mathcal{D}$ be a training dataset and $\theta$ be the parameters of a Deep Neural Network with Stochastic Approximation. Let $\hat{\sigma}(\mathcal{D})$ be an uncertainty estimator conditioned on the statistics of $\mathcal{D}$. The problem is to characterize the set of functions $\mathcal{F}_{\text{valid}}$ such that for any $f \in \mathcal{F}_{\text{valid}}$, the estimator $\hat{\\sigma}$ maintains calibration properties under distributional shifts. Specifically, identify the dependence on data moments $\mu(\\mathcal{D})$ beyond which the variance of $\hat{\sigma}$ diverges or the estimator loses consistency, establishing a necessary condition for the existence of a consistent data-adaptive uncertainty estimator.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{D}$ | Training dataset used to condition the uncertainty estimator | set | from evidence |
| $\theta$ | Parameters of the neural network model | vector | from evidence |
| $\hat{\sigma}$ | Uncertainty estimator function | function | from evidence |
| $\mu(\mathcal{D})$ | Statistics (moments) of the training data | vector | from evidence |
| $\epsilon_{\text{cal}}$ | Calibration error of the estimator | scalar | introduced for formalization |
| $\mathcal{F}_{\text{valid}}$ | Set of valid data-adaptive estimators | set | introduced for formalization |

- entities: ['Deep Neural Network with Stochastic Approximation', 'Training Dataset', 'Uncertainty Estimator', 'Data Statistics', 'Calibration Error']
- feedback or observation model: The feedback is the calibration error $\epsilon_{\text{cal}}$ and the variance of the estimator under distributional shifts. The model is unclear regarding the exact functional form of the divergence.
- decision variables / outputs: The choice of the dependence function $\hat{\sigma}(\mathcal{D})$ and the identification of the boundary condition.
- objective: To derive a necessary condition on the dependence of $\hat{\sigma}$ on $\mu(\mathcal{D})$ such that $\lim_{\text{shift}} \epsilon_{\text{cal}} < \infty$.
- constraints: The estimator must not compromise model integrity (consistency) and must handle distributional shifts.
- success criterion: Establishing a rigorous impossibility boundary or lower bound on the variance of uncertainty estimators conditioned on training data statistics.

**Assumptions.**
- Stochastic Approximation Validity (kept): The model relies on stochastic approximation methods (like MC-Dropout) to approximate uncertainty.
- Distributional Shift Existence (kept): The training data distribution may shift or contain outliers compared to the test distribution.
- Fixed Hyperparameter Insufficiency (relaxed): Fixed hyperparameters are insufficient for robust uncertainty estimation under shift.
- Identifiability of Uncertainty (questioned): Uncertainty is theoretically identifiable up to a certain dependence on data statistics.

**Open question.** What is the specific functional form of the dependence on data moments $\mu(\mathcal{D})$ that causes the calibration error to diverge?

- possible theorem target: A necessary condition for the existence of a consistent uncertainty estimator that depends on training data statistics, showing that beyond a specific dependence on data moments, calibration error diverges.
- possible algorithm target: —
- possible empirical / benchmark target: A new evaluation protocol to expose failure regimes across a family of adaptive uncertainty methods.
- evaluation protocol: The question is whether a new evaluation protocol can be constructed to expose failure regimes across a family of adaptive uncertainty methods, rather than validating a single algorithm.
- formalization confidence: medium | requires human definition: True
- formalization risk: Some terms may remain under-specified until the source papers are read.

**Ambiguity flags / terms needing definition.**
- Model Integrity: The term is used qualitatively in the source text without a precise mathematical definition. User must define: A formal constraint or metric defining 'compromised model integrity'.
- Statistically Impossible: The threshold for 'impossibility' is not defined in terms of specific error bounds or sample complexity. User must define: The specific divergence criteria (e.g., infinite variance, non-vanishing bias) that constitute impossibility.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.
### 3. Characterizing the Fundamental Limits of Calibration Under Extreme Non-Exchangeable Shifts
- representative formulation: `var:15` | member formulations: ['var:15']
- source verification-passed gaps: ['gap:713adb8bca030296'] | source direct formulations: ['direct:05']

**Problem statement.** Current federated conformal prediction frameworks rely on exchangeability assumptions that fail under extreme client heterogeneity. While existing literature identifies this fragility, it lacks a rigorous characterization of the boundary where coverage guarantees fundamentally collapse. This project moves beyond validating specific robustness techniques to establishing the theoretical limits of valid uncertainty quantification in non-exchangeable federated settings.

**Proposal-style abstract.** This project studies the fundamental boundaries of calibration validity in federated learning environments characterized by extreme non-exchangeable distribution shifts. The central question is to characterize the precise regime where standard conformal prediction guarantees become impossible to satisfy, regardless of the specific algorithmic instantiation. A successful outcome would provide a rigorous impossibility boundary and a failure regime analysis that explains why coverage degrades under specific structural violations of exchangeability. This work defines a new evaluation class for stress-testing uncertainty quantification methods, rather than merely benchmarking existing ones. By identifying the necessary conditions for validity, this research establishes a theoretical foundation for designing future methods that can operate safely in highly divergent distributed environments.

- core research object / problem class: Federated learning with extreme non-exchangeable client data distributions — Theoretical limits of uncertainty quantification under distributional shift
- assumption shift: Removes reliance on specific algorithmic fixes to instead characterize the necessity of exchangeability-like conditions
- failure boundary / mechanism: The precise boundary where coverage guarantees collapse due to non-exchangeability
- possible contribution targets — theorem: Necessary and sufficient conditions for coverage validity under non-exchangeable shifts | algorithm: — | empirical: —
- first supporting papers to inspect: ['2305.17564v2']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant successfully shifts from a narrow validation of specific robustness techniques to a fundamental theoretical inquiry about the limits of calibration under non-exchangeability, which is explicitly supported by the source's identification of the missing stress-test gap.
- main risk: High mathematical complexity in deriving tight bounds for non-exchangeable processes.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2305.17564v2) to confirm the gap is real and not already addressed. Confirm that the target — The precise boundary where coverage guarantees collapse due to non-exchangeability — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Standard federated conformal prediction methods assume data from different clients is exchangeable (statistically similar). In highly heterogeneous federated settings, this assumption often fails. This project seeks to mathematically define the exact boundary where these methods stop providing valid coverage guarantees (i.e., where the probability of the true label being in the prediction interval drops below the target level) due to extreme non-exchangeability.

**Formal problem statement.** Let $\mathcal{D}$ be a collection of client data distributions $\{D_i\}_{i \in \mathcal{I}}$ in a federated setting. Let $\mathcal{C}$ be a conformal prediction algorithm parameterized by a calibration set. The problem is to characterize the set of distributional configurations $\mathcal{D}$ and shift magnitudes $\delta$ such that the coverage probability $\mathbb{P}(Y \in \hat{C}(X))$ falls strictly below the target level $\alpha$, regardless of the specific instantiation of $\mathcal{C}$. Specifically, we seek necessary and sufficient conditions on the dependence structure and marginal differences between $D_i$ that render the exchangeability assumption invalid for valid uncertainty quantification.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{D}$ | The set of all possible client data distributions in the federated environment | set | introduced for formalization |
| $D_i$ | The data distribution associated with client $i$ | distribution | introduced for formalization |
| $\mathcal{C}$ | A conformal prediction algorithm mapping inputs to prediction sets | function | introduced for formalization |
| $\hat{C}(X)$ | The prediction set output by algorithm $\mathcal{C}$ for input $X$ | set | introduced for formalization |
| $\alpha$ | The target coverage level (e.g., 0.95) | scalar | introduced for formalization |
| $\mathbb{P}(Y \in \hat{C}(X))$ | The actual coverage probability under the joint distribution of data and labels | scalar | introduced for formalization |
| $\delta$ | A measure of the magnitude of non-exchangeable shift between clients | scalar | introduced for formalization |

- entities: ['Client data distributions', 'Conformal prediction algorithm', 'Coverage probability', 'Exchangeability condition', 'Distributional shift magnitude']
- feedback or observation model: The feedback is the empirical coverage rate measured over a test set. The measurement model is unclear regarding the specific metric used to quantify 'extreme' non-exchangeability.
- decision variables / outputs: The theoretical boundary conditions (necessary and sufficient conditions) defining the failure regime.
- objective: To derive the set of conditions $S$ such that for all $\mathcal{D} \in S$, $\inf_{\mathcal{C}} \mathbb{P}(Y \in \hat{C}(X)) < \alpha$.
- constraints: The analysis must hold for any conformal prediction algorithm $\mathcal{C}$, not just specific robust variants.
- success criterion: Derivation of a rigorous impossibility boundary theorem stating the precise structural violations of exchangeability that guarantee coverage collapse.

**Assumptions.**
- Federated Setting (kept): Data is distributed across multiple clients $i \in \mathcal{I}$.
- Non-Exchangeability (kept): The joint distribution of data across clients violates the exchangeability assumption required for standard conformal prediction.
- Existence of a Failure Boundary (kept): There exists a precise boundary where coverage guarantees fundamentally collapse.
- Algorithm Agnosticism (kept): The characterization applies to the class of conformal predictors generally, not specific algorithmic fixes.

**Open question.** What is the precise mathematical characterization of the 'failure regime' where coverage guarantees collapse due to non-exchangeability, and what are the necessary and sufficient conditions for validity?

- possible theorem target: Necessary and sufficient conditions for coverage validity under non-exchangeable shifts.
- possible algorithm target: —
- possible empirical / benchmark target: A new evaluation class for stress-testing uncertainty quantification methods.
- evaluation protocol: Theoretical derivation of bounds and impossibility results, potentially validated via simulation of extreme non-exchangeable distributions.
- formalization confidence: medium | requires human definition: True
- formalization risk: High mathematical complexity in deriving tight bounds for non-exchangeable processes; the feedback/measurement model for 'collapse' is under-specified.

**Ambiguity flags / terms needing definition.**
- Extreme non-exchangeable shifts: The term 'extreme' is qualitative and lacks a precise mathematical definition in the source evidence. User must define: A quantitative threshold or structural condition defining 'extreme' non-exchangeability.
- Coverage guarantees collapse: The degree of collapse is not specified (e.g., dropping below $\alpha$, or dropping to zero). User must define: The specific condition for 'collapse' (e.g., $\mathbb{P} < \alpha - \epsilon$).
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.
### 4. Characterizing Calibration Collapse in Federated Conformal Prediction Under Arbitrary Heterogeneity
- representative formulation: `var:03` | member formulations: ['var:03']
- source verification-passed gaps: ['gap:3f5fc34e43752eef'] | source direct formulations: ['direct:01']

**Problem statement.** Standard conformal prediction relies on exchangeability, an assumption shattered in federated learning by non-IID data. While Federated Conformal Predictors (FCP) have been proposed to mitigate this, existing literature lacks a rigorous characterization of the failure regimes where calibration guarantees catastrophically break down. This project moves beyond empirical validation to define the precise structural conditions under which FCP fails and whether robustness can be theoretically guaranteed without exchangeability.

**Proposal-style abstract.** This project studies the fundamental limits of uncertainty quantification in distributed learning systems where data distributions are arbitrarily heterogeneous. The central question is whether the violation of exchangeability in federated settings induces a phase transition in calibration accuracy, leading to a specific class of 'calibration collapse' that current methods cannot recover from. A successful outcome would establish a rigorous impossibility boundary for standard federated conformal predictors under non-exchangeable data, identifying the exact divergence between local and global coverage guarantees. Furthermore, this work proposes a constructive alternative at the evaluation class level: a new benchmark suite designed to expose failure modes across a family of conformal prediction mechanisms, rather than testing a single named method. By characterizing the mechanism of failure, the project aims to provide a unifying explanation for why standard approaches degrade in realistic federated environments, thereby shifting the scientific object from method validation to the characterization of robustness boundaries in distributed statistical learning.

- core research object / problem class: Federated learning with arbitrary non-IID (heterogeneous) data distributions — Robustness of statistical inference guarantees under distributional shift in distributed systems
- assumption shift: Removal of the exchangeability assumption and characterization of its necessity for valid coverage
- failure boundary / mechanism: Calibration collapse: the regime where local non-IID shifts cause global coverage guarantees to diverge significantly from nominal levels
- possible contribution targets — theorem: Necessary and sufficient conditions for the existence of valid coverage guarantees in federated conformal prediction without exchangeability | algorithm: — | empirical: A benchmark suite exposing failure modes across a family of conformal prediction mechanisms
- first supporting papers to inspect: ['2305.17564v2', '2502.05709v3', '2507.11739v1']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts the objective from empirical validation of existing methods to defining the theoretical failure regimes and impossibility boundaries of the class, which is a distinct scientific leap beyond the source's gap.
- main risk: Theoretical analysis of calibration collapse may require unrealistic assumptions about the nature of the data shift if the failure mechanism is too complex to characterize analytically.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2305.17564v2, 2502.05709v3, 2507.11739v1) to confirm the gap is real and not already addressed. Confirm that the target — Calibration collapse: the regime where local non-IID shifts cause global coverage guarantees to diverge significantly from nominal levels — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Standard conformal prediction requires data to be exchangeable (order-independent), but federated learning often involves non-IID data where this assumption fails. This project seeks to mathematically define the specific conditions under which Federated Conformal Predictors (FCP) lose their ability to provide valid coverage guarantees (calibration collapse) and to establish whether valid inference is theoretically possible without exchangeability.

**Formal problem statement.** Let D be a federated learning environment composed of clients C with local data distributions P_i. Let CP be a class of conformal prediction mechanisms. The problem is to characterize the set of distributional shifts {P_i} for which the coverage guarantee of any CP in the class diverges from the nominal level alpha. Specifically, determine necessary and sufficient conditions on the heterogeneity of {P_i} such that sup_{P_i} |Coverage(CP, P_i) - alpha| > epsilon for some epsilon > 0, and identify if there exists a CP that maintains coverage under arbitrary non-exchangeable shifts.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| C | Set of clients in the federated system | set | introduced for formalization |
| P_i | Data distribution at client i | distribution | introduced for formalization |
| CP | Class of conformal prediction mechanisms | set | introduced for formalization |
| alpha | Nominal coverage level | scalar | introduced for formalization |
| Coverage(CP, P_i) | Actual coverage probability of mechanism CP under distribution P_i | scalar | introduced for formalization |
| epsilon | Threshold for calibration collapse divergence | scalar | introduced for formalization |

- entities: ['Federated Learning Environment', 'Local Data Distributions', 'Conformal Prediction Mechanism', 'Coverage Guarantee', 'Nominal Level']
- feedback or observation model: The coverage guarantee is measured as the empirical frequency of true labels falling within the predicted sets over a validation set drawn from the joint distribution of clients.
- decision variables / outputs: The structural conditions defining the failure regime and the existence of a robust mechanism.
- objective: To derive necessary and sufficient conditions for the existence of valid coverage guarantees in federated conformal prediction without exchangeability.
- constraints: The analysis must hold for arbitrary non-IID (heterogeneous) data distributions.
- success criterion: Establishing a rigorous impossibility boundary or a constructive proof of robustness for the class of conformal predictors under non-exchangeable data.

**Assumptions.**
- Exchangeability (removed): The assumption that data points are exchangeable, which is standard for conformal prediction but violated in federated settings.
- Arbitrary Heterogeneity (kept): The data distributions across clients can be arbitrarily different (non-IID).
- Existence of Valid Coverage (questioned): The hypothesis that valid coverage might be achievable without exchangeability.

**Open question.** Does a phase transition exist in calibration accuracy where local non-IID shifts cause global coverage guarantees to diverge significantly from nominal levels, leading to a 'calibration collapse' that current methods cannot recover from?

- possible theorem target: Necessary and sufficient conditions for the existence of valid coverage guarantees in federated conformal prediction without exchangeability.
- possible algorithm target: —
- possible empirical / benchmark target: A benchmark suite exposing failure modes across a family of conformal prediction mechanisms.
- evaluation protocol: A benchmark suite designed to expose failure modes across a family of conformal prediction mechanisms, rather than testing a single named method, to characterize the mechanism of failure.
- formalization confidence: medium | requires human definition: True
- formalization risk: Theoretical analysis of calibration collapse may require unrealistic assumptions about the nature of the data shift if the failure mechanism is too complex to characterize analytically.

**Ambiguity flags / terms needing definition.**
- Calibration Collapse: The term is used descriptively in the source to denote a regime of failure but lacks a precise mathematical definition in the provided evidence. User must define: A quantitative threshold or structural condition that defines the onset of 'calibration collapse'.
- Robustness: The source mentions 'robustness' generally but does not specify the metric (e.g., coverage lower bound, calibration error bound). User must define: The specific metric or bound used to quantify robustness in the absence of exchangeability.
- robust: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
### 5. Calibration-Optimal Single-Pass Uncertainty via Structural Mismatch Bounds
- representative formulation: `var:31` | member formulations: ['var:31']
- source verification-passed gaps: ['gap:233bb1623d19f74e'] | source direct formulations: ['direct:11']

**Problem statement.** Deep ensembles provide robust uncertainty quantification but incur prohibitive inference costs due to multiple forward passes. Existing single-pass approximations often fail to maintain the calibration guarantees inherent to ensemble averaging because they lack a theoretical mechanism to bridge the gap between single-pass estimates and multi-pass ground truth. This project investigates the fundamental limits of single-pass uncertainty estimation under structural mismatch between the estimator and the ensemble distribution.

**Proposal-style abstract.** This project studies the theoretical boundary between single-pass inference and ensemble-level uncertainty calibration in deep learning systems. The central question is whether a constructive method class can achieve ensemble-equivalent calibration without multiple forward passes, or if a fundamental structural mismatch necessitates a trade-off. A successful outcome would define a precise failure regime where single-pass methods inevitably degrade and propose a new algorithmic framework that operates at the boundary of this regime. The work moves beyond empirical validation to characterize the identifiability limits of uncertainty estimation under computational constraints.

- core research object / problem class: Deep Learning Uncertainty Quantification — Computational-Statistical Trade-offs in Probabilistic Deep Learning
- assumption shift: Relaxes the assumption that single-pass methods can be universally tuned to match ensemble performance without structural changes; instead characterizes the necessity of structural alignment.
- failure boundary / mechanism: The phase transition where the structural complexity of the uncertainty manifold exceeds the representational capacity of a single forward pass.
- possible contribution targets — theorem: A lower bound on the calibration error of any single-pass estimator relative to the ensemble distribution under specific structural mismatch conditions. | algorithm: — | empirical: —
- first supporting papers to inspect: ['2202.12369v2', '2204.13963v1', '2210.09909v1', '2302.04019v1', '2308.09647v2']
- related seed papers: —
- evidence grounding: moderate | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts from a practical calibration framework to a fundamental theoretical investigation of structural mismatch bounds, moving beyond the source's narrow validation of existing methods to define the limits of single-pass estimation.
- main risk: The theoretical lower bound may be too loose to be practically useful for designing specific algorithms.
- caveats: No major caveats were flagged.
- **What to verify before pursuing.** Read the first supporting papers (2202.12369v2, 2204.13963v1, 2210.09909v1) to confirm the gap is real and not already addressed. Confirm that the target — The phase transition where the structural complexity of the uncertainty manifold exceeds the representational capacity of a single forward pass — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Deep ensembles provide robust uncertainty estimates but require multiple forward passes, making them computationally expensive. Single-pass methods are cheaper but often lack the calibration guarantees of ensembles. This project seeks to determine the fundamental theoretical limits of single-pass estimation by characterizing the 'structural mismatch' between a single forward pass and the ensemble distribution, specifically identifying conditions under which single-pass methods inevitably fail to match ensemble calibration.

**Formal problem statement.** Let $\mathcal{D}$ be a data distribution and $\mathcal{E}$ be an ensemble of $K$ models. Let $\pi_{\mathcal{E}}$ denote the ensemble distribution over predictions and $\pi_{SP}$ denote a single-pass estimator distribution. The problem is to characterize the set of structural mismatches $\Delta(\pi_{SP}, \pi_{\\mathcal{E}})$ such that the calibration error $\mathcal{C}(\pi_{SP})$ is bounded below by a function of $\Delta$. Specifically, determine if there exists a constructive method class where $\mathcal{C}(\pi_{SP}) \approx \mathcal{C}(\pi_{\mathcal{E}})$ without multiple passes, or if a phase transition exists where $\mathcal{C}(\pi_{SP})$ diverges from $\mathcal{C}(\pi_{\mathcal{E}})$ as the structural complexity of the uncertainty manifold exceeds the representational capacity of a single forward pass.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| $\mathcal{D}$ | The underlying probability distribution of data points | distribution | from evidence |
| $\pi_{\mathcal{E}}$ | The joint distribution of predictions generated by the ensemble of models | distribution | from evidence |
| $\pi_{SP}$ | The distribution of predictions generated by a single-pass estimator | distribution | from evidence |
| $\Delta$ | The structural mismatch between the single-pass estimator and the ensemble distribution | other | introduced for formalization |
| $\mathcal{C}(\pi)$ | The calibration error of a distribution $\pi$ relative to the true labels | scalar | from evidence |
| $\mathcal{M}$ | The uncertainty manifold representing the space of possible uncertainty distributions | set | introduced for formalization |

- entities: ['Data distribution $\\mathcal{D}$', 'Ensemble distribution $\\pi_{\\mathcal{E}}$', 'Single-pass estimator distribution $\\pi_{SP}$', 'Structural mismatch $\\Delta$', 'Calibration error $\\mathcal{C}$', 'Uncertainty manifold $\\mathcal{M}$']
- feedback or observation model: The calibration error $\mathcal{C}$ is measured as the deviation between predicted confidence and empirical accuracy. The feedback model is unclear regarding how $\mathcal{C}$ explicitly depends on $\Delta$ without empirical specification.
- decision variables / outputs: The choice of the single-pass estimator architecture and parameters to minimize $\mathcal{C}(\pi_{SP})$ subject to computational constraints.
- objective: To derive a lower bound on $\mathcal{C}(\pi_{SP})$ as a function of $\Delta(\pi_{SP}, \pi_{\\mathcal{E}})$ and to identify the boundary conditions where $\mathcal{C}(\pi_{SP})$ becomes unacceptably large.
- constraints: The estimator must operate with a single forward pass (computational constraint).
- success criterion: Derivation of a non-trivial lower bound on calibration error under structural mismatch, or identification of a specific algorithmic framework that achieves ensemble-equivalent calibration within the derived boundary.

**Assumptions.**
- Ensemble Calibration (kept): The ensemble distribution $\pi_{\mathcal{E}}$ is assumed to possess robust calibration guarantees inherent to ensemble averaging.
- Structural Mismatch Necessity (relaxed): The assumption that single-pass methods can be universally tuned to match ensemble performance without structural changes is relaxed; instead, structural alignment is characterized as necessary.
- Representational Capacity Limit (kept): There exists a phase transition where the structural complexity of the uncertainty manifold exceeds the representational capacity of a single forward pass.

**Open question.** Does a constructive method class exist that achieves ensemble-equivalent calibration without multiple forward passes, or is a fundamental structural mismatch necessitating a trade-off inevitable?

- possible theorem target: A lower bound on the calibration error of any single-pass estimator relative to the ensemble distribution under specific structural mismatch conditions.
- possible algorithm target: A new algorithmic framework operating at the boundary of the identified failure regime.
- possible empirical / benchmark target: Characterization of the identifiability limits of uncertainty estimation under computational constraints.
- evaluation protocol: Theoretical derivation of bounds and analysis of the phase transition regime. Empirical validation is secondary to the characterization of limits.
- formalization confidence: medium | requires human definition: True
- formalization risk: Some terms may remain under-specified until the source papers are read.

**Ambiguity flags / terms needing definition.**
- Structural Mismatch: The term is used to describe the gap between single-pass and ensemble distributions but lacks a precise mathematical definition in the source evidence. User must define: A formal metric or distance function quantifying the difference between $\pi_{SP}$ and $\pi_{\mathcal{E}}$.
- Representational Capacity: The source mentions this concept in the context of the phase transition but does not define it mathematically. User must define: A capacity measure for the single forward pass, such as VC dimension or Rademacher complexity, applicable to the uncertainty manifold.
- Calibration Error: While implied, the specific definition (e.g., expected calibration error, reliability diagram area) is not explicitly stated. User must define: The precise functional form of $\mathcal{C}(\pi)$.
- mismatch: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured. User must define: Define the observation channel, measurement process, or data collection protocol.

## Directions Requiring Extra Source Validation
(none)

## Caveat-Heavy or Adjacent Directions
### 1. Characterizing the Fragility Boundary of Distribution-Free Conformal Prediction Under Extreme Label Shift
- representative formulation: `var:08` | member formulations: ['var:08', 'var:07']
- source verification-passed gaps: ['gap:40df536211a4b3f4'] | source direct formulations: ['direct:03']

**Problem statement.** Current conformal prediction guarantees claim distribution-free validity, yet empirical evidence suggests these guarantees collapse under severe label shifts. The critical missing component is a rigorous characterization of the boundary between valid and invalid regimes, rather than mere validation of specific methods in new settings. This project seeks to define the precise conditions under which distribution-free validity fails.

**Proposal-style abstract.** This project studies the fundamental limits of distribution-free validity in conformal prediction when subjected to severe label shifts. The central question is identifying the structural boundary where theoretical guarantees cease to hold, moving beyond incremental validation of specific algorithms. A successful outcome would establish a rigorous failure regime characterization, defining the exact magnitude and nature of label shift required to invalidate coverage guarantees. This work proposes a systematic evaluation framework designed to expose these fragility boundaries across a broad class of conformal methods, ensuring robustness claims are grounded in verified limits rather than optimistic assumptions.

- core research object / problem class: Classification under severe, realistic label shift — Robustness of distribution-free statistical guarantees under distributional shift
- assumption shift: Relaxation of implicit 'mild shift' assumptions to characterize the exact failure boundary under severe shift
- failure boundary / mechanism: The specific boundary separating valid coverage from invalid coverage under extreme label shift
- possible contribution targets — theorem: Characterization of the minimal label shift magnitude and structure required to violate finite-sample coverage guarantees. | algorithm: — | empirical: Construction of a standardized benchmark suite to empirically map the fragility boundary across diverse conformal prediction methods.
- first supporting papers to inspect: ['2103.03323v4', '2306.05131v2']
- related seed papers: —
- evidence grounding: strong | non-incrementality: strong | specificity: strong | plausibility: strong | topic alignment: strong
- independent-critic note: The variant shifts the objective from validating specific methods to characterizing the fundamental failure boundary of the entire class of distribution-free guarantees, which is a distinct scientific question supported by the source's identification of the lack of stress-testing under severe shifts.
- main risk: Difficulty in constructing a sufficiently diverse set of shift scenarios to accurately map the theoretical boundary.
- caveats: Its variants are near-duplicates of one another, so it may be worth consolidating into a single direction.
- **What to verify before pursuing.** Read the first supporting papers (2103.03323v4, 2306.05131v2) to confirm the gap is real and not already addressed. Confirm that the target — The specific boundary separating valid coverage from invalid coverage under extreme label shift — is well-posed and checkable.

#### Formal Problem Formulation

**Plain-language problem.** Distribution-free conformal prediction guarantees are claimed to hold regardless of data distribution, but empirical evidence suggests they fail under severe label shifts. The core problem is to rigorously define the specific boundary (magnitude and structure of shift) where these theoretical coverage guarantees cease to be valid, rather than just testing specific methods.

**Formal problem statement.** Let C be the class of distribution-free conformal prediction methods. Let P be the true data-generating distribution and P' be a shifted distribution characterized by a label shift parameter delta. Let alpha be the target coverage level. The problem is to characterize the set of pairs (P, P') such that the finite-sample coverage of any method in C under P' is strictly less than 1-alpha. Specifically, identify the minimal structural properties of the label shift delta that induce this violation.

**Entities / variables.**

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| C | The class of distribution-free conformal prediction methods | set | introduced for formalization |
| P | The true data-generating distribution on (X, Y) | distribution | introduced for formalization |
| P' | The shifted data-generating distribution under label shift | distribution | introduced for formalization |
| delta | The structural parameter characterizing the label shift between P and P' | vector | introduced for formalization |
| alpha | The target coverage level (e.g., 0.95) | scalar | introduced for formalization |
| Coverage(C, P', alpha) | The actual coverage probability achieved by method C under distribution P' at level alpha | scalar | introduced for formalization |
| FragilityBoundary | The set of shift parameters delta where Coverage(C, P', alpha) < 1-alpha | set | introduced for formalization |

- entities: ['Conformal prediction method', 'Data distribution', 'Label shift parameter', 'Coverage guarantee', 'Validation set']
- feedback or observation model: The feedback is binary: whether the true label falls within the predicted set. The measurement model is the empirical coverage rate over a validation set, which estimates Coverage(C, P', alpha).
- decision variables / outputs: The characterization of the minimal delta required to violate the guarantee.
- objective: To define the set FragilityBoundary = { delta | exists C in C such that Coverage(C, P', alpha) < 1-alpha } and identify the minimal magnitude and structure of delta within this set.
- constraints: The analysis must hold for the class C of distribution-free methods without assuming specific parametric forms for P or P'.
- success criterion: A rigorous mathematical or empirical characterization of the conditions (magnitude/structure of delta) under which the coverage guarantee fails.

**Assumptions.**
- Distribution-free validity claim (relaxed): The assumption that conformal prediction methods satisfy coverage guarantees regardless of the underlying distribution P.
- Existence of severe label shift (kept): The assumption that there exist realistic scenarios where the label distribution shifts significantly from the training distribution.
- Finite-sample coverage definition (kept): The assumption that coverage is defined by the probability that the true label is contained in the prediction set.

**Open question.** What is the precise structural relationship between the label shift parameter delta and the violation of the coverage guarantee? Is there a threshold magnitude of shift below which guarantees hold and above which they fail?

- possible theorem target: A characterization of the minimal label shift magnitude and structure required to violate finite-sample coverage guarantees.
- possible algorithm target: —
- possible empirical / benchmark target: Construction of a standardized benchmark suite to empirically map the fragility boundary across diverse conformal prediction methods.
- evaluation protocol: Construct a suite of synthetic and real-world datasets with varying degrees and structures of label shift. For each dataset, compute the empirical coverage of standard conformal prediction methods. Identify the transition point where coverage drops below the target level.
- formalization confidence: medium | requires human definition: True
- formalization risk: Difficulty in constructing a sufficiently diverse set of shift scenarios to accurately map the theoretical boundary; the definition of 'severe' shift is under-specified.

**Ambiguity flags / terms needing definition.**
- Severe label shift: The term 'severe' is qualitative and lacks a precise mathematical definition in the source evidence. User must define: A quantitative threshold or structural class of distributions that constitutes 'severe' shift.
- Fragility boundary: The exact nature of the boundary (e.g., a specific value, a region, or a phase transition) is not explicitly defined in the source. User must define: Whether the boundary is defined by a specific magnitude of shift, a specific structural property, or a combination of both.
- boundary: This term may hide multiple operational meanings in the source family. User must define: Specify the measurable object, boundary, or condition denoted by this term.

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
