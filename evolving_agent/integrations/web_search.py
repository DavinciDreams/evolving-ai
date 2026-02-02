"""
Web search integration for the Self-Improving AI Agent.

Supports multiple search providers:
- DuckDuckGo (free, no API key required)
- Tavily (AI-optimized search, requires API key)
- SerpAPI (Google search API, requires API key)
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from ..utils.logging import setup_logger


class WebSearchIntegration:
    """
    Web search integration supporting multiple search providers.

    Features:
    - Multiple search provider support (DuckDuckGo, Tavily, SerpAPI)
    - Automatic fallback between providers
    - Result caching to reduce API calls
    - Content extraction from web pages
    - Rate limiting and error handling
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        serpapi_key: Optional[str] = None,
        default_provider: str = "duckduckgo",
        max_results: int = 5,
        cache_ttl: int = 3600,
    ):
        """
        Initialize web search integration.

        Args:
            tavily_api_key: Optional Tavily API key
            serpapi_key: Optional SerpAPI key
            default_provider: Default search provider to use
            max_results: Maximum number of search results to return
            cache_ttl: Cache time-to-live in seconds
        """
        self.logger = setup_logger(__name__)
        self.tavily_api_key = tavily_api_key
        self.serpapi_key = serpapi_key
        self.default_provider = default_provider
        self.max_results = max_results
        self.cache_ttl = cache_ttl

        # Search result cache
        self._cache: Dict[str, Dict[str, Any]] = {}

        # HTTP client for requests
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        self.logger.info(f"Web search integration initialized with provider: {default_provider}")

    async def initialize(self):
        """Initialize the web search integration."""
        try:
            # Test connectivity
            available_providers = []

            if self.tavily_api_key:
                available_providers.append("tavily")
            if self.serpapi_key:
                available_providers.append("serpapi")
            available_providers.append("duckduckgo")  # Always available

            self.logger.info(f"Available search providers: {', '.join(available_providers)}")

        except Exception as e:
            self.logger.error(f"Failed to initialize web search: {e}")
            raise

    async def search(
        self,
        query: str,
        provider: Optional[str] = None,
        max_results: Optional[int] = None,
        include_content: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform a web search.

        Args:
            query: Search query
            provider: Optional provider override (duckduckgo, tavily, serpapi)
            max_results: Optional max results override
            include_content: Whether to fetch and include page content

        Returns:
            Dictionary containing search results and metadata
        """
        try:
            # Check cache first
            cache_key = f"{query}:{provider or self.default_provider}:{max_results or self.max_results}"
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if (datetime.now().timestamp() - cached["timestamp"]) < self.cache_ttl:
                    self.logger.info(f"Returning cached results for: {query[:50]}")
                    return cached["results"]

            provider = provider or self.default_provider
            max_results = max_results or self.max_results

            self.logger.info(f"Searching with {provider}: {query[:100]}")

            # Try the requested provider first, then fallback
            providers_to_try = [provider]
            if provider != "duckduckgo":
                providers_to_try.append("duckduckgo")

            last_error = None
            for prov in providers_to_try:
                try:
                    if prov == "duckduckgo":
                        results = await self._search_duckduckgo(query, max_results)
                    elif prov == "tavily" and self.tavily_api_key:
                        results = await self._search_tavily(query, max_results)
                    elif prov == "serpapi" and self.serpapi_key:
                        results = await self._search_serpapi(query, max_results)
                    else:
                        continue

                    # Optionally fetch content from results
                    if include_content and results.get("results"):
                        results["results"] = await self._enrich_with_content(
                            results["results"]
                        )

                    # Cache the results
                    self._cache[cache_key] = {
                        "timestamp": datetime.now().timestamp(),
                        "results": results,
                    }

                    return results

                except Exception as e:
                    last_error = e
                    self.logger.warning(f"Provider {prov} failed: {e}")
                    continue

            raise Exception(f"All providers failed. Last error: {last_error}")

        except Exception as e:
            self.logger.error(f"Search failed for query '{query}': {e}")
            return {
                "query": query,
                "results": [],
                "error": str(e),
                "provider": provider,
                "timestamp": datetime.now().isoformat(),
            }

    async def _search_duckduckgo(
        self, query: str, max_results: int
    ) -> Dict[str, Any]:
        """
        Search using DuckDuckGo (free, no API key required).
        """
        try:
            # Use DuckDuckGo's instant answer API
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json"

            response = await self.http_client.get(url)
            response.raise_for_status()
            data = response.json()

            results = []

            # Extract results from DuckDuckGo response
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", "DuckDuckGo Result"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", ""),
                    "source": "duckduckgo",
                })

            # Add related topics
            for topic in data.get("RelatedTopics", [])[:max_results - 1]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "duckduckgo",
                    })

            # If no results from instant answer, try HTML scraping
            if not results:
                results = await self._search_duckduckgo_html(query, max_results)

            return {
                "query": query,
                "results": results[:max_results],
                "provider": "duckduckgo",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"DuckDuckGo search failed: {e}")
            raise

    async def _search_duckduckgo_html(
        self, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback HTML scraping for DuckDuckGo.
        """
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one(".result__title")
                snippet_elem = result.select_one(".result__snippet")
                url_elem = result.select_one(".result__url")

                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": url_elem.get("href", "") if url_elem else "",
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        "source": "duckduckgo",
                    })

            return results

        except Exception as e:
            self.logger.error(f"DuckDuckGo HTML scraping failed: {e}")
            return []

    async def _search_tavily(self, query: str, max_results: int) -> Dict[str, Any]:
        """
        Search using Tavily AI (requires API key).
        Tavily is optimized for AI applications.
        """
        try:
            url = "https://api.tavily.com/search"

            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False,
            }

            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "score": item.get("score", 0),
                    "source": "tavily",
                })

            return {
                "query": query,
                "results": results,
                "answer": data.get("answer"),
                "provider": "tavily",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Tavily search failed: {e}")
            raise

    async def _search_serpapi(self, query: str, max_results: int) -> Dict[str, Any]:
        """
        Search using SerpAPI (requires API key).
        Provides Google search results.
        """
        try:
            url = "https://serpapi.com/search"

            params = {
                "api_key": self.serpapi_key,
                "q": query,
                "num": max_results,
                "engine": "google",
            }

            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", 0),
                    "source": "serpapi",
                })

            return {
                "query": query,
                "results": results,
                "provider": "serpapi",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"SerpAPI search failed: {e}")
            raise

    async def _enrich_with_content(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fetch and extract content from result URLs.
        """
        enriched = []

        for result in results:
            try:
                url = result.get("url")
                if not url:
                    enriched.append(result)
                    continue

                # Fetch page content
                response = await self.http_client.get(url, timeout=10.0)
                if response.status_code != 200:
                    enriched.append(result)
                    continue

                # Extract text content
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text(separator=" ", strip=True)

                # Limit content length
                content = text[:2000] if len(text) > 2000 else text

                result["content"] = content
                enriched.append(result)

            except Exception as e:
                self.logger.warning(f"Failed to fetch content from {result.get('url')}: {e}")
                enriched.append(result)

        return enriched

    async def fetch_url_content(self, url: str) -> Dict[str, Any]:
        """
        Fetch and extract content from a specific URL.

        Args:
            url: URL to fetch

        Returns:
            Dictionary with extracted content and metadata
        """
        try:
            self.logger.info(f"Fetching content from: {url}")

            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "iframe"]):
                element.decompose()

            # Extract title
            title = soup.find("title")
            title_text = title.get_text(strip=True) if title else ""

            # Extract main content
            text = soup.get_text(separator=" ", strip=True)

            # Extract links
            links = [a.get("href") for a in soup.find_all("a", href=True)][:20]

            return {
                "url": url,
                "title": title_text,
                "content": text[:5000],  # Limit content
                "links": links,
                "success": True,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to fetch URL content: {e}")
            return {
                "url": url,
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
            }

    async def search_and_summarize(
        self, query: str, max_results: int = 3
    ) -> Dict[str, Any]:
        """
        Search the web and provide a summarized answer.

        Args:
            query: Search query
            max_results: Maximum results to fetch

        Returns:
            Dictionary with search results and summary
        """
        try:
            # Perform search
            search_results = await self.search(
                query, max_results=max_results, include_content=True
            )

            if not search_results.get("results"):
                return {
                    "query": query,
                    "summary": "No results found.",
                    "sources": [],
                }

            # Format results for summary
            sources = []
            for i, result in enumerate(search_results["results"], 1):
                sources.append({
                    "position": i,
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("snippet", ""),
                })

            return {
                "query": query,
                "sources": sources,
                "provider": search_results.get("provider"),
                "timestamp": search_results.get("timestamp"),
            }

        except Exception as e:
            self.logger.error(f"Search and summarize failed: {e}")
            return {
                "query": query,
                "error": str(e),
                "sources": [],
            }

    async def close(self):
        """Clean up resources."""
        try:
            await self.http_client.aclose()
            self.logger.info("Web search integration closed")
        except Exception as e:
            self.logger.error(f"Error closing web search integration: {e}")

    def clear_cache(self):
        """Clear the search result cache."""
        self._cache.clear()
        self.logger.info("Search cache cleared")
