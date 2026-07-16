"""DeepSeek API client with retry and exponential backoff."""

import asyncio
from typing import Any

import httpx

from app.config import settings


class DeepSeekClient:
    """Async HTTP client for the DeepSeek Chat Completion API."""

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=120.0,
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request with automatic retry.

        Args:
            messages: List of {"role": …, "content": …} dicts.
            **kwargs:  Extra parameters forwarded to the API body
                       (model, temperature, max_tokens, etc.).

        Returns:
            The content text of the first choice.
        """
        client = await self._get_client()

        body: dict[str, Any] = {
            "model": kwargs.get("model", "deepseek-chat"),
            "messages": messages,
            "thinking": {"type": "disabled"},
        }
        # Merge extra kwargs, but keep thinking fixed
        for key in ("model", "temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs:
                body[key] = kwargs[key]

        last_exc: Exception | None = None
        for attempt in range(1, 4):  # max 3 retries
            try:
                resp = await client.post(
                    "/v1/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as exc:
                last_exc = exc
                if attempt < 3:
                    wait = 2 ** attempt  # exponential backoff: 2, 4, 8 seconds
                    await asyncio.sleep(wait)

        raise RuntimeError(f"DeepSeek API failed after 3 retries: {last_exc}")
