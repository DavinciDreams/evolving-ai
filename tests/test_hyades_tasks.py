"""Contract tests for Katbot's durable Hyades handoff."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from evolving_agent.integrations.ham_memory import HAMMemoryClient, HAMMemoryError
from evolving_agent.integrations.hyades_tasks import HyadesTaskBridge, HyadesTaskError
from evolving_agent.utils.config import Config


IDENTITY = {
    "agent_id": "katbot-evolving-ai",
    "role": "agent",
    "scope_boundary": {
        "mode": "credential_allowlist",
        "allowed_scopes": ["project:evolving-ai", "shared"],
    },
}
PROJECTS = [
    {
        "slug": "evolving-ai",
        "scope": "project:evolving-ai",
        "repo": "DavinciDreams/evolving-ai",
    }
]


def _client(handler) -> HAMMemoryClient:
    def routed(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/whoami":
            return httpx.Response(200, json=IDENTITY)
        if request.url.path == "/projects":
            return httpx.Response(200, json=PROJECTS)
        return handler(request)

    return HAMMemoryClient(
        base_url="https://ham.invalid",
        api_key="synthetic-ham-credential",
        project="evolving-ai",
        transport=httpx.MockTransport(routed),
    )


@pytest.mark.asyncio
async def test_task_post_uses_credential_identity_and_project_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/projects/evolving-ai/tasks"
        payload = json.loads(request.content)
        assert payload["activity_mode"] == "test"
        assert payload["completion_policy"] == "immediate"
        assert payload["requester_ref"] == "discord:1:2:user:3"
        assert "agent_id" not in payload
        return httpx.Response(
            200,
            json={
                "task_id": "a" * 32,
                "version": 1,
                "status": "pending",
                "requested_by_agent": "katbot-evolving-ai",
            },
        )

    client = _client(handler)
    try:
        task = await client.post_task(
            title="Bounded canary",
            goal="Run a bounded canary",
            acceptance_criteria=["Use gVisor"],
            requester_ref="discord:1:2:user:3",
            idempotency_key="canary-1",
        )
    finally:
        await client.close()
    assert task["task_id"] == "a" * 32


@pytest.mark.asyncio
async def test_bridge_redacts_credentials_before_task_persistence():
    client = AsyncMock()
    client.repo = "DavinciDreams/evolving-ai"
    client.post_task.return_value = {
        "task_id": "b" * 32,
        "version": 1,
        "status": "pending",
    }
    bridge = HyadesTaskBridge(client)

    await bridge.post(
        "inspect PASSWORD=synthetic-secret-24680",
        requester_ref="discord:1:2:user:3",
        source_id="message-1",
    )

    payload = client.post_task.await_args.kwargs
    assert "synthetic-secret-24680" not in payload["goal"]
    assert "[REDACTED:credential_assignment]" in payload["goal"]
    assert payload["resources"] == [
        {"key": "repo:DavinciDreams/evolving-ai", "mode": "write"}
    ]


@pytest.mark.asyncio
async def test_bridge_follows_append_only_progress_to_completion(monkeypatch):
    client = AsyncMock()
    client.get_task.side_effect = [
        {
            "task_id": "c" * 32,
            "version": 2,
            "status": "running",
            "latest_event": {"summary": "sandbox acquired"},
        },
        {
            "task_id": "c" * 32,
            "version": 3,
            "status": "completed",
            "latest_event": {"summary": "canary passed"},
        },
    ]
    client.task_events.side_effect = [
        ([{"event_type": "progress", "summary": "sandbox acquired"}], 7, False),
        ([{"event_type": "completed", "summary": "canary passed"}], 8, False),
    ]
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    progress = AsyncMock()
    bridge = HyadesTaskBridge(client)

    result = await bridge.follow("c" * 32, progress=progress)

    assert result == "canary passed"
    assert progress.await_count == 2
    assert client.task_events.await_args_list[1].kwargs["after_event_id"] == 7


@pytest.mark.asyncio
async def test_bridge_cancels_with_current_optimistic_version():
    client = AsyncMock()
    client.get_task.return_value = {
        "task_id": "d" * 32,
        "version": 4,
        "status": "running",
    }
    client.cancel_task.return_value = {
        "task_id": "d" * 32,
        "version": 5,
        "status": "cancelled",
    }
    bridge = HyadesTaskBridge(client)

    result = await bridge.cancel("d" * 32)

    assert result["status"] == "cancelled"
    assert client.cancel_task.await_args.kwargs["expected_version"] == 4


@pytest.mark.asyncio
async def test_bridge_redacts_terminal_summary_before_discord_delivery():
    client = AsyncMock()
    client.get_task.return_value = {
        "task_id": "f" * 32,
        "version": 3,
        "status": "completed",
        "latest_event": {"summary": "PASSWORD=synthetic-secret-97531"},
    }
    client.task_events.return_value = ([], 0, False)
    bridge = HyadesTaskBridge(client)

    result = await bridge.follow("f" * 32)

    assert "synthetic-secret-97531" not in result
    assert "[REDACTED:credential_assignment]" in result


@pytest.mark.asyncio
async def test_bridge_fails_closed_when_task_telemetry_is_malformed():
    client = AsyncMock()
    client.get_task.side_effect = HAMMemoryError("malformed")
    bridge = HyadesTaskBridge(client)

    with pytest.raises(HyadesTaskError, match="telemetry"):
        await bridge.follow("e" * 32)


def test_hyades_is_opt_in_and_e2b_key_alone_does_not_enable_fallback(monkeypatch):
    monkeypatch.delenv("HYADES_TASKS_ENABLED", raising=False)
    monkeypatch.delenv("HYADES_DISCORD_USER_IDS", raising=False)
    monkeypatch.delenv("E2B_ENABLED", raising=False)
    monkeypatch.setenv("E2B_API_KEY", "synthetic-key")
    cfg = Config()

    assert cfg.hyades_tasks_enabled is False
    assert cfg.hyades_discord_user_ids == []
    assert cfg.e2b_enabled is False
    assert cfg.e2b_api_key == "synthetic-key"


def test_compose_files_forward_one_ham_authority_for_hyades():
    root = Path(__file__).resolve().parents[1]
    required = {
        "HAM_API_URL=${HAM_API_URL:-https://ham.flobots.xyz}",
        "HAM_API_KEY=${HAM_API_KEY}",
        "HAM_PROJECT=${HAM_PROJECT:-evolving-ai}",
        "HYADES_TASKS_ENABLED=${HYADES_TASKS_ENABLED:-false}",
        "HYADES_DISCORD_USER_IDS=${HYADES_DISCORD_USER_IDS}",
        "HYADES_TASK_POLL_SECONDS=${HYADES_TASK_POLL_SECONDS:-5}",
        "HYADES_TASK_TIMEOUT_SECONDS=${HYADES_TASK_TIMEOUT_SECONDS:-1800}",
    }
    for filename in ("docker-compose.yaml", "docker-compose.coolify.yaml"):
        content = (root / filename).read_text(encoding="utf-8")
        assert all(value in content for value in required)
        assert "HYADES_API_KEY" not in content
        assert "SATURN_API_KEY" not in content
