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

    def __init__(self, *, timeout: float = 60.0, max_jobs: int = 8):
        if not 0 < timeout <= 300 or not 1 <= max_jobs <= 32:
            raise ValueError("Invalid runtime limits")
        self.timeout = timeout
        self.max_jobs = max_jobs
        self._active = False
        self._closed = False
        self._workers: set[asyncio.Task] = set()
        self._jobs: set[asyncio.Task] = set()
        self._events = deque(maxlen=50)
        self.completed = self.failed = self.timeouts = self.rejected = 0

    @property
    def busy(self) -> bool:
        return self._active or bool(self._workers) or self._closed

    @property
    def idle(self) -> bool:
        return not self.busy and not self._jobs

    async def run(self, operation: Callable[[], Awaitable], *, kind: str = "chat"):
        if self.busy:
            self.rejected += 1
            raise RuntimeBusyError("Katbot is busy; retry after the current operation finishes")
        self._active = True
        started = time.monotonic()
        outcome = "completed"
        try:
            async with asyncio.timeout(self.timeout):
                result = await operation()
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
            self._events.append({"kind": kind, "outcome": outcome,
                                 "duration_ms": round((time.monotonic() - started) * 1000)})

    async def run_sync(self, operation: Callable):
        """Shield thread lifetime from caller timeout, retaining the busy lease."""
        task = asyncio.create_task(asyncio.to_thread(operation))
        self._workers.add(task)

        def finished(done):
            self._workers.discard(done)
            if not done.cancelled():
                done.exception()  # consume late failures without exposing provider text

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    def submit(self, operation: Callable[[], Awaitable], *, kind: str,
               timeout: float = 30.0) -> bool:
        if self._closed or len(self._jobs) >= self.max_jobs:
            self.rejected += 1
            return False

        async def work():
            outcome = "completed"
            try:
                async with asyncio.timeout(timeout):
                    await operation()
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
        self._jobs.add(task)
        task.add_done_callback(self._jobs.discard)
        return True

    def status(self) -> dict:
        return {"busy": self.busy, "idle": self.idle, "closed": self._closed,
                "active_workers": len(self._workers), "background_jobs": len(self._jobs),
                "timeout_seconds": self.timeout, "completed": self.completed,
                "failed": self.failed, "timeouts": self.timeouts,
                "rejected": self.rejected, "recent_events": list(self._events)}

    async def close(self):
        self._closed = True
        jobs = list(self._jobs)
        for task in jobs:
            task.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        # Native workers are deliberately not cancelled or silently replaced.

