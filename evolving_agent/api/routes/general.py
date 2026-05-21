"""General endpoints: /, /status, /health."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import evolving_agent.utils.app_state as state
from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import AgentStatus

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/", tags=["General"])
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Self-Improving AI Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/status",
    }


@router.get("/status", response_model=AgentStatus, tags=["General"])
async def get_status(current_agent: SelfImprovingAgent = Depends(get_agent)):
    """Get the current status of the agent."""
    try:
        # Get memory count
        memory_count = 0
        if hasattr(current_agent, "memory") and hasattr(
            current_agent.memory, "collection"
        ):
            try:
                memory_count = current_agent.memory.collection.count()
            except Exception:
                memory_count = 0

        # Get knowledge count
        knowledge_count = 0
        if hasattr(current_agent, "knowledge_base"):
            try:
                knowledge_count = len(current_agent.knowledge_base.knowledge)
            except Exception:
                knowledge_count = 0

        return AgentStatus(
            is_initialized=current_agent.initialized,
            session_id=current_agent.session_id,
            total_interactions=current_agent.interaction_count,
            memory_count=memory_count,
            knowledge_count=knowledge_count,
            uptime="Active",
        )
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting agent status: {str(e)}"
        )


@router.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agent_initialized": (
            state.agent is not None and state.agent.initialized if state.agent else False
        ),
        "github_available": state.github_modifier is not None,
    }
