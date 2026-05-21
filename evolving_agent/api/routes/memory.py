"""Memory endpoints: /memories."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import MemoryItem

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/memories", response_model=List[MemoryItem], tags=["Memory"])
async def get_memories(
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Retrieve stored memories from the agent's long-term memory system.

    - **limit**: Maximum number of memories to return (default: 10)
    - **offset**: Number of memories to skip (for pagination)
    - **search**: Optional search query to filter memories
    """
    try:
        if not hasattr(current_agent, "memory"):
            return []

        memories = []

        if search:
            # Search for relevant memories
            # search_memories returns List[Tuple[MemoryEntry, float]]
            search_results = await current_agent.memory.search_memories(
                query=search, n_results=limit + offset, similarity_threshold=0.0
            )
            for entry, similarity in search_results:
                memories.append(
                    MemoryItem(
                        id=entry.id,
                        content=entry.content,
                        timestamp=entry.timestamp,
                        metadata={**entry.metadata, "memory_type": entry.memory_type, "similarity": similarity},
                    )
                )
        else:
            # Get all memories by querying the collection directly
            try:
                collection = current_agent.memory.collection
                results = collection.get(limit=limit + offset, include=["documents", "metadatas"])

                if results and results.get("documents"):
                    for i, doc in enumerate(results["documents"]):
                        metadata = results["metadatas"][i] if "metadatas" in results and i < len(results["metadatas"]) else {}
                        # Get timestamp from metadata or use current time as fallback
                        timestamp_str = metadata.get("timestamp")
                        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

                        memories.append(
                            MemoryItem(
                                id=results["ids"][i] if "ids" in results else f"mem_{i}",
                                content=doc,
                                timestamp=timestamp,
                                metadata=metadata,
                            )
                        )
                else:
                    logger.warning(f"No documents in results. Results keys: {results.keys() if results else 'None'}")
            except Exception as e:
                logger.error(f"Could not retrieve all memories: {e}", exc_info=True)

        return memories[offset : offset + limit]

    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving memories: {str(e)}"
        )
