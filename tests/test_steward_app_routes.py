"""Actual registered API contracts with fake dependencies and no remote effects.

The production import tree needs ai-sdk-python. Minimal Windows installations
skip this module; the complete Ubuntu runtime executes it against the real app.
"""

import base64
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("ai_sdk", reason="Full API runtime requires ai-sdk-python")

import evolving_agent.utils.api_server as api_server
import evolving_agent.utils.app_state as app_state
from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.integrations.connectors import ConnectorService, ConnectorSettings
from evolving_agent.integrations.media import MediaService, MediaSettings
from evolving_agent.utils.deps import get_agent

PROJECT_SECRET = "synthetic-project-access-key"
MEDIA_SECRET = "synthetic-media-provider-access-key"
HOOK_SECRET = "synthetic-webhook-signing-key-123456789"
NOW = 1_788_000_000


class FakeControl:
    def __init__(self):
        self.busy = False
        self.submitted = []
        self.jobs = {}
        self.dreams = SimpleNamespace(
            settings=SimpleNamespace(enabled=True), run_once=AsyncMock()
        )
        self.lab = SimpleNamespace(
            evaluate=AsyncMock(), promote=AsyncMock(), rollback=AsyncMock()
        )

    def submit(self, kind, operation):
        if self.busy:
            raise RuntimeBusyError("synthetic-private-busy-diagnostics")
        job_id = f"job-{len(self.submitted) + 1}"
        self.submitted.append((kind, operation))
        self.jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "queued"}
        return self.jobs[job_id]

    def status(self):
        return {
            "runtime": {"busy": self.busy, "timeout_seconds": 60},
            "dreams": {"enabled": self.dreams.settings.enabled, "running": False},
            "improvement": {"enabled": self.lab is not None, "revision": 0},
            "jobs": list(self.jobs.values()),
        }


def evaluation_payload():
    return {
        "candidate_id": "candidate-1",
        "run_id": "run-1",
        "strategy": {"verify_calculations": True},
        "cases": [
            {
                "case_id": f"case-{index}",
                "prompt": f"Calculate {index}+1",
                "expected": str(index + 1),
                "split": "development" if index < 2 else "holdout",
            }
            for index in range(4)
        ],
    }


@pytest.fixture
def registered_app(monkeypatch, tmp_path):
    # conftest disables auth for old compatibility tests: explicitly restore the
    # production default here, so this suite cannot accidentally bypass it.
    monkeypatch.delenv("API_AUTH_REQUIRED", raising=False)
    monkeypatch.setenv("PROJECT_API_KEY", PROJECT_SECRET)
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", MEDIA_SECRET)
    control = FakeControl()
    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value="A synthetic answer"),
        last_evaluation_score=None,
        last_storage_status={"memory_stored": False, "knowledge_updated": False},
        steward=control,
        initialized=True,
        session_id="synthetic-session",
        interaction_count=0,
        memory=SimpleNamespace(
            get_memory_stats=AsyncMock(return_value={"total_memories": 0})
        ),
        knowledge_base=SimpleNamespace(knowledge={}),
    )
    provider_calls = []

    def provider(request):
        provider_calls.append(request.url.path)
        if request.url.path.endswith("/speech"):
            return httpx.Response(
                200, content=b"ID3synthetic", headers={"content-type": "audio/mpeg"}
            )
        if request.url.path.endswith("/transcriptions"):
            return httpx.Response(200, json={"text": "Synthetic transcript"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Synthetic image description"}}]},
        )

    @asynccontextmanager
    async def no_lifespan(_):
        yield

    app = api_server.app
    monkeypatch.setattr(app.router, "lifespan_context", no_lifespan)
    monkeypatch.setitem(app.dependency_overrides, get_agent, lambda: fake_agent)
    monkeypatch.setattr(app_state, "agent", fake_agent)
    monkeypatch.setattr(
        app.state,
        "media_service",
        MediaService(
            MediaSettings(
                api_key=MEDIA_SECRET,
                vision_enabled=True,
                transcription_enabled=True,
                speech_enabled=True,
            ),
            transport=httpx.MockTransport(provider),
        ),
        raising=False,
    )
    monkeypatch.setattr(
        app.state,
        "connector_service",
        ConnectorService(
            ConnectorSettings(
                enabled=True,
                signing_secret=HOOK_SECRET,
                database_path=str(tmp_path / "inbox.sqlite3"),
            ),
            clock=lambda: NOW,
        ),
        raising=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client,
            agent=fake_agent,
            control=control,
            provider_calls=provider_calls,
        )


def headers():
    return {"X-API-Key": PROJECT_SECRET}


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/steward/status"),
        ("GET", "/steward/jobs/test"),
        ("POST", "/steward/dream"),
        ("POST", "/steward/improvement/evaluate"),
        ("POST", "/steward/improvement/promote"),
        ("POST", "/steward/improvement/rollback"),
        ("GET", "/media/status"),
        ("POST", "/media/vision"),
        ("POST", "/media/transcribe"),
        ("POST", "/media/speech"),
        ("GET", "/connectors/status"),
        ("GET", "/connectors/events"),
        ("POST", "/connectors/webhooks/app-webhook"),
        ("POST", "/connectors/events/app-webhook/example/acknowledge"),
        ("POST", "/chat"),
        ("POST", "/chat/stream"),
        ("POST", "/v1/chat/completions"),
    ],
)
def test_registered_private_routes_authenticate_before_parsing(
    registered_app, method, path
):
    response = registered_app.client.request(
        method, path, content=b"malformed private body"
    )
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert registered_app.provider_calls == []
    registered_app.agent.run.assert_not_awaited()
    assert registered_app.control.submitted == []


