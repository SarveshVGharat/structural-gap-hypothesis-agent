# Judging

LLM-as-judge evaluation is optional. The public staging copy includes:

- `scripts/run_llm_judge_openrouter.py`
- `configs/judging/openrouter_llm_judge.example.yaml`
- `prompts/judging/judge_prompt_template.md`
- `schemas/judge_response.schema.json`

Live judging requires an environment variable named `OPENROUTER_API_KEY`. Do not commit credential files, raw judge responses, or full live output directories.

No API keys are included in this repository. Existing paper score tables can be inspected from `paper_artifacts/release_bundle/judge_scores/` and `paper_artifacts/release_bundle/tables/` without rerunning OpenRouter judging.

Preferred public workflow:

1. Build or inspect blinded packets offline.
2. Validate packets with mock responses or dry-run options.
3. Run live scoring only after explicitly configuring credentials.
4. Postprocess/unblind after scoring is complete.
5. Publish only curated summary tables, manifests, and checksums.

Help-only smoke check:

```bash
python scripts/run_llm_judge_openrouter.py --help
```

The example config is safe to commit because it contains env-var names, not credential values.
