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


def authenticate_request(request: Request) -> dict:
    """Authenticate with a service key or an approved human Nostr session."""
    from evolving_agent.utils.config import config
    from evolving_agent.utils import nostr_auth

    if not config.api_auth_required:
        claims = {"sub": "auth-disabled", "auth_method": "disabled"}
        request.state.project_auth = claims
        return claims

    supplied_key = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if not supplied_key and authorization.lower().startswith("bearer "):
        supplied_key = authorization[7:].strip()
    if supplied_key:
        _validate_project_key(supplied_key)
        claims = {"sub": "project-api-key", "auth_method": "api_key"}
        request.state.project_auth = claims
        return claims

    try:
        claims = nostr_auth.verify_session(request)
    except nostr_auth.NostrSessionUnavailable as exc:
        raise HTTPException(503, "Nostr session store is unavailable") from exc
    if claims is not None:
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            nostr_auth.require_session_origin(request)
        request.state.project_auth = claims
        return claims

    if not config.api_key and not nostr_auth.enabled():
        raise HTTPException(
            status_code=503,
            detail="Project authentication is required but not configured",
        )
    raise HTTPException(status_code=401, detail="Invalid or missing project credential")


async def verify_api_key(
    request: Request,
    api_key: str = Security(API_KEY_HEADER),
    bearer: HTTPAuthorizationCredentials | None = Security(BEARER_HEADER),
):
    """Validate project access for legacy explicitly protected dependencies."""
    existing = getattr(request.state, "project_auth", None)
    if existing is not None:
        return existing
    supplied_key = api_key or (bearer.credentials if bearer else None)
    if supplied_key:
        _validate_project_key(supplied_key)
        return {"sub": "project-api-key", "auth_method": "api_key"}
    return authenticate_request(request)


def get_agent() -> SelfImprovingAgent:
    """Dependency to get the agent instance from shared application state."""
    if state.agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return state.agent
