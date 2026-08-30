"""
Tests for the tool system (local tools, safety, AI SDK integration).
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evolving_agent.core.tools import (
    BLOCKED_COMMANDS,
    is_command_safe,
    make_read_file_tool,
    make_list_files_tool,
    make_run_command_tool,
    make_search_web_tool,
    make_search_memory_tool,
    make_search_tpmjs_tool,
    make_execute_tpmjs_tool,
    make_create_tpmjs_tool,
    make_scratchpad_write_tool,
    make_scratchpad_read_tool,
    make_scratchpad_list_tool,
    SCRATCHPAD_BYTES,
    get_all_tools,
)
from evolving_agent.core.memory import MemoryEntry


@pytest.fixture
def host_tools(monkeypatch):
    monkeypatch.setenv("ENABLE_HOST_TOOLS", "true")
    monkeypatch.setenv("TOOL_SANDBOX_DIR", "")


@pytest.fixture
def scratchpad(tmp_path, monkeypatch):
    directory = tmp_path / "scratchpad"
    directory.mkdir()
    monkeypatch.setenv("SCRATCHPAD_DIR", str(directory))
    return directory


def _symlink(link, target, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("Operating system does not permit test symlinks")


# ---------------------------------------------------------------------------
# Command safety tests
# ---------------------------------------------------------------------------


def test_safe_commands_allowed():
    """Normal commands should be allowed."""
    assert is_command_safe("ls -la") is True
    assert is_command_safe("cat /etc/hostname") is True
    assert is_command_safe("env | grep OPENAI") is True
    assert is_command_safe("git status") is True
    assert is_command_safe("python3 --version") is True


def test_dangerous_commands_blocked():
    """Dangerous commands should be blocked."""
    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("rm -rf /*") is False
    assert is_command_safe("mkfs.ext4 /dev/sda") is False
    assert is_command_safe("dd if=/dev/zero of=/dev/sda") is False
    assert is_command_safe("shutdown -h now") is False
    assert is_command_safe("reboot") is False


def test_case_insensitive_blocking():
    """Blocking should be case-insensitive."""
    assert is_command_safe("RM -RF /") is False
    assert is_command_safe("Shutdown") is False


# ---------------------------------------------------------------------------
# read_file tool
# ---------------------------------------------------------------------------


def test_read_file_tool_exists(tmp_path, host_tools):
    """read_file should read a file and return JSON."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3")

    tool = make_read_file_tool()
    result = json.loads(tool.handler(path=str(test_file)))

    assert result["total_lines"] == 3
    assert "line1" in result["content"]
    assert result["path"] == str(test_file)


def test_read_file_not_found(host_tools):
    """read_file should return error for missing file."""
    tool = make_read_file_tool()
    result = json.loads(tool.handler(path="/nonexistent/file.txt"))
    assert "error" in result


def test_read_file_max_lines(tmp_path, host_tools):
    """read_file should truncate at max_lines."""
    test_file = tmp_path / "big.txt"
    test_file.write_text("\n".join(f"line {i}" for i in range(500)))

    tool = make_read_file_tool()
    result = json.loads(tool.handler(path=str(test_file), max_lines=10))

    assert result["lines"] == 10
    assert result["total_lines"] == 500
    assert result["truncated"] is True


# ---------------------------------------------------------------------------
# list_files tool
# ---------------------------------------------------------------------------