def test_bearer_auth_and_missing_server_key_fail_closed(registered_app, monkeypatch):
    client = registered_app.client
    assert (
        client.get(
            "/steward/status", headers={"Authorization": f"Bearer {PROJECT_SECRET}"}
        ).status_code
        == 200
    )
    assert (
        client.get("/steward/status", headers={"X-API-Key": "wrong"}).status_code == 401
    )
    monkeypatch.setenv("PROJECT_API_KEY", "")
    assert client.get("/steward/status", headers=headers()).status_code == 503


@pytest.mark.parametrize(
    "path", ["/steward/status", "/media/status", "/connectors/status"]
)
def test_status_never_exposes_provider_or_project_keys(registered_app, path):
    response = registered_app.client.get(path, headers=headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    for secret in (PROJECT_SECRET, MEDIA_SECRET, HOOK_SECRET):
        assert secret not in response.text
    assert registered_app.provider_calls == []


@pytest.mark.parametrize(
    "path",
    [
        "/chat",
        "/steward/improvement/evaluate",
        "/steward/improvement/promote",
        "/media/vision",
    ],
)
def test_malformed_json_errors_never_echo_content(registered_app, path):
    response = registered_app.client.post(
        path,
        headers={**headers(), "Content-Type": "application/json"},
        content=b'{"private-field":"raw-secret-value" INVALID',
    )
    assert response.status_code in (400, 422)
    assert "raw-secret-value" not in response.text
    assert "private-field" not in response.text
    assert registered_app.provider_calls == []


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/steward/improvement/promote", {"run_id": "run-1", "expected_revision": 0}),
        (
            "/steward/improvement/rollback",
            {"expected_revision": 1, "reason": "operator review"},
        ),
        ("/media/speech", {"text": "hello"}),
    ],
)
def test_unknown_field_name_and_value_are_both_redacted(registered_app, path, payload):
    response = registered_app.client.post(
        path,
        headers=headers(),
        json={**payload, "secret-as-json-key": "private-base64-as-value"},
    )
    assert response.status_code == 422
    assert "secret-as-json-key" not in response.text
    assert "private-base64-as-value" not in response.text
    assert registered_app.provider_calls == []
    assert registered_app.control.submitted == []


def test_dream_returns_receipt_without_waiting_or_calling_model(registered_app):
    response = registered_app.client.post("/steward/dream", headers=headers())
    assert response.status_code == 202 and response.json()["status"] == "queued"
    assert registered_app.control.submitted[0][0] == "dream"
    registered_app.control.dreams.run_once.assert_not_awaited()
    job = registered_app.client.get(
        "/steward/jobs/" + response.json()["job_id"], headers=headers()
    )
    assert job.json()["status"] == "queued"


