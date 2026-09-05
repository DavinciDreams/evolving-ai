"""Registered auxiliary routes cannot bypass leases or spend during telemetry."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip("ai_sdk", reason="Full API runtime requires ai-sdk-python")

import evolving_agent.api.routes.system as system  # noqa: E402
import evolving_agent.utils.app_state as state  # noqa: E402
from evolving_agent.core.runtime import AgentRuntime  # noqa: E402
from tests.test_steward_app_routes import headers  # noqa: E402
from tests.test_steward_app_routes import registered_app as _registered_app  # noqa: E402

registered_app = _registered_app


def search_agent(fixture):
    agent = fixture.agent
    agent.runtime = AgentRuntime(timeout=0.02)
    agent.web_search = object()
    agent.dream_service = SimpleNamespace(
        status=lambda: {"running": False}, note_activity=Mock()
    )
    agent.steward.dreams = agent.dream_service
    agent.steward.lab = SimpleNamespace(status=lambda: {"busy": False})
    agent.steward.learning = SimpleNamespace(
        status=lambda: {"running": False}, note_activity=Mock()
    )
    agent.search_web = AsyncMock(return_value={"sources": [], "provider": "synthetic"})
    return agent


@pytest.mark.parametrize("busy", ["runtime", "steward", "dream", "learning", "lab"])
def test_search_rejects_every_shared_occupied_state(registered_app, busy):
    agent = search_agent(registered_app)
    if busy == "runtime":
        agent.runtime._active = True
    elif busy == "steward":
        agent.steward.busy = True
    elif busy == "dream":
        agent.dream_service.status = lambda: {"running": True}
    elif busy == "learning":
        agent.steward.learning.status = lambda: {"running": True}
    else:
        agent.steward.lab.status = lambda: {"busy": True}
    response = registered_app.client.post(
        "/web-search", json={"query": "offline"}, headers=headers()
    )
    assert response.status_code == 409
    agent.search_web.assert_not_awaited()


def test_search_redacts_input_and_response_and_holds_runtime(registered_app):
    agent = search_agent(registered_app)
    marker = "nsec1" + "q" * 58

    async def provider(**kwargs):
        assert agent.runtime.busy
        assert marker not in kwargs["query"]
        return {"sources": [{"note": marker}], "provider": "synthetic"}

    agent.search_web.side_effect = provider
    response = registered_app.client.post(
        "/web-search", json={"query": marker}, headers=headers()
    )
    assert response.status_code == 200
    assert marker not in response.text
    agent.dream_service.note_activity.assert_called_once()
    agent.steward.learning.note_activity.assert_called_once()


def test_search_deadline_and_errors_do_not_echo_diagnostics(registered_app):
    agent = search_agent(registered_app)

    async def slow(**kwargs):
        await asyncio.sleep(100)

    agent.search_web.side_effect = slow
    response = registered_app.client.post(
        "/web-search", json={"query": "offline"}, headers=headers()
    )
    assert response.status_code == 504
    agent.search_web.side_effect = RuntimeError("private-provider-diagnostic")
    response = registered_app.client.post(
        "/web-search", json={"query": "offline"}, headers=headers()
    )
    assert response.status_code == 500
    assert "private-provider-diagnostic" not in response.text


def test_search_body_is_bounded_before_provider_call(registered_app):
    agent = search_agent(registered_app)
    response = registered_app.client.post(
        "/web-search",
        content=b"x" * 8193,
        headers={**headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    agent.search_web.assert_not_awaited()


@pytest.mark.parametrize("path", ["/health/detailed", "/health/recovery"])
def test_health_is_cached_value_free_and_never_calls_dependencies(
    registered_app, monkeypatch, path
):
    probe = AsyncMock(side_effect=AssertionError("paid health probe invoked"))
    github_read = Mock(side_effect=AssertionError("GitHub health invoked"))
    registered_app.agent.check_system_health = probe
    monkeypatch.setattr(system.llm_manager, "get_available_providers", probe)
    monkeypatch.setattr(system.error_recovery_manager, "perform_health_checks", probe)
    monkeypatch.setattr(
        system.llm_manager,
        "provider_status",
        {
            "openai": {
                "available": True,
                "last_error": "private-provider-token",
                "request_count": 3,
            }
        },
    )
    monkeypatch.setattr(
        system.error_recovery_manager,
        "get_recovery_status",
        lambda: {
            "degraded_mode": False,
            "active_checkpoints": 1,
            "partial_responses": 2,
            "recovery_history_count": 3,
            "circuit_breakers": {"private-service-token": {}},
            "error_patterns": {"private-error-token": "private-history"},
        },
    )
    monkeypatch.setattr(
        state,
        "github_modifier",
        SimpleNamespace(github_integration=SimpleNamespace(get_status=github_read)),
    )
    response = registered_app.client.get(path, headers=headers())
    assert response.status_code == 200
    assert response.json()["cached_only"] is True
    assert "private-" not in response.text
    assert response.json().get("status") != "healthy"
    probe.assert_not_awaited()
    github_read.assert_not_called()


def test_recovery_replay_retired_even_with_pending_repository_effects(
    registered_app, monkeypatch
):
    replay = AsyncMock(side_effect=AssertionError("repository effects replayed"))
    monkeypatch.setattr(
        state,
        "github_modifier",
        SimpleNamespace(
            github_integration=SimpleNamespace(
                process_pending_operations=replay,
                pending_operations=[{"type": "create_pr"}],
            )
        ),
    )
    response = registered_app.client.post("/system/trigger-recovery", headers=headers())
    assert response.status_code == 410
    replay.assert_not_awaited()


def test_mode_change_cannot_clear_occupied_lease(registered_app):
    agent = search_agent(registered_app)
    agent.runtime._active = True
    response = registered_app.client.post(
        "/system/disable-degraded-mode", headers=headers()
    )
    assert response.status_code == 409
    assert agent.runtime.busy


@pytest.mark.parametrize(
    "path",
    ["/health/detailed", "/health/recovery", "/web-search", "/system/trigger-recovery"],
)
def test_auxiliary_routes_still_require_project_authorization(registered_app, path):
    method = (
        registered_app.client.get
        if path.startswith("/health")
        else registered_app.client.post
    )
    assert method(path).status_code == 401
