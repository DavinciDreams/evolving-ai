"""
Tool definitions for the Self-Improving AI Agent.

Uses the Vercel AI SDK (@tool decorator) for tool definitions and
integrates with TPMJS for external tool discovery/execution.
"""

import asyncio
import glob as glob_module
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from ai_sdk import tool

from ..utils.logging import setup_logger

if TYPE_CHECKING:
    from ..integrations.tpmjs import TPMJSClient
    from ..integrations.web_search import WebSearchIntegration
    from ..core.memory import LongTermMemory

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Command safety
# ---------------------------------------------------------------------------

BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "fork bomb",
    "> /dev/sda",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "init 0",
    "init 6",
    "kill -9 1",
    "killall",
    "pkill -9",
]

BLOCKED_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/\s*$",
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+/\s*$",
    r">\s*/dev/sd[a-z]",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

COMMAND_TIMEOUT = 30


def is_command_safe(command: str) -> bool:
    """Check if a shell command is safe to execute."""
    cmd_lower = command.lower().strip()

    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return False

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return False

    return True


# ---------------------------------------------------------------------------
# Pydantic parameter models
# ---------------------------------------------------------------------------

class ReadFileParams(BaseModel):
    path: str = Field(description="Absolute or relative file path to read")
    max_lines: int = Field(default=200, description="Maximum lines to return")


class ListFilesParams(BaseModel):
    directory: str = Field(default=".", description="Directory to list")
    pattern: str = Field(default="*", description="Glob pattern (e.g. '*.py', '**/*.js')")


class RunCommandParams(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=30, description="Timeout in seconds (max 60)")


class SearchWebParams(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=3, description="Maximum search results")


class SearchMemoryParams(BaseModel):
    query: str = Field(description="Memory search query")
    limit: int = Field(default=5, description="Maximum memories to return")


class SearchTPMJSParams(BaseModel):
    query: str = Field(description="Search query for tools (e.g. 'convert pdf to markdown')")
    limit: int = Field(default=5, description="Maximum results")


class ExecuteTPMJSToolParams(BaseModel):
    package: str = Field(description="NPM package name (e.g. '@tpmjs/hello')")
    tool_name: str = Field(description="Tool name within the package")
    prompt: str = Field(description="Input prompt for the tool")


class CreateTPMJSToolParams(BaseModel):
    name: str = Field(description="Tool name (lowercase, hyphens ok)")
    description: str = Field(description="What the tool does")
    category: str = Field(description="TPMJS category (e.g. 'text-analysis', 'web-scraping', 'utilities')")
    code: str = Field(description="Tool implementation code (JavaScript/TypeScript)")


# ---------------------------------------------------------------------------
# Tool factories — each returns an ai_sdk.Tool bound to agent context
# ---------------------------------------------------------------------------

def make_read_file_tool() -> Any:
    """Create the read_file tool."""
    @tool(
        name="read_file",
        description="Read the contents of a file. Use this to inspect configuration files, source code, environment variables, etc.",
        parameters=ReadFileParams,
    )
    def read_file(path: str, max_lines: int = 200) -> str:
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return json.dumps({"error": f"File not found: {path}"})
            if not p.is_file():
                return json.dumps({"error": f"Not a file: {path}"})
            if p.stat().st_size > 1_000_000:
                return json.dumps({"error": f"File too large: {p.stat().st_size} bytes"})

            lines = p.read_text(errors="replace").splitlines()
            total = len(lines)
            content = "\n".join(lines[:max_lines])
            result = {"path": str(p), "lines": min(total, max_lines), "total_lines": total, "content": content}
            if total > max_lines:
                result["truncated"] = True
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return read_file


def make_list_files_tool() -> Any:
    """Create the list_files tool."""
    @tool(
        name="list_files",
        description="List files in a directory matching a glob pattern. Use this to explore project structure, find files, etc.",
        parameters=ListFilesParams,
    )
    def list_files(directory: str = ".", pattern: str = "*") -> str:
        try:
            base = Path(directory).expanduser().resolve()
            if not base.exists():
                return json.dumps({"error": f"Directory not found: {directory}"})

            full_pattern = str(base / pattern)
            matches = sorted(glob_module.glob(full_pattern, recursive=True))

            # Limit results
            total = len(matches)
            matches = matches[:100]

            files = []
            for m in matches:
                p = Path(m)
                entry = {"path": str(p), "type": "dir" if p.is_dir() else "file"}
                if p.is_file():
                    entry["size"] = p.stat().st_size
                files.append(entry)

            result = {"directory": str(base), "pattern": pattern, "total": total, "files": files}
            if total > 100:
                result["truncated"] = True
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return list_files


def make_run_command_tool() -> Any:
    """Create the run_command tool."""
    @tool(
        name="run_command",
        description="Execute a shell command and return its output. Use this to check environment variables, run scripts, inspect system state, etc.",
        parameters=RunCommandParams,
    )
    def run_command(command: str, timeout: int = 30) -> str:
        if not is_command_safe(command):
            return json.dumps({"error": "Command blocked for safety reasons", "command": command})

        timeout = min(timeout, 60)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            output = {
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout[:10000] if result.stdout else "",
                "stderr": result.stderr[:5000] if result.stderr else "",
            }
            return json.dumps(output)
        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"Command timed out after {timeout}s", "command": command})
        except Exception as e:
            return json.dumps({"error": str(e), "command": command})

    return run_command


