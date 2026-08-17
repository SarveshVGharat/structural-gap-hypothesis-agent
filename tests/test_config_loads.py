from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_default_config_loads() -> None:
    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
    assert cfg["output_root"]
    assert cfg["llm"]["base_url"]
    assert cfg["retrieval"]["enabled"] is True


def test_example_configs_load() -> None:
    for path in [
        ROOT / "configs" / "examples" / "minimal_mock.yaml",
        ROOT / "configs" / "examples" / "local_vllm_example.yaml",
        ROOT / "examples" / "local_text_corpus" / "config.yaml",
        ROOT / "configs" / "judging" / "openrouter_llm_judge.example.yaml",
    ]:
        cfg = yaml.safe_load(path.read_text())
        assert isinstance(cfg, dict)


def test_configs_have_no_private_paths_or_hosts() -> None:
    forbidden = ["/" + "users" + "/student/", "/" + "jan" + "aki/", "an" + "andi"]
    for path in [
        ROOT / "configs" / "default.yaml",
        ROOT / "configs" / "examples" / "minimal_mock.yaml",
        ROOT / "configs" / "examples" / "local_vllm_example.yaml",
        ROOT / "examples" / "local_text_corpus" / "config.yaml",
        ROOT / "configs" / "judging" / "openrouter_llm_judge.example.yaml",
    ]:
        text = path.read_text()
        assert not any(item in text for item in forbidden)
