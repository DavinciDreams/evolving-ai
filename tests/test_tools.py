"""
Tests for the tool system (local tools, safety, AI SDK integration).
"""

import json
import os
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
    get_all_tools,
)


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

def test_read_file_tool_exists(tmp_path):
    """read_file should read a file and return JSON."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3")

    tool = make_read_file_tool()
    result = json.loads(tool.handler(path=str(test_file)))

    assert result["total_lines"] == 3
    assert "line1" in result["content"]
    assert result["path"] == str(test_file)


def test_read_file_not_found():
    """read_file should return error for missing file."""
    tool = make_read_file_tool()
    result = json.loads(tool.handler(path="/nonexistent/file.txt"))
    assert "error" in result


def test_read_file_max_lines(tmp_path):
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

def test_list_files_tool(tmp_path):
    """list_files should list files matching a pattern."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")

    tool = make_list_files_tool()
    result = json.loads(tool.handler(directory=str(tmp_path), pattern="*.py"))

    assert result["total"] == 2
    assert all(f["path"].endswith(".py") for f in result["files"])


def test_list_files_not_found():
    """list_files should return error for missing directory."""
    tool = make_list_files_tool()
    result = json.loads(tool.handler(directory="/nonexistent/dir"))
    assert "error" in result


# ---------------------------------------------------------------------------
# run_command tool
# ---------------------------------------------------------------------------

def test_run_command_tool():
    """run_command should execute a command and return output."""
    tool = make_run_command_tool()
    result = json.loads(tool.handler(command="echo hello"))

    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


def test_run_command_blocked():
    """run_command should block dangerous commands."""
    tool = make_run_command_tool()
    result = json.loads(tool.handler(command="rm -rf /"))

    assert "error" in result
    assert "blocked" in result["error"].lower() or "safety" in result["error"].lower()


def test_run_command_timeout():
    """run_command should timeout long-running commands."""
    tool = make_run_command_tool()
    result = json.loads(tool.handler(command="sleep 100", timeout=1))

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
    result = json.loads(tool.handler(package="@test/pkg", tool_name="tool", prompt="test"))
    assert "error" in result


def test_create_tpmjs_no_client():
    """create_tpmjs_tool should return error when not configured."""
    tool = make_create_tpmjs_tool(None)
    result = json.loads(tool.handler(name="test", description="desc", category="utilities", code=""))
    assert "error" in result


# ---------------------------------------------------------------------------
# get_all_tools
# ---------------------------------------------------------------------------

def test_get_all_tools_basic():
    """get_all_tools should return base tools without TPMJS."""
    tools = get_all_tools()
    names = [t.name for t in tools]

    assert "read_file" in names
    assert "list_files" in names
    assert "run_command" in names
    assert "search_web" in names
    assert "search_memory" in names
    # No TPMJS tools without a client
    assert "search_tpmjs" not in names


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
