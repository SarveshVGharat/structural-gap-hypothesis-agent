from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .audit_trail import AuditTrail
from .logging_utils import setup_logger
from .utils import ensure_dir, run_command_capture, utc_now_iso, write_json, write_text


RUN_SUBDIRS = [
    "logs",
    "arxiv/downloaded_pdfs",
    "parsed/paper_texts",
    "parsed/paper_sections",
    "prompts/extraction",
    "prompts/support_agent",
    "prompts/skeptic_agent",
    "prompts/feasibility_agent",
    "prompts/mechanism_agent",
    "prompts/critic",
    "prompts/evolution",
    "llm_raw_outputs/extraction",
    "llm_raw_outputs/verification",
    "llm_raw_outputs/critic",
    "llm_raw_outputs/evolution",
    "llm_parsed_outputs/extraction",
    "llm_parsed_outputs/verification",
    "llm_parsed_outputs/critic",
    "llm_parsed_outputs/evolution",
    "extracted/per_paper_json",
    "graph/visualizations/top_motif_subgraphs",
    "motifs/motif_subgraphs",
    "gaps",
    "verification",
    "evolution",
    "final",
    "resolution_extractions",
    "counterevidence_discovery",
]


@dataclass
class RunContext:
    config: dict[str, Any]
    run_id: str | None = None
    create: bool = True
    start_times: dict[str, float] = field(default_factory=dict)
    timings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Reject the forbidden personalization key with a clear error (Feature B contract).
        from .personalization import (validate_no_forbidden_personalization_keys,
                                       build_personalized_run_id, deprecated_scholar_warning)
        validate_no_forbidden_personalization_keys(self.config)
        _gs_warn = deprecated_scholar_warning(self.config)
        if _gs_warn:
            import warnings
            warnings.warn(_gs_warn, stacklevel=2)

        pers = self.config.get("personalization", {}) or {}
        self._personalized = bool(pers.get("enabled", False))
        if not self.run_id:
            if self._personalized and (pers.get("output", {}) or {}).get("use_personalized_run_dir", True):
                # personalized_<author_slug>_<topic_slug>_<timestamp>
                self.run_id = build_personalized_run_id(self.config)
            else:
                self.run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        self.output_root = Path(self.config["output_root"])
        self.dataset_root = Path(self.config["dataset_root"])
        self.run_dir = self.output_root / "runs" / self.run_id
        self.logs_dir = self.run_dir / "logs"
        if self.create:
            self.create_dirs()
            if self._personalized:
                # extra dirs only for personalized runs — keeps normal runs unchanged
                for sub in ("profile", "corpus"):
                    ensure_dir(self.run_dir / sub)
            self.write_run_metadata()
        self.audit = AuditTrail(self.logs_dir / "audit_events.jsonl", self.run_id)
        self.logger = setup_logger("sgha", self.logs_dir / "pipeline.log")

    def create_dirs(self) -> None:
        ensure_dir(self.output_root / "logs")
        ensure_dir(self.dataset_root)
        for subdir in RUN_SUBDIRS:
            ensure_dir(self.run_dir / subdir)

    def path(self, *parts: str) -> Path:
        return self.run_dir.joinpath(*parts)

    def dataset_path(self, *parts: str) -> Path:
        return self.dataset_root.joinpath(*parts)

    def write_run_metadata(self) -> None:
        ensure_dir(self.run_dir)
        with (self.run_dir / "run_config.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f, sort_keys=False)
        write_text(self.run_dir / "command.txt", " ".join(sys.argv) + "\n")
        allowed_prefixes = ("SGHA_",)
        allowed_names = {"OPENROUTER_SITE_URL", "SEMANTIC_SCHOLAR_API_KEY"}
        sensitive_fragments = ("KEY", "TOKEN", "SECRET", "PASSWORD")
        env_lines = []
        for k, v in sorted(os.environ.items()):
            if not (k.startswith(allowed_prefixes) or k in allowed_names):
                continue
            value = "[REDACTED]" if any(fragment in k.upper() for fragment in sensitive_fragments) else v
            env_lines.append(f"{k}={value}")
        write_text(self.run_dir / "environment.txt", "\n".join(env_lines) + "\n")
        code_root = self.config.get("code_root") or Path.cwd()
        status = run_command_capture(["git", "status", "--short"], cwd=code_root)
        rev = run_command_capture(["git", "rev-parse", "HEAD"], cwd=code_root)
        write_text(self.run_dir / "git_status.txt", f"HEAD={rev}\n\n{status}\n")
        write_json(self.run_dir / "timing.json", {"run_id": self.run_id, "created_at": utc_now_iso(), "stages": {}})

    def stage_start(self, stage: str) -> None:
        self.start_times[stage] = time.time()
        self.audit.event("stage_start", stage=stage)

    def stage_end(self, stage: str, **payload: Any) -> None:
        elapsed = time.time() - self.start_times.get(stage, time.time())
        self.timings.setdefault("stages", {})[stage] = {"seconds": elapsed, **payload}
        write_json(self.run_dir / "timing.json", {"run_id": self.run_id, "updated_at": utc_now_iso(), **self.timings})
        self.audit.event("stage_end", stage=stage, latency_seconds=elapsed, **payload)

    @classmethod
    def from_existing(cls, run_id: str, config: dict[str, Any]) -> "RunContext":
        return cls(config=config, run_id=run_id, create=True)
