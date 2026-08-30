"""
Tool definitions for the Self-Improving AI Agent.

Uses the Vercel AI SDK (@tool decorator) for tool definitions and
integrates with TPMJS for external tool discovery/execution.
"""

import asyncio
import fnmatch
import json
import os
import re
import subprocess
import stat
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from ai_sdk import tool

from ..utils.config import config
from ..utils.logging import setup_logger
from ..utils.secret_redaction import redact_text, redact_value

if TYPE_CHECKING:
    from ..integrations.e2b_sandbox import E2BSandbox
    from ..integrations.tpmjs import TPMJSClient
    from ..integrations.web_search import WebSearchIntegration
    from ..core.memory import LongTermMemory

logger = setup_logger(__name__)

FILE_BYTES = 1_000_000
SCRATCHPAD_BYTES = 64_000
MAX_FILE_RESULTS = 100
MAX_DIRECTORY_ENTRIES = 1000
_scratchpad_lock = threading.RLock()


def _host_tools_enabled() -> bool:
    return os.getenv("ENABLE_HOST_TOOLS", "false").lower() == "true"


def _is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _reject_links(path: Path) -> None:
    # Check lexical ancestors before resolve() erases link provenance.
    if any(_is_link(part) for part in (path, *path.parents)):
        raise ValueError("Symlinks and junctions are not allowed")


def _sensitive_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    return bool(
        parts & {".ssh", ".aws", ".azure", ".gnupg", ".codex", ".git", "secrets"}
        or name == ".env"
        or name.startswith(".env.")
        or name
        in {
            "credentials",
            "credentials.json",
            "auth.json",
            "tokens.json",
            "id_rsa",
            "id_ed25519",
        }
        or path.suffix.casefold()
        in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"}
    )


def _redacted_content(content: str) -> tuple[str, bool]:
    """Handle structured JSON keys as well as plain credential assignments."""
    structured_findings = []
    try:
        structured = json.loads(content)
        if isinstance(structured, (dict, list)):
            cleaned, structured_findings = redact_value(structured)
            if structured_findings:
                content = json.dumps(cleaned, ensure_ascii=False)
    except (ValueError, TypeError):
        pass
    cleaned, findings = redact_text(content)
    return cleaned, bool(findings or structured_findings)


