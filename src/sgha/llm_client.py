from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from .json_repair import parse_json_with_repair
from .utils import append_jsonl, ensure_dir, stable_id, utc_now_iso, write_json, write_text


class LLMClient:
    def __init__(self, run_context: Any, *, base_url: str | None = None, model: str | None = None, mock: bool | None = None):
        cfg = run_context.config.get("llm", {})
        self.ctx = run_context
        self.base_url = base_url or cfg.get("base_url", "http://localhost:8000/v1")
        self.model = model or cfg.get("model", "Qwen/Qwen3.5-9B")
        self.api_key = cfg.get("api_key", "EMPTY")
        self.temperature = float(cfg.get("temperature", 0.1))
        self.max_tokens = int(cfg.get("max_tokens", 4096))
        self.timeout = float(cfg.get("timeout_seconds", 180))
        self.retries = int(cfg.get("retries", 3))
        self.mock = bool(cfg.get("mock", False) if mock is None else mock)

    def complete_json(self, *, stage: str, agent_name: str, prompt: str, schema_name: str = "response",
                      max_tokens: int | None = None, temperature: float | None = None,
                      enable_thinking: bool | None = None) -> tuple[dict[str, Any], Path, Path, Path]:
        call_id = stable_id("llm", self.ctx.run_id, stage, agent_name, time.time())
        prompt_path = self.ctx.path("prompts", self._prompt_subdir(agent_name, stage), f"{call_id}.md")
        raw_path = self.ctx.path("llm_raw_outputs", self._raw_subdir(stage), f"{call_id}.txt")
        parsed_path = self.ctx.path("llm_parsed_outputs", self._raw_subdir(stage), f"{call_id}.json")
        write_text(prompt_path, prompt)
        t0 = time.time()
        success = False
        error = ""
        usage: dict[str, Any] = {}
        try:
            raw = self._mock_response(agent_name, prompt) if self.mock else self._complete(
                prompt, max_tokens=max_tokens, temperature=temperature, enable_thinking=enable_thinking)
            write_text(raw_path, raw)
            parsed = parse_json_with_repair(raw)
            if not isinstance(parsed, dict):
                parsed = {"items": parsed}
            write_json(parsed_path, parsed)
            success = True
            return parsed, prompt_path, raw_path, parsed_path
        except Exception as exc:
            error = str(exc)
            write_text(raw_path, error)
            write_json(parsed_path, {"error": error})
            raise
        finally:
            latency = time.time() - t0
            append_jsonl(
                self.ctx.path("logs", "llm_calls.jsonl"),
                {
                    "timestamp": utc_now_iso(),
                    "run_id": self.ctx.run_id,
                    "stage": stage,
                    "agent_name": agent_name,
                    "model": self.model,
                    "prompt_path": str(prompt_path),
                    "raw_prompt": prompt,
                    "raw_response_path": str(raw_path),
                    "parsed_response_path": str(parsed_path),
                    "token_usage_if_available": usage,
                    "latency_seconds": latency,
                    "success": success,
                    "failure": error,
                    "mock": self.mock,
                    "schema_name": schema_name,
                },
            )

    def _prompt_subdir(self, agent_name: str, stage: str) -> str:
        if stage == "extraction":
            return "extraction"
        if agent_name in {"support_agent", "skeptic_agent", "feasibility_agent", "mechanism_agent", "critic"}:
            return agent_name
        return "evolution"

    def _raw_subdir(self, stage: str) -> str:
        if stage == "extraction":
            return "extraction"
        if stage in {"critic"}:
            return "critic"
        if stage in {"evolution"}:
            return "evolution"
        return "verification"

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(3))
    def _complete(self, prompt: str, *, max_tokens: int | None = None,
                  temperature: float | None = None, enable_thinking: bool | None = None) -> str:
        from openai import OpenAI

        # Per-call overrides fall back to instance defaults when not provided.
        _max_tokens = self.max_tokens if max_tokens is None else int(max_tokens)
        _temperature = self.temperature if temperature is None else float(temperature)

        client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)
        system = {"role": "system", "content": "You return strict JSON only. No markdown fences."}

        # Pass 1: thinking on by default. For short, structured tasks (e.g. the
        # counterevidence classifier) callers pass enable_thinking=False to skip the
        # long reasoning trace, which is the dominant latency cost on Qwen3.5.
        create_kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=[system, {"role": "user", "content": prompt}],
            temperature=_temperature,
            max_tokens=_max_tokens,
        )
        if enable_thinking is False:
            create_kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        response = client.chat.completions.create(**create_kwargs)
        msg = response.choices[0].message
        content = (msg.content or "").strip()
        reasoning = (msg.model_extra or {}).get("reasoning", "") or ""

        # If the model put all its work in thinking and output nothing useful,
        # do a second pass: feed reasoning as context, ask for JSON only (no thinking)
        if reasoning and (not content or content == "{}"):
            response2 = client.chat.completions.create(
                model=self.model,
                messages=[
                    system,
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "I have carefully analyzed the paper."},
                    {
                        "role": "user",
                        "content": (
                            "Here is my analysis of the paper:\n\n"
                            + reasoning
                            + "\n\nBased on this analysis, output the final JSON object only. No other text."
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=_max_tokens,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = (response2.choices[0].message.content or "{}").strip()

        return content or "{}"

    @classmethod
    def _expand_env_vars(cls, value: str) -> str:
        """Expand ${VAR:-default} and ${VAR} patterns from environment."""
        def _replace(m: re.Match) -> str:
            var = m.group(1)
            default = m.group(2) if m.group(2) is not None else ""
            return os.environ.get(var, default)
        return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)(?::-(.*?))?\}", _replace, value)

    def _mock_response(self, agent_name: str, prompt: str) -> str:
        if agent_name == "extraction":
            paper_id = "unknown"
            for line in prompt.splitlines():
                if line.startswith("Paper ID:"):
                    paper_id = line.split(":", 1)[1].strip()
                    break
            return json.dumps(
                {
                    "paper_id": paper_id,
                    "methods": ["prompt perturbation robustness analysis"],
                    "tasks": ["language model reasoning"],
                    "datasets": ["insufficient evidence"],
                    "metrics": ["accuracy"],
                    "assumptions": ["prompts are semantically stable under perturbation"],
                    "results": ["robustness varies under prompt perturbations"],
                    "limitations": ["limited evaluation under adversarial prompt shifts"],
                    "failure_conditions": ["prompt perturbation"],
                    "claims": ["reasoning performance can be brittle to prompt wording"],
                    "contradictions_or_tensions": [],
                    "tuples": [
                        {
                            "subject": "prompt perturbation robustness analysis",
                            "relation": "fails_under",
                            "object": "prompt perturbation",
                            "evidence_text": "mock extraction for audit smoke test",
                            "section": "mock",
                            "confidence": 0.5,
                        },
                        {
                            "subject": "prompt perturbation robustness analysis",
                            "relation": "limited_by",
                            "object": "limited evaluation under adversarial prompt shifts",
                            "evidence_text": "mock extraction for audit smoke test",
                            "section": "mock",
                            "confidence": 0.5,
                        },
                    ],
                }
            )
        return json.dumps(
            {
                "gap_id": "mock-gap",
                "agent_name": agent_name,
                "summary": "mock response generated for smoke testing",
                "evidence": [],
                "counterevidence": [],
                "citations": [],
                "confidence": 0.5,
                "failure_modes": ["mock mode is not scientific evidence"],
                "scores": {
                    "evidence_diversity": 0.5,
                    "failure_recurrence": 0.5,
                    "novelty_after_counterevidence": 0.5,
                    "experimentability": 0.5,
                    "mechanism_plausibility": 0.5,
                    "traceability": 0.5,
                    "already_solved_score": 0.0,
                    "extraction_uncertainty": 0.2,
                },
            }
        )


def get_role_llm_client(ctx: Any, role: str) -> "LLMClient":
    """Return an LLMClient configured for the given role.

    Reads ctx.config["llm"]["models"][role] if present, expands env var patterns,
    falls back to default model/base_url. Performs a GET /models health check.
    """
    cfg = ctx.config.get("llm", {})
    models_cfg = cfg.get("models", {})
    role_cfg = models_cfg.get(role, {})

    if role_cfg:
        raw_url = role_cfg.get("base_url", cfg.get("base_url", "http://localhost:8000/v1"))
        raw_model = role_cfg.get("model", cfg.get("model", "Qwen/Qwen3.5-9B"))
    else:
        raw_url = cfg.get("base_url", "http://localhost:8000/v1")
        raw_model = cfg.get("model", "Qwen/Qwen3.5-9B")

    base_url = LLMClient._expand_env_vars(raw_url)
    model = LLMClient._expand_env_vars(raw_model)

    print(f"[role_llm] role={role} model={model} base_url={base_url}", flush=True)

    # Health check
    import urllib.request
    health_url = base_url.rstrip("/").removesuffix("/v1") + "/v1/models"
    try:
        with urllib.request.urlopen(health_url, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Health check returned HTTP {resp.status}")
    except Exception as exc:
        raise RuntimeError(f"[role_llm] LLM endpoint {health_url} unavailable: {exc}") from exc

    return LLMClient(ctx, base_url=base_url, model=model)
