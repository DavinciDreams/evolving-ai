"""Single-process, bounded execution with value-free telemetry.

Synchronous SDK workers cannot be killed safely. A timed-out worker therefore
keeps the runtime busy until it actually exits; we never start a replacement
over a still-running tool call. Run exactly one application worker.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from typing import Awaitable, Callable


class RuntimeBusyError(RuntimeError):
    """Work was rejected without queuing or reentering the agent."""


def bounded_seconds(name: str, default: float, maximum: float = 300.0) -> float:
    """Reject invalid deployment budgets rather than silently disabling limits."""
    value = float(os.getenv(name, str(default)))
    if not 0 < value <= maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return value


class AgentRuntime:
    """One foreground operation and a bounded set of observed background jobs."""

    def __init__(
        self, *, timeout: float = 60.0, max_jobs: int = 8, shutdown_timeout: float = 2.0
    ):
        if (
            not 0 < timeout <= 300
            or not 1 <= max_jobs <= 32
            or not 0 < shutdown_timeout <= 10
        ):
            raise ValueError("Invalid runtime limits")
        self.timeout = timeout
        self.max_jobs = max_jobs
        self.shutdown_timeout = shutdown_timeout
        self._active = False
        self._closed = False
        self._workers: set[asyncio.Task] = set()
        self._async_workers: set[asyncio.Task] = set()
        self._jobs: set[asyncio.Task] = set()
        self._job_lock = asyncio.Lock()
        self._state_changed = asyncio.Event()
        self._events = deque(maxlen=50)
        self.completed = self.failed = self.timeouts = self.rejected = 0

    @property
    def busy(self) -> bool:
        return (
            self._active
            or bool(self._workers or self._async_workers or self._jobs)
            or self._closed
        )

    @property
    def idle(self) -> bool:
        return not self.busy

    def _track(self, task: asyncio.Task, collection: set[asyncio.Task]) -> None:
        collection.add(task)

        def finished(done):
            collection.discard(done)
            if not done.cancelled():
                done.exception()  # consume late failures without exposing provider text
            self._state_changed.set()

        task.add_done_callback(finished)

    async def _cancel(self, task: asyncio.Task) -> None:
        task.cancel()
        # Let a cooperative coroutine and its done callback release the lease,
        # but do not wait for cancellation-resistant dependencies to cooperate.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def _execute(self, operation: Callable[[], Awaitable], *, timeout: float):
        async def invoke():
            return await operation()

        task = asyncio.create_task(invoke(), name="katbot-runtime-operation")
        self._track(task, self._async_workers)
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if not done:
                await self._cancel(task)
                raise TimeoutError("Katbot operation exceeded its deadline")
            return task.result()
        except asyncio.CancelledError:
            await self._cancel(task)
            raise

    async def run(self, operation: Callable[[], Awaitable], *, kind: str = "chat"):
        if self.busy:
            self.rejected += 1
            raise RuntimeBusyError(
                "Katbot is busy; retry after the current operation finishes"
            )
        self._active = True
        started = time.monotonic()
        outcome = "completed"
        try:
            result = await self._execute(operation, timeout=self.timeout)
            self.completed += 1
            return result
        except TimeoutError:
            outcome = "timed_out"
            self.timeouts += 1
            raise
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            self.failed += 1
            raise
        finally:
            self._active = False
            self._state_changed.set()
            self._events.append(
                {
                    "kind": kind,
                    "outcome": outcome,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )

    async def run_sync(self, operation: Callable):
        """Shield thread lifetime from caller timeout, retaining the busy lease."""
        task = asyncio.create_task(asyncio.to_thread(operation))
        self._track(task, self._workers)
        return await asyncio.shield(task)

    def submit(
        self, operation: Callable[[], Awaitable], *, kind: str, timeout: float = 30.0
    ) -> bool:
        if not 0 < timeout <= 300:
            raise ValueError("Invalid background job timeout")
        if self._closed or len(self._jobs) >= self.max_jobs:
            self.rejected += 1
            return False

        async def work():
            outcome = "completed"
            try:
                # Background admission is explicit and bounded, but execution is
                # serial and waits for the submitting foreground task to finish.
                async with self._job_lock:
                    while self._active or self._async_workers or self._workers:
                        self._state_changed.clear()
                        await self._state_changed.wait()
                    if self._closed:
                        outcome = "cancelled"
                        return
                    await self._execute(operation, timeout=timeout)
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise
            except TimeoutError:
                outcome = "timed_out"
                self.timeouts += 1
            except Exception:
                outcome = "failed"
                self.failed += 1
            finally:
                self._events.append({"kind": kind, "outcome": outcome})

        task = asyncio.create_task(work())
        self._track(task, self._jobs)
        return True

    def status(self) -> dict:
        return {
            "busy": self.busy,
            "idle": self.idle,
            "closed": self._closed,
            "active_workers": len(self._workers),
            "background_jobs": len(self._jobs),
            "active_async_operations": len(self._async_workers),
            "timeout_seconds": self.timeout,
            "completed": self.completed,
            "failed": self.failed,
            "timeouts": self.timeouts,
            "rejected": self.rejected,
            "recent_events": list(self._events),
        }

    async def close(self) -> bool:
        """Bounded shutdown; false reports dependencies that have not exited.

        Closing cancels async operations but does not undo remote side effects.
        Native workers are never cancelled or silently replaced. The process
        supervisor must apply its own final termination grace period if needed.
        """
        self._closed = True
        pending_async = self._jobs | self._async_workers
        current = asyncio.current_task()
        for task in pending_async:
            if task is current:
                continue
            task.cancel()
        pending_all = {
            task
            for task in pending_async | self._workers
            if task is not current and not task.done()
        }
        if not pending_all:
            return True
        _, pending = await asyncio.wait(pending_all, timeout=self.shutdown_timeout)
        return not pending
