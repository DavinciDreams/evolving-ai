import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


for _mod in ["chromadb", "chromadb.config", "sentence_transformers"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from evolving_agent.core.dream_cycle import DreamConsolidationService  # noqa: E402


class FakeMemory:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.added = []

    async def search_memories(self, *args, **kwargs):
        return self.existing

    async def add_memory(self, entry):
        self.added.append(entry)
        return f"memory-{len(self.added)}"


class FakeDataManager:
    session_id = "test-session"

    def __init__(self, interactions=None):
        self.interactions = interactions or []
        self.saved = []

    async def get_recent_interactions(self, limit=10):
        return self.interactions[:limit]

    async def save_dream_consolidation(self, **kwargs):
        self.saved.append(kwargs)
        return len(self.saved)


def _cfg():
    cfg = MagicMock()
    cfg.dream_cycle_enabled = True
    cfg.dream_cycle_interval_seconds = 60
    cfg.dream_cycle_min_interactions = 1
    cfg.dream_cycle_batch_size = 10
    cfg.dream_cycle_max_insights = 4
    cfg.dream_cycle_max_tokens = 200
    cfg.dream_cycle_llm_timeout_seconds = 1
    cfg.dream_cycle_prompt_max_chars = 4000
    return cfg


@pytest.mark.asyncio
async def test_seed_capability_memory_stores_once():
    memory = FakeMemory()
    service = DreamConsolidationService(memory, FakeDataManager())

    memory_id = await service.seed_capability_memory()

    assert memory_id == "memory-1"
    assert memory.added[0].memory_type == "capability"
    assert memory.added[0].metadata["capability_key"] == service.CAPABILITY_MEMORY_KEY


@pytest.mark.asyncio
async def test_run_once_creates_consolidation_memory(monkeypatch):
    monkeypatch.setattr("evolving_agent.core.dream_cycle.config", _cfg())
    llm = MagicMock()
    llm.generate_response = AsyncMock(
        return_value='{"summary": "The user is improving memory persistence.", '
        '"insights": ["Keep Discord context durable", "Use GitHub tools for code"]}'
    )
    memory = FakeMemory()
    data = FakeDataManager(
        interactions=[
            {
                "id": 1,
                "conversation_id": "discord-1",
                "query": "Can you implement dream memory?",
                "response": "I will add a service.",
            }
        ]
    )
    service = DreamConsolidationService(memory, data, llm_manager=llm)

    result = await service.run_once(reason="test")

    assert result.created is True
    assert result.memory_id == "memory-1"
    assert memory.added[0].memory_type == "dream_consolidation"
    assert data.saved[0]["source_interaction_count"] == 1


@pytest.mark.asyncio
async def test_run_once_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr("evolving_agent.core.dream_cycle.config", _cfg())
    llm = MagicMock()
    llm.generate_response = AsyncMock(side_effect=RuntimeError("offline"))
    memory = FakeMemory()
    data = FakeDataManager(
        interactions=[{"id": 1, "query": "remember this", "response": "ok"}]
    )
    service = DreamConsolidationService(memory, data, llm_manager=llm)

    result = await service.run_once(reason="test")

    assert result.created is True
    assert "Dream consolidation of 1 recent interaction" in result.summary
    assert memory.added[0].memory_type == "dream_consolidation"


@pytest.mark.asyncio
async def test_run_once_handles_no_interactions(monkeypatch):
    monkeypatch.setattr("evolving_agent.core.dream_cycle.config", _cfg())
    service = DreamConsolidationService(FakeMemory(), FakeDataManager())

    result = await service.run_once(reason="test")

    assert result.created is False
    assert result.reason == "no_interactions"
