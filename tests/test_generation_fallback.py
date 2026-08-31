"""Text-only fallback preserves authority boundaries and never retries tools."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests import test_agent_run as agent_tests
from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.core.identity import BASE_STEWARD_PROMPT

agent = agent_tests.agent


@pytest.mark.parametrize("failure_stage", ["model", "generation"])
async def test_one_fallback_for_sdk_failure(agent, failure_stage):
    agent._build_system_prompt = MagicMock(return_value=BASE_STEWARD_PROMPT)
    agent._build_messages = MagicMock(return_value=[])
    agent._get_ai_sdk_model = MagicMock(return_value=object())
    if failure_stage == "model":
        agent._get_ai_sdk_model.side_effect = RuntimeError("synthetic-private-error")
    agent._generate_text_candidate = AsyncMock(return_value="safe fallback")
    cfg = MagicMock(enable_tool_use=False)
    with patch("evolving_agent.core.agent.config", cfg), patch(
        "evolving_agent.core.agent.generate_text", side_effect=RuntimeError("synthetic-private-error")
    ) as sdk:
        result = await SelfImprovingAgent._generate_response(agent, "question", {})
    assert result == "safe fallback"
    agent._generate_text_candidate.assert_awaited_once_with("question", {}, None)
    assert sdk.call_count == (1 if failure_stage == "generation" else 0)
    assert "synthetic-private-error" not in str(agent.logger.mock_calls)


async def test_candidate_keeps_shared_safety_and_active_guidance(agent):
    agent._build_system_prompt = MagicMock(return_value=BASE_STEWARD_PROMPT + "\nActive closed strategy")
    agent._build_fallback_prompt = MagicMock(return_value="redacted context and question")
    cfg = MagicMock(max_tokens=2048, temperature=0.3)
    with patch("evolving_agent.core.agent.config", cfg), patch(
        "evolving_agent.integrations.bounded_llm.BoundedTextProvider.generate_response",
        new_callable=AsyncMock, return_value="answer",
    ) as call:
        await SelfImprovingAgent._generate_text_candidate(agent, "question", {})
    arguments = call.call_args.kwargs
    assert BASE_STEWARD_PROMPT in arguments["system_prompt"]
    assert "Active closed strategy" in arguments["system_prompt"]
    assert "tools are unavailable" in arguments["system_prompt"]
    assert arguments["timeout"] == 10
    assert "tools" not in arguments


async def test_failed_fallback_does_not_leak_provider_error_to_logs(agent):
    agent._build_system_prompt = MagicMock(return_value=BASE_STEWARD_PROMPT)
    agent._build_messages = MagicMock(return_value=[])
    agent._get_ai_sdk_model = MagicMock(side_effect=RuntimeError("first-private-error"))
    agent._generate_text_candidate = AsyncMock(side_effect=RuntimeError("second-private-error"))
    with patch("evolving_agent.core.agent.config", MagicMock(enable_tool_use=False)):
        with pytest.raises(RuntimeError):
            await SelfImprovingAgent._generate_response(agent, "question", {})
    assert "private-error" not in str(agent.logger.mock_calls)
    agent._generate_text_candidate.assert_awaited_once()


async def test_native_anthropic_uses_single_text_adapter_not_legacy_openai_wire(agent):
    cfg = MagicMock(default_llm_provider="anthropic")
    agent._generate_text_candidate = AsyncMock(side_effect=RuntimeError("synthetic-provider-error"))
    agent._get_ai_sdk_model = MagicMock()
    with patch("evolving_agent.core.agent.config", cfg):
        with pytest.raises(RuntimeError):
            await SelfImprovingAgent._generate_response(agent, "question", {})
    agent._get_ai_sdk_model.assert_not_called()
    agent._generate_text_candidate.assert_awaited_once()


@pytest.mark.parametrize("provider", ["openai", "zai", "openrouter"])
def test_chat_uses_selected_model_endpoint_and_disables_sdk_retries(agent, provider):
    from types import SimpleNamespace
    from evolving_agent.integrations.provider_config import ProviderSelection
    selected = ProviderSelection(provider, "pinned-model", "https://provider.test/v1", "https://provider.test/v1/chat/completions")
    cfg = SimpleNamespace(**{f"{provider}_api_key": "synthetic-test-value"})
    with patch("evolving_agent.core.agent.config", cfg), patch(
        "evolving_agent.integrations.provider_config.resolve_provider", return_value=selected
    ), patch("evolving_agent.core.agent.OpenAIModel") as model_class, patch(
        "evolving_agent.core.agent._openai_lib.OpenAI"
    ) as client_class:
        SelfImprovingAgent._get_ai_sdk_model(agent)
    model_class.assert_called_once_with("pinned-model", api_key="synthetic-test-value")
    assert client_class.call_args.kwargs["base_url"] == selected.base_url
    assert client_class.call_args.kwargs["max_retries"] == 0
    assert client_class.call_args.kwargs["timeout"] == 60