def test_dream_disabled_and_busy_fail_explicitly(registered_app):
    registered_app.control.busy = True
    response = registered_app.client.post("/steward/dream", headers=headers())
    assert response.status_code == 409
    assert "synthetic-private-busy-diagnostics" not in response.text
    registered_app.control.busy = False
    registered_app.control.dreams.settings.enabled = False
    assert (
        registered_app.client.post("/steward/dream", headers=headers()).status_code
        == 403
    )


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/steward/improvement/evaluate", evaluation_payload()),
        ("/steward/improvement/promote", {"run_id": "run-1", "expected_revision": 0}),
        (
            "/steward/improvement/rollback",
            {"expected_revision": 1, "reason": "operator request"},
        ),
    ],
)
def test_improvement_actions_enqueue_only(registered_app, path, payload):
    response = registered_app.client.post(path, headers=headers(), json=payload)
    assert response.status_code == 202 and response.json()["status"] == "queued"
    assert registered_app.control.submitted[0][0] == "improvement"
    for method in ("evaluate", "promote", "rollback"):
        getattr(registered_app.control.lab, method).assert_not_awaited()


def test_closed_strategy_rejects_injected_authority(registered_app):
    payload = evaluation_payload()
    payload["strategy"]["execute_shell"] = "private-untrusted-instruction"
    response = registered_app.client.post(
        "/steward/improvement/evaluate", headers=headers(), json=payload
    )
    assert response.status_code == 422
    assert "private-untrusted-instruction" not in response.text
    assert registered_app.control.submitted == []


