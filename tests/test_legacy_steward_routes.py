"""Legacy endpoints must not bypass bounded steward controls or publish effects."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip("ai_sdk", reason="Full API runtime requires ai-sdk-python")

import evolving_agent.utils.app_state as app_state
from tests.test_steward_app_routes import headers
from tests.test_steward_app_routes import registered_app as registered_app  # noqa: F401

RETIRED_PATHS = ("/analyze", "/self-improve", "/github/demo-pr", "/github/issue")


@pytest.mark.parametrize("path", RETIRED_PATHS)
def test_retired_routes_still_require_project_auth(registered_app, path):
    response = registered_app.client.post(path, content=b"private malformed body")
    assert response.status_code == 401
    registered_app.agent.run.assert_not_awaited()


@pytest.mark.parametrize("path", RETIRED_PATHS)
def test_legacy_flags_and_malformed_bodies_cannot_reenable_effects(
    registered_app, monkeypatch, path
):
    monkeypatch.setenv("ENABLE_SELF_MODIFICATION", "true")
    monkeypatch.setenv("AUTO_PR_ENABLED", "true")
    analyze = AsyncMock(side_effect=AssertionError("legacy analyzer executed"))
    improve = AsyncMock(side_effect=AssertionError("legacy modifier executed"))
    demo = AsyncMock(side_effect=AssertionError("legacy PR publication executed"))
    issue = AsyncMock(side_effect=AssertionError("legacy issue publication executed"))
    registered_app.agent.code_analyzer = SimpleNamespace(
        analyze_performance_patterns=analyze
    )
    monkeypatch.setattr(
        app_state,
        "github_modifier",
        SimpleNamespace(
            analyze_and_improve_codebase=improve,
            create_documentation_improvement_pr=demo,
            github_integration=SimpleNamespace(repository=object(), create_issue=issue),
        ),
    )
    response = registered_app.client.post(
        path,
        headers={**headers(), "Content-Type": "application/json"},
        content=b'{"create_pr":true,"secret":"private-input" BROKEN',
    )
    assert response.status_code == 410
    assert "private-input" not in response.text
    for method in (analyze, improve, demo, issue):
        method.assert_not_awaited()
    assert registered_app.control.submitted == []
    assert registered_app.provider_calls == []


def test_retirement_is_visible_in_actual_openapi(registered_app):
    schema = registered_app.client.get("/openapi.json").json()
    for path in RETIRED_PATHS:
        operation = schema["paths"][path]["post"]
        assert operation["deprecated"] is True
        assert "410" in operation["responses"]


def test_analysis_history_is_bounded_redacted_and_read_only(registered_app):
    history = [
        {
            "sequence": index,
            "note": "api_key=private-history-value",
            "token": "opaque-token",
        }
        for index in range(5)
    ]
    get_history = Mock(return_value=history)
    analyze = AsyncMock(side_effect=AssertionError("analysis executed during read"))
    registered_app.agent.code_analyzer = SimpleNamespace(
        get_analysis_history=get_history, analyze_performance_patterns=analyze
    )
    client = registered_app.client
    response = client.get("/analysis-history?limit=2", headers=headers())
    assert response.status_code == 200
    assert [row["sequence"] for row in response.json()] == [3, 4]
    assert (
        "private-history-value" not in response.text
        and "opaque-token" not in response.text
    )
    for invalid in (-1, 0, 101):
        assert (
            client.get(
                f"/analysis-history?limit={invalid}", headers=headers()
            ).status_code
            == 422
        )
    get_history.assert_called_once()
    analyze.assert_not_awaited()


def test_history_errors_do_not_echo_private_diagnostics(registered_app):
    registered_app.agent.code_analyzer = SimpleNamespace(
        get_analysis_history=Mock(
            side_effect=RuntimeError("private-history-diagnostics")
        )
    )
    response = registered_app.client.get("/analysis-history", headers=headers())
    assert response.status_code == 503
    assert "private-history-diagnostics" not in response.text
