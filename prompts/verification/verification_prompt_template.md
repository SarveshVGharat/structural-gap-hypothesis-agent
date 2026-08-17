# Verification Prompt Template

Purpose: stress-test candidate gaps with support, skeptic, feasibility, mechanism, critic, and counterevidence roles.

Inputs:

- candidate gap record
- graph/evidence context
- optional in-corpus counterevidence context

Output: strict JSON with confidence, evidence, counterevidence, failure modes, and survival-score components.

Implementations: `src/sgha/verification_agents.py`, `src/sgha/prompt_templates.py`, and `src/sgha/counterevidence_linking.py`.
