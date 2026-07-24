"""Tencent Cloud ASR (Automatic Speech Recognition) client.

Uses the SentenceRecognition (一句话识别) API with TC3-HMAC-SHA256 signing.
No external SDK required — uses hashlib, hmac, and httpx directly.

Usage:
    asr = TencentASR(secret_id="xxx", secret_key="yyy")
    text = await asr.recognize(audio_data, voice_format="mp3")
"""

import hashlib
import hmac
import json
import base64
from datetime import datetime, timezone

import httpx


class TencentASR:
    """Tencent Cloud ASR client for SentenceRecognition API."""

    SERVICE = "asr"
    HOST = "asr.tencentcloudapi.com"
    VERSION = "2019-06-14"
    REGION = "ap-guangzhou"
    ALGORITHM = "TC3-HMAC-SHA256"
    ACTION = "SentenceRecognition"

    def __init__(self, secret_id: str, secret_key: str):
        if not secret_id or not secret_key:
            raise ValueError("Tencent Cloud SecretId and SecretKey are required")
        self.secret_id = secret_id.strip()
        self.secret_key = secret_key.strip()

    # ── Signature (TC3-HMAC-SHA256) ──

    @staticmethod
    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _build_authorization(self, payload_str: str, timestamp: int) -> dict[str, str]:
        """Build TC3-HMAC-SHA256 Authorization header and required headers."""
        date_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
        action_lower = self.ACTION.lower()

        # ── Step 1: Canonical Request ──
        canonical_headers = (
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.HOST}\n"
            f"x-tc-action:{action_lower}\n"
        )
        signed_headers = "content-type;host;x-tc-action"

        hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        canonical_request = (
            f"POST\n"
            f"/\n"
            f"\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_payload}"
        )

        # ── Step 2: String to Sign ──
        credential_scope = f"{date_str}/{self.SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = (
            f"{self.ALGORITHM}\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical}"
        )

        # ── Step 3: Calculate Signature ──
        secret_date = self._hmac_sha256(f"TC3{self.secret_key}".encode("utf-8"), date_str)
        secret_service = self._hmac_sha256(secret_date, self.SERVICE)
        secret_signing = self._hmac_sha256(secret_service, "tc3_request")
        signature = self._hmac_sha256(secret_signing, string_to_sign).hex()

        # ── Step 4: Build Authorization ──
        authorization = (
            f"{self.ALGORITHM} "
            f"Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.HOST,
            "X-TC-Action": self.ACTION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": self.VERSION,
            "X-TC-Region": self.REGION,
        }

    # ── Public API ──

    async def recognize(self, audio_data: bytes, voice_format: str = "wav") -> str:
        """Transcribe audio to text using Tencent Cloud SentenceRecognition API.

        Args:
            audio_data: Raw audio file bytes.
            voice_format: File extension / format (mp3, wav, m4a, webm, ogg, flac, aac).

        Returns:
            Transcribed text string.

        Raises:
            RuntimeError: On API errors or unexpected responses.
            httpx.HTTPStatusError: On HTTP-level failures.
        """
        mapped_format = self._map_format(voice_format)
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        params = {
            "EngSerViceType": "16k_zh",
            "SourceType": 1,
            "VoiceFormat": mapped_format,
            "Data": audio_b64,
            "DataLen": len(audio_data),
        }

        payload_str = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        timestamp = int(datetime.now(timezone.utc).timestamp())

        headers = self._build_authorization(payload_str, timestamp)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"https://{self.HOST}",
                content=payload_str,
                headers=headers,
            )

            if resp.status_code != 200:
                body_snippet = resp.text[:500]
                raise RuntimeError(
                    f"Tencent ASR HTTP {resp.status_code}: {body_snippet}"
                )

            data = resp.json()
            response = data.get("Response", {})

            # Check for Tencent API-level error
            if "Error" in response:
                err = response["Error"]
                code = err.get("Code", "Unknown")
                message = err.get("Message", "")
                raise RuntimeError(f"Tencent ASR error [{code}]: {message}")

            return response.get("Result", "")

    # ── Helpers ──

    @staticmethod
    def _map_format(voice_format: str) -> str:
        """Map common audio extensions to Tencent ASR VoiceFormat values."""
        mapping = {
            "mp3": "mp3",
            "wav": "wav",
            "m4a": "m4a",
            "webm": "webm",
            "ogg": "ogg",
            "flac": "flac",
            "aac": "aac",
        }
        return mapping.get(voice_format.lower(), "wav")
