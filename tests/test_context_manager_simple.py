"""
Tests for context manager basic functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from evolving_agent.core.context_manager import ContextManager, ContextQuery
from evolving_agent.core.memory import LongTermMemory, MemoryEntry


async def test_get_relevant_context_basic():
    """Test basic context retrieval returns expected structure."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.search_memories = AsyncMock(return_value=[])
    mock_memory.get_memory_stats = AsyncMock(return_value={"total_memories": 0})

    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
        mock_llm.generate_response = AsyncMock(return_value="test search query")

        context = await context_manager.get_relevant_context(
            query="How to optimize Python functions?"
        )

    assert isinstance(context, dict)
    assert "system_state" in context


async def test_context_query_generation():
    """Test that context queries are generated for all context types."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
        mock_llm.generate_response = AsyncMock(return_value="search query for context")

        queries = await context_manager._generate_context_queries(
            "How to handle errors in Python?"
        )

    # Should generate queries for all default context types
    assert len(queries) > 0
    for q in queries:
        assert isinstance(q, ContextQuery)
        assert q.query
        assert q.context_type
        assert 0.0 <= q.priority <= 1.0


async def test_context_query_generation_with_llm_failure():
    """Test that context queries fall back to main query when LLM fails."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
        mock_llm.generate_response = AsyncMock(side_effect=Exception("LLM unavailable"))

        queries = await context_manager._generate_context_queries(
            "How to handle errors in Python?"
        )

    # Should still get fallback queries
    assert len(queries) > 0
    for q in queries:
        assert q.metadata.get("fallback") is True


def test_context_priority_calculation():
    """Test priority calculation for different context types."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    # similar_tasks should have high priority
    priority = context_manager._calculate_context_priority("similar_tasks", "test query")
    assert priority >= 0.8

    # optimization_insights should have lower base priority
    priority = context_manager._calculate_context_priority("optimization_insights", "test query")
    assert priority <= 0.8

    # error-related query should boost error_experiences priority
    priority = context_manager._calculate_context_priority(
        "error_experiences", "how to fix this error"
    )
    assert priority >= 0.9


async def test_retrieve_context_memories():
    """Test memory retrieval for a context query."""
    mock_memory = MagicMock(spec=LongTermMemory)

    test_memory = MemoryEntry(
        content="Python optimization tips",
        memory_type="interaction",
        timestamp=datetime.now(),
    )
    mock_memory.search_memories = AsyncMock(return_value=[(test_memory, 0.85)])

    context_manager = ContextManager(mock_memory)

    ctx_query = ContextQuery(
        query="Python optimization",
        context_type="optimization_insights",
        priority=0.8,
        timestamp=datetime.now(),
        metadata={},
    )

    results = await context_manager._retrieve_context_memories(ctx_query, 0.6, 5)

    assert len(results) > 0
    memory, score = results[0]
    assert "optimization" in memory.content.lower()


async def test_store_interaction_context():
    """Test storing interaction context."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.add_memory = AsyncMock()

    context_manager = ContextManager(mock_memory)

    await context_manager.store_interaction_context(
        query="What is Python?",
        response="Python is a programming language.",
        context_used={"similar_tasks": []},
    )

    mock_memory.add_memory.assert_called_once()
    stored_entry = mock_memory.add_memory.call_args[0][0]
    assert "Python" in stored_entry.content
    assert stored_entry.memory_type == "interaction"


def test_clear_cache():
    """Test cache clearing."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    # Add some data to caches
    context_manager.context_cache["key1"] = ([], datetime.now())
    context_manager.degraded_cache["key2"] = {"test": True}

    context_manager.clear_cache()

    assert len(context_manager.context_cache) == 0
    assert len(context_manager.degraded_cache) == 0


def test_get_status():
    """Test status reporting."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    status = context_manager.get_status()

    assert "degraded_mode" in status
    assert "cache_size" in status
    assert status["degraded_mode"] is False
