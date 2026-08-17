#!/usr/bin/env python3
"""Summarize available SGHA run outputs without requiring a complete run."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sgha.offline_demo import format_run_summary, summarize_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    print(format_run_summary(summarize_run(args.run_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
