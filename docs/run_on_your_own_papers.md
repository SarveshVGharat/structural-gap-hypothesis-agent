# Run SGHA on Your Own Papers

This guide describes the public-repo path for a local corpus. The offline commands are safe to run without a model. Model-backed SGHA stages require your own OpenAI-compatible endpoint.

## 1. Prepare Local Text or PDFs

Create a project directory with local paper text files:

```text
my_corpus/
  config.yaml
  papers.jsonl
  papers/
    paper_001.txt
    paper_002.txt
```

The easiest public workflow is to provide parsed text via `text_path`. The `sgha prepare-local-corpus` helper requires `text_path`; it does not parse PDFs or copy them. If you use `pdf_path`, keep PDFs local, use the existing SGHA parsing path, and do not commit or redistribute PDFs unless you have the right to do so.

## 2. Create `papers.jsonl`

Each line should be one JSON object:

```json
{"paper_id":"paper-001","title":"Example Paper","authors":["A. Researcher"],"year":2026,"source":"local","text_path":"papers/paper_001.txt","abstract":"Optional short abstract."}
```

Required fields:

- `paper_id`
- `title`
- `authors`
- `year`
- `source`
- `text_path` or `pdf_path`

Optional but useful:

- `abstract`
- `venue`
- `url`
- `doi`

## 3. Choose a Local Model Endpoint

For model-backed stages, SGHA expects an OpenAI-compatible chat endpoint. Start your model server separately, then set:

```bash
export SGHA_LLM_BASE_URL=http://localhost:8000/v1
export SGHA_LLM_MODEL=your-local-model-name
export SGHA_LLM_API_KEY=EMPTY
```

Do not commit real API keys or credential files.

## 4. Copy and Edit a Config

For local model-backed experiments:

```bash
cp configs/examples/local_vllm_example.yaml my_corpus/config.yaml
```

Then set local paths and keep retrieval disabled when using your own corpus:

```yaml
output_root: .
dataset_root: .
corpus:
  manifest_path: papers.jsonl
retrieval:
  enabled: false
llm:
  mock: false
  base_url: ${SGHA_LLM_BASE_URL:-http://localhost:8000/v1}
  model: ${SGHA_LLM_MODEL:-your-local-model-name}
  api_key: ${SGHA_LLM_API_KEY:-EMPTY}
```

Validate without running SGHA:

```bash
sgha validate-config my_corpus/config.yaml
```

## 5. Prepare a Local Run Directory

Stage the local text corpus into the manifest shape used by the existing SGHA stages:

```bash
cd my_corpus
sgha prepare-local-corpus config.yaml --run-id my_local_run
```

This writes metadata under `./runs/my_local_run/` by default because SGHA stores runs under `<output_root>/runs/<run_id>`, and relative `output_root` values are interpreted from the current shell directory. It does not call an LLM, OpenRouter, paper APIs, or the network. It records references to your local text files instead of copying source PDFs into the run directory.

If you prefer a different output location:

```bash
sgha prepare-local-corpus config.yaml --run-id my_local_run --output-root ./sgha_outputs
```

Use the same output root when running later stages.

## 6. Run Model-Backed SGHA Stages

The public CLI exposes SGHA stages individually:

```bash
sgha --help
sgha extract --help
sgha build-graph --help
sgha detect-gaps --help
sgha verify-gaps --help
sgha finalize --help
```

Example sequence after local corpus preparation:

```bash
sgha --config config.yaml extract --run-id my_local_run
sgha --config config.yaml build-graph --run-id my_local_run
sgha --config config.yaml detect-gaps --run-id my_local_run
sgha --config config.yaml verify-gaps --run-id my_local_run
sgha --config config.yaml finalize --run-id my_local_run
```

These stages may call your configured model endpoint. Use individual stages first so you can inspect outputs between steps. The legacy `sgha run-all` command can perform retrieval, parsing, extraction, verification, and finalization, and may call external services depending on the config. Treat it as an advanced command.

The offline demo command is only for learning the output shape:

```bash
sgha smoke-test --example-config examples/local_text_corpus/config.yaml
```

## 7. Inspect Final Outputs

After a mock or real run:

```bash
sgha summarize-run /path/to/run_dir
python scripts/summarize_run_outputs.py --run-dir /path/to/run_dir
```

Final family-level artifacts are normally under:

```text
final_sgha_family_report/
stage10_formal_problem_formulations/
```

See `docs/output_structure.md` for the stage-by-stage output map.
