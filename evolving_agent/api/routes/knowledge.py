"""Knowledge endpoints: /knowledge."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import KnowledgeItem

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/knowledge", response_model=List[KnowledgeItem], tags=["Knowledge"])
async def get_knowledge(
    limit: int = 10,
    offset: int = 0,
    category: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Retrieve knowledge items from the agent's knowledge base.

    - **limit**: Maximum number of items to return (default: 10)
    - **offset**: Number of items to skip (for pagination)
    - **category**: Optional category filter
    """
    try:
        if not hasattr(current_agent, "knowledge_base"):
            return []

        knowledge_items = []
        all_items = current_agent.knowledge_base.knowledge

        # Filter by category if specified
        if category:
            filtered_items = {
                k: v
                for k, v in all_items.items()
                if v.category.lower() == category.lower()
            }
        else:
            filtered_items = all_items

        # Convert to response format
        for item_id, entry in list(filtered_items.items())[offset : offset + limit]:
            knowledge_items.append(
                KnowledgeItem(
                    id=item_id,
                    content=entry.content,
                    category=entry.category,
                    priority=entry.confidence,  # Use confidence as priority
                    timestamp=entry.created_at,
                )
            )

        return knowledge_items

    except Exception as e:
        logger.error(f"Error retrieving knowledge: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving knowledge: {str(e)}"
        )
