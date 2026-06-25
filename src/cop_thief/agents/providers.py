"""Concrete LLM provider responders (PLAN §11, guidelines §7.4).

A *responder* is the ``Callable[[str], str]`` the :class:`LlmClient` seam calls
through the API Gatekeeper. Each builder returns a closure that performs one
chat completion. The provider SDK and the API key are read **lazily, at call
time** — importing this module never needs the optional ``llm`` extra, and the
key always comes from the environment (never code, never config).

Transient network/throttling errors are re-raised as ``ConnectionError`` so the
Gatekeeper's retry policy handles them; everything else propagates so the
strategy's legal-guard can fall back to the heuristic.
"""

from __future__ import annotations

import os
from collections.abc import Callable


def openai_responder(
    model: str, *, temperature: float = 0.7, timeout: float = 30.0
) -> Callable[..., str]:
    """Return a responder that completes ``prompt`` via the OpenAI chat API.

    The returned closure has signature ``(prompt, system=None) -> str`` and asks
    the model for a JSON object (``response_format=json_object``) so the
    strategy can parse a structured move/message.
    """

    def _respond(prompt: str, system: str | None = None) -> str:
        import openai  # lazy: optional ``llm`` extra
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in the environment "
                "(put it in your secrets .env; never in code or config)"
            )
        client = OpenAI(api_key=api_key, timeout=timeout)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError) as exc:
            raise ConnectionError(str(exc)) from exc  # let the Gatekeeper retry
        return resp.choices[0].message.content or ""

    return _respond
