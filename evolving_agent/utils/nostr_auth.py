"""NIP-07 human authentication with one-time challenges and opaque sessions.

The browser extension keeps the Nostr private key.  The server persists only
hashes of random challenges and session tokens in the durable data directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from coincurve import PublicKeyXOnly
from fastapi import HTTPException, Request

from evolving_agent.utils.config import config


KIND_HTTP_AUTH = 27235
SESSION_COOKIE = "__Host-katbot-session"
CHALLENGE_SECONDS = 300
SESSION_SECONDS = 30 * 86400
_PUBKEY = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ID = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE = re.compile(r"^[0-9a-f]{128}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_rate_lock = threading.Lock()
_rate_windows: dict[str, tuple[float, int]] = {}


class NostrSessionUnavailable(RuntimeError):
    """The durable session store could not be checked safely."""


@dataclass(frozen=True)
class NostrAuthConfig:
    verify_url: str
    allowed_origins: frozenset[str]
    allowed_pubkeys: frozenset[str]


def enabled() -> bool:
    """Return whether human Nostr authentication is enabled."""
    return config.nostr_auth_enabled


def _normalized_origin(value: str) -> str | None:
    """Normalize an HTTPS origin without accepting paths or credentials."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}{f':{port}' if port not in (None, 443) else ''}"


def auth_config() -> NostrAuthConfig:
    """Read and validate the complete fail-closed Nostr configuration."""
    if not enabled():
        raise HTTPException(404, "Nostr sign-in is not enabled")

    verify_url = config.nostr_auth_verify_url.strip()
    try:
        parsed_verify = urlsplit(verify_url)
    except ValueError as exc:
        raise RuntimeError("NOSTR_AUTH_VERIFY_URL must be an exact HTTPS URL") from exc
    verify_origin = _normalized_origin(
        f"{parsed_verify.scheme}://{parsed_verify.netloc}"
    )
    if (
        verify_origin is None
        or not parsed_verify.path.endswith("/auth/nostr/verify")
        or parsed_verify.query
        or parsed_verify.fragment
    ):
        raise RuntimeError(
            "NOSTR_AUTH_VERIFY_URL must be an exact HTTPS URL ending in /auth/nostr/verify"
        )

    raw_pubkeys = [value.strip() for value in config.project_nostr_pubkeys.split(",") if value.strip()]
    pubkeys = frozenset(raw_pubkeys)
    if not pubkeys or any(not _PUBKEY.fullmatch(value) for value in pubkeys):
        raise RuntimeError(
            "PROJECT_NOSTR_PUBKEYS must contain lowercase 64-character hex public keys"
        )
    return NostrAuthConfig(
        verify_url=verify_url,
        allowed_origins=frozenset({verify_origin}),
        allowed_pubkeys=pubkeys,
    )


def validate_config() -> None:
    """Fail startup when an enabled Nostr boundary is incomplete."""
    if enabled():
        auth_config()
        _initialize_store()


