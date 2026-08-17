# Expected Offline Outputs

`sgha smoke-test` creates a temporary mock run directory with the same high-level stage names used by SGHA:

- `extracted/`
- `graph/`
- `gaps/`
- `verification/`
- `stage7_direct_formulations/`
- `stage8_ambition_expansion/`
- `stage9_family_quality/`
- `stage10_formal_problem_formulations/`
- `final_sgha_family_report/`

The files are synthetic teaching artifacts. They are useful for learning the output shape, testing installation, and exercising summary tooling. They do not reproduce SGHA paper results and should not be interpreted as scientific findings.
