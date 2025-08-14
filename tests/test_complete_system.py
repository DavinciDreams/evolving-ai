#!/usr/bin/env python3
"""
Comprehensive test of the self-improving agent system.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pytest

from evolving_agent.core.agent import SelfImprovingAgent


@pytest.mark.asyncio
async def test_complete_system():
    """Test the complete self-improving agent system."""
    print("=== Testing Complete Self-Improving Agent System ===")

    agent = None
    try:
        # Initialize agent
        print("🚀 Initializing agent...")
        agent = SelfImprovingAgent()
        await agent.initialize()
        print("✅ Agent initialized successfully!")

        # Test basic interaction
        print("\n💬 Testing basic interaction...")
        query = "What is artificial intelligence?"
        response = await agent.run(query)
        print(f"Query: {query}")
        print(f"Response: {response[:200]}...")

        # Show session statistics
        print("\n📊 Session statistics:")
        stats = await agent.data_manager.get_session_statistics()
        for key, value in list(stats.items())[:8]:
            print(f"  {key}: {value}")

        # Test second interaction to show memory/learning
        print("\n💬 Testing second interaction...")
        query2 = "Can you explain machine learning in simple terms?"
        response2 = await agent.run(query2)
        print(f"Query: {query2}")
        print(f"Response: {response2[:200]}...")

        # Show updated statistics
        print("\n📊 Updated session statistics:")
        stats2 = await agent.data_manager.get_session_statistics()
        print(f"  Total interactions: {stats2.get('current_interactions', 0)}")
        print(f"  Average score: {stats2.get('average_evaluation_score', 0):.2f}")

        # Show memory
        print("\n🧠 Recent memories:")
        recent_memories = await agent.memory.search_memories(
            "artificial intelligence", n_results=3
        )
        for i, (memory, similarity) in enumerate(recent_memories, 1):
            print(f"  {i}. {memory.content[:100]}... (similarity: {similarity:.3f})")

        print("\n🎉 Complete system test passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if agent:
            try:
                await agent.cleanup()
                print("✅ Agent cleanup completed")
            except Exception as e:
                print(f"⚠️ Cleanup warning: {e}")


if __name__ == "__main__":
    asyncio.run(test_complete_system())
