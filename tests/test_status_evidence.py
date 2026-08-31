"""Unknown collection is not evidence of an empty memory base."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("ai_sdk")
from evolving_agent.api.routes.general import get_status


async def test_status_marks_failed_memory_collection_unknown():
    agent = SimpleNamespace(memory=SimpleNamespace(get_memory_stats=AsyncMock(side_effect=RuntimeError("synthetic-private-diagnostic"))),
        knowledge_base=SimpleNamespace(knowledge={}), initialized=True, session_id="synthetic", interaction_count=0)
    status = await get_status(agent)
    assert status.memory_count is None
    assert status.knowledge_count == 0
    assert "private-diagnostic" not in str(status)


async def test_status_preserves_confirmed_zero_and_rejects_invalid_count():
    agent = SimpleNamespace(memory=SimpleNamespace(get_memory_stats=AsyncMock(return_value={"total_memories": 0})),
        knowledge_base=SimpleNamespace(knowledge={}), initialized=True, session_id="synthetic", interaction_count=0)
    assert (await get_status(agent)).memory_count == 0
    agent.memory.get_memory_stats.return_value = {"total_memories": True}
    assert (await get_status(agent)).memory_count is None
