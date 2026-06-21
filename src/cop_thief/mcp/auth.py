"""Bearer-token auth for the MCP servers (PRD_mcp_servers §2.5).

The token value comes from the environment (never config/code). When no token
is configured the check is disabled (local development); when a token is set,
requests must present ``Authorization: Bearer <token>``. The logic here is pure
and fully unit-testable without a running server or cloud credentials; the
FastMCP servers call :func:`check_bearer` per request once deployed.
"""

from __future__ import annotations

import hmac
import os


def load_expected_token(config) -> str | None:
    """Read the expected bearer token from the env var named in config."""
    env_var = config.get("auth.token_env_var", "MCP_AUTH_TOKEN")
    return os.environ.get(env_var)


def check_bearer(authorization: str | None, expected: str | None) -> tuple[bool, str]:
    """Validate an ``Authorization`` header against the expected token.

    Returns ``(allowed, reason)``. Auth is disabled (allowed) when ``expected``
    is empty. Token comparison is constant-time.
    """
    if not expected:
        return True, "auth disabled (no token configured)"
    if not authorization:
        return False, "missing Authorization header"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False, "malformed Authorization header"
    if not hmac.compare_digest(parts[1], expected):
        return False, "invalid token"
    return True, "ok"
