# Prompt Inventory

Runtime prompts from paper runs are not included because they may contain paper text. This directory contains safe public prompt descriptions and templates.

Source prompt implementations:

- Extraction: `src/sgha/prompt_templates.py`
- Resolution extraction: `src/sgha/prompt_templates.py`
- Counterevidence classification: `src/sgha/prompt_templates.py`
- Direct formulation and ambition expansion: `src/sgha/direct_formulation.py`, `src/sgha/ambition_expansion.py`
- Formal problem formulation: `src/sgha/formal_problem.py`
- Judge prompts: `scripts/run_llm_judge_openrouter.py`
- Retrieval query planning: `src/retrieval/prompts/query_planner_prompt.txt`

The files below are release-safe summaries or templates. They are not raw prompts from any paper run.
