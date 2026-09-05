"""Read-only legacy history; unsafe synchronous improvement routes are retired."""

from fastapi import APIRouter, Depends, HTTPException, Query

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.deps import get_agent, verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.secret_redaction import redact_value

logger = setup_logger(__name__)
router = APIRouter()


@router.post(
    "/analyze",
    tags=["Self-Improvement"],
    deprecated=True,
    dependencies=[Depends(verify_api_key)],
    responses={410: {"description": "Legacy unbounded analysis is retired"}},
)
async def analyze_code():
    """Retired: use measured steward evaluation with trusted benchmark fixtures.

    This route deliberately does not parse a body, invoke the legacy analyzer,
    or fabricate evaluation scores. Code analysis is not silently represented as
    equivalent to measured response-strategy adaptation.
    """
    raise HTTPException(
        status_code=410,
        detail="Legacy synchronous analysis is retired. Use /steward/status and "
        "/steward/improvement/evaluate with explicit benchmark fixtures for measured adaptation.",
    )


@router.get(
    "/analysis-history",
    tags=["Self-Improvement"],
    dependencies=[Depends(verify_api_key)],
)
async def get_analysis_history(
    limit: int = Query(default=10, ge=1, le=100),
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """Read bounded historical records only; no new analysis or model calls."""
    try:
        analyzer = getattr(current_agent, "code_analyzer", None)
        if analyzer is None:
            return []
        history = analyzer.get_analysis_history()
        if not isinstance(history, list):
            raise ValueError("Invalid historical record shape")
        return redact_value(history[-limit:])[0]
    except Exception as exc:
        logger.error("Legacy analysis history unavailable: {}", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Analysis history is unavailable"
        ) from None


@router.post(
    "/self-improve",
    tags=["Self-Improvement"],
    deprecated=True,
    dependencies=[Depends(verify_api_key)],
    responses={410: {"description": "Legacy direct code modification is retired"}},
)
async def create_code_improvements():
    """Retired: never bypass the bounded steward to modify code or publish a PR."""
    raise HTTPException(
        status_code=410,
        detail="Legacy direct code modification and automatic PR creation are retired. "
        "Use /steward/improvement/evaluate, /steward/improvement/promote, and "
        "/steward/improvement/rollback for measured response-strategy adaptation; "
        "repository publication remains separate.",
    )
