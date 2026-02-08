#!/usr/bin/env python3
"""Simulate the exact API logic to find the bug."""

import chromadb
from chromadb.config import Settings
from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field

class MemoryItem(BaseModel):
    """Memory item model."""
    id: str = Field(..., description="Unique memory identifier")
    content: str = Field(..., description="Memory content")
    timestamp: datetime = Field(..., description="When the memory was created")
    metadata: Dict[str, Any] = Field(..., description="Memory metadata")

# Simulate the API endpoint logic
def get_memories_simulation(limit: int = 10, offset: int = 0):
    """Simulate the /memories endpoint logic."""
    try:
        # Connect to database
        client = chromadb.PersistentClient(
            path="./memory_db",
            settings=Settings(anonymized_telemetry=False)
        )
        collection = client.get_collection(name="agent_memory")

        memories = []

        # Get all memories by querying the collection directly
        try:
            print(f"Calling collection.get(limit={limit + offset}, include=['documents', 'metadatas'])")
            results = collection.get(limit=limit + offset, include=["documents", "metadatas"])

            print(f"Results type: {type(results)}")
            print(f"Results keys: {results.keys()}")
            print(f"Number of documents: {len(results.get('documents', []))}")

            if results and results.get("documents"):
                print(f"Processing {len(results['documents'])} documents...")

                for i, doc in enumerate(results["documents"]):
                    try:
                        metadata = results["metadatas"][i] if "metadatas" in results and i < len(results["metadatas"]) else {}

                        # Get timestamp from metadata or use current time as fallback
                        timestamp_str = metadata.get("timestamp")
                        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

                        memory_item = MemoryItem(
                            id=results["ids"][i] if "ids" in results else f"mem_{i}",
                            content=doc,
                            timestamp=timestamp,
                            metadata=metadata,
                        )

                        memories.append(memory_item)

                        if i == 0:  # Show first item details
                            print(f"\nFirst memory item created:")
                            print(f"  ID: {memory_item.id}")
                            print(f"  Content: {memory_item.content[:50]}...")
                            print(f"  Timestamp: {memory_item.timestamp}")

                    except Exception as e:
                        print(f"ERROR processing memory {i}: {e}")
                        import traceback
                        traceback.print_exc()

            else:
                print("No documents in results!")
                print(f"Results: {results}")

        except Exception as e:
            print(f"ERROR in try block: {e}")
            import traceback
            traceback.print_exc()

        # Apply pagination
        paginated = memories[offset : offset + limit]
        print(f"\n✓ Total memories retrieved: {len(memories)}")
        print(f"✓ After pagination ([{offset}:{offset + limit}]): {len(paginated)}")

        return paginated

    except Exception as e:
        print(f"OUTER ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    result = get_memories_simulation(limit=5, offset=0)
    print(f"\nFinal result: {len(result)} memories")
