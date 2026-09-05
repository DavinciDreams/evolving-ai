"""Learning provider budgets and exact HTTP shapes, without real credentials."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from evolving_agent.integrations.bounded_llm import BoundedTextProvider
from evolving_agent.integrations.provider_config import resolve_provider


def cfg(provider="openai", **changes):
    fields = {"default_llm_provider": provider}
    if provider == "openai":
        fields.update(
            openai_api_key="synthetic-key",
            openai_base_url="",
            openai_model="gpt-4.1-mini",
        )
    elif provider == "zai":
        fields.update(
            zai_api_key="synthetic-key",
            zai_base_url="https://api.z.ai/api/coding/paas/v4",
            zai_model="glm-5.1",
        )
    elif provider == "openrouter":
        fields.update(openrouter_api_key="synthetic-key", default_model="vendor/model")
    elif provider == "anthropic":
        fields.update(anthropic_api_key="synthetic-key", default_model="test-claude")
    return SimpleNamespace(**{**fields, **changes})


@pytest.mark.parametrize("provider", ["openai", "zai", "openrouter", "anthropic"])
@pytest.mark.asyncio
async def test_only_selected_config_and_exact_provider_request(provider):
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        selected = resolve_provider(cfg(provider))
        assert body["model"] == selected.model
        assert str(request.url) == selected.endpoint
        assert "tools" not in body and "tool_choice" not in body
        assert body["messages"][-1]["content"] == "question"
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "synthetic-key"
            assert body["max_tokens"] == 512 and body["system"] == "system"
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "thinking", "thinking": "private"},
                        {"type": "text", "text": "answer"},
                    ]
                },
            )
        assert request.headers["authorization"] == "Bearer synthetic-key"
        if provider == "openai":
            assert body["max_completion_tokens"] == 512 and "max_tokens" not in body
            assert body["store"] is False
        else:
            assert body["max_tokens"] == 512 and "max_completion_tokens" not in body
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    service = BoundedTextProvider(cfg(provider), transport=httpx.MockTransport(handler))
    assert (
        await service.generate_response(
            prompt="question",
            system_prompt="system",
            max_tokens=512,
            tools=[{"ignored": True}],
        )
        == "answer"
    )
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_openai_compatible_endpoint_retains_legacy_shape():
    def handler(request):
        assert str(request.url) == "https://example.test/v1/chat/completions"
        assert json.loads(request.content)["max_tokens"] == 900
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    provider = BoundedTextProvider(
        cfg(openai_base_url="https://example.test/v1/"),
        transport=httpx.MockTransport(handler),
    )
    assert await provider.generate_response(prompt="test") == "answer"


@pytest.mark.parametrize(
    "base,expected",
    [
        ("https://example.test", "https://example.test/v1/chat/completions"),
        (
            "https://example.test/proxy/v4",
            "https://example.test/proxy/v4/chat/completions",
        ),
    ],
)
@pytest.mark.asyncio
async def test_shared_model_override_and_endpoint_reach_actual_transport(
    base, expected
):
    def handler(request):
        assert str(request.url) == expected
        assert json.loads(request.content)["model"] == "explicit-shared-model"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    provider = BoundedTextProvider(
        cfg(openai_base_url=base, default_model_override="explicit-shared-model"),
        transport=httpx.MockTransport(handler),
    )
    assert await provider.generate_response(prompt="test") == "answer"


@pytest.mark.asyncio
async def test_official_openai_default_port_is_canonical_for_token_shape():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 900
        assert body["store"] is False
        assert "max_tokens" not in body
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    provider = BoundedTextProvider(
        cfg(openai_base_url="https://API.OPENAI.COM:443/v1/"),
        transport=httpx.MockTransport(handler),
    )
    assert await provider.generate_response(prompt="test") == "answer"


@pytest.mark.parametrize(
    "changes",
    [
        {"timeout": float("nan")},
        {"timeout": float("inf")},
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": 121},
        {"timeout": True},
        {"max_tokens": True},
        {"max_tokens": 4001},
        {"max_tokens": 0},
        {"temperature": float("nan")},
        {"temperature": -1},
        {"temperature": 3},
        {"prompt": " "},
        {"prompt": []},
        {"system_prompt": {}},
        {"prompt": "x" * 72001},
    ],
)
@pytest.mark.asyncio
async def test_invalid_limits_fail_before_network(changes):
    provider = BoundedTextProvider(
        cfg(), transport=httpx.MockTransport(lambda _: pytest.fail("network"))
    )
    with pytest.raises(ValueError):
        await provider.generate_response(**{"prompt": "test", **changes})


@pytest.mark.parametrize(
    "base",
    [
        "http://example.test",
        "https://user:pass@example.test",
        "https://example.test?secret=value",
        "https://example.test#fragment",
        "https://",
        "https://[",
        "https://example.test:444",
    ],
)
@pytest.mark.asyncio
async def test_malformed_endpoint_rejected_without_network(base):
    provider = BoundedTextProvider(
        cfg(openai_base_url=base),
        transport=httpx.MockTransport(lambda _: pytest.fail("network")),
    )
    with pytest.raises(RuntimeError, match="configured HTTPS"):
        await provider.generate_response(prompt="test")


@pytest.mark.parametrize("status", [301, 302, 401, 429, 500])
@pytest.mark.asyncio
async def test_no_retry_or_redirect_and_sanitized_error(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="opaque-secret-response",
            headers={"location": "https://other.invalid/secret"},
        )

    provider = BoundedTextProvider(cfg(), transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError) as exc:
        await provider.generate_response(prompt="test")
    assert str(exc.value) == "Budgeted learning provider failed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_total_timeout_is_bounded():
    async def handler(request):
        await asyncio.sleep(0.1)
        pytest.fail("timeout failed")

    provider = BoundedTextProvider(cfg(), transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="provider failed"):
        await provider.generate_response(prompt="test", timeout=0.01)


@pytest.mark.asyncio
async def test_cancellation_is_not_wrapped():
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    provider = BoundedTextProvider(cfg(), transport=httpx.MockTransport(handler))
    task = asyncio.create_task(provider.generate_response(prompt="test"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(
    "content",
    [
        b"x" * 128001,
        b"not-json",
        b'{"choices":[]}',
        b'{"choices":[{"message":{"content":null}}]}',
    ],
    ids=["oversized", "invalid-json", "empty-choices", "null-text"],
)
@pytest.mark.asyncio
async def test_bounded_or_malformed_response(content):
    provider = BoundedTextProvider(
        cfg(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content)),
    )
    with pytest.raises(RuntimeError, match="provider failed"):
        await provider.generate_response(prompt="test")
