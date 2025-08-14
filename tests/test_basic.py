import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Basic tests for the self-improving agent.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from evolving_agent.core.context_manager import ContextManager
from evolving_agent.core.evaluator import OutputEvaluator
from evolving_agent.core.memory import LongTermMemory, MemoryEntry
from evolving_agent.knowledge.base import KnowledgeBase, KnowledgeEntry
from evolving_agent.utils.config import config


class TestMemorySystem:
    """Test the memory system."""
    
    @pytest.mark.asyncio
    async def test_memory_initialization(self):
        """Test memory system initialization."""
        memory = LongTermMemory()
        await memory.initialize()
        
        assert memory.initialized is True
        assert memory.collection is not None
        
    @pytest.mark.asyncio
    async def test_add_and_search_memory(self):
        """Test adding and searching memories."""
        memory = LongTermMemory()
        await memory.initialize()
        
        # Add a test memory
        test_entry = MemoryEntry(
            content="This is a test memory about Python programming",
            memory_type="test",
            metadata={"test": True}
        )
        
        memory_id = await memory.add_memory(test_entry)
        assert memory_id is not None
        
        # Search for the memory
        results = await memory.search_memories(
            query="Python programming",
            n_results=5,
            similarity_threshold=0.3
        )
        
        assert len(results) > 0
        found_memory, similarity = results[0]
        assert "Python programming" in found_memory.content
        assert similarity > 0.3


class TestKnowledgeBase:
    """Test the knowledge base system."""
    
    @pytest.mark.asyncio
    async def test_knowledge_initialization(self):
        """Test knowledge base initialization."""
        kb = KnowledgeBase()
        await kb.initialize()
        
        assert kb.initialized is True
        assert len(kb.categories) > 0
        
    @pytest.mark.asyncio
    async def test_add_and_search_knowledge(self):
        """Test adding and searching knowledge."""
        kb = KnowledgeBase()
        await kb.initialize()
        
        # Add test knowledge
        test_knowledge = KnowledgeEntry(
            content="Test knowledge: Always validate inputs before processing",
            category="best_practices",
            tags=["validation", "security"],
            confidence=0.9
        )
        
        knowledge_id = await kb.add_knowledge(test_knowledge)
        assert knowledge_id is not None
        
        # Search for knowledge
        results = await kb.search_knowledge(
            query="validate inputs",
            max_results=5
        )
        
        assert len(results) > 0
        found_knowledge, relevance = results[0]
        assert "validate inputs" in found_knowledge.content.lower()


class TestEvaluator:
    """Test the evaluation system."""
    
    @pytest.mark.asyncio
    async def test_output_evaluation(self):
        """Test output evaluation."""
        evaluator = OutputEvaluator()
        
        # Test evaluation
        result = await evaluator.evaluate_output(
            query="What is Python?",
            output="Python is a high-level programming language known for its simplicity and readability.",
            context={"test": True}
        )
        
        assert result.overall_score > 0
        assert result.overall_score <= 1.0
        assert len(result.criteria_scores) > 0
        assert result.confidence > 0


class TestContextManager:
    """Test the context management system."""
    
    @pytest.mark.asyncio
    async def test_context_manager_initialization(self):
        """Test context manager initialization."""
        memory = LongTermMemory()
        await memory.initialize()
        
        context_manager = ContextManager(memory)
        assert context_manager.memory is not None
        
    @pytest.mark.asyncio
    async def test_get_relevant_context(self):
        """Test retrieving relevant context."""
        memory = LongTermMemory()
        await memory.initialize()
        
        # Add some test memories first
        test_memories = [
            MemoryEntry("Test memory about machine learning", "test"),
            MemoryEntry("Test memory about web development", "test"),
            MemoryEntry("Test memory about data science", "test")
        ]
        
        for memory_entry in test_memories:
            await memory.add_memory(memory_entry)
        
        context_manager = ContextManager(memory)
        
        # Get context
        context = await context_manager.get_relevant_context(
            query="machine learning algorithms",
            max_context_items=5
        )
        
        assert isinstance(context, dict)


class TestConfiguration:
    """Test configuration system."""
    
    def test_config_properties(self):
        """Test configuration properties."""
        assert hasattr(config, 'default_llm_provider')
        assert hasattr(config, 'openrouter_api_key')
        assert hasattr(config, 'memory_persist_directory')
        assert hasattr(config, 'enable_self_modification')
        
        # Test that default provider is now anthropic
        assert config.default_llm_provider == "anthropic"
        
    def test_config_methods(self):
        """Test configuration methods."""
        all_config = config.get_all_config()
        assert isinstance(all_config, dict)
        assert len(all_config) > 0


async def test_basic_functionality():
    """Basic functionality test."""
    print("Testing basic functionality...")
    
    try:
        # Test memory
        memory = LongTermMemory()
        await memory.initialize()
        print("✓ Memory system initialized")
        
        # Test knowledge base
        kb = KnowledgeBase()
        await kb.initialize()
        print("✓ Knowledge base initialized")
        
        # Test evaluator
        evaluator = OutputEvaluator()
        result = await evaluator.evaluate_output(
            query="Test query",
            output="Test output response"
        )
        print(f"✓ Evaluator working (score: {result.overall_score:.2f})")
        
        print("All basic tests passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        raise


if __name__ == "__main__":
    # Run a simple test
    asyncio.run(test_basic_functionality())
