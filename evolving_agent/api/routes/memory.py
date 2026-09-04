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

_PUBLIC_MEMORY_PAGE_SIZE = 100
_PUBLIC_MEMORY_MAX_SCAN_PAGES = 3
_PUBLIC_MEMORY_MAX_OFFSET = (
    _PUBLIC_MEMORY_PAGE_SIZE * (_PUBLIC_MEMORY_MAX_SCAN_PAGES - 1)
)
_PUBLIC_MEMORY_MAX_SEARCH_CHARS = 256


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
    offset: int = Query(default=0, ge=0, le=_PUBLIC_MEMORY_MAX_OFFSET),
    search: Optional[str] = Query(
        default=None,
        max_length=_PUBLIC_MEMORY_MAX_SEARCH_CHARS,
    ),
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """Return only memories explicitly published with ``audience=public``."""
    try:
        public = []
        cursor = None
        seen_cursors = set()
        requested_count = offset + limit
        normalized_search = search.casefold() if search else None
        storage_exhausted = False
        pages_scanned = 0
        while (
            len(public) < requested_count
            and pages_scanned < _PUBLIC_MEMORY_MAX_SCAN_PAGES
        ):
            candidates, next_cursor = (
                await current_agent.memory.page_recent_memories(
                    limit=_PUBLIC_MEMORY_PAGE_SIZE,
                    cursor=cursor,
                )
            )
            pages_scanned += 1
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
                if (
                    normalized_search
                    and normalized_search not in memory.content.casefold()
                ):
                    continue
                public.append(
                    MemoryItem(
                        id=memory.id,
                        content=memory.content,
                        timestamp=memory.timestamp,
                        metadata={
                            "audience": "public",
                            "memory_type": memory.metadata.get(
                                "memory_type", "general"
                            ),
                        },
                    )
                )
                if len(public) >= requested_count:
                    break
            if len(public) >= requested_count:
                break
            if next_cursor is None:
                storage_exhausted = True
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise RuntimeError("Memory pagination cursor did not advance")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        if len(public) < requested_count and not storage_exhausted:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Public memory scan budget exceeded; narrow the search or offset"
                ),
            )
        return public[offset : offset + limit]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error retrieving public memories")
        raise HTTPException(status_code=503, detail="Public memories are unavailable")
