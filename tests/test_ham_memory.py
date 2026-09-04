"""Contract tests for Katbot's transport-neutral HAM REST adapter."""

import asyncio
import json
import copy
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from evolving_agent.integrations.ham_memory import HAMMemoryClient, HAMMemoryError
from evolving_agent.core.memory import LongTermMemory
from evolving_agent.core.tools import make_search_memory_tool


IDENTITY = {
    "agent_id": "katbot-evolving-ai",
    "role": "agent",
    "scope_boundary": {
        "mode": "credential_allowlist",
        "allowed_scopes": ["project:evolving-ai"],
    },
}
PROJECTS = [
    {
        "slug": "evolving-ai",
        "scope": "project:evolving-ai",
        "repo": "DavinciDreams/evolving-ai",
    }
]


class _KeepAliveHAMHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps(
            [
                {
                    "id": 71,
                    "content": "synthetic remembered item",
                    "score": 0.9,
                    "timestamp": "2026-08-31T00:00:00Z",
                    "metadata": {"type": "fact"},
                }
            ]
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def _client(
    handler, *, identity=None, projects=None, preflight=True
) -> HAMMemoryClient:
    def routed(request):
        if preflight and request.url.path == "/whoami":
            return httpx.Response(
                200, json=identity if identity is not None else IDENTITY
            )
        if preflight and request.url.path == "/projects":
            return httpx.Response(
                200, json=projects if projects is not None else PROJECTS
            )
        return handler(request)

    return HAMMemoryClient(
        base_url="https://ham.invalid",
        api_key="test-ham-credential",
        project="evolving-ai",
        scope="project:evolving-ai",
        repo="DavinciDreams/evolving-ai",
        expected_agent_id="katbot-evolving-ai",
        transport=httpx.MockTransport(routed),
    )


@pytest.mark.asyncio
async def test_registered_memory_tool_reuses_ham_client_on_owning_event_loop():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _KeepAliveHAMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = HAMMemoryClient(
        base_url="https://ham.invalid",
        api_key="synthetic-test-only",
        project="evolving-ai",
        scope="project:evolving-ai",
        repo="DavinciDreams/evolving-ai",
        expected_agent_id="katbot-evolving-ai",
        timeout=2,
    )
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{server.server_port}",
        timeout=2,
        trust_env=False,
    )
    memory = LongTermMemory()
    memory.backend = "ham"
    memory.initialized = True
    memory.ham_client = client
    try:
        assert await client.search("warm the real connection pool", top_k=1)
        tool = make_search_memory_tool(memory)
        payload = json.loads(
            await asyncio.to_thread(
                tool.handler, query="synthetic remembered item", limit=1
            )
        )
        assert "error" not in payload
        assert payload["results"][0]["content"] == "synthetic remembered item"
    finally:
        await client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.asyncio
async def test_initialize_validates_project_scope_and_repository():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer test-ham-credential"
        if request.url.path == "/whoami":
            return httpx.Response(200, json=IDENTITY)
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

    client = _client(handler, preflight=False)
    try:
        await client.initialize()
    finally:
        await client.close()
    assert calls == ["/whoami", "/projects"]


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

    client = _client(handler, preflight=False)
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


@pytest.mark.parametrize(
    "identity",
    [
        {**IDENTITY, "agent_id": "human-user"},
        {**IDENTITY, "role": "admin"},
        {
            **IDENTITY,
            "scope_boundary": {"mode": "tenant_unrestricted", "allowed_scopes": None},
        },
        {
            **IDENTITY,
            "scope_boundary": {
                "mode": "credential_allowlist",
                "allowed_scopes": ["project:evolving-ai", "shared"],
            },
        },
        {
            **IDENTITY,
            "scope_boundary": {
                "mode": "credential_allowlist",
                "allowed_scopes": ["project:other"],
            },
        },
    ],
)
@pytest.mark.asyncio
async def test_preflight_rejects_wrong_or_broad_credential_before_any_write(identity):
    def no_mutations(request):
        pytest.fail("No mutation is permitted before identity preflight passes")

    client = _client(no_mutations, identity=identity)
    try:
        with pytest.raises(HAMMemoryError):
            await client.add(
                content="safe",
                source_id="1",
                timestamp="2026-08-30T00:00:00Z",
                memory_type="note",
                metadata={},
            )
    finally:
        await client.close()


@pytest.mark.parametrize(
    "projects",
    [
        [],
        [{**PROJECTS[0], "scope": "shared"}],
        [{**PROJECTS[0], "repo": "wrong/repo"}],
    ],
)
@pytest.mark.asyncio
async def test_project_preflight_fails_closed(projects):
    client = _client(lambda request: pytest.fail("no write"), projects=projects)
    try:
        with pytest.raises(HAMMemoryError):
            await client.initialize()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_reserved_provenance_is_stripped_and_long_keys_fit_protocol():
    payloads = []

    def handler(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        assert not {"agent_id", "actor_type", "credential_id", "run_id"} & set(
            payload["metadata"]
        )
        assert len(payload["idempotency_key"]) <= 200
        assert all(len(cue) <= 200 for cue in payload.get("cues", []))
        assert payload["metadata"]["source_memory_id"] == "x" * 250
        return httpx.Response(
            200, json={"id": 8, "metadata": {"agent_id": "katbot-evolving-ai"}}
        )

    client = _client(handler)
    metadata = {
        "agent_id": "spoof",
        "actor_type": "human",
        "credential_id": "spoof",
        "run_id": "spoof",
        "safe": True,
    }
    original = copy.deepcopy(metadata)
    try:
        for _ in range(2):
            await client.add(
                content="safe",
                source_id="x" * 250,
                timestamp="2026-08-30T00:00:00Z",
                memory_type="note",
                metadata=metadata,
            )
        await client.supersede(
            7,
            expected_version=1,
            content="safe",
            source_id="x" * 250,
            timestamp="2026-08-30T00:00:00Z",
            memory_type="note",
            metadata=metadata,
        )
    finally:
        await client.close()
    assert payloads[0]["idempotency_key"] == payloads[1]["idempotency_key"]
    assert payloads[2]["expected_version"] == 1
    assert metadata == original


@pytest.mark.parametrize(
    "url",
    [
        "http://ham.example",
        "https://user:password@ham.example",
        "https://ham.example?token=bad",
        "https://ham.example#bad",
    ],
)
def test_credential_transport_rejects_unsafe_urls(url):
    with pytest.raises(HAMMemoryError, match="HTTPS"):
        HAMMemoryClient(
            base_url=url,
            api_key="fake",
            project="evolving-ai",
            scope="project:evolving-ai",
            repo="repo",
            expected_agent_id="katbot-evolving-ai",
        )


@pytest.mark.parametrize("operation", ["search", "recent", "get", "stats"])
@pytest.mark.asyncio
async def test_malformed_read_responses_are_errors_not_empty_memory(operation):
    malformed = {} if operation in {"search", "recent"} else []
    client = _client(lambda request: httpx.Response(200, json=malformed))
    try:
        with pytest.raises(HAMMemoryError, match="malformed"):
            if operation == "search":
                await client.search("query", top_k=5)
            elif operation == "recent":
                await client.recent(limit=5)
            elif operation == "get":
                await client.get(1)
            else:
                await client.stats()
    finally:
        await client.close()