def _read_bounded(path: Path, limit: int) -> str:
    _reject_links(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Only regular, non-hardlinked files may be read")
        if info.st_size > limit:
            raise ValueError("File exceeds the tool read limit")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds the tool read limit")
    return _redacted_content(data.decode("utf-8", errors="replace"))[0]


def _validated_pattern(pattern: str, *, recursive: bool) -> str:
    if not isinstance(pattern, str) or not pattern or len(pattern) > 128:
        raise ValueError("Invalid glob pattern")
    normalized = pattern.replace("\\", "/")
    if (
        normalized.startswith("/")
        or ":" in normalized
        or ".." in normalized.split("/")
        or any(ord(char) < 32 for char in normalized)
        or (not recursive and ("/" in normalized or "**" in normalized))
    ):
        raise ValueError("Glob pattern must stay inside the selected directory")
    return normalized


def _get_sandbox_root() -> Optional[Path]:
    """Return the resolved sandbox root, or None if sandboxing is disabled."""
    sandbox = config.tool_sandbox_dir
    if not sandbox:
        return None
    root = Path(sandbox).absolute()
    _reject_links(root)
    return root.resolve()


def _is_path_within_sandbox(path: Path, sandbox: Path) -> bool:
    """Check whether *path* is inside *sandbox* (or is *sandbox* itself)."""
    try:
        path.resolve().relative_to(sandbox)
        return True
    except ValueError:
        return False


def _resolve_sandboxed_path(raw: str) -> Path:
    """Resolve a user-supplied path, enforcing the sandbox if configured.

    - If the path is relative it is resolved relative to the sandbox root
      (or cwd when sandboxing is off).
    - If the path is absolute and sandboxing is on, it must fall inside the
      sandbox; otherwise the function raises ValueError.
    """
    sandbox = _get_sandbox_root()
    if not isinstance(raw, str) or not raw or len(raw) > 4096 or "\x00" in raw:
        raise ValueError("Invalid file path")
    p = Path(raw).expanduser()

    if sandbox:
        if not p.is_absolute():
            p = sandbox / p
        _reject_links(p.absolute())
        p = p.resolve()
        if not _is_path_within_sandbox(p, sandbox):
            raise ValueError("Access denied: path is outside the configured sandbox")
    else:
        _reject_links(p.absolute())
        p = p.resolve()

    return p


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
    """Coarse denylist only; never an authorization or sandbox boundary."""
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
    max_lines: int = Field(
        default=200, ge=1, le=1000, description="Maximum lines to return"
    )


class ListFilesParams(BaseModel):
    directory: str = Field(default=".", description="Directory to list")
    pattern: str = Field(
        default="*", description="Glob pattern (e.g. '*.py', '**/*.js')"
    )


class RunCommandParams(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(
        default=30, ge=1, le=60, description="Timeout in seconds (max 60)"
    )


class SearchWebParams(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=3, description="Maximum search results")


class SearchMemoryParams(BaseModel):
    query: str = Field(description="Memory search query")
    limit: int = Field(default=5, description="Maximum memories to return")


class SearchTPMJSParams(BaseModel):
    query: str = Field(
        description="Search query for tools (e.g. 'convert pdf to markdown')"
    )
    limit: int = Field(default=5, description="Maximum results")


class ExecuteTPMJSToolParams(BaseModel):
    package: str = Field(description="NPM package name (e.g. '@tpmjs/hello')")
    tool_name: str = Field(description="Tool name within the package")
    prompt: str = Field(description="Input prompt for the tool")


class CreateTPMJSToolParams(BaseModel):
    name: str = Field(description="Tool name (lowercase, hyphens ok)")
    description: str = Field(description="What the tool does")
    category: str = Field(
        description="TPMJS category (e.g. 'text-analysis', 'web-scraping', 'utilities')"
    )
    code: str = Field(description="Tool implementation code (JavaScript/TypeScript)")


# ---------------------------------------------------------------------------
# Tool factories — each returns an ai_sdk.Tool bound to agent context
# ---------------------------------------------------------------------------


def make_read_file_tool() -> Any:
    """Create the read_file tool."""

    @tool(
        name="read_file",
        description="Read bounded redacted source/text files when host access is explicitly enabled. Credential files and links are denied.",
        parameters=ReadFileParams,
    )
    def read_file(path: str, max_lines: int = 200) -> str:
        if not _host_tools_enabled():
            return json.dumps({"error": "Host tools are disabled"})
        try:
            if type(max_lines) is not int or not 1 <= max_lines <= 1000:
                raise ValueError("Invalid line limit")
            p = _resolve_sandboxed_path(path)
            if _sensitive_path(p):
                return json.dumps(
                    {"error": "Credential and private storage paths are denied"}
                )
            if not p.exists():
                return json.dumps({"error": "File not found"})
            if not p.is_file():
                return json.dumps({"error": "Not a regular file"})
            lines = _read_bounded(p, FILE_BYTES).splitlines()
            total = len(lines)
            content = "\n".join(lines[:max_lines])
            result = {
                "path": redact_text(str(p))[0],
                "lines": min(total, max_lines),
                "total_lines": total,
                "content": content,
            }
            if total > max_lines:
                result["truncated"] = True
            return json.dumps(result)
        except Exception as e:
            return json.dumps(
                {"error": "File read rejected", "error_type": type(e).__name__}
            )

    return read_file


def make_list_files_tool() -> Any:
    """Create the list_files tool."""

    @tool(
        name="list_files",
        description="List files in a directory matching a glob pattern. Use this to explore project structure, find files, etc.",
        parameters=ListFilesParams,
    )
    def list_files(directory: str = ".", pattern: str = "*") -> str:
        if not _host_tools_enabled():
            return json.dumps({"error": "Host tools are disabled"})
        try:
            pattern = _validated_pattern(pattern, recursive=True)
            base = _resolve_sandboxed_path(directory)
            if not base.is_dir() or _sensitive_path(base):
                return json.dumps({"error": "Directory is unavailable or denied"})
            files = []
            pending = [base]
            scanned = 0
            truncated = False
            while pending and not truncated:
                current = pending.pop()
                _reject_links(current)
                with os.scandir(current) as entries:
                    for item in entries:
                        scanned += 1
                        if scanned > MAX_DIRECTORY_ENTRIES:
                            truncated = True
                            break
                        p = Path(item.path)
                        if (
                            _is_link(p)
                            or _sensitive_path(p)
                            or not p.resolve().is_relative_to(base)
                        ):
                            continue
                        is_directory = item.is_dir(follow_symlinks=False)
                        if is_directory and ("/" in pattern or "**" in pattern):
                            pending.append(p)
                        relative = PurePosixPath(p.relative_to(base).as_posix())
                        if not (
                            relative.match(pattern)
                            or (
                                pattern.startswith("**/")
                                and relative.match(pattern[3:])
                            )
                        ):
                            continue
                        if len(files) >= MAX_FILE_RESULTS:
                            truncated = True
                            break
                        # DirEntry.stat reports st_nlink=0 on Windows; Path.stat
                        # obtains the actual link count for hardlink screening.
                        info = p.stat(follow_symlinks=False)
                        if not is_directory and (
                            not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        ):
                            continue
                        entry = {
                            "path": redact_text(str(p))[0],
                            "type": "dir" if is_directory else "file",
                        }
                        if not is_directory:
                            entry["size"] = info.st_size
                        files.append(entry)
            files.sort(key=lambda entry: entry["path"])
            result = {
                "directory": redact_text(str(base))[0],
                "pattern": redact_text(pattern)[0],
                "total": len(files),
                "files": files,
                "truncated": truncated,
                "total_is_lower_bound": truncated,
            }
            return json.dumps(result)
        except Exception as e:
            return json.dumps(
                {"error": "Directory listing rejected", "error_type": type(e).__name__}
            )

    return list_files


def make_run_command_tool() -> Any:
    """Create the run_command tool."""

    @tool(
        name="run_command",
        description="Execute an operator-authorized host shell command. This is NOT sandboxed; remote execute_code is preferred.",
        parameters=RunCommandParams,
    )
    def run_command(command: str, timeout: int = 30) -> str:
        if not _host_tools_enabled():
            return json.dumps({"error": "Host tools are disabled"})
        if not isinstance(command, str) or not command.strip() or len(command) > 8000:
            return json.dumps({"error": "Invalid command"})
        if type(timeout) is not int or not 1 <= timeout <= 60:
            return json.dumps({"error": "Invalid command timeout"})
        if not is_command_safe(command):
            return json.dumps({"error": "Command blocked for safety reasons"})

        try:
            sandbox = _get_sandbox_root()
            work_dir = str(sandbox) if sandbox else os.getcwd()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
            )

            output = {
                "returncode": result.returncode,
                "stdout": redact_text(result.stdout or "")[0][:10000],
                "stderr": redact_text(result.stderr or "")[0][:5000],
            }
            return json.dumps(output)
        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"Command timed out after {timeout}s"})
        except Exception as e:
            return json.dumps(
                {"error": "Host command failed", "error_type": type(e).__name__}
            )

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
            search_query = (query or "").strip()
            if search_query:
                results = asyncio.run(
                    memory.search_memories(
                        search_query,
                        n_results=limit,
                        similarity_threshold=0.0,
                    )
                )
            else:
                results = []

            if not results and hasattr(memory, "list_recent_memories"):
                recent = asyncio.run(memory.list_recent_memories(limit=limit))
                results = [(entry, 0.0) for entry in recent]

            memories = []
            for entry, score in results:
                memories.append(
                    {
                        "content": entry.content[:500],
                        "type": entry.memory_type,
                        "timestamp": str(entry.timestamp),
                        "similarity": round(score, 3),
                    }
                )
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
                tools.append(
                    {
                        "name": t.get("name", ""),
                        "package": t.get("package", ""),
                        "description": t.get("description", ""),
                        "quality_score": t.get("qualityScore"),
                    }
                )
            return json.dumps(
                {"query": query, "tools_found": len(tools), "tools": tools}
            )
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
            result = asyncio.run(tpmjs_client.execute_tool(package, tool_name, prompt))
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
    def create_tpmjs_tool(name: str, description: str, category: str, code: str) -> str:
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
# E2B sandbox tool
# ---------------------------------------------------------------------------


