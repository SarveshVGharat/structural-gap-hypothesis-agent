# Extraction Prompt Template

Purpose: extract structured claims, limitations, assumptions, failures, future work, and graph tuples from a paper.

Inputs:

- paper id
- title
- clipped paper text supplied by the caller
- extraction schema

Output: strict JSON with paper-level fields and tuple records. Evidence fields must use verbatim text from the supplied paper text.

Full implementation: `src/sgha/prompt_templates.py`.
