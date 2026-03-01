"""
E2B sandbox integration for safe remote code execution.

Provides isolated cloud sandboxes so the agent can run AI-generated
code without affecting the production container.

Docs: https://e2b.dev/docs
"""

import json
from typing import Any, Dict, Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class E2BSandbox:
    """Thin wrapper around the E2B Python SDK."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._sdk_available = False

        try:
            import e2b  # noqa: F401
            self._sdk_available = True
        except ImportError:
            logger.warning(
                "e2b package not installed. Run: pip install e2b"
            )

    async def run_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute code in an isolated E2B sandbox.

        Args:
            code: Source code to execute.
            language: Language — "python", "javascript", or "shell".
            timeout: Max execution time in seconds.

        Returns:
            Dict with stdout, stderr, exit_code, and error (if any).
        """
        if not self._sdk_available:
            return {"error": "e2b package not installed"}

        try:
            from e2b import Sandbox

            sandbox = Sandbox(api_key=self.api_key, timeout=timeout + 10)
            try:
                if language == "shell":
                    result = sandbox.commands.run(code, timeout=timeout)
                elif language == "javascript":
                    result = sandbox.commands.run(
                        f'node -e {json.dumps(code)}',
                        timeout=timeout,
                    )
                else:
                    # Default: Python
                    result = sandbox.commands.run(
                        f'python3 -c {json.dumps(code)}',
                        timeout=timeout,
                    )

                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                }
            finally:
                try:
                    sandbox.kill()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"E2B code execution failed: {e}")
            return {"error": str(e)}

    async def run_command(
        self,
        command: str,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Run a shell command in an E2B sandbox."""
        return await self.run_code(command, language="shell", timeout=timeout)

    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write a file inside an E2B sandbox."""
        if not self._sdk_available:
            return {"error": "e2b package not installed"}

        try:
            from e2b import Sandbox

            sandbox = Sandbox(api_key=self.api_key)
            try:
                sandbox.files.write(path, content)
                return {"path": path, "written": True}
            finally:
                try:
                    sandbox.kill()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"E2B write_file failed: {e}")
            return {"error": str(e)}

    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read a file from an E2B sandbox."""
        if not self._sdk_available:
            return {"error": "e2b package not installed"}

        try:
            from e2b import Sandbox

            sandbox = Sandbox(api_key=self.api_key)
            try:
                content = sandbox.files.read(path)
                return {"path": path, "content": content}
            finally:
                try:
                    sandbox.kill()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"E2B read_file failed: {e}")
            return {"error": str(e)}
