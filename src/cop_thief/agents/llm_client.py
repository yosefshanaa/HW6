"""Provider-agnostic LLM client seam (PLAN §11).

The MVP plays with heuristic strategies, so no real provider is required. This
client routes calls through the API Gatekeeper and accepts an injected
``responder`` (used by tests and for wiring a real provider later).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cop_thief.shared.gatekeeper import ApiGatekeeper


class LlmClient:
    """Calls an LLM via the gatekeeper. ``provider == 'none'`` needs a responder."""

    def __init__(
        self,
        provider: str,
        model: str,
        gatekeeper: ApiGatekeeper,
        responder: Callable[[str], str] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._gatekeeper = gatekeeper
        self._responder = responder

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Return the model's completion for ``prompt`` (through the gatekeeper)."""
        if self._responder is None:
            raise NotImplementedError(
                f"no responder wired for provider '{self.provider}'; "
                "the MVP uses heuristic strategies instead of an LLM"
            )
        return self._gatekeeper.execute(self._responder, prompt, **kwargs)
