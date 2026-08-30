"""Network-free contract and safety tests for opt-in media."""

import asyncio
import base64
import json

import httpx
import pytest

from evolving_agent.integrations.media import (
    AUDIO_LIMIT,
    IMAGE_LIMIT,
    IntegrationError,
    MediaService,
    MediaSettings,
    SpeechRequest,
    TranscriptionRequest,
    VisionRequest,
    decode_media,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"test-image"
WAV = b"RIFF\x20\x00\x00\x00WAVE" + b"test-audio"


def image_request(**changes):
    return VisionRequest(
        **{
            "mime_type": "image/png",
            "data_base64": base64.b64encode(PNG).decode(),
            **changes,
        }
    )


def configured(handler, **changes):
    return MediaService(
        MediaSettings(
            api_key="test-provider-key",
            vision_enabled=True,
            transcription_enabled=True,
            speech_enabled=True,
            **changes
        ),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_disabled_never_contacts_provider():
    service = MediaService(
        MediaSettings(), transport=httpx.MockTransport(lambda _: pytest.fail("network"))
    )
    assert service.status()["capabilities"]["vision"]["reason"] == "disabled"
    with pytest.raises(IntegrationError, match="disabled"):
        await service.vision(image_request())


@pytest.mark.asyncio
async def test_enabled_missing_credential_fails_closed():
    service = MediaService(MediaSettings(vision_enabled=True))
    assert not service.status()["capabilities"]["vision"]["ready"]
    with pytest.raises(IntegrationError, match="credential"):
        await service.vision(image_request())


@pytest.mark.asyncio
async def test_vision_exact_shape_fixed_destination_and_redaction():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["max_completion_tokens"] == 1024
        assert payload["messages"][0]["content"][1]["image_url"] == {
            "url": "data:image/png;base64," + base64.b64encode(PNG).decode(),
            "detail": "low",
        }
        assert "tools" not in payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "api_key=super-secret-value"}}]},
        )

    service = configured(handler)
    result = await service.vision(image_request())
    assert result["stored"] is False and result["redacted"] is True
    assert "super-secret-value" not in result["text"]
    assert service.status()["active_requests"] == 0


@pytest.mark.asyncio
async def test_transcription_sends_real_multipart_shape():
    def handler(request):
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b'filename="upload.wav"' in request.content
        assert (
            b'name="model"' in request.content
            and b"gpt-4o-mini-transcribe" in request.content
        )
        assert (
            b'name="language"' in request.content and b"\r\nen\r\n" in request.content
        )
        assert WAV in request.content
        return httpx.Response(200, json={"text": "Hello Katbot"})

    result = await configured(handler).transcribe(
        TranscriptionRequest(
            mime_type="audio/wav",
            data_base64=base64.b64encode(WAV).decode(),
            language="en",
        )
    )
    assert result["text"] == "Hello Katbot"
    assert result["untrusted_content"] is True


@pytest.mark.asyncio
async def test_speech_binary_response():
    def handler(request):
        assert request.url.path == "/v1/audio/speech"
        assert json.loads(request.content) == {
            "model": "gpt-4o-mini-tts",
            "input": "Hello",
            "voice": "coral",
            "response_format": "mp3",
        }
        return httpx.Response(
            200, content=b"ID3audio", headers={"content-type": "audio/mpeg"}
        )

    assert await configured(handler).speech(SpeechRequest(text="Hello")) == b"ID3audio"


@pytest.mark.parametrize(
    "encoded",
    ["https://localhost/secrets", "data:image/png;base64,abcd", "!!!!", "aGVsbG8=\n"],
)
def test_base64_rejects_urls_and_noncanonical_whitespace(encoded):
    with pytest.raises(IntegrationError):
        decode_media(encoded, "image/png", IMAGE_LIMIT)


def test_mime_and_size_validation():
    with pytest.raises(IntegrationError) as exc:
        decode_media(base64.b64encode(PNG).decode(), "image/jpeg", IMAGE_LIMIT)
    assert exc.value.status_code == 415
    with pytest.raises(IntegrationError) as exc:
        decode_media(base64.b64encode(PNG).decode(), "image/png", 2)
    assert exc.value.status_code == 413
    assert decode_media(base64.b64encode(WAV).decode(), "audio/wav", AUDIO_LIMIT) == WAV


@pytest.mark.parametrize("status", [301, 302, 401, 500])
@pytest.mark.asyncio
async def test_provider_errors_and_redirects_are_sanitized(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="provider-secret-value",
            headers={"location": "http://127.0.0.1/private"},
        )

    with pytest.raises(IntegrationError) as exc:
        await configured(handler).vision(image_request())
    assert exc.value.status_code == 502
    assert "provider-secret-value" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_provider_timeout_releases_slot():
    def handler(request):
        raise httpx.ReadTimeout("secret diagnostics", request=request)

    service = configured(handler)
    with pytest.raises(IntegrationError) as exc:
        await service.vision(image_request())
    assert exc.value.status_code == 504
    assert service.status()["active_requests"] == 0


@pytest.mark.asyncio
async def test_concurrency_admission_and_cancellation_cleanup():
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"choices": [{"message": {"content": "fine"}}]})

    service = configured(handler, max_concurrent=1)
    task = asyncio.create_task(service.vision(image_request()))
    await entered.wait()
    with pytest.raises(IntegrationError) as exc:
        await service.vision(image_request())
    assert exc.value.status_code == 429
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service.status()["active_requests"] == 0


@pytest.mark.asyncio
async def test_response_size_bound():
    service = configured(
        lambda _: httpx.Response(200, content=b"x" * (1024 * 1024 + 1))
    )
    with pytest.raises(IntegrationError, match="exceeds limit"):
        await service.vision(image_request())


@pytest.mark.parametrize(
    "response", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}, []]
)
@pytest.mark.asyncio
async def test_malformed_provider_response(response):
    with pytest.raises(IntegrationError):
        await configured(lambda _: httpx.Response(200, json=response)).vision(
            image_request()
        )


def test_compatible_vendor_key_is_not_forwarded(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "vendor-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://vendor.invalid/v1")
    monkeypatch.delenv("MEDIA_OPENAI_API_KEY", raising=False)
    assert MediaSettings.from_env().api_key == ""
    monkeypatch.setenv("MEDIA_OPENAI_API_KEY", "dedicated-key")
    assert MediaSettings.from_env().api_key == "dedicated-key"
    assert "dedicated-key" not in repr(MediaSettings.from_env())


def test_configuration_rejects_unbounded_or_invalid_settings():
    with pytest.raises(ValueError):
        MediaSettings(timeout_seconds=float("nan"))
    with pytest.raises(ValueError):
        MediaSettings(max_concurrent=100)
    with pytest.raises(ValueError):
        MediaSettings(vision_model="https://evil.invalid/model")
