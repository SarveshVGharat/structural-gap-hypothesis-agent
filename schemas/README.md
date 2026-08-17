# Schema Inventory

The authoritative schemas are Pydantic models in the code:

- extraction: `src/sgha/extraction_schemas.py`
- candidate gap: `src/sgha/gap_objects.py::CandidateGap`
- verification: `src/sgha/gap_objects.py::VerificationResult`
- final hypothesis and formal problem: `src/sgha/gap_objects.py`
- retrieval: `src/retrieval/models.py`
- judge packets and candidates: `scripts/run_llm_judge_openrouter.py`

The JSON files in this directory are lightweight public schema summaries for release navigation. Regenerate them from Pydantic models before the final GitHub release if exact machine validation is needed.