class ExecuteCodeParams(BaseModel):
    code: str = Field(description="Source code to execute")
    language: str = Field(
        default="python",
        description="Language: 'python', 'javascript', or 'shell'",
    )
    timeout: int = Field(default=30, description="Max execution seconds (max 60)")


def make_execute_code_tool(e2b_sandbox: Optional["E2BSandbox"]) -> Any:
    """Create the execute_code tool bound to an E2BSandbox instance."""

    @tool(
        name="execute_code",
        description=(
            "Execute code safely in a remote cloud sandbox (E2B). "
            "Use this for running AI-generated code, data processing, "
            "or any command that should NOT run in the production container. "
            "Supports Python, JavaScript, and shell commands."
        ),
        parameters=ExecuteCodeParams,
    )
    def execute_code(code: str, language: str = "python", timeout: int = 30) -> str:
        if e2b_sandbox is None:
            return json.dumps(
                {"error": "Code sandbox is not configured (no E2B_API_KEY)"}
            )
        timeout = min(timeout, 60)
        try:
            result = asyncio.run(
                e2b_sandbox.run_code(code, language=language, timeout=timeout)
            )
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return execute_code


# ---------------------------------------------------------------------------
# Scratchpad tools
# ---------------------------------------------------------------------------


class ScratchpadWriteParams(BaseModel):
    filename: str = Field(description="File name (no path separators, e.g. 'notes.md')")
    content: str = Field(max_length=SCRATCHPAD_BYTES, description="Content to write")


