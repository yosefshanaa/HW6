"""Pre-match smoke test for a deployed MCP server (assignment §6 stage 5, T1/T8).

Verifies a partner/own server is reachable, healthy, and (with ``--check-auth``)
that bearer-token auth is actually enforced — i.e. the token succeeds and the
*absence* of a token is rejected. Run this against each of the four match URLs
before playing.

Usage (token from --token or the MCP_AUTH_TOKEN env var):
    uv run cop-thief-smoke https://cop-thief-cop-….run.app/mcp/ --token <t> --check-auth
"""

from __future__ import annotations

import argparse
import os
import sys

from cop_thief.agents.agent_client import HttpTransport


def _health(url: str, token: str | None, timeout: float) -> dict:
    """health_check the server (raises if unreachable / auth rejects)."""
    transport = HttpTransport(url, token=token, timeout=timeout)
    try:
        return transport.call("health_check")
    finally:
        transport.close()


def main() -> None:
    """Probe one MCP URL; exit non-zero if it is unhealthy or auth is not enforced."""
    parser = argparse.ArgumentParser(description="Smoke-test a deployed Cop/Thief MCP server.")
    parser.add_argument("url", help="server URL, e.g. https://…run.app/mcp/")
    parser.add_argument("--token", default=os.environ.get("MCP_AUTH_TOKEN"),
                        help="bearer token (default: $MCP_AUTH_TOKEN)")
    parser.add_argument("--check-auth", action="store_true",
                        help="also assert an unauthenticated call is rejected (401)")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    ok = True
    try:
        health = _health(args.url, args.token, args.timeout)
        print(f"[ok]   {args.url}  health={health}")
    except Exception as exc:  # noqa: BLE001 - report any failure cleanly, never traceback
        print(f"[FAIL] {args.url}  health_check failed: {exc}")
        sys.exit(1)

    if args.check_auth:
        if not args.token:
            print("[warn] --check-auth needs a --token to contrast against; skipping")
        else:
            try:
                _health(args.url, None, args.timeout)
                print("[FAIL] server accepted an UNAUTHENTICATED call — auth NOT enforced")
                ok = False
            except Exception:  # noqa: BLE001 - rejection is the expected, desired outcome
                print("[ok]   unauthenticated call rejected — bearer auth enforced")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
