# Output Structure

SGHA writes one run directory with stage-specific subdirectories. The exact files can vary by configuration and resume state, so tools should handle missing files gracefully.

## Common Stage Directories

- `extracted/`: paper-level extractions and scientific tuples.
- `graph/`: graph exports and graph summary files.
- `gaps/`: candidate structural gaps.
- `verification/`: support, skeptic, feasibility, mechanism, or other verification outputs.
- `stage7_direct_formulations/`: direct problem formulations from verified gaps.
- `stage8_ambition_expansion/`: expanded or more ambitious formulation variants.
- `stage9_family_quality/`: family grouping and quality scores.
- `stage10_formal_problem_formulations/`: formal problem statements.
- `final_sgha_family_report/`: final family JSON and human-readable report files.

## Offline Demo Files

`sgha smoke-test` writes a mock tree with representative files:

- `extracted/all_extractions.json`
- `extracted/all_tuples.jsonl`
- `graph/graph.json`
- `graph/graph_summary.json`
- `gaps/candidate_gaps.json`
- `verification/verification_results.jsonl`
- `verification/verified_gaps.json`
- `stage7_direct_formulations/direct_formulations.jsonl`
- `stage8_ambition_expansion/expanded_formulations.jsonl`
- `stage9_family_quality/family_quality_scores.json`
- `stage10_formal_problem_formulations/formal_problem_formulations.jsonl`
- `final_sgha_family_report/final_project_families.json`
- `final_sgha_family_report/formal_problem_statements.json`
- `final_sgha_family_report/final_report.md`
- `RUN_SUMMARY.json`

These files are synthetic teaching outputs. They do not reproduce the SGHA paper results.

## Summary Helper

Use either command:

```bash
sgha summarize-run /path/to/run_dir
python scripts/summarize_run_outputs.py --run-dir /path/to/run_dir
```

The summary reports the available counts for extracted papers, tuples, candidate gaps, verified gaps, direct formulations, final families, formal problems, and the final report path. Missing files are reported as zero or `not found`.
