"""Shared FastAPI dependencies — import from here to avoid circular imports."""

import hmac

import evolving_agent.utils.app_state as state
from evolving_agent.core.agent import SelfImprovingAgent
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

# Optional API key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_HEADER = HTTPBearer(auto_error=False)


def _validate_project_key(supplied_key: str | None) -> None:
    """Validate project-steward credentials with secure production defaults."""
    from evolving_agent.utils.config import config

    if not config.api_auth_required:
        return
    configured_key = config.api_key
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Project authentication is required but not configured",
        )
    if not supplied_key or not hmac.compare_digest(supplied_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid or missing project credential")


def authenticate_request(request: Request) -> None:
    """Authenticate a raw request for central middleware enforcement."""
    supplied_key = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if not supplied_key and authorization.lower().startswith("bearer "):
        supplied_key = authorization[7:].strip()
    _validate_project_key(supplied_key)


async def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
    bearer: HTTPAuthorizationCredentials | None = Security(BEARER_HEADER),
):
    """Validate project access for explicitly protected route dependencies."""
    supplied_key = api_key or (bearer.credentials if bearer else None)
    _validate_project_key(supplied_key)


def get_agent() -> SelfImprovingAgent:
    """Dependency to get the agent instance from shared application state."""
    if state.agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return state.agent
