"""API Gatekeeper tests (guidelines §5)."""

from __future__ import annotations

import pytest

from cop_thief.shared.gatekeeper import ApiGatekeeper, GatekeeperError


def make_gatekeeper(rpm=30, max_retries=3, sleeps=None):
    return ApiGatekeeper(
        {"requests_per_minute": rpm, "max_retries": max_retries, "retry_after_seconds": 1},
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
        clock=lambda: 0.0,
    )


def test_execute_returns_result_and_counts():
    gk = make_gatekeeper()
    assert gk.execute(lambda x: x + 1, 41) == 42
    assert gk.get_queue_status()["total_calls"] == 1


def test_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    gk = make_gatekeeper()
    assert gk.execute(flaky) == "ok"
    assert calls["n"] == 3


def test_retries_exhausted_raises():
    def always_fail():
        raise TimeoutError("nope")

    gk = make_gatekeeper(max_retries=2)
    with pytest.raises(GatekeeperError):
        gk.execute(always_fail)


def test_non_transient_error_not_retried():
    def bad():
        raise ValueError("logic bug")

    gk = make_gatekeeper()
    with pytest.raises(ValueError):
        gk.execute(bad)


def test_rate_limit_triggers_wait():
    sleeps: list[float] = []
    gk = make_gatekeeper(rpm=2, sleeps=sleeps)
    for _ in range(3):
        gk.execute(lambda: None)
    assert any(s == 60.0 for s in sleeps)


def test_from_config_builds(config):
    gk = ApiGatekeeper.from_config(config, "llm", sleep=lambda _s: None)
    assert gk.rpm == 30
