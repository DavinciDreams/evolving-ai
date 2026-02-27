"""
TPMJS (Tool Package Manager) integration for discovering and executing AI tools.

API docs: https://tpmjs.com/docs/api
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from ..utils.logging import setup_logger

logger = setup_logger(__name__)

BASE_URL = "https://tpmjs.com/api"


class TPMJSClient:
    """Client for the TPMJS tool registry API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.timeout = 30.0

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def search_tools(
        self, query: str, limit: int = 5, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search TPMJS for tools matching a query.

        Args:
            query: Search query (e.g. "convert pdf to markdown")
            limit: Max results (max 20)
            category: Optional category filter

        Returns:
            List of tool dicts with name, package, description, qualityScore
        """
        params: Dict[str, Any] = {"q": query, "limit": min(limit, 20)}
        if category:
            params["category"] = category

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{BASE_URL}/tools/search",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("success") and data.get("data"):
                    return data["data"]
                return data.get("data", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"TPMJS search failed ({e.response.status_code}): {e}")
            return []
        except Exception as e:
            logger.error(f"TPMJS search error: {e}")
            return []

    async def get_tool_details(
        self, package: str, tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get detailed info about a specific tool.

        Args:
            package: NPM package name (e.g. "@tpmjs/hello")
            tool_name: Tool name within the package (e.g. "helloWorldTool")

        Returns:
            Tool details dict or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{BASE_URL}/tools/{package}/{tool_name}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data")
        except Exception as e:
            logger.error(f"TPMJS get tool details error: {e}")
            return None

    async def execute_tool(
        self,
        package: str,
        tool_name: str,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a tool from the TPMJS registry.

        Args:
            package: NPM package name
            tool_name: Tool name within the package
            prompt: Prompt/input for the tool (max 2000 chars)
            parameters: Optional tool-specific parameters

        Returns:
            Tool execution output as string
        """
        body: Dict[str, Any] = {"prompt": prompt[:2000]}
        if parameters:
            body["parameters"] = parameters

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{BASE_URL}/tools/execute/{package}/{tool_name}",
                    json=body,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return json.dumps(data.get("data", data), default=str)
        except httpx.HTTPStatusError as e:
            error_msg = f"TPMJS execute failed ({e.response.status_code})"
            logger.error(f"{error_msg}: {e}")
            return json.dumps({"error": error_msg})
        except Exception as e:
            logger.error(f"TPMJS execute error: {e}")
            return json.dumps({"error": str(e)})

    async def create_tool(
        self,
        name: str,
        description: str,
        category: str,
        code: str,
    ) -> Dict[str, Any]:
        """Create a new tool on TPMJS.

        This generates the tool package scaffold. The actual publishing
        requires npm publish, but this creates the structure.

        Args:
            name: Tool name (e.g. "my-converter")
            description: What the tool does
            category: TPMJS category (e.g. "text-analysis", "web-scraping")
            code: Tool implementation code (JavaScript/TypeScript)

        Returns:
            Dict with package info and publish instructions
        """
        tool_package = {
            "name": f"@tpmjs/{name}",
            "version": "1.0.0",
            "description": description,
            "keywords": ["tpmjs"],
            "tpmjs": {"category": category},
            "main": "index.js",
            "code": code,
        }

        # For now, return the scaffold. Full publish integration
        # requires npm CLI or TPMJS publish API when available.
        logger.info(f"Tool scaffold created for @tpmjs/{name}")
        return {
            "package": tool_package,
            "status": "scaffold_created",
            "publish_command": f"cd {name} && npm publish --access public",
            "note": "Publish to npm with the 'tpmjs' keyword to auto-list on tpmjs.com",
        }

    async def list_tools(
        self,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tools from the TPMJS registry.

        Args:
            category: Optional category filter
            limit: Max results (max 50)
            offset: Pagination offset

        Returns:
            List of tool dicts
        """
        params: Dict[str, Any] = {"limit": min(limit, 50), "offset": offset}
        if category:
            params["category"] = category

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{BASE_URL}/tools",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.error(f"TPMJS list tools error: {e}")
            return []
