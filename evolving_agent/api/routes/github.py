"""GitHub endpoints: /github/*."""

import evolving_agent.utils.app_state as state
from fastapi import APIRouter, Depends, HTTPException

from evolving_agent.utils.config import config
from evolving_agent.utils.deps import verify_api_key

from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import (
    CreateIssueRequest,
    CreateIssueResponse,
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
        if not state.github_modifier or not state.github_modifier.github_integration.repository:
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
        if not state.github_modifier or not state.github_modifier.github_integration.repository:
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
        if not state.github_modifier or not state.github_modifier.github_integration.repository:
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


@router.post("/github/demo-pr", tags=["GitHub"], dependencies=[Depends(verify_api_key)])
async def create_demo_pr():
    """
    Create a demonstration pull request with documentation improvements.

    This is a safe demo endpoint that creates a PR with README enhancements.
    """
    try:
        if not config.enable_self_modification:
            raise HTTPException(
                status_code=403, detail="Self-modification is disabled"
            )

        if not state.github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        if not state.github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        logger.info("Creating demonstration pull request...")

        pr_result = await state.github_modifier.create_documentation_improvement_pr()

        if "error" in pr_result:
            raise HTTPException(status_code=500, detail=pr_result["error"])

        return {
            "message": "Demo pull request created successfully",
            "pr_number": pr_result.get("pr_number"),
            "pr_url": pr_result.get("pr_url"),
            "branch_name": pr_result.get("branch_name"),
            "files_updated": pr_result.get("files_updated", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating demo PR: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating demo PR: {str(e)}")


@router.post("/github/issue", response_model=CreateIssueResponse, tags=["GitHub"], dependencies=[Depends(verify_api_key)])
async def create_github_issue(request: CreateIssueRequest):
    """
    Create a new GitHub issue.

    This endpoint allows creating GitHub issues programmatically, useful for
    integrating with Discord feature requests or other external systems.

    The issue will be created in the configured GitHub repository with the
    provided title, description, and optional labels.

    Note: Assignees requires proper GitHub permissions and the users must
    have write access to the repository.
    """
    try:
        if not state.github_modifier or not state.github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=503,
                detail="GitHub integration not available or repository not connected"
            )

        logger.info(f"Creating GitHub issue: {request.title}")

        # Create the issue using the GitHub integration
        issue_result = await state.github_modifier.github_integration.create_issue(
            title=request.title,
            body=request.description,
            labels=request.labels
        )

        # Check for errors in the result
        if "error" in issue_result:
            logger.error(f"Failed to create issue: {issue_result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create issue: {issue_result['error']}"
            )

        # Handle assignees if provided
        if request.assignees:
            try:
                issue_number = issue_result.get("issue_number")
                if issue_number:
                    repository = state.github_modifier.github_integration.repository
                    issue = repository.get_issue(issue_number)
                    # Add assignees to the issue
                    issue.add_to_assignees(*request.assignees)
                    logger.info(f"Added assignees {request.assignees} to issue #{issue_number}")
            except Exception as e:
                logger.warning(f"Failed to add assignees to issue: {e}")
                # Don't fail the request if assignees fail, just log a warning

        logger.info(f"Successfully created issue #{issue_result['issue_number']}")

        return CreateIssueResponse(
            issue_number=issue_result["issue_number"],
            issue_url=issue_result["url"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating GitHub issue: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating GitHub issue: {str(e)}"
        )
