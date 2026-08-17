# Formulation-Only Rubric

Judge research-problem formulation quality only. Do not judge implementation plans, experiment plans, project management, actionability, or prose polish except where they clarify the formulation itself. Do not claim external novelty; novelty is potential from the provided text only.

Scores are 0-10:
- 0-2: poor / not a usable research-problem formulation
- 3-4: weak / vague / major missing pieces
- 5-6: plausible but needs substantial refinement
- 7-8: strong research-problem formulation
- 9-10: exceptional, unusually precise and compelling

Criteria:
1. `problem_definition_clarity_10`: core problem is clear, bounded, and stated as a problem rather than a topic.
2. `technical_specificity_10`: technical objects, setting, and question are specific enough for rigorous follow-up.
3. `well_posedness_10`: entities/variables, assumptions, objective, and observation/evidence setting are defined.
4. `assumption_boundary_clarity_10`: assumption shift, failure boundary, or regime distinction is explicit.
5. `formalizability_10`: provided text can be cast as a formal problem without inventing major missing details.
6. `nontriviality_10`: more than a minor variant, apply-X-to-Y, or routine stress test.
7. `scope_control_10`: focused rather than a loose bundle of concepts.
8. `source_grounded_specificity_10`: motivated by concrete source papers, source IDs, gaps, or context items.
9. `ambiguity_hygiene_10`: missing definitions or ambiguous terms are acknowledged honestly.
10. `overall_formulation_quality_10`: overall strength of the research-problem formulation.

Hard caps:
- If the problem is vague, `overall_formulation_quality_10 <= 6`.
- If `formal_problem_statement` is `not provided`, `well_posedness_10 <= 6` and `formalizability_10 <= 6`.
- If `assumptions_or_problem_setup` is `not provided`, `well_posedness_10 <= 6` and `assumption_boundary_clarity_10 <= 6`.
- If `ambiguity_or_missing_definitions` is `not provided`, `ambiguity_hygiene_10 <= 6`.
- If `source_context_or_grounding` is `not provided`, `source_grounded_specificity_10 <= 4`.
- If the candidate combines many loosely related concepts, `scope_control_10 <= 4`.
- If the idea is mainly apply X to Y or test X under condition Y, `nontriviality_10 <= 6`.
- If there is no clear formal skeleton, `overall_formulation_quality_10 <= 7`.

Reviewer reminders:
- Penalize polished but underspecified ideas.
- Penalize missing formal structure.
- Penalize term-soup.
- Reward precise assumption shifts, clear objectives, and source-grounded problem boundaries.
- Do not compute weighted composite scores.
- Do not run pairwise comparisons.
