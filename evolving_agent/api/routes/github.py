"""Private read-only GitHub dashboard and explicit legacy retirement responses."""

from fastapi import APIRouter, Depends, HTTPException, Query

import evolving_agent.utils.app_state as state
from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.integrations.github_reads import GitHubNotConnectedError
from evolving_agent.utils.deps import verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import GitHubStatus, RepositoryInfo
from evolving_agent.utils.secret_redaction import redact_value

logger = setup_logger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


def _reader():
    reader = getattr(state.github_modifier, "read_service", None)
    if reader is None:
        raise HTTPException(503, "GitHub read integration unavailable")
    return reader


async def _read(operation):
    try:
        return await operation()
    except GitHubNotConnectedError:
        raise HTTPException(404, "GitHub repository not connected") from None
    except RuntimeBusyError:
        raise HTTPException(
            409, "A GitHub read is still active; check status before retrying"
        ) from None
    except TimeoutError:
        raise HTTPException(504, "GitHub read exceeded its deadline") from None
    except HTTPException:
        raise
    except Exception:
        logger.warning("GitHub read unavailable")
        raise HTTPException(503, "GitHub read unavailable") from None


@router.get("/github/status", response_model=GitHubStatus, tags=["GitHub"])
async def get_github_status():
    """Connection status from the bounded read-only snapshot."""
    if state.github_modifier is None:
        return GitHubStatus(
            github_connected=False,
            repository_name=None,
            local_repo_available=False,
            auto_pr_enabled=False,
            open_prs_count=0,
        )
    return await _read(_reader().status)


@router.get("/github/repository", response_model=RepositoryInfo, tags=["GitHub"])
async def get_repository_info():
    return await _read(_reader().repository_info)


@router.get("/github/pull-requests", tags=["GitHub"])
async def get_pull_requests():
    """At most 50 open PR summaries; total_count identifies clipped results."""
    return await _read(_reader().pull_requests)


@router.get("/github/commits", tags=["GitHub"])
async def get_recent_commits(limit: int = Query(10, ge=1, le=50)):
    return await _read(lambda: _reader().commits(limit))


@router.get("/github/improvement-history", tags=["GitHub"])
async def get_improvement_history(limit: int = Query(25, ge=1, le=100)):
    """Local historical records, not a trigger for analysis or publication."""
    if state.github_modifier is None:
        raise HTTPException(503, "GitHub integration unavailable")
    try:
        history = state.github_modifier.get_improvement_history()
        if not isinstance(history, list):
            raise ValueError("Invalid historical records")
        bounded = redact_value(history[-limit:])[0]
        return {"improvement_history": bounded, "count": len(bounded)}
    except Exception:
        logger.warning("GitHub improvement history unavailable")
        raise HTTPException(503, "GitHub improvement history unavailable") from None


@router.post(
    "/github/demo-pr",
    tags=["GitHub"],
    deprecated=True,
    responses={410: {"description": "Legacy direct publication is retired"}},
)
async def create_demo_pr():
    """Retired: demo labels do not authorize unbounded repository changes."""
    raise HTTPException(
        410,
        "Legacy demo PR publication is retired. Review and publish repository "
        "changes through a separately authorized workflow.",
    )


@router.post(
    "/github/issue",
    tags=["GitHub"],
    deprecated=True,
    responses={410: {"description": "Legacy direct issue publication is retired"}},
)
async def create_github_issue():
    """Retired: receiving an app event is not permission to publish an issue."""
    raise HTTPException(
        410,
        "Legacy direct issue publication is retired. Submit signed app events to "
        "the connector review inbox; issue publication requires a separately authorized workflow.",
    )
