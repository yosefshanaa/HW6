"""HTTP bearer-token enforcement for the deployed MCP servers (assignment §MUST: token-auth).

The pure decision lives in :func:`cop_thief.mcp.auth.check_bearer`; this module is the thin
ASGI adapter that *applies* it on every HTTP request once a server is deployed, so an
unauthenticated caller is rejected with **HTTP 401** before reaching any tool. ``starlette``
ships with the ``mcp`` extra (``uv sync --extra mcp``) and is imported lazily, so the core
package and its tests never require it.
"""

from __future__ import annotations

from cop_thief.mcp.auth import check_bearer


class BearerAuthMiddleware:
    """ASGI middleware that rejects requests lacking a valid ``Authorization: Bearer`` token.

    Auth is skipped (passthrough) when ``expected`` is empty — local development with no token
    configured — and for non-HTTP scopes (lifespan/websocket). A failed check short-circuits
    with HTTP 401 before the request reaches the MCP handler.
    """

    def __init__(self, app, expected: str | None) -> None:
        self.app = app
        self.expected = expected

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or not self.expected:
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        allowed, reason = check_bearer(headers.get("authorization"), self.expected)
        if not allowed:
            await self._unauthorized(reason, scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _unauthorized(reason: str, scope, receive, send) -> None:
        from starlette.responses import JSONResponse  # lazy: mcp extra only

        response = JSONResponse({"error": "unauthorized", "reason": reason}, status_code=401)
        await response(scope, receive, send)


def bearer_middleware(expected: str | None) -> list:
    """Return a Starlette middleware list enforcing ``expected`` (empty list when no token set)."""
    if not expected:
        return []
    from starlette.middleware import Middleware  # lazy: mcp extra only

    return [Middleware(BearerAuthMiddleware, expected=expected)]
