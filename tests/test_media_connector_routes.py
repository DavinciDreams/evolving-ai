"""Exercise actual routes with synthetic media and signed requests, never providers."""

import base64
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from evolving_agent.api.routes.connectors import router as connector_router
from evolving_agent.api.routes.media import router as media_router
from evolving_agent.integrations.connectors import ConnectorService, ConnectorSettings
from evolving_agent.integrations.media import MediaService, MediaSettings

SECRET = "not-a-real-secret-just-a-test-key-1234567890"
PROJECT_KEY = "project-key-for-network-free-test"
NOW = 1_788_000_000


@pytest.fixture
def api(tmp_path):
    app = FastAPI()

    # Model central authorization without importing the core model/DB runtime.
    @app.middleware("http")
    async def authentication(request: Request, call_next):
        if request.headers.get("X-API-Key") != PROJECT_KEY:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(media_router)
    app.include_router(connector_router)
    app.state.media_service = MediaService(
        MediaSettings(api_key="test", vision_enabled=True, speech_enabled=True),
        transport=httpx.MockTransport(
            lambda request: (
                httpx.Response(
                    200, json={"choices": [{"message": {"content": "A test image"}}]}
                )
                if request.url.path.endswith("completions")
                else httpx.Response(
                    200, content=b"ID3test", headers={"content-type": "audio/mpeg"}
                )
            )
        ),
    )
    app.state.connector_service = ConnectorService(
        ConnectorSettings(
            enabled=True,
            signing_secret=SECRET,
            database_path=str(tmp_path / "inbox.sqlite3"),
        ),
        clock=lambda: NOW,
    )
    return app


def auth_headers():
    return {"X-API-Key": PROJECT_KEY}


def webhook_request():
    body = json.dumps(
        {"id": "event-1", "type": "app.updated", "data": {"text": "hello"}}
    ).encode()
    stamp = str(NOW)
    signature = (
        "sha256="
        + hmac.new(
            SECRET.encode(),
            b"app-webhook." + stamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
    )
    return body, {
        **auth_headers(),
        "content-type": "application/json",
        "X-Katbot-Timestamp": stamp,
        "X-Katbot-Signature": signature,
    }


@pytest.mark.asyncio
async def test_media_routes_require_auth_and_return_private_response(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        assert (await client.get("/media/status")).status_code == 401
        response = await client.get("/media/status", headers=auth_headers())
        assert response.json()["capabilities"]["vision"]["ready"] is True
        assert response.headers["cache-control"] == "no-store"
        response = await client.post(
            "/media/vision",
            headers=auth_headers(),
            json={
                "mime_type": "image/png",
                "data_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode(),
            },
        )
        assert response.status_code == 200 and response.json()["text"] == "A test image"


@pytest.mark.asyncio
async def test_media_validation_never_echoes_secret_or_payload(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        response = await client.post(
            "/media/vision",
            headers=auth_headers(),
            json={"secret": "sensitive-input", "data_base64": "very-private-image"},
        )
        assert response.status_code == 422
        assert (
            "sensitive-input" not in response.text
            and "very-private-image" not in response.text
        )
        response = await client.post(
            "/media/vision",
            headers={**auth_headers(), "content-type": "image/png"},
            content=b"png",
        )
        assert response.status_code == 415
        response = await client.post(
            "/media/vision",
            headers={**auth_headers(), "content-encoding": "gzip"},
            json={},
        )
        assert response.status_code == 415


@pytest.mark.asyncio
async def test_speech_disclosure_and_nosniff(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        response = await client.post(
            "/media/speech", headers=auth_headers(), json={"text": "Hello"}
        )
        assert response.status_code == 200 and response.content == b"ID3test"
        assert response.headers["x-audio-generated"] == "ai"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_webhook_requires_both_project_key_and_signature(api):
    body, headers = webhook_request()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        without_key = {
            key: value for key, value in headers.items() if key != "X-API-Key"
        }
        assert (
            await client.post(
                "/connectors/webhooks/app-webhook", headers=without_key, content=body
            )
        ).status_code == 401
        assert (
            await client.post(
                "/connectors/webhooks/app-webhook",
                headers={**auth_headers(), "content-type": "application/json"},
                content=body,
            )
        ).status_code == 401
        response = await client.post(
            "/connectors/webhooks/app-webhook", headers=headers, content=body
        )
        assert response.status_code == 202 and response.json()["dispatched"] is False
        assert (
            await client.post(
                "/connectors/webhooks/app-webhook", headers=headers, content=body
            )
        ).status_code == 409
        events = await client.get("/connectors/events", headers=auth_headers())
        assert len(events.json()["events"]) == 1
        response = await client.post(
            "/connectors/events/app-webhook/event-1/acknowledge",
            headers=auth_headers(),
            json={"disposition": "reviewed"},
        )
        assert (
            response.status_code == 200 and response.json()["payload_removed"] is True
        )


@pytest.mark.asyncio
async def test_declared_and_streaming_body_size_limits(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        response = await client.post(
            "/connectors/webhooks/app-webhook",
            headers={
                **auth_headers(),
                "content-type": "application/json",
                "content-length": "1000000",
            },
            content=b"{}",
        )
        assert response.status_code == 413

        async def chunks():
            for _ in range(10):
                yield b"x" * 8192

        response = await client.post(
            "/connectors/webhooks/app-webhook",
            headers={**auth_headers(), "content-type": "application/json"},
            content=chunks(),
        )
        assert response.status_code == 413
