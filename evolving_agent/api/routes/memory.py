"""Project-private and explicitly public memory endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import MemoryItem
from evolving_agent.utils.secret_redaction import redact_text, redact_value

logger = setup_logger(__name__)

router = APIRouter()


async def _load_memories(
    current_agent: SelfImprovingAgent,
    *,
    limit: int,
    offset: int,
    search: Optional[str],
) -> List[MemoryItem]:
    if not hasattr(current_agent, "memory"):
        return []

    if search:
        rows = await current_agent.memory.search_memories(
            query=search,
            n_results=limit + offset,
            similarity_threshold=0.0,
        )
        entries = [
            (entry, {**entry.metadata, "similarity": similarity})
            for entry, similarity in rows
        ]
    else:
        recent = await current_agent.memory.list_recent_memories(limit=limit + offset)
        entries = [(entry, entry.metadata) for entry in recent]

    return [
        MemoryItem(
            id=entry.id,
            content=entry.content,
            timestamp=entry.timestamp,
            metadata={**metadata, "memory_type": entry.memory_type},
        )
        for entry, metadata in entries[offset : offset + limit]
    ]


@router.get("/memories", response_model=List[MemoryItem], tags=["Memory"])
async def get_memories(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
        return await _load_memories(
            current_agent,
            limit=limit,
            offset=offset,
            search=search,
        )

    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving memories: {str(e)}"
        )


@router.get("/public/memories", response_model=List[MemoryItem], tags=["Memory"])
async def get_public_memories(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """Return only memories explicitly published with ``audience=public``."""
    try:
        candidates = await _load_memories(
            current_agent,
            limit=100,
            offset=0,
            search=None,
        )
        public = []
        normalized_search = search.casefold() if search else None
        for memory in candidates:
            if memory.metadata.get("audience") != "public":
                continue
            _, content_findings = redact_text(memory.content)
            _, metadata_findings = redact_value(memory.metadata)
            if content_findings or metadata_findings:
                logger.warning(
                    f"Withheld credential-shaped public memory {memory.id}"
                )
                continue
            if normalized_search and normalized_search not in memory.content.casefold():
                continue
            public.append(
                MemoryItem(
                    id=memory.id,
                    content=memory.content,
                    timestamp=memory.timestamp,
                    metadata={
                        "audience": "public",
                        "memory_type": memory.metadata.get("memory_type", "general"),
                    },
                )
            )
        return public[offset : offset + limit]
    except Exception:
        logger.exception("Error retrieving public memories")
        raise HTTPException(status_code=503, detail="Public memories are unavailable")
