#!/usr/bin/env python3
"""
Test memory system with complex metadata.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

import pytest

from evolving_agent.core.memory import LongTermMemory, MemoryEntry


@pytest.mark.asyncio
async def test_memory_metadata():
    """Test memory system with complex metadata."""
    print("=== Testing Memory System with Complex Metadata ===")
    
    try:
        # Initialize memory
        memory = LongTermMemory()
        await memory.initialize()
        print("✓ Memory initialized")
        
        # Test with simple metadata
        simple_entry = MemoryEntry(
            content="This is a test with simple metadata",
            memory_type="test",
            metadata={
                "test_type": "simple",
                "score": 0.95,
                "active": True,
                "count": 42
            }
        )
        
        simple_id = await memory.add_memory(simple_entry)
        print(f"✓ Added simple metadata entry: {simple_id}")
        
        # Test with complex metadata (should be sanitized)
        complex_entry = MemoryEntry(
            content="This is a test with complex metadata",
            memory_type="test",
            metadata={
                "test_type": "complex",
                "config": {"llm": "anthropic", "temp": 0.7},
                "tags": ["test", "complex", "metadata"],
                "nested": {"deep": {"value": 123}},
                "timestamp": datetime.now()
            }
        )
        
        complex_id = await memory.add_memory(complex_entry)
        print(f"✓ Added complex metadata entry: {complex_id}")
        
        # Test search
        results = await memory.search_memories("test metadata", n_results=2)
        print(f"✓ Found {len(results)} memories")
        
        for memory_entry, similarity in results:
            print(f"  - {memory_entry.content[:50]}... (similarity: {similarity:.3f})")
        
        print("\n🎉 Memory metadata test passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_memory_metadata())
