"""Actual API lifespan with synthetic listeners, shortened waits, and no network."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

pytest.importorskip("ai_sdk", reason="Full API runtime requires ai-sdk-python")

import evolving_agent.utils.api_server as api_server  # noqa: E402
import evolving_agent.utils.app_state as app_state  # noqa: E402
from evolving_agent.integrations.connectors import ConnectorService  # noqa: E402
from evolving_agent.integrations.media import MediaService  # noqa: E402


class CapturedLogs:
    def __init__(self):
        self.lines = []

    def __getattr__(self, _level):
        def log(template, *args, **_kwargs):
            self.lines.append(template.format(*args))

        return log


def prepare(
    monkeypatch,
    *,
    listener_failure=False,
    close_failure=False,
    resistant_close=False,
    resistant_listener=False
):
    app = FastAPI()
    entered, stopped, released = asyncio.Event(), asyncio.Event(), asyncio.Event()
    close_entered = asyncio.Event()
    order, waits = [], []
    logs = CapturedLogs()
    diagnostic = "synthetic-private-discord-diagnostic"

    async def stubborn():
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    async def start():
        entered.set()
        if listener_failure:
            raise RuntimeError(diagnostic)
        try:
            if resistant_listener:
                await stubborn()
            else:
                await stopped.wait()
        finally:
            order.append("listener_finished")

    async def close():
        close_entered.set()
        order.append("close_started")
        if close_failure:
            raise RuntimeError(diagnostic)
        if resistant_close:
            await stubborn()
        else:
            stopped.set()

    async def cleanup():
        order.append("agent_cleanup")
        return True

    agent = SimpleNamespace(
        initialize=AsyncMock(), cleanup=AsyncMock(side_effect=cleanup)
    )
    discord = SimpleNamespace(initialize=AsyncMock(), start=start, close=close)
    media = SimpleNamespace(close=AsyncMock())
    globals_ = api_server.lifespan.__wrapped__.__globals__
    monkeypatch.setitem(
        globals_,
        "config",
        SimpleNamespace(
            ham_api_key="",
            api_key="synthetic-project",
            discord_enabled=True,
            discord_bot_token="synthetic-discord",
        ),
    )
    monkeypatch.setitem(globals_, "SelfImprovingAgent", lambda: agent)
    monkeypatch.setitem(globals_, "DiscordIntegration", lambda **_: discord)
    monkeypatch.setitem(
        globals_,
        "GitHubEnabledSelfModifier",
        Mock(side_effect=AssertionError("GitHub capability invoked")),
    )
    monkeypatch.setitem(globals_, "logger", logs)

    async def short_wait(tasks, *, timeout):
        waits.append(timeout)
        return await asyncio.wait(tasks, timeout=min(timeout, 0.01))

    # Replace only this module's asyncio binding, not the global event-loop API.
    monkeypatch.setitem(
        globals_,
        "asyncio",
        SimpleNamespace(
            create_task=asyncio.create_task,
            wait=short_wait,
        ),
    )
    monkeypatch.setattr(MediaService, "from_env", lambda _: media)
    monkeypatch.setattr(ConnectorService, "from_env", lambda _: object())
    monkeypatch.setattr(
        api_server.error_recovery_manager, "cleanup_old_checkpoints", lambda: None
    )
    for name in ("agent", "github_modifier", "discord_integration"):
        monkeypatch.setattr(app_state, name, None)
    monkeypatch.setattr(app_state, "server_shutdown", False)
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_REPO", "")
    return SimpleNamespace(
        app=app,
        agent=agent,
        media=media,
        entered=entered,
        close_entered=close_entered,
        released=released,
        logs=logs,
        order=order,
        waits=waits,
        diagnostic=diagnostic,
    )


async def drain(fixture):
    fixture.released.set()
    pending = list(fixture.app.state.service_tasks)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True), timeout=0.3
        )
    await asyncio.sleep(0)


async def test_listener_is_tracked_and_stops_before_agent_cleanup(monkeypatch):
    fixture = prepare(monkeypatch)
    async with api_server.lifespan(fixture.app):
        await fixture.entered.wait()
        assert fixture.app.state.discord_task in fixture.app.state.service_tasks
        fixture.agent.cleanup.assert_not_awaited()
    assert fixture.app.state.discord_task.done()
    assert fixture.order.index("listener_finished") < fixture.order.index(
        "agent_cleanup"
    )
    fixture.agent.cleanup.assert_awaited_once()
    fixture.media.close.assert_awaited_once()
    assert app_state.server_shutdown is True
    assert not fixture.app.state.service_tasks


async def test_listener_failure_is_consumed_and_only_type_is_logged(monkeypatch):
    fixture = prepare(monkeypatch, listener_failure=True)
    async with api_server.lifespan(fixture.app):
        await fixture.entered.wait()
        await asyncio.sleep(0)
        listener = fixture.app.state.discord_task
        assert listener.done()
        # Calling exception() here would itself consume the failure and hide a bug.
        assert listener._log_traceback is False
        assert listener not in fixture.app.state.service_tasks
    assert fixture.diagnostic not in "\n".join(fixture.logs.lines)
    assert any("RuntimeError" in line for line in fixture.logs.lines)


async def test_close_failure_still_cancels_listener_before_agent_cleanup(monkeypatch):
    fixture = prepare(monkeypatch, close_failure=True)
    try:
        async with api_server.lifespan(fixture.app):
            await fixture.entered.wait()
        assert fixture.app.state.discord_task.done()
        assert fixture.order.index("listener_finished") < fixture.order.index(
            "agent_cleanup"
        )
        assert fixture.diagnostic not in "\n".join(fixture.logs.lines)
        assert not fixture.app.state.service_tasks
    finally:
        await drain(fixture)


@pytest.mark.parametrize("resistant_listener", [False, True])
async def test_resistant_close_keeps_observed_tasks_but_shutdown_is_bounded(
    monkeypatch, resistant_listener
):
    fixture = prepare(
        monkeypatch, resistant_close=True, resistant_listener=resistant_listener
    )
    context = api_server.lifespan(fixture.app)
    await context.__aenter__()
    await fixture.entered.wait()
    try:
        await asyncio.wait_for(context.__aexit__(None, None, None), timeout=0.3)
        assert fixture.close_entered.is_set()
        assert fixture.waits and all(timeout == 2 for timeout in fixture.waits)
        assert len(fixture.app.state.service_tasks) == (2 if resistant_listener else 1)
        assert any("pending" in line for line in fixture.logs.lines)
        fixture.agent.cleanup.assert_awaited_once()
        fixture.media.close.assert_awaited_once()
    finally:
        await drain(fixture)
    assert not fixture.app.state.service_tasks
