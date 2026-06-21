"""MCP bearer-token auth tests (PRD_mcp_servers §2.5)."""

from __future__ import annotations

from cop_thief.mcp.auth import check_bearer, load_expected_token


def test_auth_disabled_when_no_token():
    allowed, reason = check_bearer(None, expected=None)
    assert allowed is True
    assert "disabled" in reason


def test_valid_bearer_token_allowed():
    allowed, reason = check_bearer("Bearer s3cret", expected="s3cret")
    assert allowed is True
    assert reason == "ok"


def test_missing_header_denied():
    allowed, reason = check_bearer(None, expected="s3cret")
    assert allowed is False
    assert "missing" in reason


def test_malformed_header_denied():
    allowed, _ = check_bearer("Token s3cret", expected="s3cret")
    assert allowed is False
    allowed2, _ = check_bearer("s3cret", expected="s3cret")
    assert allowed2 is False


def test_wrong_token_denied():
    allowed, reason = check_bearer("Bearer nope", expected="s3cret")
    assert allowed is False
    assert "invalid" in reason


def test_load_expected_token_from_env(config, monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "from-env")
    assert load_expected_token(config) == "from-env"
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    assert load_expected_token(config) is None
