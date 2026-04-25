"""
FastAPI web server for the Self-Improving AI Agent with Swagger documentation.

This is the thin entry point. Route handlers live in evolving_agent/api/routes/.
"""

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import evolving_agent.utils.app_state as app_state
from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.integrations.discord_integration import DiscordIntegration
from evolving_agent.self_modification.github_enhanced_modifier import GitHubEnabledSelfModifier
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import API_KEY_HEADER, get_agent, verify_api_key  # noqa: F401 — re-exported for tests and routers
from evolving_agent.utils.error_recovery import error_recovery_manager
from evolving_agent.utils.logging import setup_logger

# Re-export app_state globals so that existing code doing
# `import evolving_agent.utils.api_server as m; m.agent` keeps working.
from evolving_agent.utils.app_state import (  # noqa: F401
    agent,
    discord_integration,
    github_modifier,
    server_shutdown,
)

logger = setup_logger(__name__)

# How long (seconds) to wait for in-flight requests during shutdown
graceful_shutdown_timeout = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the agent with graceful shutdown."""
    try:
        logger.info("Initializing Self-Improving Agent...")
        app_state.agent = SelfImprovingAgent()
        await app_state.agent.initialize()
        logger.info("Agent initialized successfully")

        # Initialize GitHub modifier if GitHub credentials are available
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPO")

        if github_token and github_repo:
            logger.info("Initializing GitHub integration...")
            local_repo_path = os.getenv("GITHUB_LOCAL_REPO_PATH", ".")
            app_state.github_modifier = GitHubEnabledSelfModifier(
                github_token=github_token, repo_name=github_repo, local_repo_path=local_repo_path
            )
            await app_state.github_modifier.initialize()
            app_state.agent.github_modifier = app_state.github_modifier
            logger.info("GitHub integration initialized successfully")
        else:
            logger.warning(
                "GitHub credentials not found. GitHub features will be unavailable."
            )

        # Initialize Discord integration if enabled
        if config.discord_enabled and config.discord_bot_token:
            logger.info("Initializing Discord integration...")
            app_state.discord_integration = DiscordIntegration(
                bot_token=config.discord_bot_token,
                agent=app_state.agent,
                config=config
            )
            await app_state.discord_integration.initialize()

            # Start Discord bot in background task
            asyncio.create_task(app_state.discord_integration.start())
            logger.info("Discord integration started successfully")
        else:
            logger.info(
                "Discord integration disabled or token not configured. "
                "Discord features will be unavailable."
            )

        yield
    finally:
        # Graceful shutdown
        logger.info("Initiating graceful shutdown...")
        app_state.server_shutdown = True

        # Cleanup Discord integration
        if app_state.discord_integration:
            logger.info("Shutting down Discord integration...")
            try:
                await app_state.discord_integration.close()
                logger.info("Discord integration shut down successfully")
            except Exception as e:
                logger.error(f"Error shutting down Discord: {e}")

        if app_state.agent:
            logger.info("Cleaning up agent...")
            try:
                await app_state.agent.cleanup()
                logger.info("Agent cleanup completed")
            except Exception as e:
                logger.error(f"Error during agent cleanup: {e}")

        # Clean up error recovery resources
        try:
            error_recovery_manager.cleanup_old_checkpoints()
            logger.info("Error recovery resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up error recovery: {e}")

        logger.info("Graceful shutdown completed")


# FastAPI app initialization
app = FastAPI(
    title="Self-Improving AI Agent API",
    description="""
    A sophisticated self-improving AI agent with persistent memory, dynamic context,
    self-evaluation, and code analysis capabilities.

    ## Features

    * **Interactive Chat**: Send queries and receive intelligent responses
    * **Memory System**: Persistent long-term memory using vector embeddings
    * **Web Search**: Real-time web search with multiple provider support
    * **Self-Analysis**: Code analysis and improvement recommendations
    * **Knowledge Management**: Automatic knowledge extraction and organization
    * **Multi-LLM Support**: OpenAI, Anthropic, and OpenRouter integration
    * **GitHub Integration**: Automated code improvements via pull requests
    * **Discord Integration**: Real-time chat bot interface
    * **OpenAI Compatible**: Drop-in `/v1/chat/completions` endpoint for standard tooling

    ## Getting Started

    1. Check agent status with `/status`
    2. Send a query using `/chat`
    3. Search the web with `/web-search`
    4. Explore memories with `/memories`
    5. Trigger code analysis with `/analyze`
    """,
    version="1.0.0",
    contact={
        "name": "Self-Improving AI Agent",
        "url": "https://github.com/your-repo/evolving-ai-agent",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
)

# Add CORS middleware
_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
if _cors_origins == "*":
    _allowed_origins = ["*"]
    _allow_credentials = False
else:
    _allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error recovery middleware
@app.middleware("http")
async def error_recovery_middleware(request: Request, call_next):
    """Middleware for error recovery and graceful degradation."""
    from fastapi import HTTPException as FastAPIHTTPException

    try:
        response = await call_next(request)
        return response
    except FastAPIHTTPException as e:
        # Let HTTP exceptions propagate normally
        raise e
    except Exception as e:
        logger.error(f"Unhandled error in request {request.url}: {e}")

        # Check if we should return a degraded response
        if error_recovery_manager.is_degraded_mode():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "message": "The system is operating in degraded mode. Please try again later.",
                    "degraded_mode": True,
                    "timestamp": datetime.now().isoformat()
                }
            )

        # Return generic error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred. Please try again.",
                "timestamp": datetime.now().isoformat()
            }
        )


# Register routers — imported after app is constructed to avoid circular init issues
from evolving_agent.api.routes.discord import router as discord_router
from evolving_agent.api.routes.feedback import router as feedback_router
from evolving_agent.api.routes.general import router as general_router
from evolving_agent.api.routes.github import router as github_router
from evolving_agent.api.routes.interaction import router as interaction_router
from evolving_agent.api.routes.knowledge import router as knowledge_router
from evolving_agent.api.routes.memory import router as memory_router
from evolving_agent.api.routes.self_improvement import router as self_improvement_router
from evolving_agent.api.routes.system import router as system_router
from evolving_agent.api.routes.web_search import router as web_search_router

app.include_router(general_router)
app.include_router(interaction_router)
app.include_router(memory_router)
app.include_router(knowledge_router)
app.include_router(self_improvement_router)
app.include_router(github_router)
app.include_router(discord_router)
app.include_router(web_search_router)
app.include_router(system_router)
app.include_router(feedback_router)


# ---------------------------------------------------------------------------
# Module shim: make `api_server_module.agent = x` propagate to app_state so
# that test fixtures that set attributes on this module still work after the
# refactor.  We replace this module in sys.modules with a thin wrapper.
# ---------------------------------------------------------------------------
import sys as _sys
import types as _types


class _ApiServerModule(_types.ModuleType):
    """Wrapper module that syncs state-attribute writes to app_state."""

    _STATE_ATTRS = frozenset({"agent", "github_modifier", "discord_integration", "server_shutdown"})

    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        if name in self._STATE_ATTRS:
            import evolving_agent.utils.app_state as _state
            _state.__dict__[name] = value

    def __getattr__(self, name: str):
        if name in self._STATE_ATTRS:
            import evolving_agent.utils.app_state as _state
            return getattr(_state, name)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_current = _sys.modules[__name__]
_shim = _ApiServerModule(__name__, _current.__doc__)
_shim.__dict__.update(_current.__dict__)
_sys.modules[__name__] = _shim


if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        app_state.server_shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the server
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "evolving_agent.utils.api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
