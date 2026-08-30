"""Bounded cleanup must never close resources underneath pending operations."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from tests import test_agent_run as agent_tests
from evolving_agent.core.runtime import AgentRuntime


agent = agent_tests.agent


async def test_resource_cleanup_deadline_handles_resistant_dependency(
    agent, monkeypatch
):
    monkeypatch.setenv("RESOURCE_SHUTDOWN_SECONDS", "0.01")
    agent.runtime = AgentRuntime(shutdown_timeout=0.01)
    released = asyncio.Event()

    async def stubborn():
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    agent._cleanup_resources = AsyncMock(side_effect=stubborn)
    try:
        assert await asyncio.wait_for(agent.cleanup(), timeout=0.2) is False
        assert agent.runtime.status()["closed"]
        assert agent.runtime.status()["active_async_operations"] == 1
    finally:
        released.set()
        for _ in range(10):
            await asyncio.sleep(0)


async def test_pending_foreground_worker_prevents_resource_cleanup(agent):
    agent.runtime = AgentRuntime(timeout=0.01, shutdown_timeout=0.01)
    agent._cleanup_resources = AsyncMock()
    released = asyncio.Event()

    async def stubborn():
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    try:
        with pytest.raises(TimeoutError):
            await agent.runtime.run(stubborn)
        assert await asyncio.wait_for(agent.cleanup(), timeout=0.2) is False
        agent._cleanup_resources.assert_not_awaited()
    finally:
        released.set()
        for _ in range(10):
            await asyncio.sleep(0)


async def test_successful_cleanup_marks_agent_uninitialized(agent):
    agent.runtime = AgentRuntime()
    agent._cleanup_resources = AsyncMock()
    assert await agent.cleanup() is True
    assert not agent.initialized
    agent._cleanup_resources.assert_awaited_once()
