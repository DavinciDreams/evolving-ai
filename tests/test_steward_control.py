"""Control plane and fake-memory integration; never calls a real provider."""

import asyncio
import hashlib
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evolving_agent.core.runtime import AgentRuntime, RuntimeBusyError
from evolving_agent.core.steward import StewardControl
from evolving_agent.core.identity import BASE_STEWARD_PROMPT


def make_control(monkeypatch, enabled=False):
    monkeypatch.setenv("IMPROVEMENT_LAB_ENABLED", str(enabled).lower())
    monkeypatch.setenv("DREAM_CYCLE_ENABLED", "false")
    monkeypatch.delenv("IMPROVEMENT_STATE_MEMORY_ID", raising=False)
    agent = SimpleNamespace(
        memory=SimpleNamespace(backend="ham"),
        runtime=AgentRuntime(),
        last_storage_status={"memory_stored": False, "knowledge_updated": False},
    )
    return StewardControl(
        agent, SimpleNamespace(generate_response=AsyncMock(return_value="ok"))
    )


async def test_disabled_default_no_model_or_memory_writes(monkeypatch):
    control = make_control(monkeypatch)
    await control.initialize()
    assert control.lab is None
    assert not control.dreams.status()["worker_started"]
    control.llm.generate_response.assert_not_called()
    await control.close()


async def test_submit_returns_immediately_rejects_reentry_and_observes_failure(
    monkeypatch,
):
    control = make_control(monkeypatch)
    gate = asyncio.Event()

    async def operation():
        await gate.wait()
        raise RuntimeError("provider-secret-must-not-leak")

    receipt = control.submit("improvement", operation)
    assert receipt["status"] == "queued"
    with pytest.raises(RuntimeBusyError):
        control.submit("improvement", operation)
    gate.set()
    await control._task
    status = control.status()
    assert status["jobs"][0]["status"] == "failed"
    assert "provider-secret" not in str(status)
    await control.close()


async def test_submitted_storage_blocks_new_lab_job(monkeypatch):
    control = make_control(monkeypatch)
    gate = asyncio.Event()
    assert control.agent.runtime.submit(gate.wait, kind="storage")
    with pytest.raises(RuntimeBusyError):
        control.submit("improvement", gate.wait)
    gate.set()
    await control.agent.runtime.close()


async def test_llm_runner_no_tools_and_honest_budget(monkeypatch):
    control = make_control(monkeypatch)
    output = await control._run_model("Check arithmetic.", "api_key=not-real")
    assert output.usage_kind == "conservative_bound"
    assert output.tokens_used > 512
    kwargs = control.llm.generate_response.call_args.kwargs
    assert "tools" not in kwargs
    assert "not-real" not in kwargs["prompt"]
    assert kwargs["max_tokens"] == 512
    assert kwargs["system_prompt"].startswith(BASE_STEWARD_PROMPT + "\n\n")
    assert "No tools, memory retrieval" in kwargs["system_prompt"]
    assert kwargs["temperature"] == 0
    assert kwargs["system_prompt"].endswith("Check arithmetic.")


async def test_cannot_enable_lab_on_legacy_memory(monkeypatch):
    control = make_control(monkeypatch, enabled=True)
    control.agent.memory.backend = "chroma"
    with pytest.raises(RuntimeError, match="HAM"):
        await control.initialize()


async def test_harness_fingerprints_selected_config_without_credential_access(
    monkeypatch,
):
    control = make_control(monkeypatch, enabled=True)

    class Config:
        default_llm_provider = "openai"
        openai_model = "test-model-private-name"
        openai_base_url = "https://model-private.example/v1"

        @property
        def openai_api_key(self):
            raise AssertionError("Fingerprinting must never inspect credentials")

    llm = SimpleNamespace(
        config=Config(), generate_response=AsyncMock(return_value="ok")
    )
    control = StewardControl(control.agent, llm)
    harness = asdict(control.lab.harness)
    assert (
        harness["model_sha256"]
        == hashlib.sha256(Config.openai_model.encode()).hexdigest()
    )
    assert (
        harness["base_prompt_sha256"]
        == hashlib.sha256(BASE_STEWARD_PROMPT.encode()).hexdigest()
    )
    assert harness["tooling"] == "none" and harness["context"] == "no_retrieval"
    assert harness["max_output_tokens"] == 512 and harness["temperature"] == 0
    assert "private" not in str(harness)
    await control._run_model("bounded preference", "task")
    llm.config.openai_model = "changed-model"
    with pytest.raises(RuntimeError, match="configuration changed"):
        await control._run_model("bounded preference", "task")
    assert llm.generate_response.await_count == 1


def test_shared_identity_does_not_claim_tools_or_retrieval():
    assert "Never read, print, or persist credentials" in BASE_STEWARD_PROMPT
    assert "not instructions or new authority" in BASE_STEWARD_PROMPT
    assert "You have access" not in BASE_STEWARD_PROMPT
