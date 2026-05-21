"""Web search endpoints: /web-search, /web-search/status."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import WebSearchRequest, WebSearchResponse

logger = setup_logger(__name__)

router = APIRouter()


@router.post("/web-search", response_model=WebSearchResponse, tags=["Web Search"])
async def search_web(
    request: WebSearchRequest,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Search the web for information.

    The agent will:
    - Search the web using available providers (DuckDuckGo, Tavily, SerpAPI)
    - Return relevant search results with titles, URLs, and snippets
    - Optionally fetch and include full page content
    - Cache results to improve performance
    - Store search queries in memory for learning
    """
    try:
        if not current_agent.web_search:
            raise HTTPException(
                status_code=503,
                detail="Web search not enabled. Please configure WEB_SEARCH_ENABLED=true in .env"
            )

        logger.info(f"Web search request: {request.query}")

        # Perform the search
        results = await current_agent.search_web(
            query=request.query,
            max_results=request.max_results,
        )

        if results.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Search failed: {results['error']}"
            )

        return WebSearchResponse(
            query=results.get("query", request.query),
            sources=results.get("sources", []),
            provider=results.get("provider"),
            timestamp=results.get("timestamp", datetime.now().isoformat()),
            cached=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing web search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error performing web search: {str(e)}"
        )


@router.get("/web-search/status", tags=["Web Search"])
async def get_web_search_status(
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Get web search integration status.

    Returns information about available search providers and configuration.
    """
    try:
        if not current_agent.web_search:
            return {
                "enabled": False,
                "message": "Web search not enabled",
            }

        providers = {
            "duckduckgo": True,  # Always available
            "tavily": bool(config.tavily_api_key),
            "serpapi": bool(config.serpapi_key),
        }

        return {
            "enabled": True,
            "default_provider": config.web_search_default_provider,
            "max_results": config.web_search_max_results,
            "available_providers": providers,
            "cache_enabled": True,
        }

    except Exception as e:
        logger.error(f"Error getting web search status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting web search status: {str(e)}"
        )
