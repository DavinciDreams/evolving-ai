"""
Tests for web search integration.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from evolving_agent.integrations.web_search import WebSearchIntegration


async def test_web_search_initialization():
    """Test web search initialization."""
    ws = WebSearchIntegration(
        tavily_api_key="test-key",
        default_provider="duckduckgo",
        max_results=3,
    )

    await ws.initialize()

    assert ws.tavily_api_key == "test-key"
    assert ws.default_provider == "duckduckgo"
    assert ws.max_results == 3


async def test_web_search_cache():
    """Test that search results are cached."""
    ws = WebSearchIntegration(default_provider="duckduckgo", max_results=3)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "AbstractText": "Python is a programming language",
        "Heading": "Python",
        "AbstractURL": "https://python.org",
        "RelatedTopics": [],
    }

    with patch.object(ws.http_client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # First call - should hit the API
        result1 = await ws.search("Python programming", include_content=False)
        assert mock_get.call_count >= 1

        first_count = mock_get.call_count

        # Second call - should return cached results
        result2 = await ws.search("Python programming", include_content=False)
        assert mock_get.call_count == first_count  # No additional API calls

    assert result1["query"] == "Python programming"
    assert result2["query"] == "Python programming"

    await ws.close()


async def test_web_search_tavily():
    """Test Tavily search provider."""
    ws = WebSearchIntegration(
        tavily_api_key="test-key",
        default_provider="tavily",
        max_results=3,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com",
                "content": "Test content about AI",
                "score": 0.95,
            }
        ],
        "answer": "AI is a broad field.",
    }

    with patch.object(ws.http_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await ws.search("AI developments", include_content=False)

    assert result["provider"] == "tavily"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Test Result"
    assert result["results"][0]["source"] == "tavily"

    await ws.close()


async def test_web_search_fallback():
    """Test that search falls back to DuckDuckGo when primary provider fails."""
    ws = WebSearchIntegration(
        tavily_api_key="bad-key",
        default_provider="tavily",
        max_results=3,
    )

    # Tavily fails
    mock_tavily_response = MagicMock()
    mock_tavily_response.raise_for_status.side_effect = Exception("401 Unauthorized")

    # DuckDuckGo succeeds
    mock_ddg_response = MagicMock()
    mock_ddg_response.status_code = 200
    mock_ddg_response.raise_for_status = MagicMock()
    mock_ddg_response.json.return_value = {
        "AbstractText": "Fallback result",
        "Heading": "Fallback",
        "AbstractURL": "https://example.com",
        "RelatedTopics": [],
    }

    with patch.object(ws.http_client, 'post', new_callable=AsyncMock) as mock_post, \
         patch.object(ws.http_client, 'get', new_callable=AsyncMock) as mock_get:
        mock_post.return_value = mock_tavily_response
        mock_get.return_value = mock_ddg_response

        result = await ws.search("test query", include_content=False)

    assert result["provider"] == "duckduckgo"
    assert len(result["results"]) > 0

    await ws.close()


async def test_search_and_summarize():
    """Test search_and_summarize method."""
    ws = WebSearchIntegration(default_provider="duckduckgo", max_results=3)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "AbstractText": "Python best practices include writing clean code.",
        "Heading": "Python Best Practices",
        "AbstractURL": "https://python.org/practices",
        "RelatedTopics": [
            {"Text": "Use type hints for better code quality", "FirstURL": "https://example.com/1"},
            {"Text": "Write unit tests for all functions", "FirstURL": "https://example.com/2"},
        ],
    }

    with patch.object(ws.http_client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await ws.search_and_summarize("Python best practices", max_results=3)

    assert result["query"] == "Python best practices"
    assert len(result["sources"]) > 0

    await ws.close()


async def test_clear_cache():
    """Test cache clearing."""
    ws = WebSearchIntegration()
    ws._cache = {"key1": {"timestamp": 0, "results": {}}}

    ws.clear_cache()
    assert len(ws._cache) == 0

    await ws.close()
