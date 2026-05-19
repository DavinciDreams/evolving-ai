"""Shared FastAPI dependencies — import from here to avoid circular imports."""

import os

import evolving_agent.utils.app_state as state
from evolving_agent.core.agent import SelfImprovingAgent
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

# Optional API key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Validate the X-API-Key header on protected endpoints.

    Auth is disabled when the API_KEY environment variable is not set or empty,
    preserving backward compatibility for deployments that do not set the key.
    """
    configured_key = os.getenv("API_KEY", "")
    if not configured_key:
        return  # Auth disabled — no key configured
    if api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_agent() -> SelfImprovingAgent:
    """Dependency to get the agent instance from shared application state."""
    if state.agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return state.agent
