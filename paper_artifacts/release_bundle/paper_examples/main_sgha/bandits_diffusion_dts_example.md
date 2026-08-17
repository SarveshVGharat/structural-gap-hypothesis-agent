# Bandits Diffusion dTS Running Example

Sanitization note: this example is derived from existing public bundle artifacts. It keeps generated candidate text, source IDs, and score metadata, but excludes raw papers, parsed full texts, private paths, raw prompts, raw model responses, logs, and caches.

## Provenance

- method: SGHA_FULL
- domain: bandits
- final_family_id: family:03
- representative_variant_id: var:09
- source_verified_gap_ids: ["gap:5b3e0ad02d0b1944"]
- source_direct_formulation_ids: ["direct:03"]
- supporting_paper_ids: ["openreview:GGAG3wFEKv", "openreview:nEnazjpwOx"]
- note: Bandits diffusion/dTS example used to illustrate evidence-graph and formulation flow.

## Title

Characterizing the Non-Convex Failure Regime of Diffusion-Based Contextual Bandits

## Problem Formulation

Diffusion-based contextual bandit algorithms like dTS rely on Gaussian posterior approximations derived from linear link functions. This assumption breaks down when score functions are non-linear, causing the posterior to diverge from the true reward distribution. The central problem is not merely fixing dTS for non-linearities, but characterizing the fundamental boundary where diffusion-based inference fails to identify optimal policies due to non-convexity in the score landscape.

## Proposal-Style Abstract

This project studies the fundamental limits of diffusion-based inference in sequential decision-making when the underlying reward structure violates linearity. The central question is identifying the precise geometric and topological conditions under which the Gaussian approximation inherent to diffusion models becomes a catastrophic failure mode, leading to unbounded regret. A successful outcome would establish a rigorous impossibility boundary defining the class of non-linear score functions for which no diffusion-based algorithm can guarantee sublinear regret without explicit non-linearity correction. This work moves beyond algorithmic patching to define the structural prerequisites for the validity of diffusion priors in bandit settings.

## Formal Problem Statement

Let $\mathcal{F}$ be a class of score functions mapping contexts to rewards. The problem is to determine the necessary conditions on the curvature and convexity of functions in $\mathcal{F}$ such that diffusion-based inference (relying on Gaussian posterior approximations) guarantees sublinear regret. Specifically, we seek to identify the phase transition boundary where the Gaussian approximation diverges from the true reward distribution due to non-convexity in the score landscape, rendering the algorithm incapable of identifying the optimal policy.

## Variables And Notation

- `$\mathcal{F}$` (set): Class of score functions mapping contexts to rewards
- `$\pi_{diff}$` (process): Diffusion-based inference algorithm relying on Gaussian approximation
- `$\mathcal{R}_{true}$` (distribution): True reward distribution induced by the score function
- `$\mathcal{R}_{approx}$` (distribution): Approximated reward distribution derived from Gaussian posterior
- `$\mathcal{L}(f)$` (function): Score landscape associated with score function $f$
- `$\mathcal{R}_T$` (scalar): Cumulative regret over time horizon $T$

## Assumptions

- Linear Link Function Assumption (relaxed): The standard dTS algorithm assumes a linear relationship between context and score to derive tractable bounds.
- Gaussian Posterior Approximation (kept): The inference mechanism relies on approximating the posterior with a Gaussian distribution.
- Sequential Decision Constraints (kept): The problem occurs in a sequential setting where actions affect future information.

## Objective

Characterize the boundary conditions on $\mathcal{F}$ such that $\lim_{T \to \infty} \mathcal{R}_T / T = 0$ holds for $\pi_{diff}$, and identify the conditions under which this limit is non-zero or unbounded due to non-convexity.

## Success Criterion

Establishing a rigorous impossibility boundary defining the class of non-linear score functions for which no diffusion-based algorithm can guarantee sublinear regret without explicit non-linearity correction.

## Risks

The boundary might be too narrow or trivial if non-linearities are mild; the result could be that 'only linear works' without interesting intermediate regimes.

## Falsification Condition

Demonstration that diffusion-based methods achieve optimal regret for a broad class of non-linear score functions without modification.

## Ambiguity Flags

- Non-convexity in the score landscape: The specific definition of non-convexity (e.g., non-convex loss, non-convex domain, or non-convex posterior geometry) is not explicitly defined in the source evidence.
- Systematic identification failure: The threshold for 'failure' (e.g., linear regret vs. exponential regret vs. divergence) is not quantified.
- failure: This term may hide multiple operational meanings in the source family.

## Source Grounding

```json
{
  "source_verified_gaps": [
    "gap:5b3e0ad02d0b1944"
  ],
  "supporting_papers": [
    "openreview:GGAG3wFEKv",
    "openreview:nEnazjpwOx"
  ],
  "representative_formulation": "var:09",
  "critic_reason": "The variant shifts the objective from fixing a specific algorithm (dTS) to characterizing a fundamental phase transition in a broader class of diffusion-based inference, moving beyond simple validation to theoretical boundary analysis."
}
```

## Judge Score

- formulation-only judge overall score: 6
- judge confidence: MEDIUM
- recommended action: PROMISING_NEEDS_REFINEMENT
