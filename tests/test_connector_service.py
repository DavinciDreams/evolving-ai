"""Network-free connector auth, replay, sanitization, and inbox contracts."""

import asyncio
import hashlib
import hmac
import json
import sqlite3
import threading
import time

import pytest

from evolving_agent.integrations.connectors import (
    WEBHOOK_LIMIT,
    ConnectorService,
    ConnectorSettings,
)
from evolving_agent.integrations.media import IntegrationError

SECRET = "test-signing-key-not-a-real-secret-123456789"
NOW = 1_788_000_000


def service(tmp_path, **changes):
    return ConnectorService(
        ConnectorSettings(
            enabled=True,
            signing_secret=SECRET,
            database_path=str(tmp_path / "inbox.sqlite3"),
            **changes,
        ),
        clock=lambda: NOW,
    )


def signed(
    data=None,
    *,
    event_id="event-1",
    timestamp=str(NOW),
    connector_id="app-webhook",
    raw=None,
):
    body = (
        raw
        if raw is not None
        else json.dumps(
            {"id": event_id, "type": "app.updated", "data": data or {"text": "hello"}}
        ).encode()
    )
    signature = (
        "sha256="
        + hmac.new(
            SECRET.encode(),
            connector_id.encode() + b"." + timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
    )
    return body, timestamp, signature


@pytest.mark.asyncio
async def test_receive_review_and_no_execution(tmp_path):
    inbox = service(tmp_path)
    result = await inbox.receive(
        "app-webhook",
        *signed(
            {
                "command": "delete everything",
                "api_key": "opaque-secret",
                "text": "token sk-abcdefghijklmnopqrstuv",
            }
        ),
    )
    assert result["dispatched"] is False
    events = await inbox.list_events()
    assert len(events) == 1 and events[0]["untrusted_content"] is True
    assert events[0]["payload"]["command"] == "delete everything"
    assert "opaque-secret" not in str(
        events
    ) and "sk-abcdefghijklmnopqrstuv" not in str(events)
    ack = await inbox.acknowledge("app-webhook", "event-1", "reviewed")
    assert ack["payload_removed"] is True and ack["dispatched"] is False
    assert await inbox.list_events() == []
    assert (await inbox.list_events(status="all"))[0]["payload"] == {}


@pytest.mark.asyncio
async def test_replay_survives_service_restart(tmp_path):
    await service(tmp_path).receive("app-webhook", *signed())
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive("app-webhook", *signed())
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_idempotency_survives_new_signature_and_ack(tmp_path):
    inbox = service(tmp_path)
    await inbox.receive("app-webhook", *signed())
    await inbox.acknowledge("app-webhook", "event-1", "discarded")
    with pytest.raises(IntegrationError) as exc:
        await inbox.receive("app-webhook", *signed(timestamp=str(NOW + 1)))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("_attempt", range(20))
async def test_concurrent_duplicate_admission_is_atomic(tmp_path, _attempt):
    inbox = service(tmp_path)
    results = await asyncio.gather(
        *[inbox.receive("app-webhook", *signed()) for _ in range(5)],
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert all(
        isinstance(result, dict)
        or (isinstance(result, IntegrationError) and result.status_code == 409)
        for result in results
    ), [
        (type(result).__name__, getattr(result, "status_code", None))
        for result in results
    ]


@pytest.mark.asyncio
async def test_parallel_service_bootstrap_serializes_journal_transition(
    tmp_path, monkeypatch
):
    # Deterministically reproduce SQLite's cold-start journal lock window. The
    # old implementation entered PRAGMA WAL from several workers concurrently.
    journal_transition = threading.Lock()
    original_connect = sqlite3.connect

    class Connection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql != "PRAGMA journal_mode=WAL":
                return super().execute(sql, *args, **kwargs)
            if not journal_transition.acquire(blocking=False):
                raise sqlite3.OperationalError(
                    "synthetic concurrent journal transition"
                )
            try:
                time.sleep(0.02)
                return super().execute(sql, *args, **kwargs)
            finally:
                journal_transition.release()

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: original_connect(*args, factory=Connection, **kwargs),
    )
    inboxes = [service(tmp_path) for _ in range(5)]
    results = await asyncio.gather(
        *[inbox.receive("app-webhook", *signed()) for inbox in inboxes],
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sorted(getattr(result, "status_code", 202) for result in results) == [
        202,
        409,
        409,
        409,
        409,
    ]


@pytest.mark.parametrize(
    "timestamp", [str(NOW - 301), str(NOW + 301), "NaN", "", "0" * 50]
)
@pytest.mark.asyncio
async def test_invalid_or_expired_timestamp(tmp_path, timestamp):
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive("app-webhook", *signed(timestamp=timestamp))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_body_and_route_signature_binding(tmp_path):
    body, timestamp, signature = signed()
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive(
            "app-webhook", body + b" ", timestamp, signature
        )
    assert exc.value.status_code == 401
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive("unreviewed-plugin", body, timestamp, signature)
    assert exc.value.status_code == 404
    assert not (tmp_path / "inbox.sqlite3").exists()


@pytest.mark.parametrize(
    "body",
    [
        b"{}",
        b"[]",
        b"{not json",
        b'{"id":"a","id":"b","type":"x","data":{}}',
        b'{"id":"a","type":"x","data":{"bad":NaN}}',
        b'{"id":"a","type":"x","data":{},"execute":true}',
    ],
)
@pytest.mark.asyncio
async def test_invalid_json_envelope(tmp_path, body):
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive("app-webhook", *signed(raw=body))
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_nested_sensitive_fields_are_redacted(tmp_path):
    inbox = service(tmp_path)
    await inbox.receive(
        "app-webhook",
        *signed(
            {
                "nested": [
                    {
                        "Authorization": "randomopaque",
                        "privateKey": "unprefixed",
                        "ok": "visible",
                    }
                ]
            }
        ),
    )
    event = (await inbox.list_events())[0]
    assert "randomopaque" not in str(event) and "unprefixed" not in str(event)
    assert "visible" in str(event)


@pytest.mark.asyncio
async def test_nested_payload_and_size_bounded(tmp_path):
    nested = {"leaf": "value"}
    for _ in range(15):
        nested = {"nested": nested}
    with pytest.raises(IntegrationError, match="nesting"):
        await service(tmp_path).receive("app-webhook", *signed(nested))
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive(
            "app-webhook", *signed(raw=b"x" * (WEBHOOK_LIMIT + 1))
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_overflowed_json_number_rejected_without_server_error(tmp_path):
    raw = b'{"id":"a","type":"x","data":{"number":1e9999}}'
    with pytest.raises(IntegrationError) as exc:
        await service(tmp_path).receive("app-webhook", *signed(raw=raw))
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_capacity_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr("evolving_agent.integrations.connectors.MAX_EVENTS", 2)
    inbox = service(tmp_path)
    await inbox.receive("app-webhook", *signed(event_id="one"))
    await inbox.receive("app-webhook", *signed(event_id="two"))
    with pytest.raises(IntegrationError) as exc:
        await inbox.receive("app-webhook", *signed(event_id="three"))
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_disabled_no_disk_effects(tmp_path):
    inbox = ConnectorService(
        ConnectorSettings(database_path=str(tmp_path / "absent" / "inbox.sqlite3"))
    )
    assert not inbox.status()["ready"]
    with pytest.raises(IntegrationError):
        await inbox.receive("app-webhook", *signed())
    assert not (tmp_path / "absent").exists()


def test_no_unreviewed_plugins_or_shared_credentials(monkeypatch):
    with pytest.raises(ValueError):
        ConnectorSettings(allowlist=("arbitrary.python.import",))
    with pytest.raises(ValueError):
        ConnectorSettings(signing_secret="short")
    monkeypatch.setenv("CONNECTOR_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("HAM_API_KEY", SECRET)
    with pytest.raises(ValueError, match="reuse"):
        ConnectorSettings.from_env()
    assert SECRET not in repr(ConnectorSettings(signing_secret=SECRET))
