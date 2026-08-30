"""Opt-in, bounded media requests; no URL fetching, tools, or memory writes."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from evolving_agent.utils.secret_redaction import redact_text

MIB = 1024 * 1024
IMAGE_LIMIT = 5 * MIB
AUDIO_LIMIT = 10 * MIB
RESPONSE_LIMIT = 12 * MIB
PROVIDER_ROOT = "https://api.openai.com/v1"
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")
AUDIO_TYPES = (
    "audio/wav",
    "audio/mpeg",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/mp4",
)


class IntegrationError(Exception):
    """Public-safe error: never include request bodies or provider diagnostics."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class VisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    data_base64: str = Field(min_length=1, max_length=4 * ((IMAGE_LIMIT + 2) // 3))
    prompt: str = Field(default="Describe this image.", min_length=1, max_length=4096)
    detail: Literal["low", "high", "auto"] = "low"


class TranscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mime_type: Literal[
        "audio/wav", "audio/mpeg", "audio/webm", "audio/ogg", "audio/flac", "audio/mp4"
    ]
    data_base64: str = Field(min_length=1, max_length=4 * ((AUDIO_LIMIT + 2) // 3))
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4096)
    voice: Literal[
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
    ] = "coral"


@dataclass(frozen=True)
class MediaSettings:
    api_key: str = field(default="", repr=False)
    vision_enabled: bool = False
    transcription_enabled: bool = False
    speech_enabled: bool = False
    vision_model: str = "gpt-4.1-mini"
    transcription_model: str = "gpt-4o-mini-transcribe"
    speech_model: str = "gpt-4o-mini-tts"
    timeout_seconds: float = 45.0
    max_concurrent: int = 2

    def __post_init__(self):
        if not 1 <= self.timeout_seconds <= 120 or not 1 <= self.max_concurrent <= 8:
            raise ValueError("Media timeout/concurrency outside safe bounds")
        for model in (self.vision_model, self.transcription_model, self.speech_model):
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
                raise ValueError("Invalid media model identifier")

    @classmethod
    def from_env(cls, config: Any = None) -> "MediaSettings":
        # OPENAI_API_KEY may actually belong to an OpenAI-compatible vendor.
        # Never forward that vendor's key to a different endpoint implicitly.
        base_url = getattr(config, "openai_base_url", os.getenv("OPENAI_BASE_URL", ""))
        key = os.getenv("MEDIA_OPENAI_API_KEY", "")
        if not key and base_url.rstrip("/") in ("", PROVIDER_ROOT):
            key = getattr(config, "openai_api_key", os.getenv("OPENAI_API_KEY", ""))
        return cls(
            api_key=key,
            vision_enabled=os.getenv("MEDIA_VISION_ENABLED", "false").lower() == "true",
            transcription_enabled=os.getenv(
                "MEDIA_TRANSCRIPTION_ENABLED", "false"
            ).lower()
            == "true",
            speech_enabled=os.getenv("MEDIA_SPEECH_ENABLED", "false").lower() == "true",
            vision_model=os.getenv("MEDIA_VISION_MODEL", "gpt-4.1-mini"),
            transcription_model=os.getenv(
                "MEDIA_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
            ),
            speech_model=os.getenv("MEDIA_SPEECH_MODEL", "gpt-4o-mini-tts"),
            timeout_seconds=float(os.getenv("MEDIA_TIMEOUT_SECONDS", "45")),
            max_concurrent=int(os.getenv("MEDIA_MAX_CONCURRENT", "2")),
        )


def decode_media(encoded: str, mime_type: str, limit: int) -> bytes:
    if len(encoded) > 4 * ((limit + 2) // 3):
        raise IntegrationError("Media exceeds size limit", 413)
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise IntegrationError(
            "Expected strict base64 content, not a URL or data URL"
        ) from None
    if not data or len(data) > limit:
        raise IntegrationError("Media is empty or exceeds size limit", 413)
    signatures = {
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        "audio/wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/mpeg": data.startswith(b"ID3")
        or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224),
        "audio/webm": data.startswith(b"\x1a\x45\xdf\xa3"),
        "audio/ogg": data.startswith(b"OggS"),
        "audio/flac": data.startswith(b"fLaC"),
        "audio/mp4": data[4:8] == b"ftyp",
    }
    if not signatures.get(mime_type, False):
        raise IntegrationError(
            "Media signature does not match an allowed MIME type", 415
        )
    return data


class MediaService:
    def __init__(
        self,
        settings: MediaSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        self._transport = transport
        self._active = 0

    @classmethod
    def from_env(cls, config: Any = None) -> "MediaService":
        return cls(MediaSettings.from_env(config))

    def status(self) -> dict:
        configured = bool(self.settings.api_key)
        capabilities = {}
        for name in ("vision", "transcription", "speech"):
            enabled = getattr(self.settings, f"{name}_enabled")
            capabilities[name] = {
                "enabled": enabled,
                "configured": configured,
                "ready": enabled and configured,
                "reason": (
                    "ready"
                    if enabled and configured
                    else "disabled" if not enabled else "credential_missing"
                ),
                "model": getattr(self.settings, f"{name}_model"),
            }
        return {
            "provider": "openai",
            "capabilities": capabilities,
            "limits": {
                "image_bytes": IMAGE_LIMIT,
                "audio_bytes": AUDIO_LIMIT,
                "speech_characters": 4096,
                "concurrent_requests": self.settings.max_concurrent,
                "timeout_seconds": self.settings.timeout_seconds,
            },
            "image_mime_types": list(IMAGE_TYPES),
            "audio_mime_types": list(AUDIO_TYPES),
            "active_requests": self._active,
            "stores_media": False,
            "provider_data_notice": "Content is sent to OpenAI; provider data controls apply.",
            "speech_notice": "Generated speech is AI-generated, not a human voice.",
        }

    def require(self, capability: str) -> None:
        if not getattr(self.settings, f"{capability}_enabled", False):
            raise IntegrationError("Media capability is disabled", 503)
        if not self.settings.api_key:
            raise IntegrationError("Media provider credential is not configured", 503)

    async def _request(
        self, path: str, *, binary: bool = False, **kwargs: Any
    ) -> bytes | dict:
        if self._active >= self.settings.max_concurrent:
            raise IntegrationError("Media service is busy; retry later", 429)
        self._active += (
            1  # No await before increment: admission is atomic on this event loop.
        )
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self.settings.timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream(
                        "POST",
                        PROVIDER_ROOT + path,
                        headers={"Authorization": "Bearer " + self.settings.api_key},
                        **kwargs,
                    ) as response:
                        if response.status_code == 429:
                            raise IntegrationError(
                                "Media provider rate limit reached", 429
                            )
                        if response.status_code != 200:
                            raise IntegrationError(
                                "Media provider rejected the request", 502
                            )
                        if binary and response.headers.get("content-type", "").split(
                            ";"
                        )[0] not in (
                            "audio/mpeg",
                            "audio/mp3",
                            "application/octet-stream",
                        ):
                            raise IntegrationError(
                                "Unexpected media provider response", 502
                            )
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(data) + len(chunk) > (
                                RESPONSE_LIMIT if binary else MIB
                            ):
                                raise IntegrationError(
                                    "Media provider response exceeds limit", 502
                                )
                            data.extend(chunk)
                        if binary:
                            if not data:
                                raise IntegrationError(
                                    "Media provider returned empty audio", 502
                                )
                            return bytes(data)
                        try:
                            value = json.loads(data)
                            if not isinstance(value, dict):
                                raise ValueError
                            return value
                        except (ValueError, UnicodeError):
                            raise IntegrationError(
                                "Invalid media provider response", 502
                            ) from None
        except (TimeoutError, httpx.TimeoutException):
            raise IntegrationError("Media request timed out", 504) from None
        except httpx.HTTPError:
            raise IntegrationError("Media provider is unavailable", 502) from None
        finally:
            self._active -= 1

    async def vision(self, request: VisionRequest) -> dict:
        self.require("vision")
        data = decode_media(request.data_base64, request.mime_type, IMAGE_LIMIT)
        body = {
            "model": self.settings.vision_model,
            "store": False,
            "max_completion_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{request.mime_type};base64,"
                                + base64.b64encode(data).decode("ascii"),
                                "detail": request.detail,
                            },
                        },
                    ],
                }
            ],
        }
        value = await self._request("/chat/completions", json=body)
        try:
            text = value["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise IntegrationError("Invalid vision provider response", 502) from None
        return self._text_result(text, self.settings.vision_model)

    async def transcribe(self, request: TranscriptionRequest) -> dict:
        self.require("transcription")
        data = decode_media(request.data_base64, request.mime_type, AUDIO_LIMIT)
        extension = {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/flac": "flac",
            "audio/mp4": "mp4",
        }[request.mime_type]
        fields = {"model": self.settings.transcription_model, "response_format": "json"}
        if request.language:
            fields["language"] = request.language
        value = await self._request(
            "/audio/transcriptions",
            data=fields,
            files={"file": ("upload." + extension, data, request.mime_type)},
        )
        return self._text_result(value.get("text"), self.settings.transcription_model)

    async def speech(self, request: SpeechRequest) -> bytes:
        self.require("speech")
        if not request.text.strip():
            raise IntegrationError("Speech text must not be blank")
        return await self._request(
            "/audio/speech",
            binary=True,
            json={
                "model": self.settings.speech_model,
                "input": request.text,
                "voice": request.voice,
                "response_format": "mp3",
            },
        )

    @staticmethod
    def _text_result(text: Any, model: str) -> dict:
        if not isinstance(text, str) or not text.strip() or len(text) > 100_000:
            raise IntegrationError("Invalid media provider text response", 502)
        safe, findings = redact_text(text)
        return {
            "text": safe,
            "model": model,
            "provider": "openai",
            "stored": False,
            "untrusted_content": True,
            "redacted": bool(findings),
        }

    async def close(self) -> None:
        """Clients are per-request and always closed, including cancellation."""
