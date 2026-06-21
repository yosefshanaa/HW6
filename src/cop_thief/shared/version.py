"""Canonical project version (guidelines §8.1: starts at 1.00)."""

from __future__ import annotations

__version__ = "1.00"


def get_version() -> str:
    """Return the canonical project version string."""
    return __version__
