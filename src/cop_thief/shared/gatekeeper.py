"""API Gatekeeper: rate limits, retries, logging (guidelines §5, PLAN §15).

Every external API call (LLM, Gmail, peer MCP) must go through this. Time and
sleep are injectable so tests never block.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Any

from cop_thief.shared.logging_setup import get_logger


class GatekeeperError(RuntimeError):
    """Raised when retries are exhausted."""


class ApiGatekeeper:
    """Centralized external-call manager."""

    def __init__(
        self,
        service_config: dict[str, Any],
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        logger=None,
    ) -> None:
        self.rpm = int(service_config.get("requests_per_minute", 30))
        self.max_retries = int(service_config.get("max_retries", 3))
        self.retry_after = float(service_config.get("retry_after_seconds", 30))
        self.max_queue_depth = int(service_config.get("max_queue_depth", 100))
        self._calls: deque[float] = deque()
        self._sleep = sleep
        self._clock = clock
        self._log = logger or get_logger("gatekeeper")
        self._total = 0

    @classmethod
    def from_config(cls, config, service: str = "default", **kwargs) -> ApiGatekeeper:
        """Build from a :class:`Config`, falling back to the ``default`` service."""
        services = config.rate_limits.get("rate_limits", {}).get("services", {})
        svc = services.get(service, services.get("default", {}))
        return cls(svc, **kwargs)

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        retry_on: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError),
        **kwargs: Any,
    ) -> Any:
        """Run ``func`` under rate limiting + retry-on-transient-error."""
        self._respect_rate_limit()
        attempt = 0
        while True:
            try:
                self._total += 1
                return func(*args, **kwargs)
            except retry_on as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise GatekeeperError(f"max retries exceeded: {exc}") from exc
                self._log.warning("transient error (attempt %s): %s", attempt, exc)
                self._sleep(min(self.retry_after, float(2**attempt)))

    def get_queue_status(self) -> dict[str, int]:
        """Return current window depth and totals."""
        return {
            "window_calls": len(self._calls),
            "total_calls": self._total,
            "rpm_limit": self.rpm,
        }

    def _respect_rate_limit(self) -> None:
        now = self._clock()
        while self._calls and now - self._calls[0] >= 60.0:
            self._calls.popleft()
        if len(self._calls) >= self.rpm:
            wait = 60.0 - (now - self._calls[0])
            if wait > 0:
                self._log.info("rate limit reached; waiting %.2fs", wait)
                self._sleep(wait)
        self._calls.append(self._clock())
