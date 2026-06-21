"""Structured logging setup (PLAN §16)."""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LOGGING = _REPO_ROOT / "config" / "logging_config.json"


def setup_logging(config_path: str | Path | None = None) -> None:
    """Configure logging from JSON config, falling back to basicConfig."""
    path = Path(config_path or _DEFAULT_LOGGING)
    if path.exists():
        logging.config.dictConfig(json.loads(path.read_text(encoding="utf-8")))
    else:
        logging.basicConfig(level=logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
