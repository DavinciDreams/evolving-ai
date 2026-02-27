"""
Tests for the TPMJS API client.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from evolving_agent.integrations.tpmjs import TPMJSClient, BASE_URL


@pytest.fixture
def client():
    return TPMJSClient(api_key="tpmjs_sk_test_key")


@pytest.fixture
def unauthenticated_client():
    return TPMJSClient()


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

def test_headers_with_key(client):
    """Headers should include Authorization when API key is set."""
    headers = client._headers()
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer tpmjs_sk_test_key"


def test_headers_without_key(unauthenticated_client):
    """Headers should not include Authorization without API key."""
    headers = unauthenticated_client._headers()
    assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# search_tools
# ---------------------------------------------------------------------------

async def test_search_tools_success(client):
    """search_tools should return tool list on success."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "data": [
            {"name": "pdf-converter", "package": "@tpmjs/pdf", "description": "Convert PDFs"},
            {"name": "markdown-tool", "package": "@tpmjs/md", "description": "Markdown utils"},
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        results = await client.search_tools("pdf converter", limit=5)

    assert len(results) == 2
    assert results[0]["name"] == "pdf-converter"


async def test_search_tools_empty(client):
    """search_tools should return empty list when no results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"success": True, "data": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        results = await client.search_tools("nonexistent tool xyz123")

    assert results == []


async def test_search_tools_error(client):
    """search_tools should return empty list on error."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("Network error")):
        results = await client.search_tools("test")

    assert results == []


async def test_search_tools_limit_capped(client):
    """search_tools should cap limit at 20."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"success": True, "data": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
        await client.search_tools("test", limit=100)

    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["limit"] == 20


# ---------------------------------------------------------------------------
# execute_tool
# ---------------------------------------------------------------------------

async def test_execute_tool_success(client):
    """execute_tool should return tool output."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": {"output": "Hello, World!", "status": "success"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.execute_tool("@tpmjs/hello", "helloWorldTool", "Say hello")

    parsed = json.loads(result)
    assert parsed["output"] == "Hello, World!"


async def test_execute_tool_error(client):
    """execute_tool should return error JSON on failure."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await client.execute_tool("@tpmjs/broken", "tool", "test")

    parsed = json.loads(result)
    assert "error" in parsed


async def test_execute_tool_prompt_truncation(client):
    """execute_tool should truncate prompts over 2000 chars."""
    long_prompt = "x" * 3000
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"output": "ok"}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await client.execute_tool("@tpmjs/test", "tool", long_prompt)

    call_body = mock_post.call_args.kwargs["json"]
    assert len(call_body["prompt"]) == 2000


# ---------------------------------------------------------------------------
# create_tool
# ---------------------------------------------------------------------------

async def test_create_tool(client):
    """create_tool should return scaffold info."""
    result = await client.create_tool(
        name="my-converter",
        description="Converts things",
        category="utilities",
        code="export function convert() { return 'done'; }",
    )

    assert result["status"] == "scaffold_created"
    assert "@tpmjs/my-converter" in result["package"]["name"]
    assert result["package"]["tpmjs"]["category"] == "utilities"


# ---------------------------------------------------------------------------
# get_tool_details
# ---------------------------------------------------------------------------

async def test_get_tool_details_success(client):
    """get_tool_details should return tool info."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "name": "helloWorldTool",
            "description": "Says hello",
            "inputSchema": {"type": "object"},
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_tool_details("@tpmjs/hello", "helloWorldTool")

    assert result is not None
    assert result["name"] == "helloWorldTool"


async def test_get_tool_details_not_found(client):
    """get_tool_details should return None on 404."""
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=MagicMock(status_code=404)),
    ):
        result = await client.get_tool_details("@tpmjs/nonexistent", "nope")

    assert result is None


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

async def test_list_tools_success(client):
    """list_tools should return tool list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"name": "tool1"},
            {"name": "tool2"},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        results = await client.list_tools(category="utilities")

    assert len(results) == 2
