"""Allowlisted connector contracts and a bounded, review-only webhook inbox.

The SQLite inbox is delivery state, not agent memory. Payloads never execute code,
enter a model prompt, or grant authority. HAM remains the memory substrate.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from evolving_agent.integrations.media import IntegrationError
from evolving_agent.utils.secret_redaction import redact_text

WEBHOOK_LIMIT = 64 * 1024
MAX_EVENTS = 500
WINDOW_SECONDS = 300
RETENTION_SECONDS = 7 * 24 * 3600
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SENSITIVE_KEY = re.compile(
    r"(?i)(?:secret|password|token|credential|authorization|api.?key|private.?key|nsec|cookie)"
)


@dataclass(frozen=True)
class ConnectorManifest:
    id: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    authority: str = "receive_untrusted_events_only"
    outbound_network: bool = False
    executes_code: bool = False


MANIFESTS = (
    ConnectorManifest(
        id="app-webhook",
        version="1.0.0",
        description="Signed event bridge for apps, CI, and reviewed plugin integrations",
        capabilities=("events.receive", "events.list", "events.acknowledge"),
    ),
)


@dataclass(frozen=True)
class ConnectorSettings:
    enabled: bool = False
    allowlist: tuple[str, ...] = ("app-webhook",)
    signing_secret: str = field(default="", repr=False)
    database_path: str = "./persistent_data/connector_inbox.sqlite3"

    def __post_init__(self):
        known = {manifest.id for manifest in MANIFESTS}
        if not set(self.allowlist).issubset(known):
            raise ValueError("Connector allowlist contains an unreviewed connector")
        if self.signing_secret and len(self.signing_secret.encode("utf-8")) < 32:
            raise ValueError("Connector signing secret must contain at least 32 bytes")

    @classmethod
    def from_env(cls, config: Any = None) -> "ConnectorSettings":
        secret = os.getenv("CONNECTOR_WEBHOOK_SECRET", "")
        project_key = getattr(
            config,
            "api_key",
            os.getenv("PROJECT_API_KEY", "") or os.getenv("API_KEY", ""),
        )
        ham_key = getattr(config, "ham_api_key", os.getenv("HAM_API_KEY", ""))
        for other in (project_key, ham_key, os.getenv("GITHUB_TOKEN", "")):
            if (
                secret
                and other
                and hmac.compare_digest(secret.encode(), other.encode())
            ):
                raise ValueError(
                    "Connector signing secret must not reuse a service credential"
                )
        data_dir = getattr(
            config,
            "persistent_data_dir",
            os.getenv("PERSISTENT_DATA_DIR", "./persistent_data"),
        )
        return cls(
            enabled=os.getenv("CONNECTORS_ENABLED", "false").lower() == "true",
            allowlist=tuple(
                part.strip()
                for part in os.getenv("CONNECTOR_ALLOWLIST", "app-webhook").split(",")
                if part.strip()
            ),
            signing_secret=secret,
            database_path=str(Path(data_dir) / "connector_inbox.sqlite3"),
        )


def _sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 12:
        raise IntegrationError("Webhook payload nesting exceeds limit", 422)
    if isinstance(value, float) and not math.isfinite(value):
        raise IntegrationError("Webhook numbers must be finite", 422)
    if isinstance(value, dict):
        if len(value) > 100:
            raise IntegrationError("Webhook object has too many fields", 422)
        output = {}
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 128:
                raise IntegrationError("Webhook field names exceed limits", 422)
            safe_key, _ = redact_text(key)
            output[safe_key] = (
                "[REDACTED:sensitive_field]"
                if _SENSITIVE_KEY.search(key)
                else _sanitize(item, depth + 1)
            )
        return output
    if isinstance(value, list):
        if len(value) > 100:
            raise IntegrationError("Webhook array has too many items", 422)
        return [_sanitize(item, depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > 16_384:
            raise IntegrationError("Webhook text exceeds limit", 422)
        return redact_text(value)[0]
    return value


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


class ConnectorService:
    def __init__(
        self, settings: ConnectorSettings, *, clock: Callable[[], float] = time.time
    ):
        self.settings = settings
        self._clock = clock

    @classmethod
    def from_env(cls, config: Any = None) -> "ConnectorService":
        return cls(ConnectorSettings.from_env(config))

    def require(self, connector_id: str = "app-webhook") -> None:
        if not self.settings.enabled:
            raise IntegrationError("Connectors are disabled", 503)
        if connector_id not in self.settings.allowlist:
            raise IntegrationError("Connector is not allowlisted", 404)
        if not self.settings.signing_secret:
            raise IntegrationError(
                "Connector signing credential is not configured", 503
            )

    def status(self) -> dict:
        configured = bool(self.settings.signing_secret)
        return {
            "enabled": self.settings.enabled,
            "configured": configured,
            "ready": self.settings.enabled
            and configured
            and bool(self.settings.allowlist),
            "manifests": [
                {
                    **asdict(manifest),
                    "allowlisted": manifest.id in self.settings.allowlist,
                }
                for manifest in MANIFESTS
            ],
            "limits": {
                "body_bytes": WEBHOOK_LIMIT,
                "retained_events": MAX_EVENTS,
                "signature_window_seconds": WINDOW_SECONDS,
                "retention_seconds": RETENTION_SECONDS,
            },
            "automatic_dispatch": False,
            "dynamic_plugins": False,
            "project_authentication_required": True,
            "storage": "bounded_local_delivery_inbox_not_agent_memory",
        }

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        path = Path(self.settings.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=2)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA secure_delete=ON")
            db.executescript(
                """
            CREATE TABLE IF NOT EXISTS connector_events (
                connector_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                received_at REAL NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_at REAL,
                PRIMARY KEY (connector_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS connector_replays (
                digest TEXT PRIMARY KEY,
                expires_at REAL NOT NULL
            );
            """
            )
            with db:
                yield db
        finally:
            db.close()

    def _verify(
        self, connector_id: str, body: bytes, timestamp: str, signature: str
    ) -> tuple[str, int]:
        self.require(connector_id)
        if not body or len(body) > WEBHOOK_LIMIT:
            raise IntegrationError("Webhook body is empty or exceeds limit", 413)
        if not re.fullmatch(r"[0-9]{10,11}", timestamp) or not re.fullmatch(
            r"sha256=[a-f0-9]{64}", signature
        ):
            raise IntegrationError("Invalid webhook authentication", 401)
        signed_time = int(timestamp)
        if abs(self._clock() - signed_time) > WINDOW_SECONDS:
            raise IntegrationError(
                "Webhook timestamp is outside the accepted window", 401
            )
        # Bind connector, timestamp, and exact bytes. Signatures cannot cross routes.
        message = connector_id.encode() + b"." + timestamp.encode() + b"." + body
        expected = hmac.new(
            self.settings.signing_secret.encode(), message, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest("sha256=" + expected, signature):
            raise IntegrationError("Invalid webhook authentication", 401)
        return expected, signed_time

    async def receive(
        self, connector_id: str, body: bytes, timestamp: str, signature: str
    ) -> dict:
        digest, signed_time = self._verify(connector_id, body, timestamp, signature)
        try:
            event = json.loads(
                body,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
        except (ValueError, UnicodeError, RecursionError):
            raise IntegrationError("Invalid webhook JSON", 422) from None
        if not isinstance(event, dict) or set(event) != {"id", "type", "data"}:
            raise IntegrationError("Webhook requires exactly id, type, and data", 422)
        if any(
            not isinstance(event[key], str) or not _IDENTIFIER.fullmatch(event[key])
            for key in ("id", "type")
        ):
            raise IntegrationError("Invalid webhook event identifier or type", 422)
        if not isinstance(event["data"], dict):
            raise IntegrationError("Webhook data must be an object", 422)
        # Identifiers are metadata, not a secret channel: reject credential shapes.
        if any(redact_text(event[key])[1] for key in ("id", "type")):
            raise IntegrationError(
                "Webhook identifiers contain credential-shaped data", 422
            )
        payload = json.dumps(
            _sanitize(event["data"]), separators=(",", ":"), allow_nan=False
        )
        try:
            return await asyncio.to_thread(
                self._insert, connector_id, event, payload, digest, signed_time
            )
        except sqlite3.Error:
            raise IntegrationError(
                "Connector inbox is unavailable; retry later", 503
            ) from None

    def _insert(
        self,
        connector_id: str,
        event: dict,
        payload: str,
        digest: str,
        signed_time: int,
    ) -> dict:
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM connector_replays WHERE expires_at < ?", (now,))
            db.execute(
                "DELETE FROM connector_events WHERE received_at < ?",
                (now - RETENTION_SECONDS,),
            )
            if db.execute(
                "SELECT 1 FROM connector_replays WHERE digest=?", (digest,)
            ).fetchone():
                raise IntegrationError("Webhook replay rejected", 409)
            if db.execute(
                "SELECT 1 FROM connector_events WHERE connector_id=? AND event_id=?",
                (connector_id, event["id"]),
            ).fetchone():
                raise IntegrationError("Webhook event was already received", 409)
            # Bound every retained row, not only pending events or in-process RAM.
            if (
                db.execute("SELECT COUNT(*) FROM connector_events").fetchone()[0]
                >= MAX_EVENTS
            ):
                raise IntegrationError(
                    "Connector retention capacity is full; retry after expiry", 429
                )
            db.execute(
                "INSERT INTO connector_replays VALUES (?,?)",
                (digest, signed_time + WINDOW_SECONDS),
            )
            db.execute(
                "INSERT INTO connector_events (connector_id,event_id,event_type,received_at,payload) VALUES (?,?,?,?,?)",
                (connector_id, event["id"], event["type"], now, payload),
            )
        return {
            "accepted": True,
            "id": event["id"],
            "connector_id": connector_id,
            "status": "pending",
            "dispatched": False,
            "untrusted_content": True,
        }

    async def list_events(self, limit: int = 50, status: str = "pending") -> list[dict]:
        self.require()
        if not 1 <= limit <= 100 or status not in (
            "pending",
            "reviewed",
            "discarded",
            "all",
        ):
            raise IntegrationError("Invalid inbox filter", 422)

        def read():
            with self._connect() as db:
                query = "SELECT * FROM connector_events WHERE received_at >= ?"
                values: list[Any] = [self._clock() - RETENTION_SECONDS]
                if status != "all":
                    query += " AND status = ?"
                    values.append(status)
                rows = db.execute(
                    query + " ORDER BY received_at DESC, event_id LIMIT ?",
                    (*values, limit),
                ).fetchall()
                return [
                    {
                        **dict(row),
                        "payload": json.loads(row["payload"]),
                        "untrusted_content": True,
                    }
                    for row in rows
                ]

        try:
            return await asyncio.to_thread(read)
        except sqlite3.Error:
            raise IntegrationError("Connector inbox is unavailable", 503) from None

    async def acknowledge(
        self, connector_id: str, event_id: str, disposition: str
    ) -> dict:
        self.require(connector_id)
        if disposition not in ("reviewed", "discarded") or not _IDENTIFIER.fullmatch(
            event_id
        ):
            raise IntegrationError("Invalid acknowledgement", 422)

        def update():
            with self._connect() as db:
                # Purge data on acknowledgement, retain ID for deduplication.
                cursor = db.execute(
                    "UPDATE connector_events SET status=?,reviewed_at=?,payload='{}' WHERE connector_id=? AND event_id=? AND status='pending'",
                    (disposition, self._clock(), connector_id, event_id),
                )
                if cursor.rowcount != 1:
                    raise IntegrationError("Pending event not found", 404)
            return {
                "id": event_id,
                "status": disposition,
                "dispatched": False,
                "payload_removed": True,
            }

        try:
            return await asyncio.to_thread(update)
        except sqlite3.Error:
            raise IntegrationError("Connector inbox is unavailable", 503) from None
