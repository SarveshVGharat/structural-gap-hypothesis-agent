# Baselines

The staging tree includes wrapper scripts for public-facing baseline comparisons:

- `scripts/run_baseline_ai_scientist_v2_ideation.py`
- `scripts/run_baseline_simple_qwen_ideation.py`
- `scripts/run_baseline_qwen_rag_ideation.py`
- `scripts/run_baseline_moose_star_public_model.py`

Baseline wrappers are designed to avoid reading SGHA graph, gap, verification, and finalization outputs as input. They should use selected corpus metadata or parsed chunks only, depending on the baseline.

Third-party baseline repositories are not copied wholesale into this staging tree. AI-Scientist-v2 reproduction requires the user to obtain the upstream AI-Scientist-v2 code or dependency outside this repository. Before final release, document upstream repository URLs, commit hashes, license compatibility, and any patch files needed to reproduce baseline behavior.

Start with mock or validation-only modes before any live model inference:

```bash
python scripts/run_baseline_ai_scientist_v2_ideation.py --help
python scripts/run_baseline_simple_qwen_ideation.py --help
python scripts/run_baseline_qwen_rag_ideation.py --help
python scripts/run_baseline_moose_star_public_model.py --help
```

Artifact-only inspection:

- Existing baseline candidate outputs and score summaries are included in `paper_artifacts/release_bundle/baselines/`, `paper_artifacts/release_bundle/candidate_packets/`, and `paper_artifacts/release_bundle/judge_scores/`.
- Users can inspect those paper artifacts without rerunning any baseline or judge.

Notes:

- AI-Scientist-style, Simple Qwen, and Qwen RAG wrappers can use local OpenAI-compatible endpoints and expose mock options.
- MOOSE-Star requires a user-provided MOOSE repository plus user-managed access to the public model or model path unless running validation-only behavior.
- Do not commit third-party repositories, checkpoints, or baseline run outputs.
