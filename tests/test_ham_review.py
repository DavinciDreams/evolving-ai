"""Tests for bounded asynchronous HAM corpus reviews."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from evolving_agent.core.ham_review import HAMReviewService
from evolving_agent.core.memory import MemoryEntry


def memory(memory_id: str, content: str) -> MemoryEntry:
    return MemoryEntry(
        entry_id=memory_id,
        content=content,
        memory_type="research",
        timestamp=datetime(2026, 9, 18, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_review_batches_deduplicates_and_cites_sources():
    first = memory("101", "Kuramoto synchronization and phase transitions")
    second = memory("102", "Clifford algebra model of geometric resonance")
    paged = memory("103", "Physics criticality and solar flare prediction")
    store = MagicMock()
    store.search_memories = AsyncMock(
        side_effect=[
            [(first, 0.9), (second, 0.8)],
            [(first, 0.85)],
        ]
    )
    store.page_recent_memories = AsyncMock(return_value=([paged], None))
    provider = MagicMock()
    provider.generate_response = AsyncMock(
        side_effect=[
            '["phase synchronization", "clifford resonance"]',
            "Themes [memory:101], [memory:102], [memory:103]",
            "Final synthesis [memory:101] [memory:102] [memory:103]",
        ]
    )
    progress = AsyncMock()
    service = HAMReviewService(
        store,
        provider,
        max_queries=2,
        results_per_query=10,
        max_sources=10,
        max_pages=1,
        chunk_size=10,
    )

    result = await service.review("Review HAM physics", progress=progress)

    assert result.source_count == 3
    assert result.semantic_queries == 2
    assert result.project_records_scanned == 1
    assert "Final synthesis" in result.report
    assert "[memory:101]" in result.report
    assert store.search_memories.await_count == 2
    store.page_recent_memories.assert_awaited_once_with(limit=100, cursor=None)
    assert progress.await_count == 4
    for call in provider.generate_response.await_args_list:
        assert "tools" not in call.kwargs
        assert call.kwargs["timeout"] <= 60


@pytest.mark.asyncio
async def test_review_falls_back_to_original_query_when_planning_fails():
    entry = memory("201", "Physics memory")
    store = MagicMock()
    store.search_memories = AsyncMock(return_value=[(entry, 0.7)])
    store.page_recent_memories = AsyncMock(return_value=([], None))
    provider = MagicMock()
    provider.generate_response = AsyncMock(
        side_effect=[
            RuntimeError("planner unavailable"),
            "Batch [memory:201]",
            "Review [memory:201]",
        ]
    )
    service = HAMReviewService(store, provider, max_pages=0)

    result = await service.review("Review HAM physics")

    assert result.semantic_queries == 1
    store.search_memories.assert_awaited_once()
    assert store.search_memories.await_args.args[0] == "Review HAM physics"
    assert "[memory:201]" in result.report


@pytest.mark.asyncio
async def test_review_reports_empty_bounded_result_without_synthesis():
    store = MagicMock()
    store.search_memories = AsyncMock(return_value=[])
    store.page_recent_memories = AsyncMock(return_value=([], None))
    provider = MagicMock()
    provider.generate_response = AsyncMock(return_value='["physics"]')
    service = HAMReviewService(store, provider, max_pages=1)

    result = await service.review("Review HAM physics")

    assert result.source_count == 0
    assert "No relevant HAM memories" in result.report
    assert provider.generate_response.await_count == 1
