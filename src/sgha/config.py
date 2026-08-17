from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


def deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_paths: list[str | Path] | None = None, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = load_yaml(DEFAULT_CONFIG_PATH)
    for path in config_paths or []:
        cfg = deep_merge(cfg, load_yaml(path))
    cfg = deep_merge(cfg, env_overrides())
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg


def env_overrides() -> dict[str, Any]:
    out: dict[str, Any] = {}
    mapping = {
        "SGHA_OUTPUT_ROOT": ("output_root",),
        "SGHA_DATASET_ROOT": ("dataset_root",),
        "SGHA_MODEL_CACHE_ROOT": ("model_cache_root",),
        "SGHA_QUERY": ("query",),
        "SGHA_MAX_RESULTS": ("max_results",),
        "SGHA_LLM_BASE_URL": ("llm", "base_url"),
        "SGHA_LLM_MODEL": ("llm", "model"),
        "SGHA_LLM_MOCK": ("llm", "mock"),
    }
    for env_key, path in mapping.items():
        if env_key not in os.environ:
            continue
        value: Any = os.environ[env_key]
        if env_key == "SGHA_MAX_RESULTS":
            value = int(value)
        if env_key == "SGHA_LLM_MOCK":
            value = value.lower() in {"1", "true", "yes", "on"}
        node = out
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = value
    return out


def config_get(config: Mapping[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = config
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return default
        cur = cur[part]
    return cur


def cli_overrides(**kwargs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    direct = {
        "query": ("query",),
        "max_results": ("max_results",),
        "output_root": ("output_root",),
        "dataset_root": ("dataset_root",),
        "llm_base_url": ("llm", "base_url"),
        "mock_llm": ("llm", "mock"),
        "generations": ("evolution", "generations"),
        "population_size": ("evolution", "population_size"),
        "skeptic_external_arxiv": ("verification", "skeptic_external_arxiv"),
    }
    for key, path in direct.items():
        if kwargs.get(key) is None:
            continue
        node = out
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = kwargs[key]
    return out