class ScratchpadReadParams(BaseModel):
    filename: str = Field(description="File name to read")


class ScratchpadListParams(BaseModel):
    pattern: str = Field(default="*", description="Glob pattern (e.g. '*.md', '*')")


def _get_scratchpad_dir() -> Path:
    """Return the scratchpad directory, creating it if needed."""
    scratchpad = config.scratchpad_dir
    p = Path(scratchpad).absolute()
    _reject_links(p)
    p.mkdir(parents=True, exist_ok=True)
    _reject_links(p)
    return p.resolve()


def _sanitize_filename(name: str) -> str:
    """Reject unsafe paths instead of silently redirecting writes to basenames."""
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 128
        or name in {".", ".."}
        or any(char in name for char in '/\\:*?"<>|')
        or any(ord(char) < 32 for char in name)
        or name.endswith((".", " "))
    ):
        raise ValueError("Scratchpad requires a single bounded filename")
    if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name):
        raise ValueError("Device filenames are not allowed")
    if _sensitive_path(Path(name)):
        raise ValueError("Credential filenames are not allowed")
    if redact_text(name)[1]:
        raise ValueError("Credential-shaped filenames are not allowed")
    return name


def _scratchpad_path(root: Path, name: str) -> Path:
    path = root / _sanitize_filename(name)
    _reject_links(path)
    if not path.resolve().is_relative_to(root):
        raise ValueError("Scratchpad path escaped its root")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("Scratchpad entry must be a regular, non-hardlinked file")
    return path


def make_scratchpad_write_tool() -> Any:
    """Create the scratchpad_write tool."""

    @tool(
        name="scratchpad_write",
        description=(
            "Write a file to your persistent scratchpad. "
            "Use this to save notes, working drafts, intermediate results, "
            "or local working artifacts. Durable facts and handoffs belong in HAM."
        ),
        parameters=ScratchpadWriteParams,
    )
    def scratchpad_write(filename: str, content: str) -> str:
        try:
            if (
                not isinstance(content, str)
                or len(content.encode("utf-8")) > SCRATCHPAD_BYTES
            ):
                raise ValueError("Scratchpad content exceeds the byte limit")
            clean_content, findings = _redacted_content(content)
            data = clean_content.encode("utf-8")
            if len(data) > SCRATCHPAD_BYTES:
                raise ValueError("Redacted scratchpad content exceeds the byte limit")
            with _scratchpad_lock:
                safe_name = _sanitize_filename(filename)
                scratchpad = _get_scratchpad_dir()
                filepath = _scratchpad_path(scratchpad, safe_name)
                if not filepath.exists():
                    with os.scandir(scratchpad) as entries:
                        count = sum(
                            1 for _, _entry in zip(range(MAX_FILE_RESULTS), entries)
                        )
                    if count >= MAX_FILE_RESULTS:
                        raise ValueError("Scratchpad file quota reached")
                with tempfile.NamedTemporaryFile(
                    dir=scratchpad, delete=False
                ) as handle:
                    temporary_path = Path(handle.name)
                    try:
                        handle.write(data)
                        handle.flush()
                        os.fsync(handle.fileno())
                    except BaseException:
                        handle.close()
                        temporary_path.unlink(missing_ok=True)
                        raise
                try:
                    _scratchpad_path(scratchpad, safe_name)
                    os.replace(temporary_path, filepath)
                finally:
                    temporary_path.unlink(missing_ok=True)
            return json.dumps(
                {
                    "written": True,
                    "filename": safe_name,
                    "size": len(data),
                    "redacted": bool(findings),
                }
            )
        except Exception as e:
            return json.dumps(
                {"error": "Scratchpad write rejected", "error_type": type(e).__name__}
            )

    return scratchpad_write


