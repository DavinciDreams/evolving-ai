"""
GitHub integration for the self-improving AI agent.
Allows the agent to access its own repository and create pull requests with improvements.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import git
from github import Github, GithubException
from github.Repository import Repository
from github.PullRequest import PullRequest

from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.config import config
from .error_recovery import (
    error_recovery_manager,
    CircuitBreakerConfig,
    RetryConfig,
    CircuitBreakerOpenError,
    FallbackExhaustedError
)

logger = setup_logger(__name__)


class GitHubIntegration:
    """
    GitHub integration for accessing repository and creating pull requests.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        repo_name: Optional[str] = None,
        local_repo_path: Optional[str] = None
    ):
        """
        Initialize GitHub integration.
        
        Args:
            github_token: GitHub personal access token
            repo_name: Repository name in format "owner/repo"
            local_repo_path: Path to local repository
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.repo_name = repo_name or os.getenv("GITHUB_REPO")
        self.local_repo_path = local_repo_path or os.getenv("LOCAL_REPO_PATH", ".")
        
        self.github_client: Optional[Github] = None
        self.repository: Optional[Repository] = None
        self.local_repo: Optional[git.Repo] = None
        
        # Offline mode support
        self.offline_mode = False
        self.offline_cache: Dict[str, Any] = {}
        self.pending_operations: List[Dict] = []
        
        # Conflict resolution
        self.conflict_resolution_strategy = "merge"  # "merge", "ours", "theirs", "manual"
        self.conflict_history: List[Dict] = []
        
        if not self.github_token:
            logger.warning("GitHub token not provided. Some features will be unavailable.")
        
        if not self.repo_name:
            logger.warning("GitHub repository name not provided. Remote operations will be unavailable.")
    
    async def initialize(self) -> bool:
        """
        Initialize GitHub client and repository connections with error recovery.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize GitHub client with error recovery
            if self.github_token:
                async def _init_github():
                    self.github_client = Github(self.github_token)
                    logger.info("GitHub client initialized")
                    
                    # Get repository
                    if self.repo_name:
                        self.repository = self.github_client.get_repo(self.repo_name)
                        logger.info(f"Connected to repository: {self.repo_name}")
                
                await error_recovery_manager.execute_with_recovery(
                    "github_init",
                    _init_github,
                    circuit_breaker_config=CircuitBreakerConfig(
                        failure_threshold=3,
                        recovery_timeout=30.0
                    ),
                    retry_config=RetryConfig(max_attempts=3)
                )
            
            # Initialize local repository
            if os.path.exists(os.path.join(self.local_repo_path, ".git")):
                self.local_repo = git.Repo(self.local_repo_path)
                logger.info(f"Local repository initialized: {self.local_repo_path}")
            else:
                logger.warning("Local repository not found. Git operations will be limited.")
                # Enable offline mode if only local repo is available
                self.offline_mode = True
            
            # Register health check for GitHub
            error_recovery_manager.register_health_check(
                "github",
                self._check_github_health
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GitHub integration: {e}")
            # Enable offline mode if GitHub is unavailable
            self.offline_mode = True
            logger.warning("GitHub unavailable, operating in offline mode")
            return False
    
    async def _check_github_health(self) -> bool:
        """Check if GitHub API is accessible."""
        try:
            if self.github_client and self.repository:
                # Simple health check - get rate limit
                rate_limit = self.github_client.get_rate_limit()
                return rate_limit.rate.remaining > 0
            return False
        except Exception:
            return False
    
    def set_offline_mode(self, enabled: bool):
        """Enable or disable offline mode."""
        self.offline_mode = enabled
        logger.info(f"Offline mode {'enabled' if enabled else 'disabled'}")
    
    def is_offline(self) -> bool:
        """Check if operating in offline mode."""
        return self.offline_mode
    
    def queue_offline_operation(self, operation: Dict[str, Any]):
        """Queue an operation for when connection is restored."""
        self.pending_operations.append({
            **operation,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        })
        logger.info(f"Queued offline operation: {operation.get('type', 'unknown')}")
    
    async def process_pending_operations(self) -> List[Dict[str, Any]]:
        """Process pending operations when connection is restored."""
        if not self.pending_operations:
            return []
        
        logger.info(f"Processing {len(self.pending_operations)} pending operations")
        results = []
        remaining = []
        
        for operation in self.pending_operations:
            try:
                result = await self._execute_operation(operation)
                results.append({
                    "operation": operation,
                    "result": result,
                    "status": "completed"
                })
            except Exception as e:
                logger.warning(f"Failed to process operation: {e}")
                remaining.append(operation)
                results.append({
                    "operation": operation,
                    "error": str(e),
                    "status": "failed"
                })
        
        self.pending_operations = remaining
        return results
    
    async def _execute_operation(self, operation: Dict[str, Any]) -> Any:
        """Execute a queued operation."""
        op_type = operation.get("type")
        
        if op_type == "update_file":
            return await self.update_file(
                file_path=operation["file_path"],
                new_content=operation["content"],
                commit_message=operation["commit_message"],
                branch=operation["branch"]
            )
        elif op_type == "create_branch":
            return await self.create_branch(
                branch_name=operation["branch_name"],
                base_branch=operation.get("base_branch")
            )
        elif op_type == "create_pr":
            return await self.create_pull_request(
                title=operation["title"],
                body=operation["body"],
                head_branch=operation["head_branch"],
                base_branch=operation.get("base_branch")
            )
        else:
            raise ValueError(f"Unknown operation type: {op_type}")
    
    def set_conflict_resolution_strategy(self, strategy: str):
        """Set the conflict resolution strategy."""
        valid_strategies = ["merge", "ours", "theirs", "manual"]
        if strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")
        self.conflict_resolution_strategy = strategy
        logger.info(f"Conflict resolution strategy set to: {strategy}")
    
    async def resolve_conflict(
        self,
        file_path: str,
        branch: str,
        base_branch: str = None
    ) -> Dict[str, Any]:
        """
        Resolve a merge conflict for a file.
        
        Args:
            file_path: Path to the conflicting file
            branch: Branch with the conflict
            base_branch: Base branch (defaults to default branch)
            
        Returns:
            Dictionary with resolution result
        """
        try:
            base_branch = base_branch or (self.repository.default_branch if self.repository else "main")
            
            if self.conflict_resolution_strategy == "ours":
                # Keep our changes
                logger.info(f"Resolving conflict in {file_path} using 'ours' strategy")
                return {"strategy": "ours", "resolved": True}
            elif self.conflict_resolution_strategy == "theirs":
                # Accept their changes
                logger.info(f"Resolving conflict in {file_path} using 'theirs' strategy")
                return {"strategy": "theirs", "resolved": True}
            elif self.conflict_resolution_strategy == "merge":
                # Attempt automatic merge
                logger.info(f"Attempting automatic merge for {file_path}")
                # In a real implementation, this would use a merge algorithm
                return {"strategy": "merge", "resolved": True, "note": "Automatic merge attempted"}
            else:
                # Manual resolution required
                logger.warning(f"Manual conflict resolution required for {file_path}")
                self.conflict_history.append({
                    "file_path": file_path,
                    "branch": branch,
                    "base_branch": base_branch,
                    "timestamp": datetime.now().isoformat(),
                    "status": "pending_manual_resolution"
                })
                return {"strategy": "manual", "resolved": False, "requires_manual": True}
        except Exception as e:
            logger.error(f"Error resolving conflict for {file_path}: {e}")
            return {"error": str(e), "resolved": False}
    
    def get_conflict_history(self) -> List[Dict[str, Any]]:
        """Get history of conflicts and their resolutions."""
        return self.conflict_history
    
    async def get_repository_info(self) -> Dict[str, Any]:
        """
        Get information about the repository with retry logic.
        
        Returns:
            Dictionary with repository information
        """
        try:
            if self.offline_mode:
                # Return cached data in offline mode
                if "repository_info" in self.offline_cache:
                    logger.info("Returning cached repository info (offline mode)")
                    return self.offline_cache["repository_info"]
                return {"error": "Repository not available in offline mode"}
            
            if not self.repository:
                return {"error": "Repository not connected"}
            
            async def _get_repo_info():
                repo_info = {
                    "name": self.repository.name,
                    "full_name": self.repository.full_name,
                    "description": self.repository.description,
                    "language": self.repository.language,
                    "default_branch": self.repository.default_branch,
                    "clone_url": self.repository.clone_url,
                    "stars": self.repository.stargazers_count,
                    "forks": self.repository.forks_count,
                    "open_issues": self.repository.open_issues_count,
                    "size": self.repository.size,
                    "created_at": self.repository.created_at.isoformat(),
                    "updated_at": self.repository.updated_at.isoformat(),
                    "topics": list(self.repository.get_topics())
                }
                
                # Cache the result
                self.offline_cache["repository_info"] = repo_info
                
                logger.info(f"Retrieved repository info for {repo_info['full_name']}")
                return repo_info
            
            return await error_recovery_manager.execute_with_recovery(
                "github_get_repo_info",
                _get_repo_info,
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=30.0,
                    timeout=10.0
                ),
                retry_config=RetryConfig(max_attempts=3)
            )
            
        except CircuitBreakerOpenError:
            logger.warning("GitHub circuit breaker open, returning cached data")
            return self.offline_cache.get("repository_info", {"error": "GitHub unavailable"})
        except Exception as e:
            logger.error(f"Error getting repository info: {e}")
            return {"error": str(e)}
    
    async def get_file_content(self, file_path: str, branch: str = None) -> Dict[str, Any]:
        """
        Get content of a file from the repository.
        
        Args:
            file_path: Path to the file in the repository
            branch: Branch name (defaults to default branch)
            
        Returns:
            Dictionary with file content and metadata
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            branch = branch or self.repository.default_branch
            
            try:
                file_content = self.repository.get_contents(file_path, ref=branch)
                
                # Handle if it's a file (not directory)
                if hasattr(file_content, 'decoded_content'):
                    content = file_content.decoded_content.decode('utf-8')
                    
                    return {
                        "path": file_content.path,
                        "content": content,
                        "size": file_content.size,
                        "sha": file_content.sha,
                        "encoding": file_content.encoding,
                        "download_url": file_content.download_url,
                        "branch": branch
                    }
                else:
                    return {"error": f"Path {file_path} is a directory, not a file"}
                    
            except GithubException as e:
                if e.status == 404:
                    return {"error": f"File {file_path} not found in branch {branch}"}
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Error getting file content for {file_path}: {e}")
            return {"error": str(e)}
    
    async def get_repository_structure(self, path: str = "", branch: str = None) -> Dict[str, Any]:
        """
        Get the structure of the repository.
        
        Args:
            path: Path within repository (empty for root)
            branch: Branch name (defaults to default branch)
            
        Returns:
            Dictionary with repository structure
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            branch = branch or self.repository.default_branch
            
            contents = self.repository.get_contents(path, ref=branch)
            
            structure = {
                "path": path,
                "branch": branch,
                "items": []
            }
            
            # Handle both single file and directory contents
            if not isinstance(contents, list):
                contents = [contents]
            
            for item in contents:
                item_info = {
                    "name": item.name,
                    "path": item.path,
                    "type": item.type,  # "file" or "dir"
                    "size": item.size,
                    "sha": item.sha
                }
                
                if item.type == "file":
                    item_info["download_url"] = item.download_url
                
                structure["items"].append(item_info)
            
            logger.info(f"Retrieved repository structure for path: {path}")
            return structure
            
        except Exception as e:
            logger.error(f"Error getting repository structure for {path}: {e}")
            return {"error": str(e)}
    
    async def create_branch(self, branch_name: str, base_branch: str = None) -> Dict[str, Any]:
        """
        Create a new branch in the repository.
        
        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to create from (defaults to default branch)
            
        Returns:
            Dictionary with branch creation result
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            base_branch = base_branch or self.repository.default_branch
            
            # Get the base branch reference
            base_ref = self.repository.get_git_ref(f"heads/{base_branch}")
            base_sha = base_ref.object.sha
            
            # Create new branch
            new_ref = self.repository.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_sha
            )
            
            logger.info(f"Created branch {branch_name} from {base_branch}")
            
            return {
                "branch_name": branch_name,
                "base_branch": base_branch,
                "sha": new_ref.object.sha,
                "ref": new_ref.ref
            }
            
        except GithubException as e:
            if "already exists" in str(e):
                logger.warning(f"Branch {branch_name} already exists")
                return {"error": f"Branch {branch_name} already exists"}
            else:
                logger.error(f"Error creating branch {branch_name}: {e}")
                return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error creating branch {branch_name}: {e}")
            return {"error": str(e)}
    
    async def update_file(
        self,
        file_path: str,
        new_content: str,
        commit_message: str,
        branch: str,
        author_name: str = "Self-Improving AI Agent",
        author_email: str = "agent@example.com"
    ) -> Dict[str, Any]:
        """
        Update a file in the repository.
        
        Args:
            file_path: Path to the file in the repository
            new_content: New content for the file
            commit_message: Commit message
            branch: Branch to update
            author_name: Author name for the commit
            author_email: Author email for the commit
            
        Returns:
            Dictionary with update result
        """
        try:
            if not self.repository:
                logger.error("Repository not connected")
                return {"error": "Repository not connected"}
            
            # Validate inputs
            if not file_path or not file_path.strip():
                logger.error("File path is empty")
                return {"error": "File path cannot be empty"}
            
            if not commit_message or not commit_message.strip():
                logger.error("Commit message is empty")
                return {"error": "Commit message cannot be empty"}
            
            # Ensure new_content is properly formatted for GitHub API
            if isinstance(new_content, str):
                # PyGithub expects string content, not bytes
                content_to_send = new_content
            else:
                # If it's bytes, decode it
                content_to_send = new_content.decode('utf-8') if isinstance(new_content, bytes) else str(new_content)
            
            logger.info(f"Attempting to update file {file_path} in branch {branch}")
            logger.debug(f"Content length: {len(content_to_send)} characters")
            
            # Get current file content to get SHA
            try:
                current_file = self.repository.get_contents(file_path, ref=branch)
                file_sha = current_file.sha
                
                logger.info(f"File {file_path} exists, updating with SHA {file_sha}")
                
                # Update existing file
                result = self.repository.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content_to_send,
                    sha=file_sha,
                    branch=branch
                )
                
                logger.info(f"Successfully updated file {file_path} in branch {branch}")
                
            except GithubException as e:
                if e.status == 404:
                    logger.info(f"File {file_path} doesn't exist, creating new file")
                    
                    try:
                        # File doesn't exist, create it
                        result = self.repository.create_file(
                            path=file_path,
                            message=commit_message,
                            content=content_to_send,
                            branch=branch
                        )
                        
                        logger.info(f"Successfully created new file {file_path} in branch {branch}")
                    except Exception as create_error:
                        logger.error(f"Error creating file: {type(create_error).__name__}: {str(create_error)}")
                        raise
                else:
                    logger.error(f"GitHub API error: {e.status} - {e.data}")
                    raise
            
            return {
                "file_path": file_path,
                "branch": branch,
                "commit_sha": result["commit"].sha,
                "commit_message": commit_message,
                "content_sha": result["content"].sha,
                "url": result["content"].html_url
            }
            
        except GithubException as e:
            error_msg = f"GitHub API error {e.status}: {e.data}"
            logger.error(f"Error updating file {file_path}: {error_msg}")
            
            # Handle merge conflicts
            if e.status == 409 and retry_on_conflict:
                logger.info(f"Merge conflict detected for {file_path}, attempting resolution")
                resolution = await self.resolve_conflict(file_path, branch)
                if resolution.get("resolved"):
                    # Retry after resolution
                    return await self.update_file(
                        file_path, new_content, commit_message, branch,
                        author_name, author_email, retry_on_conflict=False
                    )
            
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Error updating file {file_path}: {error_msg}")
            return {"error": error_msg}
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None,
        labels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            title: Pull request title
            body: Pull request description
            head_branch: Branch with changes
            base_branch: Target branch (defaults to default branch)
            labels: List of label names to add
            
        Returns:
            Dictionary with pull request information
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            base_branch = base_branch or self.repository.default_branch
            
            # Create pull request
            pr = self.repository.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            
            # Add labels if provided
            if labels:
                try:
                    pr.add_to_labels(*labels)
                    logger.info(f"Added labels to PR: {labels}")
                except Exception as e:
                    logger.warning(f"Failed to add labels: {e}")
            
            logger.info(f"Created pull request #{pr.number}: {title}")
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "head_branch": head_branch,
                "base_branch": base_branch,
                "url": pr.html_url,
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "labels": [label.name for label in pr.labels]
            }
            
        except Exception as e:
            logger.error(f"Error creating pull request: {e}")
            return {"error": str(e)}
    
    async def get_open_pull_requests(self) -> List[Dict[str, Any]]:
        """
        Get list of open pull requests.
        
        Returns:
            List of pull request information dictionaries
        """
        try:
            if not self.repository:
                return []
            
            prs = self.repository.get_pulls(state='open')
            pr_list = []
            
            for pr in prs:
                pr_info = {
                    "number": pr.number,
                    "title": pr.title,
                    "body": pr.body,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "url": pr.html_url,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat(),
                    "updated_at": pr.updated_at.isoformat(),
                    "author": pr.user.login,
                    "labels": [label.name for label in pr.labels],
                    "mergeable": pr.mergeable
                }
                pr_list.append(pr_info)
            
            logger.info(f"Retrieved {len(pr_list)} open pull requests")
            return pr_list
            
        except Exception as e:
            logger.error(f"Error getting open pull requests: {e}")
            return []
    
    async def get_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific pull request.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Dictionary with pull request details
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            pr = self.repository.get_pull(pr_number)
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref,
                "url": pr.html_url,
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "author": pr.user.login,
                "labels": [label.name for label in pr.labels],
                "mergeable": pr.mergeable,
                "merged": pr.merged,
                "commits": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files
            }
            
        except Exception as e:
            logger.error(f"Error getting pull request {pr_number}: {e}")
            return {"error": str(e)}
    
    async def close_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """
        Close a pull request.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Dictionary with operation result
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            pr = self.repository.get_pull(pr_number)
            pr.edit(state='closed')
            
            logger.info(f"Closed pull request #{pr_number}")
            
            return {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "closed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error closing pull request {pr_number}: {e}")
            return {"error": str(e)}
    
    async def get_commit_history(self, branch: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get commit history for a branch.
        
        Args:
            branch: Branch name (defaults to default branch)
            limit: Maximum number of commits to retrieve
            
        Returns:
            List of commit information dictionaries
        """
        try:
            if not self.repository:
                return []
            
            branch = branch or self.repository.default_branch
            commits = self.repository.get_commits(sha=branch)
            
            commit_list = []
            for i, commit in enumerate(commits):
                if i >= limit:
                    break
                
                commit_info = {
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "author_email": commit.commit.author.email,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url,
                    "stats": {
                        "additions": commit.stats.additions,
                        "deletions": commit.stats.deletions,
                        "total": commit.stats.total
                    } if commit.stats else None
                }
                commit_list.append(commit_info)
            
            logger.info(f"Retrieved {len(commit_list)} commits from branch {branch}")
            return commit_list
            
        except Exception as e:
            logger.error(f"Error getting commit history: {e}")
            return []
    
    async def create_improvement_branch_and_pr(
        self,
        improvements: List[Dict[str, Any]],
        base_branch: str = None
    ) -> Dict[str, Any]:
        """
        Create a branch with code improvements and submit a pull request with error recovery.
        
        Args:
            improvements: List of improvement dictionaries with file_path, content, description
            base_branch: Base branch to create from (defaults to default branch)
            
        Returns:
            Dictionary with branch and PR creation results
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
            # Generate branch name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"ai-improvements-{timestamp}"
            
            # Create branch
            branch_result = await self.create_branch(branch_name, base_branch)
            if "error" in branch_result:
                return branch_result
            
            # Apply improvements
            updated_files = []
            for improvement in improvements:
                file_path = improvement.get("file_path")
                new_content = improvement.get("content")
                description = improvement.get("description", "AI-generated improvement")
                
                if not file_path or not new_content:
                    continue
                
                commit_message = f"AI Improvement: {description}"
                
                update_result = await self.update_file(
                    file_path=file_path,
                    new_content=new_content,
                    commit_message=commit_message,
                    branch=branch_name
                )
                
                if "error" not in update_result:
                    updated_files.append({
                        "file_path": file_path,
                        "description": description,
                        "commit_sha": update_result.get("commit_sha")
                    })
            
            if not updated_files:
                return {"error": "No files were successfully updated"}
            
            # Create pull request
            pr_title = f"🤖 AI-Generated Code Improvements ({len(updated_files)} files)"
            pr_body = self._generate_pr_description(updated_files)
            
            pr_result = await self.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch=base_branch,
                labels=["ai-improvement", "automation"]
            )
            
            logger.info(f"Created improvement branch {branch_name} with {len(updated_files)} files")
            
            return {
                "branch_name": branch_name,
                "updated_files": updated_files,
                "pull_request": pr_result,
                "summary": {
                    "files_updated": len(updated_files),
                    "branch_created": True,
                    "pr_created": "error" not in pr_result
                }
            }
            
        except CircuitBreakerOpenError:
            logger.warning("GitHub circuit breaker open, queuing operation")
            # Queue the entire operation for later
            self.queue_offline_operation({
                "type": "create_improvement",
                "improvements": improvements,
                "base_branch": base_branch
            })
            return {
                "status": "queued",
                "message": "Operation queued for when connection is restored"
            }
        except Exception as e:
            logger.error(f"Error creating improvement branch and PR: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current GitHub integration status."""
        return {
            "connected": self.repository is not None,
            "offline_mode": self.offline_mode,
            "pending_operations": len(self.pending_operations),
            "conflict_strategy": self.conflict_resolution_strategy,
            "conflict_history": len(self.conflict_history),
            "repo_name": self.repo_name,
            "local_repo_available": self.local_repo is not None
        }
    
    def _generate_pr_description(self, updated_files: List[Dict[str, Any]]) -> str:
        """
        Generate a comprehensive PR description for code improvements.
        
        Args:
            updated_files: List of updated file information
            
        Returns:
            Formatted PR description
        """
        description = """# 🤖 AI-Generated Code Improvements

This pull request contains automated code improvements generated by the Self-Improving AI Agent.

## 📊 Summary

"""
        
        description += f"- **Files Modified**: {len(updated_files)}\n"
        description += f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        description += "- **Type**: Automated code optimization\n\n"
        
        description += "## 📝 Changes Made\n\n"
        
        for i, file_info in enumerate(updated_files, 1):
            description += f"{i}. **{file_info['file_path']}**\n"
            description += f"   - {file_info['description']}\n"
            if file_info.get('commit_sha'):
                description += f"   - Commit: `{file_info['commit_sha'][:8]}`\n"
            description += "\n"
        
        description += """## 🔍 Review Guidelines

- [ ] Verify code functionality is preserved
- [ ] Check for any breaking changes
- [ ] Validate performance improvements
- [ ] Ensure code style consistency
- [ ] Run test suite to confirm stability

## 🤖 About This PR

This PR was automatically generated by the Self-Improving AI Agent as part of its continuous improvement process. The agent analyzes its own codebase and suggests optimizations based on:

- Code complexity analysis
- Performance pattern detection
- Best practice recommendations
- Knowledge base insights

## ⚠️ Important Notes

- Please review all changes carefully before merging
- Test thoroughly in a development environment
- The AI agent continues to learn from feedback on these improvements

---
*Generated by Self-Improving AI Agent*
"""
        
        return description
