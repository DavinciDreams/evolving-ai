"""
Tests for the context manager's error recovery and degraded mode features.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from evolving_agent.core.context_manager import ContextManager, ContextQuery
from evolving_agent.core.memory import LongTermMemory, MemoryEntry


async def test_degraded_mode_activation():
    """Test that degraded mode activates after repeated memory failures."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.get_memory_stats = AsyncMock(return_value={"total_memories": 0})

    context_manager = ContextManager(mock_memory)
    assert context_manager.degraded_mode is False

    # Patch _retrieve_context_memories to raise (bypassing its internal try/except)
    # so _retrieve_context_memories_with_recovery can detect the failure
    with patch.object(context_manager, '_retrieve_context_memories', new_callable=AsyncMock) as mock_retrieve, \
         patch('evolving_agent.core.context_manager.error_recovery_manager') as mock_recovery:
        mock_retrieve.side_effect = Exception("DB unavailable")
        mock_recovery.set_degraded_mode = MagicMock()

        for _ in range(context_manager.memory_failure_threshold):
            await context_manager._retrieve_context_memories_with_recovery(
                ContextQuery(
                    query="test",
                    context_type="similar_tasks",
                    priority=0.8,
                    timestamp=datetime.now(),
                    metadata={},
                ),
                0.6, 5,
            )

    assert context_manager.degraded_mode is True


async def test_degraded_context_returns_minimal():
    """Test that degraded mode returns minimal context."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    context_manager.degraded_mode = True
    context = context_manager._get_degraded_context("test query")

    assert "system_state" in context
    assert context.get("degraded") is True


async def test_degraded_cache_stores_and_retrieves():
    """Test that degraded cache stores context for later retrieval."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    # Store context in degraded cache
    test_context = {"test_key": "test_value", "system_state": {}}
    context_manager._update_degraded_cache("Python optimization", test_context)

    # Enable degraded mode
    context_manager.degraded_mode = True

    # Should find the cached context for a similar query
    result = context_manager._get_degraded_context("Python optimization")
    assert result == test_context


async def test_degraded_cache_limit():
    """Test that degraded cache respects size limit."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    # Add more than 10 items
    for i in range(15):
        context_manager._update_degraded_cache(f"query_{i}", {"data": i})

    # Should keep only 10 items
    assert len(context_manager.degraded_cache) <= 10


async def test_recovery_from_degraded_mode():
    """Test disabling degraded mode."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.error_recovery_manager') as mock_recovery:
        mock_recovery.set_degraded_mode = MagicMock()

        context_manager.degraded_mode = True
        context_manager.memory_unavailable_count = 5

        context_manager._disable_degraded_mode()

    assert context_manager.degraded_mode is False
    assert context_manager.memory_unavailable_count == 0


async def test_check_memory_health_success():
    """Test memory health check when healthy."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.get_memory_stats = AsyncMock(return_value={"total_memories": 100})

    context_manager = ContextManager(mock_memory)
    healthy = await context_manager.check_memory_health()

    assert healthy is True


async def test_check_memory_health_failure():
    """Test memory health check when unhealthy."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.get_memory_stats = AsyncMock(side_effect=Exception("DB down"))

    context_manager = ContextManager(mock_memory)
    healthy = await context_manager.check_memory_health()

    assert healthy is False
    assert context_manager.memory_unavailable_count == 1


async def test_cache_warming():
    """Test cache warming functionality."""
    mock_memory = MagicMock(spec=LongTermMemory)
    mock_memory.search_memories = AsyncMock(return_value=[])
    mock_memory.get_memory_stats = AsyncMock(return_value={"total_memories": 0})

    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
        mock_llm.generate_response = AsyncMock(return_value="warmed query")

        await context_manager.warm_cache(["query 1", "query 2"])

    assert context_manager.last_cache_warm is not None


def test_enable_disable_cache_warming():
    """Test toggling cache warming."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    context_manager.enable_cache_warming(False)
    assert context_manager.cache_warming_enabled is False

    context_manager.enable_cache_warming(True)
    assert context_manager.cache_warming_enabled is True


async def test_filter_and_rank_memories():
    """Test memory filtering and ranking."""
    mock_memory = MagicMock(spec=LongTermMemory)
    context_manager = ContextManager(mock_memory)

    # Create memories with different timestamps
    old_memory = MemoryEntry(
        content="Old content",
        memory_type="test",
        timestamp=datetime.now() - timedelta(days=20),
    )
    recent_memory = MemoryEntry(
        content="Recent content",
        memory_type="test",
        timestamp=datetime.now() - timedelta(hours=1),
    )

    memories = [(old_memory, 0.8), (recent_memory, 0.8)]

    ctx_query = ContextQuery(
        query="test",
        context_type="similar_tasks",
        priority=0.9,
        timestamp=datetime.now(),
        metadata={},
    )

    ranked = context_manager._filter_and_rank_memories(memories, ctx_query, 2)

    # Recent memory should rank higher (same similarity, better recency)
    assert len(ranked) == 2
    assert ranked[0][0].content == "Recent content"


async def test_get_relevant_context_with_memories():
    """Test full context retrieval with actual memories."""
    mock_memory = MagicMock(spec=LongTermMemory)

    test_entry = MemoryEntry(
        content="Python optimization: use list comprehensions",
        memory_type="interaction",
        timestamp=datetime.now(),
    )
    mock_memory.search_memories = AsyncMock(return_value=[(test_entry, 0.9)])
    mock_memory.get_memory_stats = AsyncMock(return_value={"total_memories": 5})

    context_manager = ContextManager(mock_memory)

    with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
        mock_llm.generate_response = AsyncMock(return_value="optimization query")

        context = await context_manager.get_relevant_context(
            query="How to optimize Python?",
            max_context_items=5,
        )

    assert isinstance(context, dict)
    assert "system_state" in context
    # Should have at least system_state and recent_interactions
    assert len(context) >= 1
