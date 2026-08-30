"""No provider, database, network, or native dependency needed."""
import asyncio
import threading

import pytest

from evolving_agent.core.runtime import AgentRuntime, RuntimeBusyError, bounded_seconds


async def test_timeout_releases_async_operation():
    runtime = AgentRuntime(timeout=.01)
    with pytest.raises(TimeoutError):
        await runtime.run(lambda: asyncio.sleep(10))
    assert not runtime.busy
    assert runtime.status()["timeouts"] == 1


async def test_rejects_concurrent_request_without_queue():
    runtime = AgentRuntime()
    gate = asyncio.Event()
    first = asyncio.create_task(runtime.run(gate.wait))
    await asyncio.sleep(0)
    with pytest.raises(RuntimeBusyError):
        await runtime.run(gate.wait)
    gate.set()
    await first
    assert runtime.status()["rejected"] == 1


async def test_timed_out_thread_keeps_busy_until_actual_exit():
    runtime = AgentRuntime(timeout=.01)
    gate = threading.Event()
    try:
        with pytest.raises(TimeoutError):
            await runtime.run(lambda: runtime.run_sync(lambda: gate.wait(2)))
        assert runtime.busy
        with pytest.raises(RuntimeBusyError):
            await runtime.run(lambda: asyncio.sleep(0))
    finally:
        gate.set()
    for _ in range(100):
        if not runtime.busy:
            break
        await asyncio.sleep(.005)
    assert not runtime.busy


async def test_background_is_bounded_observed_and_cancelled():
    runtime = AgentRuntime(max_jobs=1)
    assert runtime.submit(lambda: asyncio.sleep(10), kind="maintenance")
    assert not runtime.submit(lambda: asyncio.sleep(10), kind="overflow")
    await asyncio.sleep(0)
    await runtime.close()
    assert runtime.status()["background_jobs"] == 0
    assert not runtime.submit(lambda: asyncio.sleep(0), kind="closed")


def test_nan_timeout_is_rejected(monkeypatch):
    monkeypatch.setenv("CHAT_TIMEOUT_SECONDS", "nan")
    with pytest.raises(ValueError):
        bounded_seconds("CHAT_TIMEOUT_SECONDS", 60)
