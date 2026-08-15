"""Contract tests for Katbot's transport-neutral HAM REST adapter."""

import json

import httpx
import pytest

from evolving_agent.integrations.ham_memory import HAMMemoryClient, HAMMemoryError


def _client(handler) -> HAMMemoryClient:
    return HAMMemoryClient(
        base_url="https://ham.invalid",
        api_key="test-ham-credential",
        project="evolving-ai",
        scope="project:evolving-ai",
        repo="DavinciDreams/evolving-ai",
        expected_agent_id="katbot-evolving-ai",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_initialize_validates_project_scope_and_repository():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-ham-credential"
        return httpx.Response(
            200,
            json=[
                {
                    "slug": "evolving-ai",
                    "scope": "project:evolving-ai",
                    "repo": "DavinciDreams/evolving-ai",
                }
            ],
        )

    client = _client(handler)
    try:
        await client.initialize()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_add_never_sends_agent_identity_and_checks_server_attribution():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ingest"
        payload = json.loads(request.content)
        assert "agent_id" not in payload
        assert "agent_id" not in payload["metadata"]
        return httpx.Response(200, json={"id": 41, "agent_id": "katbot-evolving-ai"})

    client = _client(handler)
    try:
        memory_id = await client.add(
            content="safe project memory",
            source_id="source-1",
            timestamp="2026-08-15T00:00:00Z",
            memory_type="fact",
            metadata={"audience": "project"},
        )
    finally:
        await client.close()
    assert memory_id == 41


@pytest.mark.asyncio
async def test_idempotent_add_fetches_stored_attribution_before_accepting_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/ingest":
            return httpx.Response(200, json={"id": 42, "deduplicated": True})
        if request.url.path == "/memories/42":
            return httpx.Response(
                200,
                json={
                    "id": 42,
                    "content": "safe project memory",
                    "metadata": {"agent_id": "katbot-evolving-ai"},
                },
            )
        raise AssertionError(f"unexpected path {request.url.path}")

    client = _client(handler)
    try:
        memory_id = await client.add(
            content="safe project memory",
            source_id="source-2",
            timestamp="2026-08-15T00:00:00Z",
            memory_type="fact",
            metadata={},
        )
    finally:
        await client.close()
    assert memory_id == 42
    assert calls == ["/ingest", "/memories/42"]


@pytest.mark.asyncio
async def test_identity_mismatch_fails_closed():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 43, "agent_id": "different-agent"})

    client = _client(handler)
    try:
        with pytest.raises(HAMMemoryError, match="identity mismatch"):
            await client.add(
                content="safe project memory",
                source_id="source-3",
                timestamp="2026-08-15T00:00:00Z",
                memory_type="fact",
                metadata={},
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_remote_error_body_is_not_reflected():
    marker = "sensitive-remote-detail"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": marker})

    client = _client(handler)
    try:
        with pytest.raises(HAMMemoryError) as raised:
            await client.initialize()
    finally:
        await client.close()
    assert marker not in str(raised.value)


@pytest.mark.asyncio
async def test_get_returns_none_for_not_found():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = _client(handler)
    try:
        assert await client.get(404) is None
    finally:
        await client.close()
