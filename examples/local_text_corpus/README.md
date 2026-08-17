# Local Text Corpus Example

This is a tiny offline SGHA example project. All paper texts are synthetic and are included only to demonstrate the public repository workflow and output structure.

## Files

- `config.yaml`: offline-safe SGHA example config with retrieval disabled and `llm.mock: true`.
- `papers.jsonl`: one JSON record per synthetic paper.
- `papers/`: short synthetic text files referenced by `papers.jsonl`.
- `expected_outputs/README.md`: notes on the mock output tree written by `sgha smoke-test`.

## Try It

From the repository root:

```bash
sgha validate-config examples/local_text_corpus/config.yaml
sgha smoke-test --example-config examples/local_text_corpus/config.yaml
```

The smoke test writes a temporary mock run directory and prints its path. It does not call an LLM, OpenRouter, a paper API, or the network.

## Use Your Own Papers

Copy this directory and replace the synthetic files under `papers/` with your own local paper text files. Then edit `papers.jsonl` so each line has:

- `paper_id`
- `title`
- `authors`
- `year`
- `source`
- `text_path` or `pdf_path`
- optional `abstract`

For the simplest path, provide parsed text with `text_path`. The `sgha prepare-local-corpus` helper requires local text files; it does not parse PDFs. If you use `pdf_path`, keep the PDFs local and do not commit them to a public repository unless you have redistribution rights.

The most important config fields are:

- `output_root`: where SGHA writes the `runs/<run_id>/` directory.
- `dataset_root`: where local corpus metadata can live.
- `corpus.manifest_path`: path to `papers.jsonl`.
- `retrieval.enabled`: keep this `false` when using a local corpus.
- `llm.base_url` and `llm.model`: the OpenAI-compatible endpoint and model for model-backed stages.

For a local OpenAI-compatible model server:

```bash
export SGHA_LLM_BASE_URL=http://localhost:8000/v1
export SGHA_LLM_MODEL=your-local-model-name
```

The offline smoke test uses mock outputs only. Model-backed SGHA stages require your own endpoint and are described in `docs/run_on_your_own_papers.md`.
