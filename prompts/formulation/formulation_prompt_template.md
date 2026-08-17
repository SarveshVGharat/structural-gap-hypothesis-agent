# Formulation Prompt Template

Purpose: convert verified structural gaps into research-problem formulations, ambition-expanded variants, consolidated project families, and formal problem statements.

Inputs:

- verified gap records
- evidence trail
- optional family/context records

Output: strict JSON records with source IDs, problem statement, assumptions, ambiguity flags, variables, objective, evaluation model, and provenance.

Implementations: `src/sgha/direct_formulation.py`, `src/sgha/ambition_expansion.py`, `src/sgha/family_quality.py`, and `src/sgha/formal_problem.py`.
