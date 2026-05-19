"""Feedback endpoint: POST /feedback — human ratings for interactions."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from evolving_agent.utils.deps import get_agent, verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.persistent_storage import persistent_data_manager

logger = setup_logger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    interaction_id: int = Field(..., description="ID of the interaction to rate")
    rating: int = Field(..., ge=-1, le=1, description="+1 (thumbs up) or -1 (thumbs down)")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional comment")


class FeedbackResponse(BaseModel):
    feedback_id: int
    interaction_id: int
    rating: int
    timestamp: datetime
    message: str


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    tags=["Feedback"],
    summary="Submit human feedback for an interaction",
)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit explicit human feedback (thumbs up/down) for a prior interaction.

    This signal is weighted more heavily than self-evaluation scores
    and feeds into the agent's hill-climbing loop.

    - **interaction_id**: The `interaction_id` returned by /chat or stored in the DB
    - **rating**: +1 for helpful, -1 for unhelpful
    - **comment**: Optional free-text explanation
    """
    try:
        if request.rating not in (-1, 1):
            raise HTTPException(
                status_code=422,
                detail="rating must be +1 (thumbs up) or -1 (thumbs down)",
            )

        feedback_id = await persistent_data_manager.save_user_feedback(
            interaction_id=request.interaction_id,
            rating=request.rating,
            comment=request.comment,
        )

        if feedback_id < 0:
            raise HTTPException(
                status_code=500, detail="Failed to persist feedback"
            )

        logger.info(
            f"Feedback recorded: interaction={request.interaction_id} "
            f"rating={request.rating} feedback_id={feedback_id}"
        )

        return FeedbackResponse(
            feedback_id=feedback_id,
            interaction_id=request.interaction_id,
            rating=request.rating,
            timestamp=datetime.now(),
            message="Feedback recorded. Thank you!",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
