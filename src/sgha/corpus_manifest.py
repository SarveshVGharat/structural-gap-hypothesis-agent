from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .extraction_schemas import ArxivPaper
from .utils import model_dump, model_validate, read_json, write_csv, write_json


def write_manifest(run_dir: Path, papers: list[ArxivPaper]) -> None:
    rows = [model_dump(p) for p in papers]
    write_json(run_dir / "arxiv" / "papers_manifest.json", rows)
    write_csv(run_dir / "arxiv" / "papers_manifest.csv", rows)


def read_manifest(run_dir: Path) -> list[ArxivPaper]:
    data = read_json(run_dir / "arxiv" / "papers_manifest.json", default=[])
    return [model_validate(ArxivPaper, item) for item in data]


def read_manifest_csv(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
