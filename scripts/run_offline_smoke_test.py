#!/usr/bin/env python3
"""Run a no-network, no-LLM SGHA public-release smoke test."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sgha.offline_demo import DEFAULT_EXAMPLE_CONFIG, build_synthetic_objects, create_mock_run, format_run_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_EXAMPLE_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    result = create_mock_run(config_path=args.config, output_dir=args.output_dir)
    print("offline smoke test ok")
    print(f"mock_run_dir={result['run_dir']}")
    print(format_run_summary(result["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
