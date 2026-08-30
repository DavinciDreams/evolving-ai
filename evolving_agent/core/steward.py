"""Operator control plane for bounded dreams and measured response adaptation."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import asdict, is_dataclass

from .dream_cycle import DreamConfig, DreamConsolidationService
from .identity import BASE_STEWARD_PROMPT
from .learning_cycle import LearningConfig, LearningCycle, load_suite
from .runtime import RuntimeBusyError
from ..self_modification.improvement_lab import (
    HarnessDescriptor,
    ImprovementLab,
    ModelOutput,
)
from ..utils.secret_redaction import redact_text


EXPERIMENT_BOUNDARY_PROMPT = (
    "This is a bounded text-guidance experiment. No tools, memory retrieval, "
    "conversation history, or external actions are available. Answer only the "
    "provided task; do not claim to have retrieved evidence or performed actions."
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _harness_for(llm) -> HarnessDescriptor:
    """Inspect only non-secret selected-provider configuration; never credentials."""
    cfg = getattr(llm, "config", None)
    provider = getattr(cfg, "default_llm_provider", "unspecified")
    model, endpoint = "unspecified", "unspecified"
    if provider == "anthropic":
        model, endpoint = cfg.default_model, "https://api.anthropic.com/v1/messages"
    elif provider == "openrouter":
        model, endpoint = (
            cfg.default_model,
            "https://openrouter.ai/api/v1/chat/completions",
        )
    elif provider == "zai":
        model, endpoint = (
            cfg.zai_model,
            cfg.zai_base_url.rstrip("/") + "/chat/completions",
        )
    elif provider == "openai":
        model = cfg.openai_model
        endpoint = (cfg.openai_base_url or "https://api.openai.com/v1").rstrip(
            "/"
        ) + "/chat/completions"
    return HarnessDescriptor(
        provider=provider,
        model_sha256=_sha256(model),
        endpoint_sha256=_sha256(endpoint),
        adapter_sha256=_sha256(type(llm).__module__ + "." + type(llm).__qualname__),
        base_prompt_sha256=_sha256(BASE_STEWARD_PROMPT),
        experiment_prompt_sha256=_sha256(EXPERIMENT_BOUNDARY_PROMPT),
        tooling="none",
        context="no_retrieval",
        input_transform="secret_redaction_v1",
        temperature=0,
        max_output_tokens=512,
    )


class StewardControl:
    """Single-worker job supervisor. Status never contains prompts or credentials."""

    def __init__(self, agent, llm):
        self.agent = agent
        self.llm = llm
        self.jobs = {}
        self._task = None
        self.current_kind = None
        self.closed = False
        self.learning = None
        self._harness = _harness_for(llm)
        self.enabled = os.getenv("IMPROVEMENT_LAB_ENABLED", "false").lower() == "true"
        self.lab = (
            ImprovementLab(agent.memory, self._run_model, harness=self._harness)
            if self.enabled
            else None
        )
        self.dreams = DreamConsolidationService(
            agent.memory,
            llm_manager=llm,
            settings=DreamConfig.from_env(),
            is_idle=lambda: agent.runtime.idle
            and self.current_kind != "improvement"
            and not (self.lab and self.lab.status()["busy"])
            and not (self.learning and self.learning.status()["running"]),
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
        learning_config = LearningConfig.from_env()
        if learning_config.enabled:
            self.learning = LearningCycle(
                self,
                cases=load_suite(learning_config.suite_file),
                settings=learning_config,
            )
            self.learning.start()
        self.dreams.start()

    async def _run_model(self, guidance: str, prompt: str) -> ModelOutput:
        # No tools; never pass expected answers or holdout labels to the model.
        if _harness_for(self.llm) != self._harness:
            raise RuntimeError(
                "Learning harness configuration changed; create a fresh lab"
            )
        system = "\n\n".join(
            (BASE_STEWARD_PROMPT, EXPERIMENT_BOUNDARY_PROMPT, guidance)
        )
        response = await self.llm.generate_response(
            prompt=redact_text(prompt)[0],
            system_prompt=system,
            temperature=0,
            max_tokens=512,
            timeout=10,
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
        if self.learning and self.learning.status()["running"]:
            raise RuntimeBusyError("A learning dependency is still running")
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
            "runtime": self.agent.runtime.status(),
            "dreams": self.dreams.status(),
            "improvement": {
                "enabled": self.enabled,
                **(self.lab.status() if self.lab else {}),
            },
            "jobs": [
                {key: value for key, value in job.items() if key != "result"}
                for job in self.jobs.values()
            ],
            "storage": self.agent.last_storage_status,
            "learning": self.learning.status() if self.learning else {"enabled": False},
            "deployment_contract": "one_worker_private_authenticated_ham",
        }

    async def close(self):
        self.closed = True
        if self.learning:
            await self.learning.stop()
        if self.busy:
            self._task.cancel()
            await asyncio.wait({self._task}, timeout=2)
        await self.dreams.stop()