def make_search_web_tool(web_search: Optional["WebSearchIntegration"]) -> Any:
    """Create the search_web tool bound to a WebSearchIntegration instance."""
    @tool(
        name="search_web",
        description="Search the web for current information. Use this for questions about recent events, documentation, tutorials, or anything requiring up-to-date knowledge.",
        parameters=SearchWebParams,
    )
    def search_web(query: str, max_results: int = 3) -> str:
        if web_search is None:
            return json.dumps({"error": "Web search is not configured"})
        try:
            result = asyncio.run(
                web_search.search_and_summarize(query, max_results=max_results)
            )
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return search_web


def make_search_memory_tool(memory: Optional["LongTermMemory"]) -> Any:
    """Create the search_memory tool bound to a LongTermMemory instance."""
    @tool(
        name="search_memory",
        description="Search the agent's long-term memory for relevant past interactions, learned patterns, and stored knowledge.",
        parameters=SearchMemoryParams,
    )
    def search_memory(query: str, limit: int = 5) -> str:
        if memory is None:
            return json.dumps({"error": "Memory system is not available"})
        try:
            results = asyncio.run(memory.search_memories(query, n_results=limit))
            memories = []
            for entry, score in results:
                memories.append({
                    "content": entry.content[:500],
                    "type": entry.memory_type,
                    "timestamp": str(entry.timestamp),
                    "similarity": round(score, 3),
                })
            return json.dumps({"query": query, "results": memories})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return search_memory


def make_search_tpmjs_tool(tpmjs_client: Optional["TPMJSClient"]) -> Any:
    """Create the search_tpmjs tool bound to a TPMJSClient instance."""
    @tool(
        name="search_tpmjs",
        description="Search tpmjs.com for AI tools. Use this when you need a specialized tool that isn't available locally (e.g. PDF conversion, image processing, data extraction).",
        parameters=SearchTPMJSParams,
    )
    def search_tpmjs(query: str, limit: int = 5) -> str:
        if tpmjs_client is None:
            return json.dumps({"error": "TPMJS is not configured (no API key)"})
        try:
            results = asyncio.run(tpmjs_client.search_tools(query, limit=limit))
            tools = []
            for t in results:
                tools.append({
                    "name": t.get("name", ""),
                    "package": t.get("package", ""),
                    "description": t.get("description", ""),
                    "quality_score": t.get("qualityScore"),
                })
            return json.dumps({"query": query, "tools_found": len(tools), "tools": tools})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return search_tpmjs


def make_execute_tpmjs_tool(tpmjs_client: Optional["TPMJSClient"]) -> Any:
    """Create the execute_tpmjs_tool bound to a TPMJSClient instance."""
    @tool(
        name="execute_tpmjs_tool",
        description="Execute a tool from tpmjs.com. First use search_tpmjs to find the right tool, then execute it here.",
        parameters=ExecuteTPMJSToolParams,
    )
    def execute_tpmjs_tool(package: str, tool_name: str, prompt: str) -> str:
        if tpmjs_client is None:
            return json.dumps({"error": "TPMJS is not configured (no API key)"})
        try:
            result = asyncio.run(
                tpmjs_client.execute_tool(package, tool_name, prompt)
            )
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    return execute_tpmjs_tool


def make_create_tpmjs_tool(tpmjs_client: Optional["TPMJSClient"]) -> Any:
    """Create the create_tpmjs_tool bound to a TPMJSClient instance."""
    @tool(
        name="create_tpmjs_tool",
        description="Create a new tool on tpmjs.com when no existing tool matches the need. Generates a tool scaffold that can be published to npm.",
        parameters=CreateTPMJSToolParams,
    )
    def create_tpmjs_tool(
        name: str, description: str, category: str, code: str
    ) -> str:
        if tpmjs_client is None:
            return json.dumps({"error": "TPMJS is not configured (no API key)"})
        try:
            result = asyncio.run(
                tpmjs_client.create_tool(name, description, category, code)
            )
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return create_tpmjs_tool


# ---------------------------------------------------------------------------
# Tool collection builder
# ---------------------------------------------------------------------------

def get_all_tools(
    *,
    web_search: Optional["WebSearchIntegration"] = None,
    memory: Optional["LongTermMemory"] = None,
    tpmjs_client: Optional["TPMJSClient"] = None,
    enable_tpmjs: bool = True,
) -> List[Any]:
    """Build the complete list of tools available to the agent.

    Args:
        web_search: WebSearchIntegration instance (or None to disable)
        memory: LongTermMemory instance (or None to disable)
        tpmjs_client: TPMJSClient instance (or None to disable TPMJS tools)
        enable_tpmjs: Whether to include TPMJS tools

    Returns:
        List of ai_sdk.Tool instances
    """
    tools = [
        make_read_file_tool(),
        make_list_files_tool(),
        make_run_command_tool(),
        make_search_web_tool(web_search),
        make_search_memory_tool(memory),
    ]

    if enable_tpmjs and tpmjs_client is not None:
        tools.extend([
            make_search_tpmjs_tool(tpmjs_client),
            make_execute_tpmjs_tool(tpmjs_client),
            make_create_tpmjs_tool(tpmjs_client),
        ])

    return tools
