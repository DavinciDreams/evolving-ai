"""Web search endpoints: /web-search, /web-search/status."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.api.routes.integration_requests import (
    bounded_json,
    json_request_schema,
)
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import get_agent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import WebSearchRequest, WebSearchResponse
from evolving_agent.utils.secret_redaction import redact_text, redact_value

logger = setup_logger(__name__)

router = APIRouter()


@router.post(
    "/web-search",
    response_model=WebSearchResponse,
    tags=["Web Search"],
    openapi_extra=json_request_schema(WebSearchRequest),
)
async def search_web(
    incoming: Request,
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
    request = await bounded_json(incoming, WebSearchRequest, 8192)
    try:
        if not current_agent.web_search:
            raise HTTPException(
                status_code=503,
                detail="Web search not enabled. Please configure WEB_SEARCH_ENABLED=true in .env",
            )

        runtime = getattr(current_agent, "runtime", None)
        if runtime is None:
            raise HTTPException(503, "Bounded runtime unavailable")
        steward = getattr(current_agent, "steward", None)
        dreams = getattr(current_agent, "dream_service", None)
        learning = getattr(steward, "learning", None)
        lab = getattr(steward, "lab", None)
        if (
            runtime.busy
            or (steward and steward.busy)
            or (dreams and dreams.status()["running"])
            or (learning and learning.status()["running"])
            or (lab and lab.status()["busy"])
        ):
            raise RuntimeBusyError("Another operation is running")
        # These calls and runtime.run admission do not await, so no other agent
        # operation can slip between the shared idle check and lease acquisition.
        for service in (dreams, learning):
            if service:
                service.note_activity()
        query = redact_text(request.query)[0]
        results = await runtime.run(
            lambda: current_agent.search_web(
                query=query, max_results=request.max_results
            ),
            kind="web_search",
        )
        results = redact_value(results)[0]

        if results.get("error"):
            raise HTTPException(status_code=500, detail="Web search provider failed")

        return WebSearchResponse(
            query=results.get("query", query),
            sources=results.get("sources", []),
            provider=results.get("provider"),
            timestamp=results.get("timestamp", datetime.now().isoformat()),
            cached=False,
        )

    except HTTPException:
        raise
    except RuntimeBusyError:
        raise HTTPException(
            409, "Katbot is busy; inspect steward status before retrying"
        ) from None
    except TimeoutError:
        raise HTTPException(
            504, "Web search deadline exceeded; pending work retains its lease"
        ) from None
    except Exception as e:
        logger.error("Web search failed: {}", type(e).__name__)
        raise HTTPException(
            status_code=500, detail="Web search is unavailable"
        ) from None


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
        logger.error("Web search status failed: {}", type(e).__name__)
        raise HTTPException(
            status_code=500, detail="Web search status is unavailable"
        ) from None
