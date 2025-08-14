"""
GitHub integration for the self-improving AI agent.
Allows the agent to access its own repository and create pull requests with improvements.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

from evolving_agent.utils.config import config
from evolving_agent.utils.logging import setup_logger

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
        
        if not self.github_token:
            logger.warning("GitHub token not provided. Some features will be unavailable.")
        
        if not self.repo_name:
            logger.warning("GitHub repository name not provided. Remote operations will be unavailable.")
    
    async def initialize(self) -> bool:
        """
        Initialize GitHub client and repository connections.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize GitHub client
            if self.github_token:
                self.github_client = Github(self.github_token)
                logger.info("GitHub client initialized")
                
                # Get repository
                if self.repo_name:
                    self.repository = self.github_client.get_repo(self.repo_name)
                    logger.info(f"Connected to repository: {self.repo_name}")
            
            # Initialize local repository
            if os.path.exists(os.path.join(self.local_repo_path, ".git")):
                self.local_repo = git.Repo(self.local_repo_path)
                logger.info(f"Local repository initialized: {self.local_repo_path}")
            else:
                logger.warning("Local repository not found. Git operations will be limited.")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GitHub integration: {e}")
            return False
    
    async def get_repository_info(self) -> Dict[str, Any]:
        """
        Get information about the repository.
        
        Returns:
            Dictionary with repository information
        """
        try:
            if not self.repository:
                return {"error": "Repository not connected"}
            
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
            
            logger.info(f"Retrieved repository info for {repo_info['full_name']}")
            return repo_info
            
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
        Create a branch with code improvements and submit a pull request.
        
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
            import subprocess

            for improvement in improvements:
                file_path = improvement.get("file_path")
                new_content = improvement.get("content")
                description = improvement.get("description", "AI-generated improvement")
                
                if not file_path or not new_content:
                    continue

                # Write the new content to the local file before linting
                abs_file_path = os.path.join(self.local_repo_path, file_path)
                try:
                    os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
                    with open(abs_file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except Exception as e:
                    logger.error(f"Failed to write file {abs_file_path} before linting: {e}")
                    continue

                # Run isort and black autofix
                lint_failed = False
                for cmd, tool in [
                    (["isort", abs_file_path], "isort"),
                    (["black", abs_file_path], "black"),
                ]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            logger.error(f"{tool} failed for {file_path}: {result.stderr.strip()}")
                            lint_failed = True
                            break
                    except Exception as e:
                        logger.error(f"Exception running {tool} on {file_path}: {e}")
                        lint_failed = True
                        break

                if lint_failed:
                    logger.warning(f"Skipping commit for {file_path} due to linting failure.")
                    continue

                # Run flake8 and capture linting messages
                flake8_output = ""
                try:
                    flake8_cmd = ["flake8", abs_file_path]
                    flake8_proc = subprocess.run(flake8_cmd, capture_output=True, text=True)
                    flake8_output = flake8_proc.stdout.strip() + ("\n" + flake8_proc.stderr.strip() if flake8_proc.stderr else "")
                except Exception as e:
                    logger.error(f"Exception running flake8 on {file_path}: {e}")
                    flake8_output = f"flake8 execution error: {e}"

                # Read back the possibly modified content after linting
                try:
                    with open(abs_file_path, "r", encoding="utf-8") as f:
                        linted_content = f.read()
                except Exception as e:
                    logger.error(f"Failed to read linted file {abs_file_path}: {e}")
                    continue

                commit_message = f"AI Improvement: {description}"
                
                update_result = await self.update_file(
                    file_path=file_path,
                    new_content=linted_content,
                    commit_message=commit_message,
                    branch=branch_name
                )
                
                if "error" not in update_result:
                    updated_files.append({
                        "file_path": file_path,
                        "description": description,
                        "commit_sha": update_result.get("commit_sha"),
                        "flake8_lint": flake8_output
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
            
        except Exception as e:
            logger.error(f"Error creating improvement branch and PR: {e}")
            return {"error": str(e)}
    
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
