# Sanitized Paper Run Configs

These YAML files document public-safe approximations of the paper runs. They are intended to show corpus budgets, source types, model families, enabled stages, verification gates, baseline modes, and judge settings without exposing private paths or runtime artifacts.

- `main_domains/` covers the five SGHA paper domains with selected paper budget 250 and a local OpenAI-compatible model placeholder.
- `profile_conditioned/` covers the Yann LeCun, Geoffrey Hinton, and Michael I. Jordan profile-conditioned runs.
- `judging/` documents formulation-only and personalized judge settings. Rerunning judges requires a user-provided `OPENROUTER_API_KEY`; no key is included.
- `baselines/` documents AI-Scientist-v2 Qwen, AI-Scientist-v2 Claude Opus, and MOOSE-Star public-model baseline settings.

These configs are documentation artifacts, not raw runtime configs. Raw papers, parsed full texts, raw prompts, raw model responses, logs, caches, private paths, secret values, and full run directories are excluded.
