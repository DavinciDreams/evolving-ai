#!/usr/bin/env python3
"""
Test persistent storage functionality.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pytest

from evolving_agent.utils.persistent_storage import persistent_data_manager


@pytest.mark.asyncio
async def test_persistent_storage():
    """Test the persistent storage system."""
    print("=== Testing Persistent Storage ===")

    try:
        # Initialize
        await persistent_data_manager.initialize()
        print("✓ Persistent data manager initialized")

        # Test saving interaction
        interaction_id = await persistent_data_manager.save_interaction(
            query="What is machine learning?",
            response="Machine learning is a subset of AI that enables computers to learn without explicit programming.",
            evaluation_score=0.85,
            context_used={"test": True},
            metadata={"test_run": True},
        )
        print(f"✓ Saved interaction: {interaction_id}")

        # Test saving evaluation
        await persistent_data_manager.save_evaluation(
            interaction_id=interaction_id,
            overall_score=0.85,
            criteria_scores={"accuracy": 0.9, "relevance": 0.8},
            feedback="Good explanation but could be more detailed",
            improvement_suggestions=["Add examples", "Include use cases"],
            confidence=0.8,
        )
        print("✓ Saved evaluation")

        # Test saving modification
        await persistent_data_manager.save_modification(
            component="test_component",
            modification_type="enhancement",
            description="Added test functionality",
            success=True,
            metadata={"test": True},
        )
        print("✓ Saved modification record")

        # Test saving agent state
        await persistent_data_manager.save_agent_state(
            {"test_state": True, "version": "1.0"}
        )
        print("✓ Saved agent state")

        # Test getting statistics
        stats = await persistent_data_manager.get_session_statistics()
        print(f"✓ Session statistics retrieved: {len(stats)} fields")

        # Test getting recent interactions
        interactions = await persistent_data_manager.get_recent_interactions(limit=5)
        print(f"✓ Retrieved {len(interactions)} recent interactions")

        # Test creating backup
        backup_path = await persistent_data_manager.create_backup("agent_state")
        print(f"✓ Created backup: {backup_path}")

        print("\n🎉 All persistent storage tests passed!")

        # Show some sample data
        if stats:
            print(f"\nSample session stats:")
            for key, value in list(stats.items())[:5]:
                print(f"  {key}: {value}")

        if interactions:
            print(f"\nSample interaction:")
            interaction = interactions[0]
            print(f"  Query: {interaction.get('query', 'N/A')[:50]}...")
            print(f"  Score: {interaction.get('evaluation_score', 'N/A')}")
            print(f"  Timestamp: {interaction.get('timestamp', 'N/A')}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

    finally:
        # Cleanup
        try:
            await persistent_data_manager.cleanup()
            print("✓ Cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


if __name__ == "__main__":
    asyncio.run(test_persistent_storage())