def test_chat_truthfully_reports_unstored_and_unevaluated_response(registered_app):
    response = registered_app.client.post(
        "/chat", headers=headers(), json={"query": "hello", "conversation_id": "conv-1"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "A synthetic answer"
    assert body["evaluation_score"] is None
    assert body["memory_stored"] is False and body["knowledge_updated"] is False
    registered_app.agent.run.assert_awaited_once_with(
        "hello", context_hints=None, conversation_id="conv-1", wait_for_storage=True
    )


@pytest.mark.parametrize(
    "exception,status",
    [
        (RuntimeBusyError("private-busy-state"), 409),
        (TimeoutError("private-provider-timeout"), 504),
        (RuntimeError("private-provider-body"), 500),
    ],
)
def test_chat_failures_are_typed_and_sanitized(registered_app, exception, status):
    registered_app.agent.run.side_effect = exception
    response = registered_app.client.post(
        "/chat", headers=headers(), json={"query": "hello"}
    )
    assert response.status_code == status
    assert str(exception) not in response.text
    registered_app.agent.run.assert_awaited_once()


def sse_events(response):
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


def test_sse_delegates_once_to_guarded_core_and_reports_truthful_completion(
    registered_app,
):
    response = registered_app.client.post(
        "/chat/stream", headers=headers(), json={"query": "hello"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    events = sse_events(response)
    assert events[-1]["type"] == "complete" and events[-1]["buffered"] is True
    assert (
        events[-1]["evaluation_score"] is None and events[-1]["memory_stored"] is False
    )
    assert (
        "".join(event["content"] for event in events if event["type"] == "chunk")
        == "A synthetic answer"
    )
    registered_app.agent.run.assert_awaited_once()
    assert registered_app.agent.run.call_args.kwargs["wait_for_storage"] is True


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/chat/stream", {"query": "hello"}),
        (
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hello"}], "stream": True},
        ),
    ],
)
def test_stream_errors_do_not_expose_exception_bodies(registered_app, path, payload):
    registered_app.agent.run.side_effect = RuntimeError(
        "upstream-credential-and-private-body"
    )
    response = registered_app.client.post(path, headers=headers(), json=payload)
    assert response.status_code == 200  # Headers precede the SSE error frame.
    assert "upstream-credential-and-private-body" not in response.text
    assert "error" in response.text
    assert not any(event.get("type") == "complete" for event in sse_events(response))
    registered_app.agent.run.assert_awaited_once()


def test_media_routes_use_fake_provider_only_and_never_core_agent(registered_app):
    client = registered_app.client
    image = base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
    audio = base64.b64encode(b"RIFF\x20\x00\x00\x00WAVEfixture").decode()
    vision = client.post(
        "/media/vision",
        headers=headers(),
        json={"mime_type": "image/png", "data_base64": image},
    )
    assert vision.status_code == 200 and vision.json()["stored"] is False
    transcript = client.post(
        "/media/transcribe",
        headers=headers(),
        json={"mime_type": "audio/wav", "data_base64": audio},
    )
    assert (
        transcript.status_code == 200
        and transcript.json()["text"] == "Synthetic transcript"
    )
    speech = client.post("/media/speech", headers=headers(), json={"text": "hello"})
    assert speech.status_code == 200 and speech.content == b"ID3synthetic"
    assert speech.headers["x-audio-generated"] == "ai"
    assert registered_app.provider_calls == [
        "/v1/chat/completions",
        "/v1/audio/transcriptions",
        "/v1/audio/speech",
    ]
    registered_app.agent.run.assert_not_awaited()


def test_connector_requires_signature_then_reviews_without_dispatch(registered_app):
    client = registered_app.client
    body = json.dumps(
        {
            "id": "event-1",
            "type": "app.updated",
            "data": {"token": "private-app-secret", "message": "hello"},
        }
    ).encode()
    timestamp = str(NOW)
    signature = (
        "sha256="
        + hmac.new(
            HOOK_SECRET.encode(),
            b"app-webhook." + timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
    )
    signed_headers = {
        **headers(),
        "Content-Type": "application/json",
        "X-Katbot-Timestamp": timestamp,
        "X-Katbot-Signature": signature,
    }
    assert (
        client.post(
            "/connectors/webhooks/app-webhook",
            headers={**headers(), "Content-Type": "application/json"},
            content=body,
        ).status_code
        == 401
    )
    accepted = client.post(
        "/connectors/webhooks/app-webhook", headers=signed_headers, content=body
    )
    assert accepted.status_code == 202 and accepted.json()["dispatched"] is False
    assert (
        client.post(
            "/connectors/webhooks/app-webhook", headers=signed_headers, content=body
        ).status_code
        == 409
    )
    listing = client.get("/connectors/events", headers=headers())
    assert listing.status_code == 200 and len(listing.json()["events"]) == 1
    assert "private-app-secret" not in listing.text
    ack = client.post(
        "/connectors/events/app-webhook/event-1/acknowledge",
        headers=headers(),
        json={"disposition": "reviewed"},
    )
    assert ack.status_code == 200 and ack.json()["payload_removed"] is True
    registered_app.agent.run.assert_not_awaited()


def test_real_lifespan_initializes_and_closes_fake_agent(monkeypatch):
    """Exercise actual startup plumbing while replacing every external capability."""
    for name in (
        "GITHUB_TOKEN",
        "GITHUB_REPO",
        "HAM_API_KEY",
        "CONNECTOR_WEBHOOK_SECRET",
        "MEDIA_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.setenv(name, "")
    for name in (
        "DISCORD_ENABLED",
        "CONNECTORS_ENABLED",
        "MEDIA_VISION_ENABLED",
        "MEDIA_TRANSCRIPTION_ENABLED",
        "MEDIA_SPEECH_ENABLED",
    ):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setenv("PROJECT_API_KEY", PROJECT_SECRET)
    fake_agent = SimpleNamespace(
        initialize=AsyncMock(), cleanup=AsyncMock(), initialized=True
    )
    # api_server replaces its module with a compatibility shim. Existing function
    # globals still point at the original module dictionary, not the shim's copy.
    lifespan_globals = api_server.lifespan.__wrapped__.__globals__
    monkeypatch.setitem(lifespan_globals, "SelfImprovingAgent", lambda: fake_agent)
    monkeypatch.setattr(app_state, "agent", None)
    monkeypatch.setattr(app_state, "github_modifier", None)
    monkeypatch.setattr(app_state, "discord_integration", None)
    monkeypatch.setattr(app_state, "server_shutdown", False)
    monkeypatch.setattr(
        api_server.error_recovery_manager, "cleanup_old_checkpoints", lambda: None
    )
    # Restore any app.state objects populated by this real lifespan afterwards.
    monkeypatch.setattr(api_server.app.state, "media_service", None, raising=False)
    monkeypatch.setattr(api_server.app.state, "connector_service", None, raising=False)
    with TestClient(api_server.app, raise_server_exceptions=False) as client:
        assert client.get("/health").json()["agent_initialized"] is True
        fake_agent.initialize.assert_awaited_once()
        assert (
            api_server.app.state.media_service.status()["capabilities"]["vision"][
                "enabled"
            ]
            is False
        )
        assert api_server.app.state.connector_service.status()["enabled"] is False
    fake_agent.cleanup.assert_awaited_once()
    assert app_state.server_shutdown is True
