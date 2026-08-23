"""Small typed OpenRouter Chat Completions client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    """A safe, user-facing upstream LLM failure without including credentials."""


class OpenRouterClient:
    """Call OpenRouter only when an API key is explicitly supplied."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "stealth/ox-alpha",
        *,
        endpoint: str = OPENROUTER_CHAT_URL,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self._http_client = http_client

    @property
    def configured(self) -> bool:
        """Whether this client is allowed to make an upstream request."""
        return bool(self.api_key)

    def complete(
        self,
        messages: Sequence[Mapping[str, str | Sequence[Mapping[str, Any]]]],
        *,
        response_format: Mapping[str, Any] | None = None,
        max_tokens: int = 3_000,
    ) -> str:
        """Return assistant text for text or multimodal Chat Completions messages."""
        if not self.configured:
            raise OpenRouterError("OpenRouter is not configured.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = dict(response_format)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        client = self._http_client
        close_client = client is None
        if client is None:
            client = httpx.Client(timeout=self.timeout)
        try:
            response = client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise OpenRouterError("OpenRouter returned no assistant content.")
            return content.strip()
        except OpenRouterError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError("OpenRouter request failed.") from error
        finally:
            if close_client:
                client.close()
