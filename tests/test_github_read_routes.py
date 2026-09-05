"""Registered private GitHub reads never publish, leak diagnostics, or invent activity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip("ai_sdk", reason="Full API runtime requires ai-sdk-python")

import evolving_agent.utils.app_state as app_state
from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.integrations.github_reads import (
    GitHubReadService,
    GitHubNotConnectedError,
)
from tests.test_github_reads import repository
from tests.test_steward_app_routes import headers
from tests.test_steward_app_routes import registered_app as registered_app  # noqa: F401

PATHS = (
    "/github/status",
    "/github/repository",
    "/github/pull-requests",
    "/github/commits",
    "/github/improvement-history",
)


@pytest.mark.parametrize("path", PATHS)
def test_github_reads_require_project_auth(registered_app, path):
    assert registered_app.client.get(path).status_code == 401


@pytest.mark.parametrize(
    "failure,status",
    [
        (RuntimeError("private-provider-error"), 503),
        (TimeoutError("private-timeout-detail"), 504),
        (RuntimeBusyError("private-worker-detail"), 409),
        (GitHubNotConnectedError("private-connection-detail"), 404),
    ],
)
def test_read_failure_is_safe_not_empty_success(
    registered_app, monkeypatch, failure, status
):
    reader = SimpleNamespace(pull_requests=AsyncMock(side_effect=failure))
    monkeypatch.setattr(
        app_state, "github_modifier", SimpleNamespace(read_service=reader)
    )
    response = registered_app.client.get("/github/pull-requests", headers=headers())
    assert response.status_code == status
    assert "private-" not in response.text and "open_pull_requests" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_registered_reads_share_real_fake_sdk_snapshot(registered_app, monkeypatch):
    repo = repository(3)
    reader = GitHubReadService(SimpleNamespace(repository=repo, local_repo=None))
    monkeypatch.setattr(
        app_state, "github_modifier", SimpleNamespace(read_service=reader)
    )
    client = registered_app.client
    assert (
        client.get("/github/status", headers=headers()).json()["auto_pr_enabled"]
        is False
    )
    assert (
        client.get("/github/repository", headers=headers()).json()["full_name"]
        == "example/katbot"
    )
    assert (
        client.get("/github/pull-requests", headers=headers()).json()["total_count"]
        == 3
    )
    assert client.get("/github/commits?limit=2", headers=headers()).json()["count"] == 2
    assert repo.get_pulls.call_count == 1 and repo.get_commits.call_count == 1
    for limit in (-1, 0, 51):
        assert (
            client.get(f"/github/commits?limit={limit}", headers=headers()).status_code
            == 422
        )
    registered_app.agent.run.assert_not_awaited()
    assert registered_app.provider_calls == []


def test_history_is_local_bounded_and_redacted(registered_app, monkeypatch):
    history = Mock(
        return_value=[{"id": i, "token": "private-history-token"} for i in range(5)]
    )
    reader = SimpleNamespace(
        status=AsyncMock(side_effect=AssertionError("history invoked provider"))
    )
    monkeypatch.setattr(
        app_state,
        "github_modifier",
        SimpleNamespace(read_service=reader, get_improvement_history=history),
    )
    client = registered_app.client
    response = client.get("/github/improvement-history?limit=2", headers=headers())
    assert response.status_code == 200 and response.json()["count"] == 2
    assert [row["id"] for row in response.json()["improvement_history"]] == [3, 4]
    assert "private-history-token" not in response.text
    assert (
        client.get(
            "/github/improvement-history?limit=101", headers=headers()
        ).status_code
        == 422
    )
    history.side_effect = RuntimeError("private-history-error")
    response = client.get("/github/improvement-history", headers=headers())
    assert response.status_code == 503 and "private-history-error" not in response.text
    reader.status.assert_not_awaited()


def test_missing_integration_is_explicit_and_read_only(registered_app, monkeypatch):
    monkeypatch.setattr(app_state, "github_modifier", None)
    response = registered_app.client.get("/github/status", headers=headers())
    assert response.status_code == 200 and response.json()["github_connected"] is False
    assert (
        registered_app.client.get("/github/repository", headers=headers()).status_code
        == 503
    )
