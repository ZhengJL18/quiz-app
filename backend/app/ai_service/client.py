"""DeepSeek API client with retry and exponential backoff."""

import asyncio
from typing import Any

import httpx


class DeepSeekClient:
    """Async HTTP client for the DeepSeek Chat Completion API.

    Requires an explicit API key — no global fallback.
    Each user must provide their own DeepSeek API key.
    """

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        if not api_key:
            raise ValueError(
                "DeepSeek API key is required. "
                "Go to https://platform.deepseek.com/api_keys to get one, "
                "then set it in your profile settings."
            )
        self.api_key = api_key
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
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                # Never retry on auth errors (401/403) — they won't fix themselves
                if exc.response.status_code in (401, 403):
                    raise RuntimeError(
                        f"DeepSeek API authentication failed ({exc.response.status_code}). "
                        f"Please check your API key in Profile Settings."
                    )
                if attempt < 3:
                    wait = 2 ** attempt  # exponential backoff: 2, 4, 8 seconds
                    await asyncio.sleep(wait)
            except (httpx.RequestError, KeyError) as exc:
                last_exc = exc
                if attempt < 3:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)

        raise RuntimeError(f"DeepSeek API failed after 3 retries: {last_exc}")

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ):
        """Stream chat completion chunks via SSE.

        Yields content delta strings as they arrive from the API.
        Uses stream=True; does NOT retry (streaming + retry is fragile).
        """
        client = await self._get_client()

        body: dict[str, Any] = {
            "model": kwargs.get("model", "deepseek-chat"),
            "messages": messages,
            "stream": True,
            "thinking": {"type": "disabled"},
        }
        for key in ("temperature", "max_tokens", "top_p"):
            if key in kwargs:
                body[key] = kwargs[key]

        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    import json as _json
                    try:
                        chunk = _json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (_json.JSONDecodeError, KeyError, IndexError):
                        continue
