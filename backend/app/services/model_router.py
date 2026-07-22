"""Model Router — DeepSeek as default orchestrator, multi-modal models as needed.

Architecture:
- DeepSeek Chat: default for conversation, question generation, explanation, planning
- Multi-modal (Kimi/Doubao/Qwen): only for processing PDFs/images → output Markdown → stored in vault
- Original files are NOT stored on the server — they're "in transit" only

The user configures optional API keys in settings.
When a multi-modal task arrives, the router checks which keys are available.
If none → degrades to text extraction (PyMuPDF for PDFs).
"""

import base64
import os
import tempfile
from pathlib import Path
from collections.abc import AsyncGenerator
from typing import Optional

import httpx

MODEL_CONFIG = {
    "deepseek": {
        "name": "DeepSeek",
        "chat_model": "deepseek-chat",
        "reasoner_model": "deepseek-reasoner",
        "embedding_model": "deepseek-embedding",
        "base_url": "https://api.deepseek.com",
        "is_default": True,
    },
    "kimi": {
        "name": "Kimi (月之暗面)",
        "chat_model": "moonshot-v1-8k",
        "vision_model": "moonshot-v1-8k-vision",
        "base_url": "https://api.moonshot.cn/v1",
        "is_default": False,
    },
    "doubao": {
        "name": "豆包 (字节)",
        "vision_model": "doubao-vision-pro-32k",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "is_default": False,
    },
    "qwen": {
        "name": "千问 (阿里)",
        "vision_model": "qwen-vl-max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "is_default": False,
    },
}


class ModelRouter:
    """Routes tasks to the right model based on task type and available keys."""

    def __init__(self, user_api_keys: dict[str, str]):
        """
        user_api_keys: {"deepseek": "sk-xxx", "kimi": "sk-xxx", ...}
        At minimum, deepseek key must be present.
        """
        self.keys = user_api_keys
        if not self.keys.get("deepseek"):
            raise ValueError("DeepSeek API key is required as the default model")

    def get_default(self) -> tuple[str, str]:
        """Get default model for general tasks."""
        return MODEL_CONFIG["deepseek"]["chat_model"], self.keys["deepseek"]

    def get_for_vision(self) -> tuple[str, str, str] | None:
        """Get best available vision model. Returns (provider, model, api_key)."""
        for provider in ["kimi", "doubao", "qwen"]:
            key = self.keys.get(provider)
            if key and MODEL_CONFIG[provider].get("vision_model"):
                return provider, MODEL_CONFIG[provider]["vision_model"], key
        return None

    def get_for_reasoner(self) -> tuple[str, str]:
        """Get reasoner model. Falls back to chat if not configured."""
        ds_key = self.keys["deepseek"]
        return MODEL_CONFIG["deepseek"]["reasoner_model"], ds_key

    async def stream_vision(
        self,
        text_content: str,
        images: list[tuple[bytes, str]] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Stream from a vision model with optional images.

        Args:
            text_content: The text prompt to send.
            images: List of (file_bytes, file_name) tuples for images.
            max_tokens: Maximum tokens in the response.

        Yields:
            Content delta strings as they arrive from the vision API.
        """
        vision = self.get_for_vision()
        if not vision:
            raise RuntimeError("No vision model available. Configure Kimi/Doubao/Qwen.")
        provider, model, api_key = vision
        config = MODEL_CONFIG[provider]
        base_url = config["base_url"]

        # Build content list
        content_parts: list[dict] = [{"type": "text", "text": text_content}]
        if images:
            ext_to_mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            }
            for file_data, file_name in images:
                ext = Path(file_name).suffix.lower()
                mime = ext_to_mime.get(ext, "image/png")
                b64 = base64.b64encode(file_data).decode()
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })

        # Qwen uses a different non-streaming response format, but in streaming
        # mode all three providers use the same OpenAI-compatible SSE format.
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content_parts}],
                    "stream": True,
                    "max_tokens": max_tokens,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            ) as resp:
                resp.raise_for_status()
                import json as _json
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            return
                        try:
                            chunk = _json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (_json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def process_media_to_markdown(
        self,
        file_data: bytes,
        file_name: str,
        instruction: str = "请提取并整理此文件中的全部文字内容，包括公式和表格。输出为 Markdown 格式。保留章节结构。",
    ) -> str:
        """Process a PDF or image through vision model → output Markdown.

        The original file is NOT stored — only the resulting Markdown goes into the vault.
        """
        vision = self.get_for_vision()
        if not vision:
            # Degrade: try text extraction for PDFs
            return self._extract_pdf_text(file_data, file_name)

        provider, model, api_key = vision
        return await self._call_vision_api(provider, model, api_key, file_data, file_name, instruction)

    async def _call_vision_api(
        self, provider: str, model: str, api_key: str,
        file_data: bytes, file_name: str, instruction: str,
    ) -> str:
        """Call a multi-modal API with a file and return the text response."""
        config = MODEL_CONFIG[provider]
        base_url = config["base_url"]

        # Encode file as base64 data URL
        ext = Path(file_name).suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        data_url = f"data:{mime};base64,{base64.b64encode(file_data).decode()}"

        # Build the request based on provider
        if provider == "kimi":
            return await self._call_openai_compat(base_url, model, api_key, instruction, data_url)
        elif provider == "doubao":
            return await self._call_openai_compat(base_url, model, api_key, instruction, data_url)
        elif provider == "qwen":
            return await self._call_qwen(base_url, model, api_key, instruction, data_url)
        else:
            raise ValueError(f"Unsupported vision provider: {provider}")

    async def _call_openai_compat(self, base_url: str, model: str, api_key: str, instruction: str, data_url: str) -> str:
        """Call an OpenAI-compatible vision API."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }],
                    "max_tokens": 4096,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_qwen(self, base_url: str, model: str, api_key: str, instruction: str, data_url: str) -> str:
        """Call Qwen vision API."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }],
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["output"]["choices"][0]["message"]["content"]

    def _extract_pdf_text(self, file_data: bytes, file_name: str) -> str:
        """Fallback: extract text from PDF using PyMuPDF when no vision model available."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return f"> ⚠️ 无法处理此文件。请配置多模态 AI（Kimi/豆包/千问）以支持 PDF 和图片分析。\n\n文件：{file_name}"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)
            parts = [f"# {file_name}\n\n"]
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    parts.append(f"## 第 {page_num + 1} 页\n\n{text}\n\n")
            doc.close()
            result = "\n".join(parts)
            if len(result.strip()) < 50:
                return f"> ⚠️ PDF 可能是扫描版或图片型，文本提取失败。请配置多模态 AI 以支持 OCR。\n\n文件：{file_name}"
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
