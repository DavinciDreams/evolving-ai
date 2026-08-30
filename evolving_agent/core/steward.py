"""Operator control plane for bounded dreams and measured response adaptation."""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import asdict, is_dataclass

from .dream_cycle import DreamConfig, DreamConsolidationService
from .runtime import RuntimeBusyError
from ..self_modification.improvement_lab import ImprovementLab, ModelOutput
from ..utils.secret_redaction import redact_text


class StewardControl:
    """Single-worker job supervisor. Status never contains prompts or credentials."""

    def __init__(self, agent, llm):
        self.agent = agent
        self.llm = llm
        self.jobs = {}
        self._task = None
        self.current_kind = None
        self.closed = False
        self.enabled = os.getenv("IMPROVEMENT_LAB_ENABLED", "false").lower() == "true"
        self.lab = ImprovementLab(agent.memory, self._run_model) if self.enabled else None
        self.dreams = DreamConsolidationService(
            agent.memory, llm_manager=llm, settings=DreamConfig.from_env(),
            is_idle=lambda: agent.runtime.idle and self.current_kind != "improvement"
            and not (self.lab and self.lab.status()["busy"]),
        )

    @property
    def busy(self):
        return bool(self._task and not self._task.done())

    async def initialize(self):
        if self.lab and getattr(self.agent.memory, "backend", None) != "ham":
            raise RuntimeError("Improvement lab requires authoritative HAM memory")
        state_id = os.getenv("IMPROVEMENT_STATE_MEMORY_ID", "")
        if self.lab and state_id:
            if not state_id.isdecimal():
                raise ValueError("IMPROVEMENT_STATE_MEMORY_ID must be an exact HAM ID")
            await self.lab.restore(state_id)
        self.agent.improvement_lab = self.lab
        self.agent.dream_service = self.dreams
        self.dreams.start()

    async def _run_model(self, guidance: str, prompt: str) -> ModelOutput:
        # No tools; never pass expected answers or holdout labels to the model.
        system = "You are Katbot. Respect safety and user instructions.\n" + guidance
        response = await self.llm.generate_response(
            prompt=redact_text(prompt)[0], system_prompt=system,
            temperature=0, max_tokens=512, timeout=10,
        )
        # Manager returns text, not provider usage. This is a conservative debit,
        # explicitly not a claim about actual billing or reported token usage.
        debit = len((system + prompt).encode("utf-8")) + 512 + 128
        return ModelOutput(response, debit, usage_kind="conservative_bound")

    def submit(self, kind: str, operation) -> dict:
        if self.closed or self.busy or not self.agent.runtime.idle:
            raise RuntimeBusyError("Another operation is still running")
        if self.dreams.status()["running"] or (self.lab and self.lab.status()["busy"]):
            raise RuntimeBusyError("A background dependency is still running")
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "queued"}
        self.current_kind = kind
        while len(self.jobs) > 30:
            self.jobs.pop(next(iter(self.jobs)))

        async def work():
            job = self.jobs[job_id]
            job["status"] = "running"
            try:
                # Each engine owns its strict deadline and late-callback quarantine.
                result = await operation()
                job["status"] = "completed"
                if is_dataclass(result):
                    result = asdict(result)
                job["result"] = result
            except asyncio.CancelledError:
                job["status"] = "cancelled"
                raise
            except Exception as exc:
                job.update(status="failed", error_type=type(exc).__name__)
            finally:
                self.current_kind = None

        self._task = asyncio.create_task(work(), name=f"katbot-{kind}")
        return dict(self.jobs[job_id])

    def status(self):
        return {
            "runtime": self.agent.runtime.status(), "dreams": self.dreams.status(),
            "improvement": {"enabled": self.enabled, **(self.lab.status() if self.lab else {})},
            "jobs": [{key: value for key, value in job.items() if key != "result"}
                     for job in self.jobs.values()],
            "storage": self.agent.last_storage_status,
            "deployment_contract": "one_worker_private_authenticated_ham",
        }

    async def close(self):
        self.closed = True
        if self.busy:
            self._task.cancel()
            await asyncio.wait({self._task}, timeout=2)
        await self.dreams.stop()
