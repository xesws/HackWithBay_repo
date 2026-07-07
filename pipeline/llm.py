#!/usr/bin/env python3
"""llm — OpenRouter chat helper for the pipeline (Track B).

Human ruling: ALL LLM calls go through **OpenRouter** (OpenAI-compatible), never
Anthropic/OpenAI directly.

  * base URL : https://openrouter.ai/api/v1
  * API key  : env OPENROUTER_API_KEY   (may be empty -> NEEDS-HUMAN)
  * default  : z-ai/glm-5.2

`openrouter_chat(messages, model=...)` returns the assistant message *string*.
Prefers the `openai` client (with base_url); falls back to stdlib urllib so the
helper works even if `openai` is absent. Raises RuntimeError when no key is set —
callers keep the deterministic regex extractor as the offline default and only
reach this when OPENROUTER_API_KEY is present.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.5-flash"


def has_key() -> bool:
    """True when an OpenRouter key is configured (so the LLM path is usable)."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _require_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. The LLM path is DEFERRED / NEEDS-HUMAN; "
            "the pipeline defaults to the offline regex extractor without a key."
        )
    return key


def openrouter_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float = 30.0,
    **kwargs: Any,
) -> str:
    """Send `messages` (OpenAI chat format) to OpenRouter; return the reply string.

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        model:    OpenRouter model id (default z-ai/glm-5.2).
    """
    key = _require_key()
    params: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    params.update(kwargs)

    # Preferred path: openai client pointed at OpenRouter's OpenAI-compatible API.
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        OpenAI = None  # fall through to urllib

    if OpenAI is not None:
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, timeout=timeout)
        completion = client.chat.completions.create(**params)
        return completion.choices[0].message.content or ""

    # Fallback: stdlib urllib POST to /chat/completions (no extra deps).
    request = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=json.dumps(params).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # pragma: no cover - needs key
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"] or ""


__all__ = ["openrouter_chat", "has_key", "OPENROUTER_BASE_URL", "DEFAULT_MODEL"]
