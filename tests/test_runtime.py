"""No provider, database, network, or native dependency needed."""

import asyncio
import threading
import time

import pytest

from evolving_agent.core.runtime import AgentRuntime, RuntimeBusyError, bounded_seconds


async def test_timeout_releases_async_operation():
    runtime = AgentRuntime(timeout=0.01)
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
    runtime = AgentRuntime(timeout=0.01)
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
        await asyncio.sleep(0.005)
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


async def test_cancellation_resistant_async_operation_retains_lease_after_timeout():
    runtime = AgentRuntime(timeout=0.01, shutdown_timeout=0.01)
    released = asyncio.Event()

    async def stubborn():
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass
        return "late response must not be accepted"

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(runtime.run(stubborn), timeout=0.2)
    assert time.monotonic() - started < 0.2
    assert runtime.busy and runtime.status()["active_async_operations"] == 1
    assert runtime.completed == 0 and runtime.timeouts == 1
    with pytest.raises(RuntimeBusyError):
        await runtime.run(lambda: asyncio.sleep(0))
    assert await runtime.close() is False
    released.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert runtime.status()["active_async_operations"] == 0
    assert runtime.completed == 0


async def test_caller_cancellation_cannot_release_stubborn_dependency_lease():
    runtime = AgentRuntime()
    entered, released = asyncio.Event(), asyncio.Event()

    async def stubborn():
        entered.set()
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    caller = asyncio.create_task(runtime.run(stubborn))
    await entered.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert runtime.busy
    released.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not runtime.busy


async def test_background_starts_after_foreground_and_blocks_next_chat():
    runtime = AgentRuntime()
    foreground_finished = False
    background_entered, release_background = asyncio.Event(), asyncio.Event()

    async def background():
        assert foreground_finished
        background_entered.set()
        await release_background.wait()

    async def foreground():
        assert runtime.submit(background, kind="storage")
        await asyncio.sleep(0)
        assert not background_entered.is_set()

    await runtime.run(foreground)
    foreground_finished = True
    await background_entered.wait()
    assert runtime.busy and not runtime.idle
    with pytest.raises(RuntimeBusyError):
        await runtime.run(lambda: asyncio.sleep(0))
    release_background.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert runtime.idle


async def test_background_jobs_do_not_overlap_and_stuck_worker_blocks_queue():
    runtime = AgentRuntime(shutdown_timeout=0.01)
    first_entered, released, second_entered = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )

    async def first():
        first_entered.set()
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    async def second():
        second_entered.set()

    assert runtime.submit(first, kind="storage", timeout=0.01)
    assert runtime.submit(second, kind="maintenance")
    await first_entered.wait()
    await asyncio.sleep(0.03)
    assert runtime.timeouts == 1
    assert not second_entered.is_set()
    assert runtime.busy
    released.set()
    await asyncio.wait_for(second_entered.wait(), timeout=0.2)
    for _ in range(10):
        await asyncio.sleep(0)
    assert runtime.idle


async def test_shutdown_is_bounded_for_stubborn_background_work():
    runtime = AgentRuntime(shutdown_timeout=0.01)
    entered, released = asyncio.Event(), asyncio.Event()

    async def stubborn():
        entered.set()
        while not released.is_set():
            try:
                await released.wait()
            except asyncio.CancelledError:
                pass

    runtime.submit(stubborn, kind="storage")
    await entered.wait()
    assert await asyncio.wait_for(runtime.close(), timeout=0.2) is False
    assert runtime.status()["closed"]
    assert runtime.status()["active_async_operations"] == 1
    released.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert await runtime.close() is True


async def test_shutdown_does_not_cancel_native_worker_and_reports_it():
    runtime = AgentRuntime(timeout=0.01, shutdown_timeout=0.01)
    released = threading.Event()
    try:
        with pytest.raises(TimeoutError):
            await runtime.run(lambda: runtime.run_sync(lambda: released.wait(2)))
        assert await runtime.close() is False
        assert runtime.status()["active_workers"] == 1
    finally:
        released.set()
    for _ in range(100):
        if not runtime.status()["active_workers"]:
            break
        await asyncio.sleep(0.005)
    assert await runtime.close() is True


async def test_late_async_exception_is_consumed_without_content_in_telemetry():
    runtime = AgentRuntime(timeout=0.01)
    released = asyncio.Event()

    async def stubborn():
        try:
            await released.wait()
        except asyncio.CancelledError:
            await released.wait()
        raise RuntimeError("sensitive provider detail")

    with pytest.raises(TimeoutError):
        await runtime.run(stubborn)
    released.set()
    for _ in range(10):
        await asyncio.sleep(0)
    assert runtime.idle
    assert "sensitive provider detail" not in str(runtime.status())


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 301])
def test_invalid_background_deadline_rejected(timeout):
    with pytest.raises(ValueError):
        AgentRuntime().submit(lambda: asyncio.sleep(0), kind="invalid", timeout=timeout)
