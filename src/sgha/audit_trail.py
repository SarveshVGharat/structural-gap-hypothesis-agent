from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .utils import append_jsonl, utc_now_iso


class AuditTrail:
    def __init__(self, path: str | Path, run_id: str):
        self.path = Path(path)
        self.run_id = run_id

    def event(self, event_type: str, **payload: Any) -> None:
        append_jsonl(
            self.path,
            {
                "timestamp": utc_now_iso(),
                "run_id": self.run_id,
                "event_type": event_type,
                **payload,
            },
        )

    def failure(self, stage: str, error: BaseException | str, **payload: Any) -> None:
        record = {"stage": stage, "error": str(error), **payload}
        self.event("failure", **record)
        append_jsonl(self.path.parent / "errors.jsonl", {"timestamp": utc_now_iso(), "run_id": self.run_id, **record})


def audit_event(path: str | Path, run_id: str, event_type: str, payload: Mapping[str, Any] | None = None) -> None:
    AuditTrail(path, run_id).event(event_type, **dict(payload or {}))
