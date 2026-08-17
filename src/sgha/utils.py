from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TypeVar


T = TypeVar("T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(data), f, indent=indent, ensure_ascii=False)
        f.write("\n")
    return p


def append_jsonl(path: str | Path, record: Mapping[str, Any]) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(to_jsonable(record), ensure_ascii=False) + "\n")


def write_text(path: str | Path, text: str) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(text, encoding="utf-8")
    return p


def read_text(path: str | Path, default: str = "") -> str:
    p = Path(path)
    if not p.exists():
        return default
    return p.read_text(encoding="utf-8", errors="replace")


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in fieldnames})
    return p


def read_jsonl(path: str | Path) -> list[Any]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    text = "\n".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:length]
    return f"{prefix}:{digest}"


def slugify(text: str, *, max_len: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip()).strip("_")
    return (slug[:max_len] or "item").lower()


_UNICODE_SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿᵐ", "0123456789nm")
_UNICODE_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def normalize_math(text: str) -> str:
    """Normalize math notation so equivalent bounds hash to the same string.

    Handles: unicode super/subscripts, LaTeX exponents (^{2/3}), tilde/hat
    wrappers (\\tilde{O}), and stray braces. Preserves O/Ω/Θ distinctions.
    """
    text = text.translate(_UNICODE_SUPER).translate(_UNICODE_SUB)
    # LaTeX decorated letters: \tilde{O}, \hat{n} → O, n
    text = re.sub(r"\\(?:tilde|hat|widetilde|bar|mathcal|mathrm)\{([^}]*)\}", r"\1", text)
    # LaTeX exponents: d^{2/3} → d2/3
    text = re.sub(r"\^\{([^}]*)\}", r"\1", text)
    # Plain carets: d^2 → d2
    text = text.replace("^", "")
    # Remove stray braces
    text = text.replace("{", "").replace("}", "")
    # Normalize Omega/Theta spelled out in unicode
    text = re.sub(r"[Ωω]", "Omega", text)
    text = re.sub(r"[Θθ]", "Theta", text)
    return text


def normalize_label(text: str) -> str:
    text = normalize_math(text)
    # Strip trailing parenthetical acronym: "Foo Bar (FB)" → "Foo Bar"
    # Matches only all-uppercase acronyms (2+ chars) so math like O(T) is preserved
    text = re.sub(r"\s*\([A-Z][A-Z0-9\-]{1,}\)\s*$", "", text.strip())
    return re.sub(r"\s+", " ", text.strip().lower())


def safe_symlink_or_copy(src: str | Path, dst: str | Path) -> Path:
    src_p = Path(src)
    dst_p = Path(dst)
    ensure_dir(dst_p.parent)
    if dst_p.exists() or dst_p.is_symlink():
        return dst_p
    try:
        rel = os.path.relpath(src_p, start=dst_p.parent)
        dst_p.symlink_to(rel)
    except OSError:
        shutil.copy2(src_p, dst_p)
    return dst_p


def run_command_capture(cmd: Sequence[str], cwd: str | Path | None = None) -> str:
    try:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False, timeout=30)
        return (result.stdout + result.stderr).strip()
    except Exception as exc:  # pragma: no cover - defensive capture
        return f"command failed: {cmd}: {exc}"


def model_dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def model_validate(model_cls: type[T], data: Any) -> T:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)  # type: ignore[attr-defined]
    return model_cls.parse_obj(data)  # type: ignore[attr-defined]


def to_jsonable(value: Any) -> Any:
    value = model_dump(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    return value


def flatten_dict(d: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in d.items():
        new_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            out.update(flatten_dict(value, new_key))
        else:
            out[new_key] = value
    return out


def _csv_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(to_jsonable(value), ensure_ascii=False)


def bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def chunks(items: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
