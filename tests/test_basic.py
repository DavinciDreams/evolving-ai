"""
Basic tests for the self-improving agent.
"""

import os

import pytest

from evolving_agent.core.context_manager import ContextManager
from evolving_agent.core.evaluator import OutputEvaluator
from evolving_agent.core.memory import LongTermMemory, MemoryEntry
from evolving_agent.knowledge.base import KnowledgeBase, KnowledgeEntry
from evolving_agent.utils.config import Config


class TestMemorySystem:
    """Test the memory system."""

    async def test_memory_initialization(self):
        """Test memory system initialization."""
        memory = LongTermMemory()
        await memory.initialize()

        assert memory.initialized is True
        assert memory.collection is not None

    async def test_add_and_search_memory(self):
        """Test adding and searching memories."""
        memory = LongTermMemory()
        await memory.initialize()

        # Add a test memory
        test_entry = MemoryEntry(
            content="This is a test memory about Python programming",
            memory_type="test",
            metadata={"test": True},
        )

        memory_id = await memory.add_memory(test_entry)
        assert memory_id is not None

        # Search for the memory
        results = await memory.search_memories(
            query="Python programming", n_results=5, similarity_threshold=0.3
        )

        assert len(results) > 0
        found_memory, similarity = results[0]
        assert "Python programming" in found_memory.content
        assert similarity > 0.3


class TestKnowledgeBase:
    """Test the knowledge base system."""

    async def test_knowledge_initialization(self):
        """Test knowledge base initialization."""
        kb = KnowledgeBase()
        await kb.initialize()

        assert kb.initialized is True
        assert len(kb.categories) > 0

    async def test_add_and_search_knowledge(self):
        """Test adding and searching knowledge."""
        kb = KnowledgeBase()
        await kb.initialize()

        # Add test knowledge
        test_knowledge = KnowledgeEntry(
            content="Test knowledge: Always validate inputs before processing",
            category="best_practices",
            tags=["validation", "security"],
            confidence=0.9,
        )

        knowledge_id = await kb.add_knowledge(test_knowledge)
        assert knowledge_id is not None

        # Search for knowledge
        results = await kb.search_knowledge(query="validate inputs", max_results=5)

        assert len(results) > 0
        found_knowledge, relevance = results[0]
        assert "validate inputs" in found_knowledge.content.lower()


class TestEvaluator:
    """Test the evaluation system."""

    async def test_output_evaluation(self, monkeypatch):
        """Test output evaluation with mocked LLM."""
        from unittest.mock import AsyncMock, patch

        evaluator = OutputEvaluator()

        mock_response = '{"scores": {"accuracy": 0.8, "completeness": 0.75, "clarity": 0.9, "relevance": 0.85, "creativity": 0.7, "efficiency": 0.8, "safety": 0.95}, "strengths": ["Clear explanation"], "weaknesses": [], "suggestions": ["Add examples"]}'

        with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            result = await evaluator.evaluate_output(
                query="What is Python?",
                output="Python is a high-level programming language known for its simplicity and readability.",
                context={"test": True},
            )

        assert result.overall_score > 0
        assert result.overall_score <= 1.0
        assert len(result.criteria_scores) > 0
        assert result.confidence > 0


class TestContextManager:
    """Test the context management system."""

    async def test_context_manager_initialization(self):
        """Test context manager initialization."""
        memory = LongTermMemory()
        await memory.initialize()

        context_manager = ContextManager(memory)
        assert context_manager.memory is not None

    async def test_get_relevant_context(self):
        """Test retrieving relevant context."""
        memory = LongTermMemory()
        await memory.initialize()

        # Add some test memories first
        test_memories = [
            MemoryEntry("Test memory about machine learning", "test"),
            MemoryEntry("Test memory about web development", "test"),
            MemoryEntry("Test memory about data science", "test"),
        ]

        for memory_entry in test_memories:
            await memory.add_memory(memory_entry)

        context_manager = ContextManager(memory)

        # Get context
        context = await context_manager.get_relevant_context(
            query="machine learning algorithms", max_context_items=5
        )

        assert isinstance(context, dict)


class TestConfiguration:
    """Test configuration system."""

    def test_config_properties(self):
        """Test configuration properties."""
        # Create a fresh config to read from current env
        cfg = Config()

        assert hasattr(cfg, "default_llm_provider")
        assert hasattr(cfg, "openrouter_api_key")
        assert hasattr(cfg, "memory_persist_directory")
        assert hasattr(cfg, "enable_self_modification")

        # Verify provider is set (value comes from .env, not hardcoded)
        assert cfg.default_llm_provider is not None
        assert len(cfg.default_llm_provider) > 0

    def test_config_methods(self):
        """Test configuration methods."""
        cfg = Config()
        all_config = cfg.get_all_config()
        assert isinstance(all_config, dict)
        assert len(all_config) > 0


async def test_basic_functionality():
    """Basic functionality smoke test."""
    from unittest.mock import AsyncMock, patch

    # Test memory
    memory = LongTermMemory()
    await memory.initialize()
    assert memory.initialized is True

    # Test knowledge base
    kb = KnowledgeBase()
    await kb.initialize()
    assert kb.initialized is True

    # Test evaluator with mocked LLM
    evaluator = OutputEvaluator()
    mock_response = '{"scores": {"accuracy": 0.8, "completeness": 0.75, "clarity": 0.9, "relevance": 0.85, "creativity": 0.7, "efficiency": 0.8, "safety": 0.95}, "strengths": ["Good"], "weaknesses": [], "suggestions": ["Improve"]}'

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        result = await evaluator.evaluate_output(
            query="Test query", output="Test output response"
        )
    assert result.overall_score > 0
