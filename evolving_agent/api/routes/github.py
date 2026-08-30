"""GitHub endpoints: /github/*."""

from fastapi import APIRouter, Depends, HTTPException

import evolving_agent.utils.app_state as state
from evolving_agent.utils.deps import verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import (
    GitHubStatus,
    RepositoryInfo,
)

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/github/status", response_model=GitHubStatus, tags=["GitHub"])
async def get_github_status():
    """
    Get GitHub integration status.

    Returns information about GitHub connection, repository status, and configuration.
    """
    try:
        if not state.github_modifier:
            return GitHubStatus(
                github_connected=False,
                repository_name=None,
                local_repo_available=False,
                auto_pr_enabled=False,
                open_prs_count=0,
            )

        # Get repository status
        repo_status = await state.github_modifier.get_repository_status()

        return GitHubStatus(
            github_connected=repo_status.get("github_connected", False),
            repository_name=repo_status.get("repository_info", {}).get("full_name"),
            local_repo_available=repo_status.get("local_repo_available", False),
            auto_pr_enabled=repo_status.get("auto_pr_enabled", False),
            open_prs_count=len(repo_status.get("open_pull_requests", [])),
        )

    except Exception as e:
        logger.error(f"Error getting GitHub status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting GitHub status: {str(e)}"
        )


@router.get("/github/repository", response_model=RepositoryInfo, tags=["GitHub"])
async def get_repository_info():
    """
    Get information about the connected GitHub repository.
    """
    try:
        if (
            not state.github_modifier
            or not state.github_modifier.github_integration.repository
        ):
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        repo_info = await state.github_modifier.github_integration.get_repository_info()

        if "error" in repo_info:
            raise HTTPException(status_code=500, detail=repo_info["error"])

        return RepositoryInfo(
            name=repo_info["name"],
            full_name=repo_info["full_name"],
            description=repo_info.get("description"),
            language=repo_info.get("language"),
            stars=repo_info["stars"],
            forks=repo_info["forks"],
            open_issues=repo_info["open_issues"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repository info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting repository info: {str(e)}"
        )


@router.get("/github/pull-requests", tags=["GitHub"])
async def get_pull_requests():
    """
    Get list of open pull requests in the repository.
    """
    try:
        if (
            not state.github_modifier
            or not state.github_modifier.github_integration.repository
        ):
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        prs = await state.github_modifier.github_integration.get_open_pull_requests()

        return {"open_pull_requests": prs, "count": len(prs)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pull requests: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting pull requests: {str(e)}"
        )


@router.get("/github/commits", tags=["GitHub"])
async def get_recent_commits(limit: int = 10):
    """
    Get recent commits from the repository.

    - **limit**: Maximum number of commits to retrieve (default: 10)
    """
    try:
        if (
            not state.github_modifier
            or not state.github_modifier.github_integration.repository
        ):
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        commits = await state.github_modifier.github_integration.get_commit_history(
            limit=limit
        )

        return {"recent_commits": commits, "count": len(commits)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent commits: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting recent commits: {str(e)}"
        )


@router.get("/github/improvement-history", tags=["GitHub"])
async def get_improvement_history():
    """
    Get history of automated improvements made by the AI agent.
    """
    try:
        if not state.github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        history = state.github_modifier.get_improvement_history()

        return {"improvement_history": history, "count": len(history)}

    except Exception as e:
        logger.error(f"Error getting improvement history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting improvement history: {str(e)}"
        )


@router.post(
    "/github/demo-pr",
    tags=["GitHub"],
    deprecated=True,
    dependencies=[Depends(verify_api_key)],
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
    dependencies=[Depends(verify_api_key)],
    responses={410: {"description": "Legacy direct issue publication is retired"}},
)
async def create_github_issue():
    """Retired: receiving an app event is not permission to publish an issue."""
    raise HTTPException(
        410,
        "Legacy direct issue publication is retired. Submit signed app events to "
        "the connector review inbox; issue publication requires a separately authorized workflow.",
    )
