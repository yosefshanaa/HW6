"""Shared pytest fixtures (guidelines §6)."""

from __future__ import annotations

import json

import pytest
import yaml

from cop_thief.shared.config import Config, load_config


@pytest.fixture
def config() -> Config:
    """The real project configuration."""
    return load_config()


@pytest.fixture
def write_config(tmp_path):
    """Factory: write a config+rate_limits pair to temp files, return paths."""

    def _write(overrides: dict | None = None) -> tuple[str, str]:
        base = {
            "version": "1.00",
            "grid_size": [5, 5],
            "max_moves": 25,
            "num_games": 6,
            "max_barriers": 5,
            "vision_radius": 2,
            "movement_mode": "eight_directional",
            "scoring": {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5},
            "start_mode": "fixed",
            "seed": 1234,
            "fixed_start": {"cop": [0, 0], "thief": [4, 4]},
        }
        if overrides:
            base.update(overrides)
        cfg_path = tmp_path / "config.yaml"
        rl_path = tmp_path / "rate_limits.json"
        cfg_path.write_text(yaml.safe_dump(base), encoding="utf-8")
        rl_path.write_text(
            json.dumps({"rate_limits": {"version": "1.00", "services": {}}}),
            encoding="utf-8",
        )
        return str(cfg_path), str(rl_path)

    return _write
