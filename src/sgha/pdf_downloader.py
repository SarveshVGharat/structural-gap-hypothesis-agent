from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .utils import append_jsonl, ensure_dir, sha256_file, utc_now_iso


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))
def download_pdf(url: str, output_path: str | Path, *, timeout: int = 60) -> tuple[str, str]:
    out = Path(output_path)
    ensure_dir(out.parent)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with out.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    return str(out), sha256_file(out)


def log_download(path: str | Path, record: dict[str, Any]) -> None:
    append_jsonl(path, {"timestamp": utc_now_iso(), **record})
