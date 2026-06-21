"""Configuration loading and validation (PRD §12, PLAN §14, ADR-006).

All tunable values come from config files; secrets come from the environment.
Validation runs at load time, including a version-compatibility check.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cop_thief.shared.version import __version__

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "config.yaml"
_DEFAULT_RATE_LIMITS = _REPO_ROOT / "config" / "rate_limits.json"

_REQUIRED_KEYS = (
    "grid_size", "max_moves", "num_games", "max_barriers",
    "vision_radius", "movement_mode", "scoring",
)
_REQUIRED_SCORING = ("cop_win", "thief_win", "cop_loss", "thief_loss")


class ConfigError(ValueError):
    """Raised when configuration is missing keys or fails validation."""


@dataclass(frozen=True)
class Config:
    """Validated configuration with dotted-key access."""

    data: dict[str, Any]
    rate_limits: dict[str, Any]

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Return a value by dotted key (e.g. ``"scoring.cop_win"``)."""
        node: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def load_config(
    config_path: str | os.PathLike[str] | None = None,
    rate_limits_path: str | os.PathLike[str] | None = None,
) -> Config:
    """Load + validate config and rate limits, then return a :class:`Config`."""
    cfg_path = Path(config_path or os.environ.get("COPTHIEF_CONFIG") or _DEFAULT_CONFIG)
    rl_path = Path(rate_limits_path or _DEFAULT_RATE_LIMITS)
    data = _read_yaml(cfg_path)
    rate_limits = _read_json(rl_path)
    _validate(data, rate_limits)
    return Config(data=data, rate_limits=rate_limits)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Rate-limits file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(data: dict[str, Any], rate_limits: dict[str, Any]) -> None:
    _check_version(data, rate_limits)
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ConfigError(f"Missing required config key: {key}")
    grid = data["grid_size"]
    if not (isinstance(grid, list) and len(grid) == 2 and all(int(v) > 0 for v in grid)):
        raise ConfigError("grid_size must be [rows>0, cols>0]")
    for key in ("max_moves", "num_games", "vision_radius"):
        if int(data[key]) <= 0:
            raise ConfigError(f"{key} must be a positive integer")
    if int(data["max_barriers"]) < 0:
        raise ConfigError("max_barriers must be >= 0")
    scoring = data["scoring"]
    for key in _REQUIRED_SCORING:
        if key not in scoring:
            raise ConfigError(f"Missing scoring key: {key}")


def _check_version(data: dict[str, Any], rate_limits: dict[str, Any]) -> None:
    cfg_version = str(data.get("version", ""))
    rl_version = str(rate_limits.get("rate_limits", {}).get("version", ""))
    expected_major = __version__.split(".")[0]
    for label, value in (("config", cfg_version), ("rate_limits", rl_version)):
        if not value:
            raise ConfigError(f"Missing {label} version (expected major {expected_major})")
        if value.split(".")[0] != expected_major:
            raise ConfigError(
                f"{label} version {value} incompatible with code {__version__}"
            )