def make_scratchpad_read_tool() -> Any:
    """Create the scratchpad_read tool."""

    @tool(
        name="scratchpad_read",
        description="Read a file from your persistent scratchpad.",
        parameters=ScratchpadReadParams,
    )
    def scratchpad_read(filename: str) -> str:
        try:
            with _scratchpad_lock:
                safe_name = _sanitize_filename(filename)
                scratchpad = _get_scratchpad_dir()
                filepath = _scratchpad_path(scratchpad, safe_name)
                content = _read_bounded(filepath, SCRATCHPAD_BYTES)
            return json.dumps(
                {
                    "filename": safe_name,
                    "content": content[:50000],
                    "truncated": len(content) > 50000,
                }
            )
        except Exception as e:
            return json.dumps(
                {"error": "Scratchpad read rejected", "error_type": type(e).__name__}
            )

    return scratchpad_read


def make_scratchpad_list_tool() -> Any:
    """Create the scratchpad_list tool."""

    @tool(
        name="scratchpad_list",
        description="List files in your persistent scratchpad.",
        parameters=ScratchpadListParams,
    )
    def scratchpad_list(pattern: str = "*") -> str:
        try:
            pattern = _validated_pattern(pattern, recursive=False)
            scratchpad = _get_scratchpad_dir()
            files = []
            truncated = False
            with _scratchpad_lock, os.scandir(scratchpad) as entries:
                for index, item in enumerate(entries):
                    if index >= MAX_DIRECTORY_ENTRIES or len(files) >= MAX_FILE_RESULTS:
                        truncated = True
                        break
                    if not fnmatch.fnmatchcase(item.name, pattern):
                        continue
                    try:
                        path = _scratchpad_path(scratchpad, item.name)
                        info = path.stat()
                        if stat.S_ISREG(info.st_mode):
                            files.append({"filename": path.name, "size": info.st_size})
                    except (ValueError, OSError):
                        continue
            files.sort(key=lambda entry: entry["filename"])
            return json.dumps(
                {"files": files, "count": len(files), "truncated": truncated}
            )
        except Exception as e:
            return json.dumps(
                {"error": "Scratchpad listing rejected", "error_type": type(e).__name__}
            )

    return scratchpad_list


# ---------------------------------------------------------------------------
# Tool collection builder
# ---------------------------------------------------------------------------


def get_all_tools(
    *,
    web_search: Optional["WebSearchIntegration"] = None,
    memory: Optional["LongTermMemory"] = None,
    tpmjs_client: Optional["TPMJSClient"] = None,
    enable_tpmjs: bool = True,
    e2b_sandbox: Optional["E2BSandbox"] = None,
) -> List[Any]:
    """Build the complete list of tools available to the agent.

    Args:
        web_search: WebSearchIntegration instance (or None to disable)
        memory: LongTermMemory instance (or None to disable)
        tpmjs_client: TPMJSClient instance (or None to disable TPMJS tools)
        enable_tpmjs: Whether to include TPMJS tools
        e2b_sandbox: E2BSandbox instance (or None to disable sandbox execution)

    Returns:
        List of ai_sdk.Tool instances
    """
    tools = [
        make_search_web_tool(web_search),
        make_search_memory_tool(memory),
        # Scratchpad — always available
        make_scratchpad_write_tool(),
        make_scratchpad_read_tool(),
        make_scratchpad_list_tool(),
    ]

    # A command blacklist is not a sandbox. Never expose host effects merely
    # because a provider supports tool calling.
    if _host_tools_enabled():
        tools.extend(
            [make_read_file_tool(), make_list_files_tool(), make_run_command_tool()]
        )

    if e2b_sandbox is not None:
        tools.append(make_execute_code_tool(e2b_sandbox))

    if enable_tpmjs and tpmjs_client is not None:
        tools.extend(
            [
                make_search_tpmjs_tool(tpmjs_client),
                make_execute_tpmjs_tool(tpmjs_client),
                make_create_tpmjs_tool(tpmjs_client),
            ]
        )

    return tools
