"""Durable Katbot-to-Hyades execution handoff through HAM tasks.

Katbot deliberately has no Saturn or Hyades control-plane credential.  It posts
an explicit project task with its existing HAM identity, then observes HAM's
append-only lifecycle while Hyades owns workspace authority and gVisor
execution.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Awaitable, Callable, Dict, Optional

from .ham_memory import HAMMemoryClient, HAMMemoryError
from ..utils.secret_redaction import redact_text


ProgressCallback = Callable[[str], Awaitable[None]]


class HyadesTaskError(RuntimeError):
    """Raised when a durable Hyades task cannot safely continue."""


class HyadesTaskBridge:
    """Post, follow, and cancel bounded Hyades work through HAM."""

    TERMINAL_FAILURES = frozenset({"failed", "cancelled", "stalled"})

    def __init__(
        self,
        client: HAMMemoryClient,
        *,
        poll_seconds: float = 5.0,
        timeout_seconds: float = 1800.0,
    ) -> None:
        self.client = client
        self.poll_seconds = min(max(float(poll_seconds), 1.0), 60.0)
        self.timeout_seconds = min(max(float(timeout_seconds), 60.0), 3600.0)

    @staticmethod
    def _key(prefix: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"katbot:{prefix}:{digest}"

    async def post(
        self,
        request: str,
        *,
        requester_ref: str,
        source_id: str,
    ) -> Dict[str, object]:
        """Create one idempotent, least-authority execution task."""
        safe_request, findings = redact_text(request)
        safe_request = safe_request.strip()
        if not safe_request:
            raise HyadesTaskError("The Hyades task is empty after safety filtering")

        first_line = next(
            (line.strip() for line in safe_request.splitlines() if line.strip()),
            "bounded execution",
        )
        title = f"Katbot gVisor: {first_line}"[:400]
        goal = (
            "Complete the following request inside the Hyades managed workspace. "
            "Execution must use workspaceDriver=sandbox-pod (gVisor), remain "
            "bounded and cancellable, and report a concise result plus artifact "
            "references through the HAM task lifecycle. Do not merge, deploy, "
            "publish, rotate credentials, or broaden authority.\n\n"
            f"Request:\n{safe_request}"
        )
        if findings:
            goal += "\n\nCredential-shaped input was redacted before task persistence."
        repository = self.client.repo
        resources = (
            [{"key": f"repo:{repository}", "mode": "write"}]
            if repository
            else []
        )

        try:
            return await self.client.post_task(
                title=title,
                goal=goal,
                acceptance_criteria=[
                    "Run only in a Hyades sandbox-pod gVisor workspace.",
                    "Respect the run deadline and cancellation state.",
                    "Return a concise summary and stable artifact references.",
                    "Do not perform external publication or deployment mutations.",
                ],
                requester_ref=requester_ref,
                idempotency_key=self._key("hyades-post", source_id),
                resources=resources,
                activity_mode="test",
                completion_policy="immediate",
            )
        except HAMMemoryError as exc:
            raise HyadesTaskError("HAM rejected the Hyades task handoff") from exc

    async def follow(
        self,
        task_id: str,
        *,
        progress: Optional[ProgressCallback] = None,
    ) -> str:
        """Follow lifecycle events until completion, clarification, or failure."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout_seconds
        event_cursor = 0
        last_notice = ""

        while True:
            try:
                task = await self.client.get_task(task_id)
                for _ in range(5):
                    previous_cursor = event_cursor
                    events, event_cursor, has_more = await self.client.task_events(
                        task_id,
                        after_event_id=event_cursor,
                    )
                    for event in events:
                        summary = event.get("summary") if isinstance(event, dict) else None
                        event_type = (
                            str(event.get("event_type", "progress"))
                            if isinstance(event, dict)
                            else "progress"
                        )
                        safe_summary = (
                            redact_text(str(summary))[0] if summary else ""
                        )
                        notice = (
                            f"{event_type}: {safe_summary}"
                            if safe_summary
                            else event_type
                        )
                        if progress is not None and notice != last_notice:
                            await progress(notice[:1_800])
                            last_notice = notice
                    if not has_more:
                        break
                    if event_cursor <= previous_cursor:
                        raise HAMMemoryError("HAM task event cursor did not advance")
            except HAMMemoryError as exc:
                raise HyadesTaskError("HAM task telemetry became unavailable") from exc

            status = str(task["status"])
            latest = task.get("latest_event")
            summary = latest.get("summary") if isinstance(latest, dict) else None
            if status == "completed":
                safe_summary = redact_text(str(summary))[0] if summary else ""
                return safe_summary or "Hyades completed the task without a summary."
            if status == "needs_clarification":
                safe_summary = redact_text(str(summary))[0] if summary else ""
                return "Hyades needs clarification: " + (
                    safe_summary or "no clarification prompt was supplied"
                )
            if status in self.TERMINAL_FAILURES:
                safe_summary = redact_text(str(summary))[0] if summary else ""
                raise HyadesTaskError(
                    f"Hyades task ended with status {status}: "
                    f"{safe_summary or 'no safe summary was supplied'}"
                )

            remaining = deadline - loop.time()
            if remaining <= 0:
                try:
                    await self.client.cancel_task(
                        task_id,
                        expected_version=int(task["version"]),
                        summary="Katbot cancelled the task after its bounded deadline.",
                        idempotency_key=self._key("hyades-timeout", task_id),
                    )
                except HAMMemoryError:
                    pass
                raise HyadesTaskError("Hyades task exceeded its bounded deadline")
            await asyncio.sleep(min(self.poll_seconds, remaining))

    async def cancel(self, task_id: str) -> Dict[str, object]:
        """Cancel active work with optimistic concurrency against current state."""
        try:
            task = await self.client.get_task(task_id)
            if task["status"] in {"completed", "failed", "cancelled"}:
                return task
            return await self.client.cancel_task(
                task_id,
                expected_version=int(task["version"]),
                summary="Cancelled by the originating Discord requester.",
                idempotency_key=self._key("hyades-cancel", task_id),
            )
        except HAMMemoryError as exc:
            raise HyadesTaskError("HAM rejected the Hyades cancellation") from exc
