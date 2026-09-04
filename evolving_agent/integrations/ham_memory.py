"""Transport-neutral HAM REST client for Katbot's authoritative memory.

The service credential determines tenant, AgentPrincipal, and allowed scopes.
This client deliberately never sends an agent identity header or payload field.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar
from urllib.parse import urlsplit

import httpx


_T = TypeVar("_T")


class HAMMemoryError(RuntimeError):
    """Raised when HAM rejects or cannot complete a memory operation."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HAMMemoryClient:
    """Small async adapter over HAM's authenticated REST API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        project: str,
        scope: str,
        repo: str,
        expected_agent_id: str,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not api_key:
            raise HAMMemoryError("HAM_API_KEY is required when MEMORY_BACKEND=ham")
        if not project or not scope:
            raise HAMMemoryError("HAM_PROJECT and HAM_SCOPE are required")
        if not expected_agent_id:
            raise HAMMemoryError(
                "HAM_EXPECTED_AGENT_ID is required for credential attribution checks"
            )
        parsed_url = urlsplit(base_url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise HAMMemoryError(
                "HAM_API_URL must be an HTTPS service URL without credentials, query, or fragment"
            )

        self.project = project
        self.scope = scope
        self.repo = repo
        self.expected_agent_id = expected_agent_id
        self._initialized = False
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker_wait_seconds = max(float(timeout) + 1.0, 2.0)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        current_loop = asyncio.get_running_loop()
        if self._owner_loop is None:
            self._owner_loop = current_loop
        elif current_loop is not self._owner_loop:
            raise HAMMemoryError("HAM transport must run on its owning event loop")
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise HAMMemoryError(
                f"HAM request failed with status {status}", status_code=status
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HAMMemoryError(f"HAM request failed: {type(exc).__name__}") from exc

    def run_on_owner(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run a read submitted by a synchronous SDK tool on the client loop."""
        owner = self._owner_loop
        if owner is None or not owner.is_running() or owner.is_closed():
            raise HAMMemoryError("HAM transport owner event loop is unavailable")
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is owner:
            raise HAMMemoryError("Synchronous HAM bridge cannot block its owning loop")
        future = asyncio.run_coroutine_threadsafe(operation(), owner)
        try:
            return future.result(timeout=self._worker_wait_seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise HAMMemoryError("HAM tool read exceeded its deadline") from exc

    async def initialize(self) -> None:
        """Verify principal and least authority before the first memory mutation."""
        self._initialized = False
        identity = await self._request("GET", "/whoami")
        if (
            not isinstance(identity, dict)
            or identity.get("agent_id") != self.expected_agent_id
        ):
            raise HAMMemoryError(
                "HAM credential identity does not match expected agent"
            )
        boundary = identity.get("scope_boundary") or {}
        if (
            identity.get("role") != "agent"
            or not isinstance(boundary, dict)
            or boundary.get("mode") != "credential_allowlist"
            or boundary.get("allowed_scopes") != [self.scope]
        ):
            raise HAMMemoryError(
                "HAM credential must be a non-admin agent restricted to exactly the configured project scope"
            )
        projects = await self._request("GET", "/projects")
        if not isinstance(projects, list):
            raise HAMMemoryError("HAM project response was malformed")
        visible = {
            str(item.get("slug")): item for item in projects if isinstance(item, dict)
        }
        configured = visible.get(self.project)
        if configured is None:
            raise HAMMemoryError(
                f"HAM credential cannot access configured project {self.project!r}"
            )
        if configured.get("scope") != self.scope:
            raise HAMMemoryError(
                "HAM project scope does not match the configured least-privilege scope"
            )
        if self.repo and configured.get("repo") not in {None, self.repo}:
            raise HAMMemoryError("HAM project repository attribution does not match")
        self._initialized = True

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()

    @staticmethod
    def _metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {"agent_id", "actor_type", "credential_id", "run_id"}
        return {key: value for key, value in metadata.items() if key not in reserved}

    @staticmethod
    def _bounded_key(value: str) -> str:
        """HAM keys and cues have a 200-character protocol limit."""
        return (
            value
            if len(value) <= 200
            else "sha256:" + hashlib.sha256(value.encode()).hexdigest()
        )

    async def _assert_write_identity(
        self, result: Dict[str, Any], memory_id: int
    ) -> None:
        """Verify server-side attribution, including idempotent retry responses."""
        attributed_agent = result.get("agent_id") or (result.get("metadata") or {}).get(
            "agent_id"
        )
        if not attributed_agent:
            stored = await self.get(memory_id)
            attributed_agent = (stored or {}).get("metadata", {}).get("agent_id")
        if attributed_agent != self.expected_agent_id:
            raise HAMMemoryError(
                "HAM write identity mismatch: the credential is not bound to the "
                f"expected principal {self.expected_agent_id!r}"
            )

    async def add(
        self,
        *,
        content: str,
        source_id: str,
        timestamp: str,
        memory_type: str,
        metadata: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> int:
        await self._ensure_initialized()
        payload = {
            "content": content,
            "timestamp": timestamp,
            "metadata": {
                **self._metadata(metadata),
                "source_memory_id": source_id,
                "audience": metadata.get("audience", "project"),
            },
            "type": memory_type,
            "title": f"Katbot {memory_type}",
            "scopes": [self.scope],
            "project": self.project,
            "repo": self.repo,
            "task": "katbot-runtime-memory",
            "durability": "project",
            "visibility": "shared",
            "idempotency_key": self._bounded_key(
                idempotency_key or f"evolving-ai:{source_id}"
            ),
            "cues": [
                self._bounded_key(f"katbot {memory_type}"),
                self._bounded_key(f"source memory {source_id}"),
            ],
        }
        result = await self._request("POST", "/ingest", json=payload)
        memory_id = int(result["id"])
        await self._assert_write_identity(result, memory_id)
        return memory_id

    async def search(
        self,
        query: str,
        *,
        top_k: int,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "query": query,
            "top_k": min(max(top_k, 1), 100),
            "scopes": [self.scope],
            "project": self.project,
            "repo": self.repo,
        }
        if memory_type:
            payload["types"] = [memory_type]
        result = await self._request("POST", "/search", json=payload)
        if not isinstance(result, list):
            raise HAMMemoryError("HAM search response was malformed")
        return result

    async def recent(
        self,
        *,
        limit: int,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "limit": min(max(limit, 1), 100),
            "scopes": [self.scope],
            "project": self.project,
            "repo": self.repo,
        }
        if memory_type:
            payload["types"] = [memory_type]
        result = await self._request("POST", "/memories/recent", json=payload)
        if not isinstance(result, list):
            raise HAMMemoryError("HAM recent response was malformed")
        return result

    async def page(
        self,
        *,
        limit: int,
        cursor: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Page deterministically through visible memories in newest-first order."""
        payload: Dict[str, Any] = {
            "limit": min(max(limit, 1), 100),
            "scopes": [self.scope],
            "project": self.project,
            "repo": self.repo,
        }
        if cursor:
            payload["cursor"] = cursor
        if memory_type:
            payload["types"] = [memory_type]
        result = await self._request("POST", "/memories/page", json=payload)
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise HAMMemoryError("HAM memory page response was malformed")
        next_cursor = result.get("next_cursor")
        if next_cursor is not None and not isinstance(next_cursor, str):
            raise HAMMemoryError("HAM memory page cursor was malformed")
        return result["items"], next_cursor

    async def get(self, memory_id: int) -> Optional[Dict[str, Any]]:
        try:
            result = await self._request("GET", f"/memories/{memory_id}")
        except HAMMemoryError as exc:
            if exc.status_code == 404:
                return None
            raise
        if not isinstance(result, dict):
            raise HAMMemoryError("HAM memory response was malformed")
        return result

    async def stats(self) -> Dict[str, Any]:
        result = await self._request("GET", "/stats")
        if not isinstance(result, dict):
            raise HAMMemoryError("HAM stats response was malformed")
        return result

    async def supersede(
        self,
        memory_id: int,
        *,
        expected_version: int,
        content: str,
        source_id: str,
        timestamp: str,
        memory_type: str,
        metadata: Dict[str, Any],
    ) -> int:
        await self._ensure_initialized()
        payload = {
            "content": content,
            "timestamp": timestamp,
            "metadata": {
                **self._metadata(metadata),
                "source_memory_id": source_id,
                "audience": metadata.get("audience", "project"),
            },
            "type": memory_type,
            "scopes": [self.scope],
            "project": self.project,
            "repo": self.repo,
            "task": "katbot-runtime-memory",
            "durability": "project",
            "visibility": "shared",
            "expected_version": expected_version,
            "idempotency_key": self._bounded_key(
                f"evolving-ai:supersede:{memory_id}:{source_id}"
            ),
            "reason": "Katbot memory update",
        }
        result = await self._request(
            "POST", f"/memories/{memory_id}/supersede", json=payload
        )
        replacement_id = int(result["id"])
        await self._assert_write_identity(result, replacement_id)
        return replacement_id

    async def retract(self, memory_id: int, *, expected_version: int) -> bool:
        await self._ensure_initialized()
        await self._request(
            "POST",
            f"/memories/{memory_id}/retract",
            json={
                "expected_version": expected_version,
                "reason": "Retracted by Katbot memory lifecycle",
            },
        )
        return True

    async def close(self) -> None:
        if self._owner_loop is not None and asyncio.get_running_loop() is not self._owner_loop:
            raise HAMMemoryError("HAM transport must close on its owning event loop")
        await self._client.aclose()