def test_list_files_tool(tmp_path, host_tools):
    """list_files should list files matching a pattern."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")

    tool = make_list_files_tool()
    result = json.loads(tool.handler(directory=str(tmp_path), pattern="*.py"))

    assert result["total"] == 2
    assert all(f["path"].endswith(".py") for f in result["files"])


def test_list_files_not_found(host_tools):
    """list_files should return error for missing directory."""
    tool = make_list_files_tool()
    result = json.loads(tool.handler(directory="/nonexistent/dir"))
    assert "error" in result


# ---------------------------------------------------------------------------
# run_command tool
# ---------------------------------------------------------------------------


def test_run_command_tool(host_tools):
    """run_command should execute a command and return output."""
    tool = make_run_command_tool()
    with patch(
        "evolving_agent.core.tools.subprocess.run",
        return_value=subprocess.CompletedProcess("echo hello", 0, "hello", ""),
    ) as run:
        result = json.loads(tool.handler(command="echo hello"))
    run.assert_called_once()

    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


def test_run_command_blocked(host_tools):
    """run_command should block dangerous commands."""
    tool = make_run_command_tool()
    result = json.loads(tool.handler(command="rm -rf /"))

    assert "error" in result
    assert "blocked" in result["error"].lower() or "safety" in result["error"].lower()


def test_run_command_timeout(host_tools):
    """run_command should timeout long-running commands."""
    tool = make_run_command_tool()
    with patch(
        "evolving_agent.core.tools.subprocess.run",
        side_effect=subprocess.TimeoutExpired("synthetic", 1),
    ):
        result = json.loads(tool.handler(command="synthetic test command", timeout=1))

    assert "error" in result
    assert "timed out" in result["error"].lower()


# ---------------------------------------------------------------------------
# search_web tool
# ---------------------------------------------------------------------------


def test_search_web_no_instance():
    """search_web should return error when no web search is configured."""
    tool = make_search_web_tool(None)
    result = json.loads(tool.handler(query="test"))
    assert "error" in result
    assert "not configured" in result["error"]


# ---------------------------------------------------------------------------
# search_memory tool
# ---------------------------------------------------------------------------


def test_search_memory_no_instance():
    """search_memory should return error when memory is not available."""
    tool = make_search_memory_tool(None)
    result = json.loads(tool.handler(query="test"))
    assert "error" in result
    assert "not available" in result["error"]


def test_search_memory_uses_zero_threshold():
    """search_memory should expose stored memories even for weak broad matches."""

    class MemoryStub:
        async def search_memories(self, query, n_results=5, similarity_threshold=0.5):
            assert query == "previous interactions"
            assert n_results == 3
            assert similarity_threshold == 0.0
            return [
                (
                    MemoryEntry(
                        content="Query: hello\n\nResponse: hi",
                        memory_type="interaction",
                    ),
                    0.12,
                )
            ]

    tool = make_search_memory_tool(MemoryStub())
    result = json.loads(tool.handler(query="previous interactions", limit=3))
    assert len(result["results"]) == 1
    assert result["results"][0]["type"] == "interaction"


def test_search_memory_falls_back_to_recent_memories():
    """When semantic search finds nothing, list recent memories like the UI does."""

    class MemoryStub:
        async def search_memories(self, query, n_results=5, similarity_threshold=0.5):
            return []

        async def list_recent_memories(self, limit=5):
            assert limit == 2
            return [
                MemoryEntry(
                    content="Query: remembered thing\n\nResponse: saved answer",
                    memory_type="interaction",
                )
            ]

    tool = make_search_memory_tool(MemoryStub())
    result = json.loads(tool.handler(query="", limit=2))
    assert len(result["results"]) == 1
    assert "remembered thing" in result["results"][0]["content"]


# ---------------------------------------------------------------------------
# TPMJS tools
# ---------------------------------------------------------------------------


def test_search_tpmjs_no_client():
    """search_tpmjs should return error when not configured."""
    tool = make_search_tpmjs_tool(None)
    result = json.loads(tool.handler(query="test"))
    assert "error" in result


def test_execute_tpmjs_no_client():
    """execute_tpmjs_tool should return error when not configured."""
    tool = make_execute_tpmjs_tool(None)
    result = json.loads(
        tool.handler(package="@test/pkg", tool_name="tool", prompt="test")
    )
    assert "error" in result


def test_create_tpmjs_no_client():
    """create_tpmjs_tool should return error when not configured."""
    tool = make_create_tpmjs_tool(None)
    result = json.loads(
        tool.handler(name="test", description="desc", category="utilities", code="")
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# get_all_tools
# ---------------------------------------------------------------------------


def test_get_all_tools_basic(monkeypatch):
    """get_all_tools should return base tools without TPMJS."""
    monkeypatch.delenv("ENABLE_HOST_TOOLS", raising=False)
    tools = get_all_tools()
    names = [t.name for t in tools]

    assert "read_file" not in names
    assert "list_files" not in names
    assert "run_command" not in names
    assert "search_web" in names
    assert "search_memory" in names
    # No TPMJS tools without a client
    assert "search_tpmjs" not in names


def test_get_all_tools_explicit_host_opt_in(host_tools):
    names = {item.name for item in get_all_tools()}
    assert {"read_file", "list_files", "run_command"} <= names


def test_get_all_tools_with_tpmjs():
    """get_all_tools should include TPMJS tools when client is provided."""
    mock_client = MagicMock()
    tools = get_all_tools(tpmjs_client=mock_client)
    names = [t.name for t in tools]

    assert "search_tpmjs" in names
    assert "execute_tpmjs_tool" in names
    assert "create_tpmjs_tool" in names


def test_tools_have_openai_schema():
    """All tools should produce valid OpenAI function schemas."""
    tools = get_all_tools()
    for t in tools:
        schema = t.to_openai_dict()
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_cached_host_tools_cannot_bypass_revoked_flag(
    tmp_path, monkeypatch, host_tools
):
    read = make_read_file_tool()
    listing = make_list_files_tool()
    command = make_run_command_tool()
    monkeypatch.setenv("ENABLE_HOST_TOOLS", "false")
    with patch("evolving_agent.core.tools.subprocess.run") as run:
        assert "disabled" in json.loads(command.handler(command="echo fake"))["error"]
    run.assert_not_called()
    assert (
        "disabled" in json.loads(read.handler(path=str(tmp_path / "missing")))["error"]
    )
    assert "disabled" in json.loads(listing.handler(directory=str(tmp_path)))["error"]


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.production",
        "credentials.json",
        "auth.json",
        "id_ed25519",
        "key.pem",
        "memory.sqlite3",
    ],
)
def test_host_read_denies_credential_and_storage_files(tmp_path, host_tools, name):
    source = tmp_path / name
    source.write_text("PRIVATE_CONTENT")
    result = make_read_file_tool().handler(path=str(source))
    assert "error" in json.loads(result)
    assert "PRIVATE_CONTENT" not in result


def test_host_read_redacts_credentials_in_otherwise_allowed_file(tmp_path, host_tools):
    value = "sk-" + "synthetic-secret-only-123456"
    source = tmp_path / "example.txt"
    source.write_text(f"normal text\nAPI_KEY={value}\n")
    result = make_read_file_tool().handler(path=str(source))
    assert value not in result
    assert "REDACTED" in result and "normal text" in result


@pytest.mark.parametrize("limit", [0, -1, 1001, True])
def test_host_read_rejects_invalid_limits_before_reading(tmp_path, host_tools, limit):
    assert "error" in json.loads(
        make_read_file_tool().handler(path=str(tmp_path), max_lines=limit)
    )


def test_host_read_denies_oversized_file(tmp_path, host_tools):
    source = tmp_path / "large.txt"
    source.write_bytes(b"x" * 1_000_001)
    assert "error" in json.loads(make_read_file_tool().handler(path=str(source)))


@pytest.mark.parametrize(
    "pattern", ["../*", "../../*", "/tmp/*", "C:\\outside\\*", "sub/../../*"]
)
def test_host_glob_cannot_escape_base(tmp_path, host_tools, pattern):
    assert "error" in json.loads(
        make_list_files_tool().handler(directory=str(tmp_path), pattern=pattern)
    )


def test_host_recursive_listing_stays_bounded_and_filters_secret_paths(
    tmp_path, host_tools
):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "safe.py").write_text("pass")
    (nested / ".env").write_text("private")
    result = json.loads(
        make_list_files_tool().handler(directory=str(tmp_path), pattern="**/*")
    )
    paths = {entry["path"] for entry in result["files"]}
    assert str(nested / "safe.py") in paths
    assert str(nested / ".env") not in paths
    for index in range(105):
        (tmp_path / f"{index}.txt").write_text("")
    result = json.loads(
        make_list_files_tool().handler(directory=str(tmp_path), pattern="*.txt")
    )
    assert len(result["files"]) == 100 and result["truncated"]
    assert result["total_is_lower_bound"]


def test_host_tools_reject_symlink_and_do_not_traverse_linked_directory(
    tmp_path, host_tools
):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "private.txt"
    target.write_text("PRIVATE_CONTENT")
    _symlink(base / "link.txt", target)
    _symlink(base / "linked_dir", outside, directory=True)
    assert "error" in json.loads(
        make_read_file_tool().handler(path=str(base / "link.txt"))
    )
    result = json.loads(
        make_list_files_tool().handler(directory=str(base), pattern="**/*")
    )
    assert result["files"] == []


def test_host_tool_sandbox_denies_outside_path(tmp_path, host_tools, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("private")
    monkeypatch.setenv("TOOL_SANDBOX_DIR", str(root))
    assert "error" in json.loads(make_read_file_tool().handler(path="../outside.txt"))


def test_command_output_redacted_and_command_not_reflected(host_tools):
    value = "sk-" + "synthetic-secret-only-123456"
    with patch(
        "evolving_agent.core.tools.subprocess.run",
        return_value=subprocess.CompletedProcess(
            "fake", 0, f"API_KEY={value}", f"Bearer {value}"
        ),
    ):
        result = make_run_command_tool().handler(command=f"echo {value}")
    assert value not in result and "command" not in json.loads(result)
    assert "REDACTED" in result


@pytest.mark.parametrize("timeout", [-1, 0, 61, True])
def test_command_invalid_timeout_never_starts_process(host_tools, timeout):
    with patch("evolving_agent.core.tools.subprocess.run") as run:
        assert "error" in json.loads(
            make_run_command_tool().handler(command="fake", timeout=timeout)
        )
    run.assert_not_called()


def test_scratchpad_roundtrip_and_redaction(scratchpad):
    value = "sk-" + "synthetic-secret-only-123456"
    result = json.loads(
        make_scratchpad_write_tool().handler(
            filename="notes.md", content=f"Useful note\nAPI_KEY={value}"
        )
    )
    assert result["written"] and result["redacted"]
    assert value not in (scratchpad / "notes.md").read_text()
    read = json.loads(make_scratchpad_read_tool().handler(filename="notes.md"))
    assert "Useful note" in read["content"] and value not in read["content"]
    listing = json.loads(make_scratchpad_list_tool().handler(pattern="*.md"))
    assert [entry["filename"] for entry in listing["files"]] == ["notes.md"]


@pytest.mark.parametrize(
    "name",
    [
        "../outside.txt",
        "..\\outside.txt",
        "/outside.txt",
        "C:\\outside.txt",
        ".",
        "..",
        "CON",
        "NUL.txt",
        "file:stream",
        "trailing.",
        "trailing ",
        "a/b",
        "",
        ".env",
        "foo*bar",
    ],
)
def test_scratchpad_rejects_unsafe_names(scratchpad, name):
    assert "error" in json.loads(
        make_scratchpad_write_tool().handler(filename=name, content="safe")
    )
    assert "error" in json.loads(make_scratchpad_read_tool().handler(filename=name))
    assert list(scratchpad.iterdir()) == []


@pytest.mark.parametrize(
    "pattern", ["../*", "..\\*", "/tmp/*", "C:\\*", "**/*", "nested/*", ""]
)
def test_scratchpad_glob_is_nonrecursive_and_confined(scratchpad, pattern):
    assert "error" in json.loads(make_scratchpad_list_tool().handler(pattern=pattern))


def test_scratchpad_size_limit_is_bytes_and_reads_are_bounded(scratchpad):
    write = make_scratchpad_write_tool()
    assert "error" in json.loads(
        write.handler(filename="oversized.txt", content="x" * (SCRATCHPAD_BYTES + 1))
    )
    assert "error" in json.loads(
        write.handler(filename="unicode.txt", content="漢" * 25000)
    )
    source = scratchpad / "legacy-large.txt"
    source.write_bytes(b"x" * (SCRATCHPAD_BYTES + 1))
    assert "error" in json.loads(
        make_scratchpad_read_tool().handler(filename=source.name)
    )


def test_scratchpad_cannot_follow_symlink_or_modify_external_target(
    scratchpad, tmp_path
):
    target = tmp_path / "outside.txt"
    target.write_text("UNCHANGED")
    _symlink(scratchpad / "linked.txt", target)
    assert "error" in json.loads(
        make_scratchpad_read_tool().handler(filename="linked.txt")
    )
    assert "error" in json.loads(
        make_scratchpad_write_tool().handler(filename="linked.txt", content="changed")
    )
    assert target.read_text() == "UNCHANGED"
    assert json.loads(make_scratchpad_list_tool().handler())["files"] == []


def test_scratchpad_root_cannot_be_a_symlink(tmp_path, monkeypatch):
    target = tmp_path / "outside"
    target.mkdir()
    link = tmp_path / "scratch"
    _symlink(link, target, directory=True)
    monkeypatch.setenv("SCRATCHPAD_DIR", str(link))
    assert "error" in json.loads(
        make_scratchpad_write_tool().handler(filename="note.txt", content="changed")
    )
    assert list(target.iterdir()) == []


def test_scratchpad_rejects_hardlinks(scratchpad, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("UNCHANGED")
    try:
        os.link(target, scratchpad / "hardlink.txt")
    except OSError:
        pytest.skip("Operating system does not permit hardlinks")
    assert "error" in json.loads(
        make_scratchpad_write_tool().handler(filename="hardlink.txt", content="changed")
    )
    assert "error" in json.loads(
        make_scratchpad_read_tool().handler(filename="hardlink.txt")
    )
    assert target.read_text() == "UNCHANGED"


def test_scratchpad_file_quota_and_existing_file_update(scratchpad):
    for index in range(100):
        (scratchpad / f"{index}.txt").write_text("old")
    write = make_scratchpad_write_tool()
    assert "error" in json.loads(write.handler(filename="new.txt", content="new"))
    assert json.loads(write.handler(filename="0.txt", content="updated"))["written"]
    assert (scratchpad / "0.txt").read_text() == "updated"
    assert len(list(scratchpad.iterdir())) == 100


def test_scratchpad_legacy_secret_content_redacted_on_read(scratchpad):
    value = "sk-" + "synthetic-secret-only-123456"
    (scratchpad / "legacy.txt").write_text(f"API_KEY={value}")
    result = make_scratchpad_read_tool().handler(filename="legacy.txt")
    assert value not in result and "REDACTED" in result


def test_structured_json_secrets_are_redacted_before_scratchpad_write(scratchpad):
    content = json.dumps({"settings": {"api_key": "opaque-value-without-prefix"}})
    result = json.loads(
        make_scratchpad_write_tool().handler(filename="settings.json", content=content)
    )
    assert result["written"] and result["redacted"]
    assert "opaque-value" not in (scratchpad / "settings.json").read_text()