def _db_path() -> Path:
    return Path(config.persistent_data_dir) / "nostr_auth.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _initialize_store() -> None:
    try:
        with _connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS nostr_auth_challenges (
                    token_hash TEXT PRIMARY KEY,
                    pubkey TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_nostr_challenges_owner
                    ON nostr_auth_challenges(pubkey, origin, created_at DESC);
                CREATE TABLE IF NOT EXISTS nostr_auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    pubkey TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_nostr_sessions_owner
                    ON nostr_auth_sessions(pubkey, created_at DESC);
                """
            )
    except sqlite3.Error as exc:
        raise NostrSessionUnavailable("Nostr session store is unavailable") from exc


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_token(value: str) -> bool:
    """Return whether a challenge/session token has the expected opaque shape."""
    return _TOKEN.fullmatch(value) is not None


def require_json_origin(request: Request, cfg: NostrAuthConfig | None = None) -> str:
    """Require JSON and a configured browser Origin for state-changing calls."""
    cfg = cfg or auth_config()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(415, "Nostr sign-in requires application/json")
    origin = _normalized_origin(request.headers.get("origin", "").strip())
    if origin not in cfg.allowed_origins:
        raise HTTPException(403, "Nostr sign-in requires an allowed origin")
    return origin


def require_session_origin(request: Request) -> None:
    """Protect unsafe cookie-authenticated API calls from cross-site requests."""
    origin = _normalized_origin(request.headers.get("origin", "").strip())
    if origin not in auth_config().allowed_origins:
        raise HTTPException(403, "Session request requires an allowed origin")


def _client_bucket(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    """Bound public signature-verification and challenge work per direct peer."""
    key = _client_bucket(request)
    now = time.monotonic()
    with _rate_lock:
        start, count = _rate_windows.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= 20:
            raise HTTPException(429, "Too many Nostr sign-in attempts")
        _rate_windows[key] = (start, count + 1)
        if len(_rate_windows) > 2048:
            cutoff = now - 60
            for stale in [name for name, (began, _count) in _rate_windows.items() if began < cutoff]:
                _rate_windows.pop(stale, None)


def _required_tag(tags: list, name: str) -> str:
    values = [tag[1] for tag in tags if isinstance(tag, list) and len(tag) == 2 and tag[0] == name]
    if len(values) != 1 or not isinstance(values[0], str):
        raise HTTPException(400, f"Nostr event requires one {name} tag")
    return values[0]


def _validated_event_values(event: dict, cfg: NostrAuthConfig) -> tuple[str, str, str, int, list]:
    if set(event) != {"id", "pubkey", "created_at", "kind", "tags", "content", "sig"}:
        raise HTTPException(400, "Invalid Nostr event fields")
    pubkey = event.get("pubkey")
    event_id = event.get("id")
    signature = event.get("sig")
    created_at = event.get("created_at")
    tags = event.get("tags")
    if pubkey not in cfg.allowed_pubkeys or not _PUBKEY.fullmatch(pubkey or ""):
        raise HTTPException(403, "This Nostr account is not authorized for Katbot")
    if not _EVENT_ID.fullmatch(event_id or "") or not _SIGNATURE.fullmatch(signature or ""):
        raise HTTPException(400, "Invalid Nostr event signature fields")
    if type(created_at) is not int or event.get("kind") != KIND_HTTP_AUTH:
        raise HTTPException(400, "Invalid Nostr authentication event")
    if (
        event.get("content") != ""
        or not isinstance(tags, list)
        or len(tags) != 3
        or any(
            not isinstance(tag, list)
            or len(tag) != 2
            or any(not isinstance(value, str) or len(value) > 2048 for value in tag)
            for tag in tags
        )
    ):
        raise HTTPException(400, "Invalid Nostr authentication event content")
    return pubkey, event_id, signature, created_at, tags


def _validate_event_scope(
    created_at: int, tags: list, challenge: str, cfg: NostrAuthConfig
) -> None:
    now = int(time.time())
    if created_at < now - 120 or created_at > now + 30:
        raise HTTPException(400, "Nostr authentication event is outside the allowed time window")
    if _required_tag(tags, "u") != cfg.verify_url:
        raise HTTPException(400, "Nostr authentication event has the wrong URL")
    if _required_tag(tags, "method") != "POST":
        raise HTTPException(400, "Nostr authentication event has the wrong method")
    if _required_tag(tags, "challenge") != challenge:
        raise HTTPException(400, "Nostr authentication event has the wrong challenge")


def _verify_event_signature(
    pubkey: str, event_id: str, signature: str, created_at: int, tags: list
) -> None:
    serialized = json.dumps(
        [0, pubkey, created_at, KIND_HTTP_AUTH, tags, ""],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    calculated = hashlib.sha256(serialized).hexdigest()
    if not secrets.compare_digest(calculated, event_id):
        raise HTTPException(400, "Invalid Nostr event id")
    try:
        valid = PublicKeyXOnly(bytes.fromhex(pubkey)).verify(
            bytes.fromhex(signature), bytes.fromhex(event_id)
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise HTTPException(400, "Invalid Nostr event signature")


def verify_event(event: dict, challenge: str, cfg: NostrAuthConfig) -> str:
    """Verify a tightly-scoped NIP-98-style NIP-07 event."""
    pubkey, event_id, signature, created_at, tags = _validated_event_values(event, cfg)
    _validate_event_scope(created_at, tags, challenge, cfg)
    _verify_event_signature(pubkey, event_id, signature, created_at, tags)
    return pubkey


def create_challenge(pubkey: str, origin: str) -> str:
    challenge = secrets.token_urlsafe(32)
    now = int(time.time())
    try:
        with _connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM nostr_auth_challenges WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO nostr_auth_challenges "
                "(token_hash, pubkey, origin, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (_digest(challenge), pubkey, origin, now + CHALLENGE_SECONDS, now),
            )
            connection.execute(
                "DELETE FROM nostr_auth_challenges WHERE token_hash IN ("
                "SELECT token_hash FROM nostr_auth_challenges WHERE pubkey = ? AND origin = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET 5)",
                (pubkey, origin),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise NostrSessionUnavailable("Nostr session store is unavailable") from exc
    return challenge


def consume_challenge(challenge: str, pubkey: str, origin: str) -> str:
    """Atomically consume a challenge and create an opaque session token."""
    session = secrets.token_urlsafe(32)
    now = int(time.time())
    try:
        with _connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            deleted = connection.execute(
                "DELETE FROM nostr_auth_challenges "
                "WHERE token_hash = ? AND pubkey = ? AND origin = ? AND expires_at > ?",
                (_digest(challenge), pubkey, origin, now),
            )
            if deleted.rowcount != 1:
                connection.rollback()
                raise HTTPException(400, "Nostr sign-in challenge is expired or already used")
            connection.execute("DELETE FROM nostr_auth_sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO nostr_auth_sessions "
                "(token_hash, pubkey, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (_digest(session), pubkey, now + SESSION_SECONDS, now),
            )
            connection.execute(
                "DELETE FROM nostr_auth_sessions WHERE token_hash IN ("
                "SELECT token_hash FROM nostr_auth_sessions WHERE pubkey = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET 5)",
                (pubkey,),
            )
            connection.commit()
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise NostrSessionUnavailable("Nostr session store is unavailable") from exc
    return session


def verify_session(request: Request) -> dict | None:
    if not enabled():
        return None
    cfg = auth_config()
    token = request.cookies.get(SESSION_COOKIE, "")
    if not _TOKEN.fullmatch(token):
        return None
    now = int(time.time())
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT pubkey FROM nostr_auth_sessions "
                "WHERE token_hash = ? AND expires_at > ?",
                (_digest(token), now),
            ).fetchone()
    except sqlite3.Error as exc:
        raise NostrSessionUnavailable("Nostr session store is unavailable") from exc
    if not row or row["pubkey"] not in cfg.allowed_pubkeys:
        return None
    return {
        "sub": "nostr:" + row["pubkey"],
        "auth_method": "nostr",
        "nostr_pubkey": row["pubkey"],
    }


def delete_session(token: str) -> None:
    if not _TOKEN.fullmatch(token):
        return
    try:
        with _connect() as connection:
            connection.execute(
                "DELETE FROM nostr_auth_sessions WHERE token_hash = ?", (_digest(token),)
            )
    except sqlite3.Error as exc:
        raise NostrSessionUnavailable("Nostr session store is unavailable") from exc
