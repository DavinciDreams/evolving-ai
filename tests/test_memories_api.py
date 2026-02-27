#!/usr/bin/env python3
"""Test script to debug the /memories endpoint issue."""

import asyncio
from datetime import datetime
from evolving_agent.core.agent import SelfImprovingAgent


async def test_memories_retrieval():
    """Test memory retrieval to debug API issue."""
    agent = SelfImprovingAgent()
    await agent.initialize()

    print(f"Agent initialized: {agent.initialized}")
    print(f"Has memory: {hasattr(agent, 'memory')}")

    if not hasattr(agent, "memory"):
        print("ERROR: Agent has no memory attribute!")
        return

    # Test collection count
    count = agent.memory.collection.count()
    print(f"Total memories in collection: {count}")

    # Test direct collection.get() call (simulating API endpoint)
    limit = 10
    offset = 0

    try:
        collection = agent.memory.collection
        print(f"\nTrying collection.get(limit={limit + offset}, include=['documents', 'metadatas'])")
        results = collection.get(limit=limit + offset, include=["documents", "metadatas"])

        print(f"Results keys: {results.keys()}")
        print(f"Number of documents: {len(results.get('documents', []))}")
        print(f"Number of ids: {len(results.get('ids', []))}")
        print(f"Number of metadatas: {len(results.get('metadatas', []))}")

        # Check if we have results
        if results and results.get("documents"):
            print("\n✓ Successfully retrieved documents!")
            memories = []

            for i, doc in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if "metadatas" in results and i < len(results["metadatas"]) else {}

                # Get timestamp from metadata
                timestamp_str = metadata.get("timestamp")
                print(f"\nMemory {i}:")
                print(f"  ID: {results['ids'][i]}")
                print(f"  Content: {doc[:100]}...")
                print(f"  Timestamp: {timestamp_str}")
                print(f"  Metadata keys: {list(metadata.keys())}")

                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        print(f"  Parsed timestamp: {timestamp}")
                    except Exception as e:
                        print(f"  ERROR parsing timestamp: {e}")

                if i >= 2:  # Only show first 3
                    break

            print(f"\n✓ Would return {len(results['documents'][offset:offset + limit])} memories")
        else:
            print("\n✗ No documents found in results!")
            print(f"Results: {results}")

    except Exception as e:
        print(f"\n✗ Exception occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_memories_retrieval())
