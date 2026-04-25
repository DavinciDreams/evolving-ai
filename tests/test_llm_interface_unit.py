"""Unit tests for LLM interface classes — no real API calls made."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLLMProvider:
    def test_provider_enum_values(self):
        from evolving_agent.utils.llm_interface import LLMProvider
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.OPENROUTER.value == "openrouter"
        assert LLMProvider.ZAI.value == "zai"


class TestOpenAIInterface:
    def test_instantiation(self):
        from evolving_agent.utils.llm_interface import OpenAIInterface
        iface = OpenAIInterface(api_key="sk-test-key", model="gpt-4")
        assert iface.model == "gpt-4"

    def test_prepare_messages_no_system(self):
        from evolving_agent.utils.llm_interface import OpenAIInterface
        iface = OpenAIInterface(api_key="sk-test", model="gpt-4")
        msgs = iface._prepare_messages("Hello")
        assert msgs == [{"role": "user", "content": "Hello"}]

    def test_prepare_messages_with_system(self):
        from evolving_agent.utils.llm_interface import OpenAIInterface
        iface = OpenAIInterface(api_key="sk-test", model="gpt-4")
        msgs = iface._prepare_messages("Hello", system_prompt="Be helpful")
        assert msgs[0] == {"role": "system", "content": "Be helpful"}
        assert msgs[1] == {"role": "user", "content": "Hello"}

    def test_filter_kwargs_keeps_valid_keys(self):
        from evolving_agent.utils.llm_interface import OpenAIInterface
        iface = OpenAIInterface(api_key="sk-test", model="gpt-4")
        result = iface._filter_kwargs({"stream": True, "unknown_param": "x", "user": "u1"})
        assert "unknown_param" not in result
        assert "stream" in result

    @pytest.mark.asyncio
    async def test_make_completion_request_calls_openai(self):
        from evolving_agent.utils.llm_interface import OpenAIInterface
        iface = OpenAIInterface(api_key="sk-test", model="gpt-4")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked answer"

        with patch.object(
            iface.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await iface._make_completion_request(
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )
        assert result == "Mocked answer"


class TestAnthropicInterface:
    def test_instantiation(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        assert iface.model == "claude-3-5-sonnet-20241022"

    def test_extract_system_prompt(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        messages = [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ]
        system, filtered = iface._extract_system_prompt(messages)
        assert system == "Be concise"
        assert filtered == [{"role": "user", "content": "Hello"}]

    def test_extract_system_prompt_no_system(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        messages = [{"role": "user", "content": "Hello"}]
        system, filtered = iface._extract_system_prompt(messages)
        assert system is None
        assert filtered == messages

    def test_prepare_create_params_includes_system(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        params = iface._prepare_create_params(
            messages=[{"role": "user", "content": "Hi"}],
            system_prompt="Be helpful",
            temperature=0.5,
            max_tokens=256,
        )
        assert params["system"] == "Be helpful"
        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 256

    def test_prepare_create_params_no_system_key_absent(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        params = iface._prepare_create_params(
            messages=[{"role": "user", "content": "Hi"}],
            system_prompt=None,
            temperature=0.5,
            max_tokens=256,
        )
        assert "system" not in params

    def test_filter_kwargs_strips_unknown(self):
        from evolving_agent.utils.llm_interface import AnthropicInterface
        iface = AnthropicInterface(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        result = iface._filter_kwargs({"top_p": 0.9, "bad_param": True, "top_k": 40})
        assert "bad_param" not in result
        assert "top_p" in result


class TestOpenRouterInterface:
    def test_instantiation(self):
        from evolving_agent.utils.llm_interface import OpenRouterInterface
        iface = OpenRouterInterface(api_key="or-test-key", model="anthropic/claude-3-haiku")
        assert iface.model == "anthropic/claude-3-haiku"
        assert "openrouter.ai" in iface.base_url

    def test_get_headers_has_authorization(self):
        from evolving_agent.utils.llm_interface import OpenRouterInterface
        iface = OpenRouterInterface(api_key="or-test-key", model="test")
        headers = iface._get_headers()
        assert headers["Authorization"] == "Bearer or-test-key"
        assert "Content-Type" in headers

    def test_prepare_payload_structure(self):
        from evolving_agent.utils.llm_interface import OpenRouterInterface
        iface = OpenRouterInterface(api_key="or-test-key", model="test-model")
        payload = iface._prepare_payload(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.5,
            max_tokens=128,
        )
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 128
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]

    def test_filter_kwargs_strips_invalid(self):
        from evolving_agent.utils.llm_interface import OpenRouterInterface
        iface = OpenRouterInterface(api_key="or-test-key", model="test")
        result = iface._filter_kwargs({"top_p": 0.9, "invalid": "x"})
        assert "invalid" not in result


class TestZAIInterface:
    def test_instantiation(self):
        from evolving_agent.utils.llm_interface import ZAIInterface
        iface = ZAIInterface(api_key="zai-test-key", model="glm-4.7")
        assert iface.model == "glm-4.7"
        assert "z.ai" in iface.base_url

    def test_get_headers_has_authorization(self):
        from evolving_agent.utils.llm_interface import ZAIInterface
        iface = ZAIInterface(api_key="zai-test-key", model="glm-4.7")
        headers = iface._get_headers()
        assert headers["Authorization"] == "Bearer zai-test-key"


class TestLLMManager:
    def test_instantiation_does_not_crash(self):
        from evolving_agent.utils.llm_interface import LLMManager
        manager = LLMManager()
        assert isinstance(manager.interfaces, dict)
        assert isinstance(manager.provider_priority, list)
        assert manager._initialized is False

    def test_provider_priority_starts_with_anthropic(self):
        from evolving_agent.utils.llm_interface import LLMManager
        manager = LLMManager()
        assert manager.provider_priority[0] == "anthropic"

    def test_ensure_initialized_sets_flag(self):
        from evolving_agent.utils.llm_interface import LLMManager
        with patch.object(LLMManager, "_initialize_interfaces", return_value=None):
            manager = LLMManager()
            manager._ensure_initialized()
            assert manager._initialized is True

    def test_ensure_initialized_is_idempotent(self):
        from evolving_agent.utils.llm_interface import LLMManager
        with patch.object(LLMManager, "_initialize_interfaces", return_value=None) as mock_init:
            manager = LLMManager()
            manager._ensure_initialized()
            manager._ensure_initialized()
            mock_init.assert_called_once()

    def test_initialize_provider_registers_interface(self):
        from evolving_agent.utils.llm_interface import LLMManager, OpenRouterInterface
        manager = LLMManager()
        manager._initialize_provider(
            "openrouter", OpenRouterInterface, "test-key", "test-model"
        )
        assert "openrouter" in manager.interfaces
        assert isinstance(manager.interfaces["openrouter"], OpenRouterInterface)

    def test_initialize_provider_handles_exception_gracefully(self):
        from evolving_agent.utils.llm_interface import LLMManager

        class BrokenInterface:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("Cannot init")

        manager = LLMManager()
        manager._initialize_provider("broken", BrokenInterface, "key", "model")
        assert "broken" not in manager.interfaces
