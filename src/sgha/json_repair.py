from __future__ import annotations

import json
import re
from typing import Any


class JsonRepairError(ValueError):
    pass


def parse_json_with_repair(text: str) -> Any:
    # Try the robust json_repair library first
    try:
        import json_repair as _jr
        result = _jr.repair_json(text, return_objects=True)
        if result not in (None, "", {}, []):
            return result
    except Exception:
        pass

    attempts = [_strip_code_fences(text), _extract_json_candidate(text)]
    last_error: Exception | None = None
    for candidate in attempts:
        if not candidate:
            continue
        for repaired in _repair_variants(candidate):
            try:
                return json.loads(repaired)
            except Exception as exc:
                last_error = exc
    raise JsonRepairError(f"could not parse JSON: {last_error}")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_candidate(text: str) -> str:
    stripped = _strip_code_fences(text)
    starts = [idx for idx in [stripped.find("{"), stripped.find("[")] if idx >= 0]
    if not starts:
        return stripped
    start = min(starts)
    end_obj = stripped.rfind("}")
    end_arr = stripped.rfind("]")
    end = max(end_obj, end_arr)
    if end <= start:
        return stripped[start:]
    return stripped[start : end + 1]


def _repair_variants(candidate: str) -> list[str]:
    base = candidate.strip()
    variants = [base]
    no_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", base)
    variants.append(no_trailing_commas)
    smart_quotes = no_trailing_commas.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    variants.append(smart_quotes)
    return list(dict.fromkeys(variants))
