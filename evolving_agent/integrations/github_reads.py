"""Bounded read-only PyGithub projection; never invokes legacy mutation helpers.

The SDK is synchronous, including lazy object attributes. One shielded snapshot
worker serves concurrent dashboard reads. A timed-out thread keeps its lease
until it exits, so polling cannot accumulate replacement threads.
"""

from __future__ import annotations

import asyncio
import copy
import time
from itertools import islice

from evolving_agent.core.runtime import AgentRuntime, RuntimeBusyError
from evolving_agent.utils.secret_redaction import redact_text


class GitHubReadError(RuntimeError):
    """A provider read failed; never expose provider diagnostics."""


class GitHubNotConnectedError(GitHubReadError):
    """No repository was configured/connected."""


def _text(value, limit=4096):
    if value is None:
        return None
    if not isinstance(value, str):
        raise GitHubReadError("Invalid GitHub response")
    return redact_text(value)[0][:limit]


def _date(value):
    return value.isoformat() if value is not None else None


class GitHubReadService:
    MAX_ROWS = 50

    def __init__(
        self, integration, *, timeout=15.0, cache_seconds=15.0, clock=time.monotonic
    ):
        if not 0 <= cache_seconds <= 60:
            raise ValueError("Invalid GitHub read cache lifetime")
        self.integration = integration
        self.runtime = AgentRuntime(timeout=timeout, max_jobs=1)
        self.cache_seconds = cache_seconds
        self.clock = clock
        self._cache = None
        self._expires = 0.0
        self._pending = None
        self._closed = False

    def _read_snapshot(self):
        repo = self.integration.repository
        local = self.integration.local_repo is not None
        if repo is None:
            return {
                "status": {
                    "github_connected": False,
                    "repository_name": None,
                    "local_repo_available": local,
                    "auto_pr_enabled": False,
                    "open_prs_count": 0,
                },
                "repository": None,
                "pull_requests": [],
                "commits": [],
            }
        # Every lazy SDK property access stays in this one worker thread.
        repository = {
            "name": _text(repo.name, 256),
            "full_name": _text(repo.full_name, 512),
            "description": _text(repo.description),
            "language": _text(repo.language, 128),
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "open_issues": repo.open_issues_count,
        }
        pulls = repo.get_pulls(state="open")
        total = pulls.totalCount
        if type(total) is not int or total < 0:
            raise GitHubReadError("Invalid GitHub count")
        pull_requests = [
            {
                "number": pr.number,
                "title": _text(pr.title, 512),
                "state": _text(pr.state, 32),
                "created_at": _date(pr.created_at),
                "updated_at": _date(pr.updated_at),
            }
            for pr in islice(pulls, self.MAX_ROWS)
        ]
        commits = []
        for item in islice(repo.get_commits(sha=repo.default_branch), self.MAX_ROWS):
            commit = item.commit
            commits.append(
                {
                    "sha": _text(item.sha, 64),
                    "message": _text(commit.message),
                    "author": _text(commit.author.name, 256),
                    "date": _date(commit.author.date),
                }
            )
        return {
            "status": {
                "github_connected": True,
                "repository_name": repository["full_name"],
                "local_repo_available": local,
                "auto_pr_enabled": False,
                "open_prs_count": total,
            },
            "repository": repository,
            "pull_requests": pull_requests,
            "commits": commits,
        }

    async def _fetch(self):
        try:
            snapshot = await self.runtime.run(
                lambda: self.runtime.run_sync(self._read_snapshot), kind="github_read"
            )
        except (RuntimeBusyError, TimeoutError, asyncio.CancelledError):
            raise
        except Exception:
            raise GitHubReadError("GitHub read unavailable") from None
        self._cache = snapshot
        self._expires = self.clock() + self.cache_seconds
        return snapshot

    async def snapshot(self):
        if self._closed:
            raise GitHubReadError("GitHub read service is closed")
        if self._cache is not None and self.clock() < self._expires:
            return copy.deepcopy(self._cache)
        if self._pending is None or self._pending.done():
            self._pending = asyncio.create_task(
                self._fetch(), name="katbot-github-read"
            )
            self._pending.add_done_callback(
                lambda task: None if task.cancelled() else task.exception()
            )
        return copy.deepcopy(await asyncio.shield(self._pending))

    async def status(self):
        return (await self.snapshot())["status"]

    async def _connected_snapshot(self):
        snapshot = await self.snapshot()
        if snapshot["repository"] is None:
            raise GitHubNotConnectedError("GitHub repository not connected")
        return snapshot

    async def repository_info(self):
        return (await self._connected_snapshot())["repository"]

    async def pull_requests(self):
        snapshot = await self._connected_snapshot()
        rows = snapshot["pull_requests"]
        return {
            "open_pull_requests": rows,
            "count": len(rows),
            "total_count": snapshot["status"]["open_prs_count"],
            "truncated": snapshot["status"]["open_prs_count"] > len(rows),
        }

    async def commits(self, limit=10):
        if type(limit) is not int or not 1 <= limit <= self.MAX_ROWS:
            raise ValueError("Commit limit must be between 1 and 50")
        rows = (await self._connected_snapshot())["commits"][:limit]
        return {"recent_commits": rows, "count": len(rows), "limit": limit}

    async def close(self):
        self._closed = True
        self._cache = None
        return await self.runtime.close()
