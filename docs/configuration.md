# Configuration

Configuration files are YAML overlays loaded on top of `configs/default.yaml`.

Important path settings:

- `output_root`: where run outputs are written.
- `dataset_root`: where local datasets and parsed inputs are stored.
- `model_cache_root`: optional model cache location.
- `llm.base_url`: OpenAI-compatible endpoint.
- `llm.model`: served model name.
- `llm.mock`: use deterministic mock behavior for tests and smoke checks.

Public configs must use relative paths or environment-variable placeholders. Do not commit machine-specific absolute paths, private hostnames, account names, tokens, or credential files.

Useful examples:

- `configs/examples/minimal_mock.yaml`: offline smoke configuration.
- `configs/examples/local_vllm_example.yaml`: local OpenAI-compatible model configuration.
- `examples/local_text_corpus/config.yaml`: tiny synthetic local-corpus example used by `sgha smoke-test`.
- `configs/judging/openrouter_llm_judge.example.yaml`: optional live judge configuration that reads credentials from environment variables.

Validation commands:

```bash
sgha validate-config examples/local_text_corpus/config.yaml
sgha smoke-test
sgha prepare-local-corpus examples/local_text_corpus/config.yaml --run-id local_example --output-root /tmp/sgha_local_example
python -m pytest tests/test_config_loads.py -q
```

`configs/default.yaml` intentionally keeps model and path fields configurable through environment-style placeholders. `configs/examples/minimal_mock.yaml` and `examples/local_text_corpus/config.yaml` use local relative paths and `llm.mock: true` for offline checks.
