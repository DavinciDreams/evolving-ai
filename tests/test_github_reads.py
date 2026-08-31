"""No GitHub client, credentials or network; exercise the actual threaded bridge."""

import asyncio
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.integrations.github_reads import (
    GitHubNotConnectedError,
    GitHubReadError,
    GitHubReadService,
)


class Page(list):
    @property
    def totalCount(self):
        return len(self)


def repository(size=2):
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    pulls = Page(
        SimpleNamespace(
            number=i, title=f"PR {i}", state="open", created_at=now, updated_at=now
        )
        for i in range(size)
    )
    commits = [
        SimpleNamespace(
            sha=str(i),
            commit=SimpleNamespace(
                message=f"Change {i}", author=SimpleNamespace(name="Operator", date=now)
            ),
        )
        for i in range(size)
    ]
    return SimpleNamespace(
        name="katbot",
        full_name="example/katbot",
        description="Fixture",
        language="Python",
        stargazers_count=1,
        forks_count=2,
        open_issues_count=3,
        default_branch="main",
        get_pulls=Mock(return_value=pulls),
        get_commits=Mock(return_value=commits),
    )


def service(repo=None, **kwargs):
    return GitHubReadService(
        SimpleNamespace(repository=repo, local_repo=None), **kwargs
    )


async def test_concurrent_dashboard_reads_coalesce_and_cache_deep_copies():
    repo = repository()
    reader = service(repo)
    status, info, prs, commits = await asyncio.gather(
        reader.status(),
        reader.repository_info(),
        reader.pull_requests(),
        reader.commits(),
    )
    assert status["github_connected"] and status["auto_pr_enabled"] is False
    assert status["open_prs_count"] == 2 and info["full_name"] == "example/katbot"
    assert prs["count"] == 2 and commits["count"] == 2
    repo.get_pulls.assert_called_once_with(state="open")
    repo.get_commits.assert_called_once_with(sha="main")
    prs["open_pull_requests"][0]["title"] = "changed caller copy"
    assert (await reader.pull_requests())["open_pull_requests"][0]["title"] == "PR 0"
    assert reader.runtime.completed == 1
    assert await reader.close()
    with pytest.raises(GitHubReadError):
        await reader.status()


async def test_counts_are_truthful_and_rows_and_credentials_are_bounded():
    repo = repository(70)
    repo.get_pulls.return_value[0].title = "api_key=private-value"
    repo.get_commits.return_value[0].commit.message = "x" * 9000
    reader = service(repo)
    prs = await reader.pull_requests()
    assert prs["count"] == 50 and prs["total_count"] == 70 and prs["truncated"] is True
    assert "private-value" not in str(prs)
    commits = await reader.commits(3)
    assert (
        commits["count"] == 3 and len(commits["recent_commits"][0]["message"]) == 4096
    )
    assert "author_email" not in str(commits)
    await reader.close()


async def test_provider_failure_is_not_empty_success_or_raw_diagnostic():
    repo = repository()
    repo.get_pulls.side_effect = RuntimeError("private-provider-body")
    reader = service(repo)
    with pytest.raises(GitHubReadError) as caught:
        await reader.pull_requests()
    assert "private-provider-body" not in str(caught.value)
    assert reader._cache is None
    await reader.close()


async def test_expired_cache_cannot_hide_new_read_failure():
    clock = [0.0]
    repo = repository()
    reader = service(repo, clock=lambda: clock[0], cache_seconds=1)
    assert (await reader.pull_requests())["count"] == 2
    clock[0] = 2
    repo.get_pulls.side_effect = RuntimeError("provider now failed")
    with pytest.raises(GitHubReadError):
        await reader.pull_requests()
    await reader.close()


async def test_disconnected_status_is_explicit_and_history_returns_not_connected():
    reader = service()
    assert (await reader.status())["github_connected"] is False
    for operation in (reader.repository_info, reader.pull_requests, reader.commits):
        with pytest.raises(GitHubNotConnectedError):
            await operation()
    await reader.close()


@pytest.mark.parametrize("limit", [0, -1, 51, True, 1.5, "10"])
async def test_invalid_commit_limits_do_not_invoke_sdk(limit):
    repo = repository()
    reader = service(repo)
    with pytest.raises(ValueError):
        await reader.commits(limit)
    repo.get_pulls.assert_not_called()
    await reader.close()


async def test_timeout_keeps_single_worker_lease_and_does_not_block_event_loop():
    repo = repository()
    gate = threading.Event()
    entered = threading.Event()
    worker_threads = []

    def slow_read(**_):
        worker_threads.append(threading.get_ident())
        entered.set()
        gate.wait(2)
        return Page()

    repo.get_pulls.side_effect = slow_read
    reader = service(repo, timeout=0.02)
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(reader.status(), timeout=0.5)
        assert entered.is_set() and reader.runtime.status()["active_workers"] == 1
        assert worker_threads[0] != threading.get_ident()
        for _ in range(4):
            with pytest.raises(RuntimeBusyError):
                await reader.status()
        assert repo.get_pulls.call_count == 1
    finally:
        gate.set()
        await reader.close()


async def test_cancelled_waiter_does_not_cancel_shared_snapshot():
    repo = repository()
    gate, entered = threading.Event(), threading.Event()

    def slow_read(**_):
        entered.set()
        gate.wait(2)
        return Page()

    repo.get_pulls.side_effect = slow_read
    reader = service(repo)
    first = asyncio.create_task(reader.status())
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert reader.runtime.busy
        second = asyncio.create_task(reader.commits())
        gate.set()
        assert (await second)["count"] == 2
        assert repo.get_pulls.call_count == 1
    finally:
        gate.set()
        await reader.close()
