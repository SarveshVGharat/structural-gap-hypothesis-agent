# Bandits Best SGHA Network Lasso Example

Sanitization note: this example is derived from existing public bundle artifacts. It keeps generated candidate text, source IDs, and score metadata, but excludes raw papers, parsed full texts, private paths, raw prompts, raw model responses, logs, and caches.

## Provenance

- method: SGHA_FULL
- domain: bandits
- final_family_id: family:01
- representative_variant_id: var:05
- source_verified_gap_ids: ["gap:ba210076fbccfacb"]
- source_direct_formulation_ids: ["direct:02"]
- supporting_paper_ids: ["openreview:KWUFlIMn8A", "openreview:WxW4nZMD3D"]
- note: Best retained SGHA Bandits qualitative example in the paper tables.

## Title

Characterizing Identifiability Limits of Structured Bandits Under Piecewise Non-Stationarity

## Problem Formulation

Current robust bandit algorithms for structured action sets, such as Network Lasso, rely on the i.i.d. assumption of context generation. This assumption fails in environments with piecewise constant non-stationarity, leading to unbounded regret and failure in identifying optimal arms. The fundamental question is not merely how to fix a specific algorithm, but whether the network structure itself allows for consistent learning under such distributional shifts, or if a fundamental identifiability barrier exists.

## Proposal-Style Abstract

This project studies the fundamental limits of learning in contextual bandits with network-structured action sets when the underlying data distribution undergoes piecewise constant shifts. The central question is whether the structural constraints imposed by network regularization are sufficient to guarantee consistent policy identification in non-stationary regimes, or if the combination of structural sparsity and temporal drift creates an inherent identifiability gap. A successful outcome would characterize the precise boundary between learnable and unlearnable regimes for this problem class, providing necessary and sufficient conditions for robustness that are independent of any specific algorithmic implementation. This work moves beyond validating a single method to establishing a theoretical framework for the viability of structured learning under non-stationarity.

## Formal Problem Statement

Let $\mathcal{A}$ be a set of actions constrained by a network structure $\mathcal{G}$. Let $\mathcal{D}_t$ denote the distribution of contexts at time $t$. The environment exhibits piecewise constant non-stationarity, meaning $\mathcal{D}_t = \mathcal{D}_{k}$ for $t \in [t_k, t_{k+1})$. The question is whether there exists a sequence of policies $\pi_t$ such that the regret $R_T$ grows sublinearly with time $T$ (or equivalently, whether the optimal arm class is identifiable) solely based on the structural constraints of $\mathcal{G}$, without assuming $\mathcal{D}_t$ is i.i.d. across time.

## Variables And Notation

- `$\mathcal{A}$` (set): Set of available actions
- `$\mathcal{G}$` (set): Network structure constraining action sets
- `$\mathcal{D}_t$` (distribution): Distribution of contexts at time $t$
- `$t_k$` (scalar): Time points where the distribution shifts
- `$\pi_t$` (function): Policy at time $t$
- `$R_T$` (scalar): Cumulative regret up to time $T$

## Assumptions

- Network Structure Constraint (kept): Actions are not chosen freely but are constrained by a specific network topology.
- Piecewise Constant Non-Stationarity (kept): The underlying data distribution changes abruptly at specific time points and remains constant between them.
- i.i.d. Context Generation (removed): The assumption that contexts are generated independently and identically distributed over time.
- Existence of Consistent Learning (questioned): The hypothesis that consistent learning might be possible under these conditions.

## Objective

Characterize the necessary and sufficient conditions for consistent learning (identifiability) in network-structured bandits under piecewise constant non-stationarity.

## Success Criterion

Establishing a precise boundary between regimes where network structure aids robustness versus regimes where structural constraints amplify non-stationarity errors, leading to impossibility.

## Risks

Proving impossibility results requires rigorous mathematical machinery that may be technically demanding and susceptible to counter-examples if the structural assumptions are not precisely defined.

## Falsification Condition

The discovery of a specific non-stationary environment and network topology where consistent learning is achieved despite violating the proposed necessary conditions for failure.

## Ambiguity Flags

- Network Structure: The specific type of network (e.g., graph topology, sparsity pattern) and how it mathematically constrains the action set are not explicitly defined in the evidence.
- Piecewise Constant Non-Stationarity: The evidence does not specify the magnitude of the shift, the frequency of shifts, or the relationship between the shift and the network structure.
- Feedback Model: The specific reward function and the exact nature of the observation process are not detailed.
- boundary: This term may hide multiple operational meanings in the source family.
- feedback_or_measurement_model: The source evidence does not fully specify what is observed or measured.

## Source Grounding

```json
{
  "source_verified_gaps": [
    "gap:ba210076fbccfacb"
  ],
  "supporting_papers": [
    "openreview:KWUFlIMn8A",
    "openreview:WxW4nZMD3D"
  ],
  "representative_formulation": "var:05",
  "critic_reason": "The variant successfully elevates the specific failure of Network Lasso into a fundamental question about identifiability limits for the entire class of structured bandits under non-stationarity, moving beyond algorithmic repair to theoretical impossibility boundaries."
}
```

## Judge Score

- best-candidate mean overall formulation quality: 6.25
- judges: 4; median/max/min: 6.0/7.0/6.0
- selected reason: selected by highest mean_overall_formulation_quality=6.25, median=6.0, max=7.0, tie_break_mean_wellposed_formal_source_ambiguity=6.75
- formulation-only judge overall score: 7
- judge confidence: HIGH
- recommended action: PROMISING_NEEDS_REFINEMENT
