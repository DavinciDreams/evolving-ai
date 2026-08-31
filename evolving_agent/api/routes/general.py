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
        memory_count = None
        if hasattr(current_agent, "memory"):
            try:
                memory_stats = await current_agent.memory.get_memory_stats()
                value = memory_stats.get("total_memories")
                memory_count = value if type(value) is int and value >= 0 else None
            except Exception:
                memory_count = None

        # Get knowledge count
        knowledge_count = None
        if hasattr(current_agent, "knowledge_base"):
            try:
                knowledge_count = len(current_agent.knowledge_base.knowledge)
            except Exception:
                knowledge_count = None

        return AgentStatus(
            is_initialized=current_agent.initialized,
            session_id=current_agent.session_id,
            total_interactions=current_agent.interaction_count,
            memory_count=memory_count,
            knowledge_count=knowledge_count,
            uptime="Active",
        )
    except Exception as e:
        logger.error("Agent status unavailable: {}", type(e).__name__)
        raise HTTPException(
            status_code=503, detail="Agent status is unavailable"
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
