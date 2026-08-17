from __future__ import annotations

import logging
from pathlib import Path

from .utils import ensure_dir


def setup_logger(name: str, log_path: str | Path, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    ensure_dir(Path(log_path).parent)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
