"""
Test script for the optimized context manager.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from evolving_agent.core.context_manager import ContextManager, ContextQuery, ContextUtility
from evolving_agent.core.memory import LongTermMemory, MemoryEntry


class TestOptimizedContextManager(unittest.TestCase):
    """Test cases for the optimized context manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock memory system
        self.mock_memory = MagicMock(spec=LongTermMemory)
        
        # Create the context manager with the mock memory
        self.context_manager = ContextManager(self.mock_memory)
        
        # Create test memory entries
        self.test_memories = [
            MemoryEntry(
                content="Test content about Python functions",
                memory_type="similar_tasks",
                timestamp=datetime.now() - timedelta(days=1),
                metadata={"source": "test"}
            ),
            MemoryEntry(
                content="Error handling in Python",
                memory_type="error_experiences",
                timestamp=datetime.now() - timedelta(days=2),
                metadata={"source": "test"}
            ),
            MemoryEntry(
                content="Optimization techniques for Python code",
                memory_type="optimization_insights",
                timestamp=datetime.now() - timedelta(days=3),
                metadata={"source": "test"}
            ),
        ]

    async def test_context_query_caching(self):
        """Test that context queries are properly cached."""
        query = "How to optimize Python functions?"
        
        # Mock the LLM response
        with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
            mock_llm.generate_response.return_value = "Python function optimization techniques"
            
            # First call should generate new queries
            queries1 = await self.context_manager._generate_context_queries_cached(query)
            
            # Second call should use cached queries
            queries2 = await self.context_manager._generate_context_queries_cached(query)
            
            # Verify both calls return the same result
            self.assertEqual(len(queries1), len(queries2))
            for q1, q2 in zip(queries1, queries2):
                self.assertEqual(q1.query, q2.query)
                self.assertEqual(q1.context_type, q2.context_type)
            
            # Verify LLM was only called once (for the first call)
            self.assertEqual(mock_llm.generate_response.call_count, 6)  # Once for each context type

    async def test_fallback_mechanism(self):
        """Test fallback mechanism when LLM fails."""
        query = "How to handle errors in Python?"
        
        # Mock LLM to raise an exception
        with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
            mock_llm.generate_response.side_effect = Exception("LLM unavailable")
            
            # Generate queries with fallback
            queries = await self.context_manager._generate_context_queries_with_fallback(query)
            
            # Verify we still get queries despite LLM failure
            self.assertGreater(len(queries), 0)
            
            # Verify all queries have fallback metadata
            for query_obj in queries:
                self.assertEqual(query_obj.metadata.get("generated_by"), "fallback")
            
            # Verify fallback queries contain relevant keywords
            error_query = next(q for q in queries if q.context_type == "error_experiences")
            self.assertIn("error", error_query.query.lower())

    async def test_early_stopping(self):
        """Test early stopping when sufficient context is found."""
        # Mock memory search to return high-relevance results
        high_relevance_memories = [
            (self.test_memories[0], 0.9),
            (self.test_memories[1], 0.85),
            (self.test_memories[2], 0.8),
        ]
        
        self.mock_memory.search_memories.return_value = high_relevance_memories
        
        # Create context queries
        context_queries = [
            ContextQuery(
                query="Python optimization",
                context_type="optimization_insights",
                priority=0.8,
                timestamp=datetime.now(),
                metadata={}
            ),
            ContextQuery(
                query="Error handling",
                context_type="error_experiences",
                priority=0.7,
                timestamp=datetime.now(),
                metadata={}
            ),
        ]
        
        # Retrieve memories with early stopping
        all_contexts = {}
        total_items = 0
        sufficient_context_found = False
        
        for ctx_query in context_queries:
            if sufficient_context_found:
                break
                
            contexts = await self.context_manager._retrieve_context_memories(
                ctx_query, 0.6, 10
            )
            
            if contexts:
                all_contexts[ctx_query.context_type] = contexts
                total_items += len(contexts)
                
                # Check if we have sufficient context
                avg_relevance = sum(score for _, score in contexts) / len(contexts)
                if avg_relevance >= self.context_manager.SUFFICIENT_CONTEXT_THRESHOLD and total_items >= 10 * 0.7:
                    sufficient_context_found = True
        
        # Verify early stopping was triggered
        self.assertTrue(sufficient_context_found)
        self.assertGreater(total_items, 0)

    async def test_adaptive_context_ranking(self):
        """Test adaptive context ranking with learning."""
        # Set up context utilities with historical data
        self.context_manager.context_utilities = {
            "similar_tasks": ContextUtility(
                context_type="similar_tasks",
                success_count=8,
                usage_count=10,
                avg_relevance=0.8
            ),
            "error_experiences": ContextUtility(
                context_type="error_experiences",
                success_count=3,
                usage_count=10,
                avg_relevance=0.4
            ),
        }
        
        # Create test contexts
        all_contexts = {
            "similar_tasks": [(self.test_memories[0], 0.7)],
            "error_experiences": [(self.test_memories[1], 0.6)],
        }
        
        # Organize contexts with adaptive ranking
        organized = await self.context_manager._organize_contexts_adaptive(all_contexts, "test query")
        
        # Verify similar_tasks comes first due to higher utility
        self.assertIn("similar_tasks", organized)
        self.assertIn("error_experiences", organized)
        
        # Verify adaptive priorities are included
        self.assertGreater(
            organized["similar_tasks"]["adaptive_priority"],
            organized["error_experiences"]["adaptive_priority"]
        )

    def test_keyword_extraction(self):
        """Test keyword extraction from queries."""
        # Test with programming-related text
        text = "How to implement a REST API server with error handling and database optimization?"
        keywords = self.context_manager._extract_keywords(text)
        
        # Verify relevant keywords are extracted
        self.assertIn("implement", keywords)
        self.assertIn("server", keywords)
        self.assertIn("database", keywords)
        self.assertIn("optimization", keywords)
        
        # Test with non-programming text
        text = "What is the weather like today?"
        keywords = self.context_manager._extract_keywords(text)
        
        # Should still extract meaningful words
        self.assertGreater(len(keywords), 0)

    def test_context_utility_tracking(self):
        """Test context utility tracking updates."""
        # Initialize with no utilities
        self.assertEqual(len(self.context_manager.context_utilities), 0)
        
        # Update utility with test contexts
        contexts = [
            (self.test_memories[0], 0.8),
            (self.test_memories[1], 0.7),
        ]
        
        self.context_manager._update_context_utility("similar_tasks", contexts)
        
        # Verify utility was created and updated
        self.assertIn("similar_tasks", self.context_manager.context_utilities)
        utility = self.context_manager.context_utilities["similar_tasks"]
        self.assertEqual(utility.usage_count, 1)
        self.assertEqual(utility.avg_relevance, 0.75)  # Average of 0.8 and 0.7
        self.assertEqual(utility.success_count, 1)  # Above threshold

    async def test_summarization_fallback(self):
        """Test summarization fallback when LLM fails."""
        # Create test context items
        context_items = [
            {"content": "First item about Python functions"},
            {"content": "Second item about Python optimization"},
            {"content": "Third item about Python error handling"},
        ]
        
        # Test fallback summarization
        summary = self.context_manager._simple_summary_fallback(
            [item["content"] for item in context_items],
            "similar_tasks"
        )
        
        # Verify summary contains relevant information
        self.assertIn("3", summary)  # Number of items
        self.assertIn("entries", summary)
        self.assertIn("similar tasks", summary.lower())

    def test_performance_stats(self):
        """Test performance statistics collection."""
        # Set up some test data
        self.context_manager.llm_failure_count = 2
        self.context_manager.last_llm_failure = datetime.now()
        
        # Add some utilities
        self.context_manager.context_utilities = {
            "test_type": ContextUtility(
                context_type="test_type",
                success_count=5,
                usage_count=10,
                avg_relevance=0.7
            )
        }
        
        # Get performance stats
        stats = self.context_manager.get_performance_stats()
        
        # Verify stats contain expected information
        self.assertIn("context_cache_size", stats)
        self.assertIn("query_cache_size", stats)
        self.assertEqual(stats["llm_failure_count"], 2)
        self.assertIn("context_utilities", stats)
        self.assertEqual(stats["context_utilities"]["test_type"]["success_rate"], 0.5)

    async def test_health_check(self):
        """Test health check functionality."""
        # Mock LLM to be available
        with patch('evolving_agent.core.context_manager.llm_manager') as mock_llm:
            mock_llm.generate_response.return_value = "OK"
            
            # Mock memory stats
            self.mock_memory.get_memory_stats.return_value = {"total_memories": 100}
            
            # Perform health check
            health = await self.context_manager.health_check()
            
            # Verify health check results
            self.assertEqual(health["status"], "healthy")
            self.assertTrue(health["llm_available"])
            self.assertEqual(health["memory_system"], "operational")
            self.assertIn("cache_sizes", health)

    async def test_max_context_limits(self):
        """Test that context retrieval respects maximum limits."""
        # Create many test memories
        many_memories = []
        for i in range(20):
            memory = MemoryEntry(
                content=f"Test content {i}",
                memory_type="test",
                timestamp=datetime.now(),
                metadata={}
            )
            many_memories.append((memory, 0.8))
        
        # Mock memory search to return many memories
        self.mock_memory.search_memories.return_value = many_memories
        
        # Create a context query
        context_query = ContextQuery(
            query="test query",
            context_type="test",
            priority=0.8,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Retrieve memories with limit
        memories = await self.context_manager._retrieve_context_memories(
            context_query, 0.6, 5  # Limit to 5 items
        )
        
        # Verify limit is respected
        self.assertLessEqual(len(memories), 5)


async def run_tests():
    """Run all async tests."""
    test_instance = TestOptimizedContextManager()
    test_instance.setUp()
    
    # Run async tests
    await test_instance.test_context_query_caching()
    await test_instance.test_fallback_mechanism()
    await test_instance.test_early_stopping()
    await test_instance.test_adaptive_context_ranking()
    await test_instance.test_summarization_fallback()
    await test_instance.test_health_check()
    await test_instance.test_max_context_limits()
    
    # Run sync tests
    test_instance.test_keyword_extraction()
    test_instance.test_context_utility_tracking()
    test_instance.test_performance_stats()
    
    print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(run_tests())