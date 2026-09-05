"""Credential-free shared provider selection; all hosts/models are synthetic."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from evolving_agent.integrations.provider_config import resolve_provider
from evolving_agent.utils.config import Config


@pytest.mark.parametrize(
    "provider,model,base",
    [
        ("openai", "openai-specific", "https://api.openai.com/v1"),
        ("zai", "zai-specific", "https://api.z.ai/api/coding/paas/v4"),
        ("anthropic", "selected-default", "https://api.anthropic.com/v1"),
        ("openrouter", "selected-default", "https://openrouter.ai/api/v1"),
    ],
)
def test_selected_provider_only_without_credentials(provider, model, base):
    class SelectedOnly:
        default_llm_provider = provider
        default_model_override = ""
        default_model = "selected-default"

        def __getattr__(self, name):
            allowed = {
                "openai": {"openai_model": "openai-specific", "openai_base_url": ""},
                "zai": {
                    "zai_model": "zai-specific",
                    "zai_base_url": "https://api.z.ai/api/coding/paas/v4",
                },
            }.get(provider, {})
            if name in allowed:
                return allowed[name]
            raise AssertionError(f"Unrelated configuration accessed: {name}")

    selected = resolve_provider(SelectedOnly())
    assert (selected.provider, selected.model, selected.base_url) == (
        provider,
        model,
        base,
    )
    assert selected.endpoint == base + (
        "/messages" if provider == "anthropic" else "/chat/completions"
    )
    with pytest.raises(FrozenInstanceError):
        selected.model = "mutated"


@pytest.mark.parametrize("provider", ["openai", "zai", "anthropic", "openrouter"])
def test_explicit_default_model_wins_consistently_with_real_config(
    monkeypatch, provider
):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", provider)
    monkeypatch.setenv("DEFAULT_MODEL", "explicit-selected-model")
    monkeypatch.setenv("OPENAI_MODEL", "unused-openai-model")
    monkeypatch.setenv("ZAI_MODEL", "unused-zai-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test")
    monkeypatch.setenv("ZAI_BASE_URL", "https://example.test/v4")
    config = Config.__new__(Config)  # Do not load any developer .env file.
    assert resolve_provider(config).model == "explicit-selected-model"
    assert config.selected_model == "explicit-selected-model"


@pytest.mark.parametrize(
    "provider,expected", [("openai", "openai-specific"), ("zai", "zai-specific")]
)
def test_absent_default_model_does_not_override_provider_specific_setting(
    monkeypatch, provider, expected
):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", provider)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "openai-specific")
    monkeypatch.setenv("ZAI_MODEL", "zai-specific")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setenv("ZAI_BASE_URL", "https://example.test/v4")
    config = Config.__new__(Config)
    assert (
        config.default_model == "glm-5.1"
    )  # Legacy property is not an explicit override.
    assert config.selected_model == expected


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("", "https://api.openai.com/v1"),
        ("https://example.test", "https://example.test/v1"),
        ("https://example.test/", "https://example.test/v1"),
        ("https://example.test/v1/", "https://example.test/v1"),
        ("https://example.test/v4", "https://example.test/v4"),
        ("HTTPS://EXAMPLE.TEST:443/v1/", "https://example.test/v1"),
        ("https://example.test/gateway/model", "https://example.test/gateway/model"),
    ],
)
def test_openai_normalizes_only_bare_host(configured, expected):
    selected = resolve_provider(
        SimpleNamespace(
            default_llm_provider="openai",
            openai_model="test-model",
            openai_base_url=configured,
        )
    )
    assert selected.base_url == expected
    assert selected.endpoint == expected + "/chat/completions"


@pytest.mark.parametrize(
    "base",
    [
        "http://example.test",
        "https://user:secret@example.test",
        "https://example.test:444",
        "https://example.test?token=secret",
        "https://example.test#fragment",
        "https://example.test?",
        "https://example.test#",
        "https://",
        "https://[",
        "https://example.test\\secret",
        "https://example.test/\n",
        "https:// example.test",
    ],
)
def test_invalid_bases_fail_without_echoing_values(base):
    config = SimpleNamespace(
        default_llm_provider="openai", openai_model="test-model", openai_base_url=base
    )
    with pytest.raises(RuntimeError, match="configured HTTPS") as caught:
        resolve_provider(config)
    assert base not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_unknown_provider_has_no_fallback():
    with pytest.raises(RuntimeError, match="Unsupported selected provider"):
        resolve_provider(
            SimpleNamespace(
                default_llm_provider="unknown", openai_api_key="must-not-use"
            )
        )
