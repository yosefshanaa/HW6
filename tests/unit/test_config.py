"""Tests for config loading/validation and version (Phase 2)."""

from __future__ import annotations

import pytest

from cop_thief.shared.config import ConfigError, load_config
from cop_thief.shared.version import __version__, get_version


def test_version_starts_at_1_00():
    assert __version__ == "1.00"
    assert get_version() == "1.00"


def test_real_config_loads_and_validates(config):
    assert config.get("grid_size") == [5, 5]
    assert config.get("scoring.cop_win") == 20
    assert config.get("scoring.thief_win") == 10
    assert config.get("report.recipient") == "rmisegal+uoh26b@gmail.com"


def test_dotted_get_with_default(config):
    assert config.get("does.not.exist", "fallback") == "fallback"


def test_config_change_observable_without_code_change(write_config):
    cfg_path, rl_path = write_config({"grid_size": [7, 7], "vision_radius": 3})
    cfg = load_config(cfg_path, rl_path)
    assert cfg.get("grid_size") == [7, 7]
    assert cfg.get("vision_radius") == 3


def test_missing_required_key_raises(write_config):
    cfg_path, rl_path = write_config({"scoring": {"cop_win": 20}})
    with pytest.raises(ConfigError):
        load_config(cfg_path, rl_path)


def test_incompatible_version_raises(write_config):
    cfg_path, rl_path = write_config({"version": "2.00"})
    with pytest.raises(ConfigError):
        load_config(cfg_path, rl_path)


def test_invalid_grid_size_raises(write_config):
    cfg_path, rl_path = write_config({"grid_size": [0, 5]})
    with pytest.raises(ConfigError):
        load_config(cfg_path, rl_path)


def test_missing_config_file_raises():
    with pytest.raises(ConfigError):
        load_config("/nonexistent/config.yaml", "/nonexistent/rl.json")
