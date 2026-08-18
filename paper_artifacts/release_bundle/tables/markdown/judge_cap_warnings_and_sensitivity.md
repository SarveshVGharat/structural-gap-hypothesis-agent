# Judge Cap Warnings and Sensitivity

Sensitivity caveat: excluding flagged candidates, SGHA_FULL remains higher on overall formulation quality (6.3077 vs. 4.9231) per source caveat. Claude Opus same-provider sensitivity is in the source path manifest.

|domain|method|candidate_id|title|violated cap rule|score field|score|severity|retry still violated|
|---|---|---|---|---|---|---|---|---|
|Uncertainty / calibration / conformal prediction|SGHA_FULL|Candidate 016|Characterizing the Fragility Boundary of Distribution-Free Conformal Prediction Under Extreme Label Shift|many_loose_concepts_but_scope_control_above_4|scope_control_10|8|MINOR|True|
|Bandits|SGHA_FULL|Candidate 020|Characterizing the Non-Convex Failure Regime of Diffusion-Based Contextual Bandits|many_loose_concepts_but_scope_control_above_4|scope_control_10|6|MODERATE|True|
|Bandits|NATIVE_AI_SCIENTIST_V2|Candidate 023|Bandits with Adversarial Arm Execution: Robust Learning When Your Choices Don't Match Reality|many_loose_concepts_but_scope_control_above_4|scope_control_10|7|MODERATE|True|
|Uncertainty / calibration / conformal prediction|NATIVE_AI_SCIENTIST_V2|Candidate 027|Fair Conformal Prediction: Subgroup-Aware Uncertainty Quantification with Coverage Guarantees|many_loose_concepts_but_scope_control_above_4|scope_control_10|7|MODERATE|True|
