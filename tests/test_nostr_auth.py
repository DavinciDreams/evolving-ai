"""NIP-07 human authentication and service-key compatibility."""

import hashlib
import json
import time

import pytest
from coincurve import PrivateKey
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from evolving_agent.api.routes.auth import router
from evolving_agent.utils import nostr_auth
from evolving_agent.utils.deps import verify_api_key


ORIGIN = "https://katbot-ui.example"
VERIFY_URL = ORIGIN + "/api/auth/nostr/verify"


def _event(private_key: PrivateKey, challenge: str, **changes) -> dict:
    event = {
        "pubkey": private_key.public_key_xonly.format().hex(),
        "created_at": int(time.time()),
        "kind": 27235,
        "tags": [
            ["u", VERIFY_URL],
            ["method", "POST"],
            ["challenge", challenge],
        ],
        "content": "",
    }
    event.update(changes)
    serialized = json.dumps(
        [0, event["pubkey"], event["created_at"], event["kind"], event["tags"], event["content"]],
        separators=(",", ":"),
    ).encode()
    event["id"] = hashlib.sha256(serialized).hexdigest()
    event["sig"] = private_key.sign_schnorr(bytes.fromhex(event["id"])).hex()
    return event


@pytest.fixture
def auth_setup(monkeypatch, tmp_path):
    private_key = PrivateKey()
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_API_KEY", "separate-service-key")
    monkeypatch.setenv("NOSTR_AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "PROJECT_NOSTR_PUBKEYS", private_key.public_key_xonly.format().hex()
    )
    monkeypatch.setenv("NOSTR_AUTH_VERIFY_URL", VERIFY_URL)
    monkeypatch.setenv("PERSISTENT_DATA_DIR", str(tmp_path))
    nostr_auth._rate_windows.clear()
    nostr_auth.validate_config()
    return private_key


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)

    @application.get("/private")
    def private_get(claims=Depends(verify_api_key)):
        return claims

    @application.post("/private")
    def private_post(claims=Depends(verify_api_key)):
        return claims

    return application


def test_valid_nostr_session_is_one_time_origin_bound_and_revocable(auth_setup, app):
    pubkey = auth_setup.public_key_xonly.format().hex()
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        options = client.post("/auth/nostr/options", json={"pubkey": pubkey})
        assert options.status_code == 200, options.text
        challenge = options.json()["challenge"]
        body = {"challenge": challenge, "event": _event(auth_setup, challenge)}

        verified = client.post("/auth/nostr/verify", json=body)
        assert verified.status_code == 200, verified.text
        assert "__Host-katbot-session=" in verified.headers["set-cookie"]
        assert "HttpOnly" in verified.headers["set-cookie"]
        assert "SameSite=strict" in verified.headers["set-cookie"]
        assert client.get("/private").json()["auth_method"] == "nostr"
        assert client.post("/private").status_code == 200
        assert client.post("/private", headers={"Origin": ""}).status_code == 403
        assert client.post("/auth/nostr/verify", json=body).status_code == 400
        assert client.post("/auth/nostr/logout", json={}).status_code == 200
        assert client.get("/private").status_code == 401


def test_project_api_key_remains_available_for_automation(auth_setup, app):
    with TestClient(app, base_url=ORIGIN) as client:
        response = client.post("/private", headers={"X-API-Key": "separate-service-key"})
    assert response.status_code == 200
    assert response.json()["auth_method"] == "api_key"


def test_events_are_bound_to_url_method_challenge_and_allowlisted_pubkey(auth_setup):
    cfg = nostr_auth.auth_config()
    challenge = "a" * 43
    assert nostr_auth.verify_event(_event(auth_setup, challenge), challenge, cfg) == (
        auth_setup.public_key_xonly.format().hex()
    )

    wrong_url = _event(auth_setup, challenge)
    wrong_url["tags"][0][1] = "https://evil.example/auth/nostr/verify"
    with pytest.raises(Exception, match="wrong URL"):
        nostr_auth.verify_event(wrong_url, challenge, cfg)

    stranger = PrivateKey()
    with pytest.raises(Exception, match="not authorized"):
        nostr_auth.verify_event(_event(stranger, challenge), challenge, cfg)


def test_enabled_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("NOSTR_AUTH_ENABLED", "true")
    monkeypatch.setenv("PROJECT_NOSTR_PUBKEYS", "")
    monkeypatch.setenv("NOSTR_AUTH_VERIFY_URL", "http://not-secure.example/auth/nostr/verify")
    with pytest.raises(RuntimeError):
        nostr_auth.validate_config()


def test_actual_application_keeps_auth_bootstrap_public(monkeypatch):
    from evolving_agent.utils.api_server import app as production_app

    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_API_KEY", "separate-service-key")
    monkeypatch.setenv("NOSTR_AUTH_ENABLED", "false")
    client = TestClient(production_app, base_url=ORIGIN)
    try:
        assert client.get("/auth/nostr/session").json() == {
            "enabled": False,
            "signed_in": False,
        }
        assert client.get("/status").status_code == 401
    finally:
        client.close()
