# Representative SGHA Outputs By Domain

Sanitization note: entries below are selected from the existing sanitized final-family and formal-problem artifacts. They include generated problem text, source IDs, and judge scores, but no raw papers or parsed full texts.

## bandits

- final_family_id: family:01
- title: Characterizing Identifiability Limits of Structured Bandits Under Piecewise Non-Stationarity
- judge mean overall formulation quality: 6.25
- judges: 4
- selected reason: selected by highest mean_overall_formulation_quality=6.25, median=6.0, max=7.0, tie_break_mean_wellposed_formal_source_ambiguity=6.75

### Problem Statement

Current robust bandit algorithms for structured action sets, such as Network Lasso, rely on the i.i.d. assumption of context generation. This assumption fails in environments with piecewise constant non-stationarity, leading to unbounded regret and failure in identifying optimal arms. The fundamental question is not merely how to fix a specific algorithm, but whether the network structure itself allows for consistent learning under such distributional shifts, or if a fundamental identifiability barrier exists.

### Formal Objective

Characterize the necessary and sufficient conditions for consistent learning (identifiability) in network-structured bandits under piecewise constant non-stationarity.

### Ambiguity Flags

- Network Structure: The specific type of network (e.g., graph topology, sparsity pattern) and how it mathematically constrains the action set are not explicitly defined in the evidence.
- Piecewise Constant Non-Stationarity: The evidence does not specify the magnitude of the shift, the frequency of shifts, or the relationship between the shift and the network structure.
- Feedback Model: The specific reward function and the exact nature of the observation process are not detailed.
- boundary: This term may hide multiple operational meanings in the source family.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured.

## in_context_learning

- final_family_id: family:01
- title: Characterizing the Depth-Window Phase Transition in Linear Attention Mechanisms
- judge mean overall formulation quality: 6.75
- judges: 4
- selected reason: selected by highest mean_overall_formulation_quality=6.75, median=7.0, max=7.0, tie_break_mean_wellposed_formal_source_ambiguity=7.1875

### Problem Statement

Current empirical studies on Linear Attention mechanisms focus on shallow architectures, leaving the fundamental limits of information propagation in deep networks unquantified. Specifically, it remains unknown if and where the performance degradation occurs as depth increases beyond two layers or when attention windows are fixed, suggesting a potential phase transition rather than a smooth decline. This project aims to map the precise boundary conditions under which Linear Attention fails to support in-context learning, distinguishing between architectural depth limits and window adaptability constraints.

### Formal Objective

To empirically map the boundary conditions (D*, W*) where Linear Attention transitions from supporting to failing in-context learning.

### Ambiguity Flags

- Functional vs. Non-functional: The specific performance threshold that defines the transition from functional to non-functional is not explicitly defined in the source evidence.
- Task Complexity: The relationship between task complexity and the phase transition is mentioned but not formalized.

## reasoning_models_test_time_compute

- final_family_id: family:01
- title: Characterizing the Identifiability Boundary of Bootstrapped Reasoning under Unverifiable Feedback
- judge mean overall formulation quality: 7.25
- judges: 4
- selected reason: selected by highest mean_overall_formulation_quality=7.25, median=7.0, max=8.0, tie_break_mean_wellposed_formal_source_ambiguity=7.4375

### Problem Statement

Current self-improvement frameworks like STaR collapse when training data contains non-verifiable responses or negative examples, relying on an idealized assumption of ground-truth availability. This reliance prevents the generalization of learned reasoning strategies to out-of-distribution tasks where verification is impossible or ambiguous. The core failure is not merely a lack of robustness but a fundamental breakdown in the learning signal when the verifier itself is absent or unreliable.

### Formal Objective

To identify the set of conditions C such that if (V, D) satisfies C, then the bootstrapping process converges to P; otherwise, the process converges to a spurious pattern or fails.

### Ambiguity Flags

- Unverifiable Feedback: The term is used to describe both the absence of a verifier and the presence of a verifier that is unreliable or ambiguous.
- Spurious Pattern: The source evidence mentions learning spurious patterns but does not define the structural properties of these patterns.
- boundary: This term may hide multiple operational meanings in the source family.

## offline_reinforcement_learning_arxiv

- final_family_id: family:01
- title: Characterizing the Failure Regime of Q-Learning in Offline RL via Distributional Shift
- judge mean overall formulation quality: 6.0
- judges: 4
- selected reason: selected by highest mean_overall_formulation_quality=6.0, median=6.0, max=7.0, tie_break_mean_wellposed_formal_source_ambiguity=6.6875

### Problem Statement

Existing literature treats Q-learning as a monolithic baseline in offline reinforcement learning, failing to distinguish between its successes and catastrophic failures across diverse data distributions. This lack of granular empirical validation obscures the specific structural conditions under which Q-learning's implicit regularization breaks down. Consequently, the field lacks a standardized understanding of the boundary between safe exploration and distributional collapse in offline settings.

### Formal Objective

To identify the critical threshold theta such that for all delta > theta, the algorithm Q diverges or fails to converge to the optimal policy, and for delta < theta, Q converges stably.

### Ambiguity Flags

- Catastrophic overestimation: The term implies divergence to infinity but could also refer to severe bias without divergence; the exact mathematical definition of 'catastrophic' is not provided.
- Support mismatch: While intuitively understood as the difference between behavior and data supports, the specific metric (e.g., KL divergence, set difference measure) is not defined.
- mismatch: This term may hide multiple operational meanings in the source family.

## uncertainty_calibration_conformal_prediction_arxiv

- final_family_id: family:03
- title: Characterizing the Fragility Boundary of Distribution-Free Conformal Prediction Under Extreme Label Shift
- judge mean overall formulation quality: 6.25
- judges: 4
- selected reason: selected by highest mean_overall_formulation_quality=6.25, median=6.0, max=8.0, tie_break_mean_wellposed_formal_source_ambiguity=7.0

### Problem Statement

Current conformal prediction guarantees claim distribution-free validity, yet empirical evidence suggests these guarantees collapse under severe label shifts. The critical missing component is a rigorous characterization of the boundary between valid and invalid regimes, rather than mere validation of specific methods in new settings. This project seeks to define the precise conditions under which distribution-free validity fails.

### Formal Objective

To define the set FragilityBoundary = { delta | exists C in C such that Coverage(C, P', alpha) < 1-alpha } and identify the minimal magnitude and structure of delta within this set.

### Ambiguity Flags

- Severe label shift: The term 'severe' is qualitative and lacks a precise mathematical definition in the source evidence.
- Fragility boundary: The exact nature of the boundary (e.g., a specific value, a region, or a phase transition) is not explicitly defined in the source.
- boundary: This term may hide multiple operational meanings in the source family.
