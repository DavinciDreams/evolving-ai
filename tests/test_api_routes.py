"""FastAPI route tests using TestClient with mocked agent dependency."""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import evolving_agent.utils.api_server as api_server_module
from evolving_agent.utils.api_server import app, get_agent
from evolving_agent.core.memory import MemoryEntry


@pytest.fixture(scope="module")
def client():
    """TestClient with lifespan suppressed and agent dependency mocked."""
    mock_agent = MagicMock()
    mock_agent.initialized = True
    mock_agent.session_id = "test-session-id"
    mock_agent.interaction_count = 0
    mock_agent.last_evaluation_score = 0.9
    mock_agent.memory = MagicMock()
    mock_agent.memory.get_memory_stats = AsyncMock(return_value={"total_memories": 0})
    mock_agent.memory.list_recent_memories = AsyncMock(return_value=[])
    mock_agent.memory.page_recent_memories = AsyncMock(return_value=([], None))
    mock_agent.memory.search_memories = AsyncMock(return_value=[])
    mock_agent.knowledge_base = MagicMock()
    mock_agent.knowledge_base.knowledge = {}

    @asynccontextmanager
    async def noop_lifespan(application):
        api_server_module.agent = mock_agent
        api_server_module.github_modifier = None
        api_server_module.discord_integration = None
        yield
        api_server_module.agent = None

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_agent] = lambda: mock_agent

    # Auth is disabled by tests/conftest.py for compatibility tests below.
    # A separate TestApiKeyAuth class tests the enforcement path with a key configured.
    with patch.dict("os.environ", {"API_KEY": ""}, clear=False):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status_field(self, client):
        data = client.get("/health").json()
        assert "status" in data

    def test_health_reports_healthy(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_reports_agent_initialized(self, client):
        data = client.get("/health").json()
        assert data.get("agent_initialized") is True


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        assert client.get("/").status_code == 200

    def test_root_has_message(self, client):
        data = client.get("/").json()
        assert "message" in data

    def test_root_has_docs_link(self, client):
        data = client.get("/").json()
        assert "docs" in data


class TestStatusEndpoint:
    def test_status_returns_200_with_mock(self, client):
        assert client.get("/status").status_code == 200

    def test_status_has_is_initialized(self, client):
        data = client.get("/status").json()
        assert "is_initialized" in data

    def test_status_has_total_interactions(self, client):
        data = client.get("/status").json()
        assert "total_interactions" in data

    def test_status_has_session_id(self, client):
        data = client.get("/status").json()
        assert "session_id" in data


class TestChatEndpoint:
    def test_chat_empty_body_is_422(self, client):
        assert client.post("/chat", json={}).status_code == 422

    def test_chat_empty_query_is_422(self, client):
        assert client.post("/chat", json={"query": ""}).status_code == 422

    def test_chat_oversized_query_is_422(self, client):
        response = client.post("/chat", json={"query": "x" * 10001})
        assert response.status_code == 422

    def test_chat_valid_query_returns_200(self, client):
        with patch.object(
            api_server_module.agent,
            "run",
            new_callable=AsyncMock,
            return_value="Mock response",
        ):
            response = client.post("/chat", json={"query": "Hello!"})
        assert response.status_code == 200

    def test_chat_response_has_required_fields(self, client):
        with patch.object(
            api_server_module.agent,
            "run",
            new_callable=AsyncMock,
            return_value="Test response",
        ):
            data = client.post("/chat", json={"query": "Test"}).json()
        for field in ("response", "query_id", "timestamp", "memory_stored", "knowledge_updated"):
            assert field in data, f"Missing field: {field}"

    def test_chat_response_text_matches(self, client):
        with patch.object(
            api_server_module.agent,
            "run",
            new_callable=AsyncMock,
            return_value="Expected answer",
        ):
            data = client.post("/chat", json={"query": "Hi"}).json()
        assert data["response"] == "Expected answer"

    def test_chat_waits_for_storage_before_returning(self, client):
        with patch.object(
            api_server_module.agent,
            "run",
            new_callable=AsyncMock,
            return_value="Stored answer",
        ) as run_mock:
            response = client.post(
                "/chat",
                json={"query": "Remember this", "conversation_id": "conv-1"},
            )

        assert response.status_code == 200
        run_mock.assert_awaited_once()
        assert run_mock.call_args.kwargs["wait_for_storage"] is True
        assert run_mock.call_args.kwargs["conversation_id"] == "conv-1"


class TestMemoriesEndpoint:
    def test_memories_returns_200(self, client):
        assert client.get("/memories").status_code == 200

    def test_memories_returns_list(self, client):
        assert isinstance(client.get("/memories").json(), list)

    def test_memories_accepts_limit_param(self, client):
        assert client.get("/memories?limit=5").status_code == 200

    def test_memories_accepts_offset_param(self, client):
        assert client.get("/memories?offset=0").status_code == 200


class TestKnowledgeEndpoint:
    def test_knowledge_returns_200(self, client):
        assert client.get("/knowledge").status_code == 200

    def test_knowledge_returns_list(self, client):
        assert isinstance(client.get("/knowledge").json(), list)


class TestGitHubStatusEndpoint:
    def test_github_status_returns_200(self, client):
        assert client.get("/github/status").status_code == 200

    def test_github_status_reports_not_connected_when_no_modifier(self, client):
        data = client.get("/github/status").json()
        assert data["github_connected"] is False


class TestOpenAICompatEndpoints:
    def test_v1_models_returns_200(self, client):
        assert client.get("/v1/models").status_code == 200

    def test_v1_completions_requires_messages(self, client):
        response = client.post("/v1/chat/completions", json={"model": "evolving-ai"})
        assert response.status_code == 422

    def test_v1_completions_with_user_message(self, client):
        with patch.object(
            api_server_module.agent,
            "run",
            new_callable=AsyncMock,
            return_value="OpenAI-compat response",
        ):
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "evolving-ai",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "OpenAI-compat response"


class TestApiKeyAuth:
    """Tests verifying that API key enforcement works when API_KEY env var is set."""

    def test_chat_blocked_without_key_when_api_key_configured(self, client):
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.post("/chat", json={"query": "Hello"})
            assert response.status_code == 401

    def test_chat_allowed_with_correct_key(self, client):
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            with patch.object(
                api_server_module.agent,
                "run",
                new_callable=AsyncMock,
                return_value="Authenticated response",
            ):
                response = client.post(
                    "/chat",
                    json={"query": "Hello"},
                    headers={"X-API-Key": "secret-key"},
                )
            assert response.status_code == 200

    def test_bearer_project_credential_is_supported(self, client):
        with patch.dict(
            "os.environ",
            {"PROJECT_API_KEY": "project-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get(
                "/status", headers={"Authorization": "Bearer project-key"}
            )
        assert response.status_code == 200

    def test_wrong_project_credential_is_rejected(self, client):
        with patch.dict(
            "os.environ",
            {"PROJECT_API_KEY": "project-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get(
                "/status", headers={"X-API-Key": "different-key"}
            )
        assert response.status_code == 401

    def test_health_accessible_without_key_even_when_configured(self, client):
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get("/health")
            assert response.status_code == 200

    def test_private_memory_blocked_without_key(self, client):
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get("/memories")
            assert response.status_code == 401

    def test_public_memory_route_remains_public_and_filters_private_rows(self, client):
        memory = api_server_module.agent.memory
        memory.page_recent_memories.return_value = (
            [
                MemoryEntry("published", metadata={"audience": "public"}),
                MemoryEntry(
                    "TELLUS_TOKEN=sk-" + "redacted-test-value-12345",
                    metadata={"audience": "public"},
                ),
                MemoryEntry("private", metadata={"audience": "project"}),
                MemoryEntry("legacy-default-private", metadata={}),
            ],
            None,
        )
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get("/public/memories")
            assert response.status_code == 200
            assert [row["content"] for row in response.json()] == ["published"]
            memory.search_memories.assert_not_awaited()
        memory.page_recent_memories.return_value = ([], None)

    def test_public_memory_offset_can_cross_storage_pages(self, client):
        memory = api_server_module.agent.memory
        first_page = [
            MemoryEntry(f"public-{index}", metadata={"audience": "public"})
            for index in range(100)
        ]
        memory.page_recent_memories.side_effect = [
            (first_page, "cursor-100"),
            ([MemoryEntry("public-100", metadata={"audience": "public"})], None),
        ]
        response = client.get("/public/memories?offset=100&limit=1")
        assert response.status_code == 200
        assert [row["content"] for row in response.json()] == ["public-100"]
        cursors = [
            item.kwargs["cursor"]
            for item in memory.page_recent_memories.await_args_list
        ]
        assert cursors[-2:] == [None, "cursor-100"]
        memory.page_recent_memories.side_effect = None
        memory.page_recent_memories.return_value = ([], None)

    def test_public_memory_search_pages_past_newer_private_rows(self, client):
        memory = api_server_module.agent.memory
        private_page = [
            MemoryEntry(f"private-{index}", metadata={"audience": "project"})
            for index in range(100)
        ]
        memory.page_recent_memories.side_effect = [
            (private_page, "cursor-private"),
            (
                [
                    MemoryEntry("older irrelevant", metadata={"audience": "public"}),
                    MemoryEntry("older needle", metadata={"audience": "public"}),
                ],
                None,
            ),
        ]
        response = client.get("/public/memories?search=needle&limit=1")
        assert response.status_code == 200
        assert [row["content"] for row in response.json()] == ["older needle"]
        memory.page_recent_memories.side_effect = None
        memory.page_recent_memories.return_value = ([], None)

    def test_missing_server_key_fails_closed(self, client):
        with patch.dict(
            "os.environ",
            {"API_KEY": "", "PROJECT_API_KEY": "", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get("/memories")
            assert response.status_code == 503

    @pytest.mark.parametrize("path", ["/knowledge", "/github/status", "/analysis-history"])
    def test_other_data_routes_are_private_by_default(self, client, path):
        with patch.dict(
            "os.environ",
            {"API_KEY": "secret-key", "API_AUTH_REQUIRED": "true"},
            clear=False,
        ):
            response = client.get(path)
        assert response.status_code == 401


def test_service_credentials_must_be_distinct():
    with patch.dict(
        "os.environ",
        {
            "HAM_API_KEY": "reused-service-key",
            "PROJECT_API_KEY": "reused-service-key",
            "GITHUB_TOKEN": "separate-github-key",
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="must be distinct"):
            api_server_module._validate_separate_service_credentials()
