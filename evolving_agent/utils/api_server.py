"""
FastAPI web server for the Self-Improving AI Agent with Swagger documentation.
"""

import asyncio
import os
import uuid
import signal
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.integrations.discord_integration import DiscordIntegration
from evolving_agent.utils.config import config
from evolving_agent.utils.github_enhanced_modifier import GitHubEnabledSelfModifier
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.error_recovery import error_recovery_manager
from evolving_agent.utils.llm_interface import llm_manager

logger = setup_logger(__name__)

# Global agent instance
agent: Optional[SelfImprovingAgent] = None
github_modifier: Optional[GitHubEnabledSelfModifier] = None
discord_integration: Optional[DiscordIntegration] = None

# Server state
server_shutdown = False
graceful_shutdown_timeout = 30  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the agent with graceful shutdown."""
    global agent, github_modifier, discord_integration, server_shutdown
    try:
        logger.info("Initializing Self-Improving Agent...")
        agent = SelfImprovingAgent()
        await agent.initialize()
        logger.info("Agent initialized successfully")

        # Initialize GitHub modifier if GitHub credentials are available
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPO")

        if github_token and github_repo:
            logger.info("Initializing GitHub integration...")
            github_modifier = GitHubEnabledSelfModifier(
                github_token=github_token, repo_name=github_repo, local_repo_path="."
            )
            await github_modifier.initialize()
            logger.info("GitHub integration initialized successfully")
        else:
            logger.warning(
                "GitHub credentials not found. GitHub features will be unavailable."
            )

        # Initialize Discord integration if enabled
        if config.discord_enabled and config.discord_bot_token:
            logger.info("Initializing Discord integration...")
            discord_integration = DiscordIntegration(
                bot_token=config.discord_bot_token,
                agent=agent,
                config=config
            )
            await discord_integration.initialize()

            # Start Discord bot in background task
            asyncio.create_task(discord_integration.start())
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
        server_shutdown = True
        
        # Cleanup Discord integration
        if discord_integration:
            logger.info("Shutting down Discord integration...")
            try:
                await discord_integration.close()
                logger.info("Discord integration shut down successfully")
            except Exception as e:
                logger.error(f"Error shutting down Discord: {e}")

        if agent:
            logger.info("Cleaning up agent...")
            try:
                await agent.cleanup()
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


# Pydantic models for API requests and responses
class QueryRequest(BaseModel):
    """Request model for agent queries."""

    query: str = Field(
        ...,
        description="The query to send to the agent",
        min_length=1,
        max_length=10000,
    )
    context_hints: Optional[List[str]] = Field(
        None, description="Optional context hints to guide the response"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What are the best practices for code optimization?",
                "context_hints": ["performance", "maintainability"],
            }
        }
    }


class QueryResponse(BaseModel):
    """Response model for agent queries."""

    response: str = Field(..., description="The agent's response to the query")
    query_id: str = Field(..., description="Unique identifier for this query")
    timestamp: datetime = Field(..., description="When the query was processed")
    evaluation_score: Optional[float] = Field(
        None, description="Quality score of the response (0.0-1.0)"
    )
    memory_stored: bool = Field(
        ..., description="Whether the interaction was stored in memory"
    )
    knowledge_updated: bool = Field(
        ..., description="Whether new knowledge was extracted"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Here are the key best practices for code optimization...",
                "query_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2025-06-28T20:30:00Z",
                "evaluation_score": 0.85,
                "memory_stored": True,
                "knowledge_updated": True,
            }
        }
    }


class AnalysisRequest(BaseModel):
    """Request model for code analysis."""

    evaluation_insights: Optional[Dict[str, Any]] = Field(
        None, description="Evaluation insights to consider"
    )
    knowledge_suggestions: Optional[List[Dict[str, Any]]] = Field(
        None, description="Knowledge-based suggestions"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "evaluation_insights": {
                    "score_trend": "improving",
                    "recent_average_score": 0.85,
                    "confidence_level": 0.9,
                },
                "knowledge_suggestions": [
                    {
                        "message": "Consider implementing caching",
                        "priority": 0.8,
                        "category": "performance",
                    }
                ],
            }
        }
    }


class AnalysisResponse(BaseModel):
    """Response model for code analysis."""

    improvement_potential: float = Field(
        ..., description="Overall improvement potential (0.0-1.0)"
    )
    improvement_opportunities: List[Dict[str, Any]] = Field(
        ..., description="Specific improvement opportunities"
    )
    recommendations: List[str] = Field(..., description="Actionable recommendations")
    codebase_metrics: Dict[str, Any] = Field(
        ..., description="Current codebase metrics"
    )
    analysis_id: str = Field(..., description="Unique identifier for this analysis")
    timestamp: datetime = Field(..., description="When the analysis was performed")


class MemoryItem(BaseModel):
    """Memory item model."""

    id: str = Field(..., description="Unique memory identifier")
    content: str = Field(..., description="Memory content")
    timestamp: datetime = Field(..., description="When the memory was created")
    metadata: Dict[str, Any] = Field(..., description="Memory metadata")


class KnowledgeItem(BaseModel):
    """Knowledge base item model."""

    id: str = Field(..., description="Unique knowledge identifier")
    content: str = Field(..., description="Knowledge content")
    category: str = Field(..., description="Knowledge category")
    priority: float = Field(..., description="Knowledge priority/relevance")
    timestamp: datetime = Field(..., description="When the knowledge was added")


class AgentStatus(BaseModel):
    """Agent status model."""

    is_initialized: bool = Field(..., description="Whether the agent is initialized")
    session_id: Optional[str] = Field(None, description="Current session ID")
    total_interactions: int = Field(..., description="Total number of interactions")
    memory_count: int = Field(..., description="Number of memories stored")
    knowledge_count: int = Field(..., description="Number of knowledge items")
    uptime: str = Field(..., description="Agent uptime")


class GitHubStatus(BaseModel):
    """GitHub integration status model."""

    github_connected: bool = Field(..., description="Whether GitHub is connected")
    repository_name: Optional[str] = Field(
        None, description="Connected repository name"
    )
    local_repo_available: bool = Field(
        ..., description="Whether local repository is available"
    )
    auto_pr_enabled: bool = Field(
        ..., description="Whether auto PR creation is enabled"
    )
    open_prs_count: int = Field(..., description="Number of open pull requests")


class ImprovementRequest(BaseModel):
    """Request model for code improvements."""

    create_pr: bool = Field(True, description="Whether to create a pull request")
    evaluation_insights: Optional[Dict[str, Any]] = Field(
        None, description="Evaluation insights"
    )
    knowledge_suggestions: Optional[List[Dict[str, Any]]] = Field(
        None, description="Knowledge suggestions"
    )


class ImprovementResponse(BaseModel):
    """Response model for code improvements."""

    improvements_generated: int = Field(
        ..., description="Number of improvements generated"
    )
    improvements_validated: int = Field(
        ..., description="Number of improvements validated"
    )
    pr_created: bool = Field(..., description="Whether a pull request was created")
    pr_number: Optional[int] = Field(None, description="Pull request number if created")
    pr_url: Optional[str] = Field(None, description="Pull request URL if created")
    improvement_potential: float = Field(
        ..., description="Overall improvement potential"
    )


class WebSearchRequest(BaseModel):
    """Request model for web search."""

    query: str = Field(
        ...,
        description="Search query",
        min_length=1,
        max_length=500,
    )
    max_results: Optional[int] = Field(
        None,
        description="Maximum number of results to return",
        ge=1,
        le=10,
    )
    include_content: bool = Field(
        True,
        description="Whether to fetch and include page content",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Latest developments in AI",
                "max_results": 5,
                "include_content": True,
            }
        }
    }


class WebSearchResponse(BaseModel):
    """Response model for web search."""

    query: str = Field(..., description="The search query")
    sources: List[Dict[str, Any]] = Field(..., description="Search result sources")
    provider: Optional[str] = Field(None, description="Search provider used")
    timestamp: str = Field(..., description="When the search was performed")
    cached: bool = Field(False, description="Whether results were cached")


class RepositoryInfo(BaseModel):
    """Repository information model."""

    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name")
    description: Optional[str] = Field(None, description="Repository description")
    language: Optional[str] = Field(None, description="Primary language")
    stars: int = Field(..., description="Number of stars")
    forks: int = Field(..., description="Number of forks")
    open_issues: int = Field(..., description="Number of open issues")


class CreateIssueRequest(BaseModel):
    """Request model for creating a GitHub issue."""

    title: str = Field(
        ...,
        description="Issue title",
        min_length=1,
        max_length=255,
    )
    description: str = Field(
        ...,
        description="Issue description/body",
        min_length=1,
        max_length=65536,
    )
    labels: Optional[List[str]] = Field(
        None,
        description="Optional list of labels to add to the issue",
    )
    assignees: Optional[List[str]] = Field(
        None,
        description="Optional list of assignees (note: requires GitHub permissions)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Add new feature for Discord integration",
                "description": "Users should be able to request features from Discord...",
                "labels": ["enhancement", "discord"],
                "assignees": ["username"],
            }
        }
    }


class CreateIssueResponse(BaseModel):
    """Response model for creating a GitHub issue."""

    issue_number: int = Field(..., description="GitHub issue number")
    issue_url: str = Field(..., description="GitHub issue URL")


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error recovery middleware
@app.middleware("http")
async def error_recovery_middleware(request: Request, call_next):
    """Middleware for error recovery and graceful degradation."""
    try:
        response = await call_next(request)
        return response
    except HTTPException as e:
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


def get_agent() -> SelfImprovingAgent:
    """Dependency to get the agent instance."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return agent


@app.get("/", tags=["General"])
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Self-Improving AI Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/status",
    }


@app.get("/status", response_model=AgentStatus, tags=["General"])
async def get_status(current_agent: SelfImprovingAgent = Depends(get_agent)):
    """Get the current status of the agent."""
    try:
        # Get memory count
        memory_count = 0
        if hasattr(current_agent, "memory") and hasattr(
            current_agent.memory, "collection"
        ):
            try:
                memory_count = current_agent.memory.collection.count()
            except Exception:
                memory_count = 0

        # Get knowledge count
        knowledge_count = 0
        if hasattr(current_agent, "knowledge_base"):
            try:
                knowledge_count = len(current_agent.knowledge_base.knowledge)
            except Exception:
                knowledge_count = 0

        return AgentStatus(
            is_initialized=current_agent.initialized,
            session_id=current_agent.session_id,
            total_interactions=current_agent.interaction_count,
            memory_count=memory_count,
            knowledge_count=knowledge_count,
            uptime="Active",  # Could be calculated from initialization time
        )
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting agent status: {str(e)}"
        )


@app.post("/chat", response_model=QueryResponse, tags=["Interaction"])
async def chat_with_agent(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Send a query to the agent and receive a response.

    The agent will:
    - Process your query using its knowledge and memory
    - Generate an intelligent response
    - Evaluate the response quality
    - Store the interaction for future learning
    - Update its knowledge base if new insights are discovered
    """
    try:
        query_id = str(uuid.uuid4())
        timestamp = datetime.now()

        logger.info(f"Processing query {query_id}: {request.query[:100]}...")

        # Process the query
        response = await current_agent.run(request.query, request.context_hints)

        # Note: The agent's run method returns just the response string
        # Additional metrics would need to be retrieved separately

        return QueryResponse(
            response=response,
            query_id=query_id,
            timestamp=timestamp,
            evaluation_score=None,  # Would need to be retrieved from evaluator
            memory_stored=True,  # Assuming successful storage
            knowledge_updated=True,  # Assuming knowledge was processed
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/analyze", response_model=AnalysisResponse, tags=["Self-Improvement"])
async def analyze_code(
    request: AnalysisRequest, current_agent: SelfImprovingAgent = Depends(get_agent)
):
    """
    Trigger code analysis and get improvement recommendations.

    The agent will:
    - Analyze its own codebase structure and complexity
    - Identify improvement opportunities
    - Generate actionable recommendations
    - Consider evaluation insights and knowledge suggestions
    """
    try:
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now()

        logger.info(f"Starting code analysis {analysis_id}...")

        # Use default insights if none provided
        evaluation_insights = request.evaluation_insights or {
            "score_trend": "stable",
            "recent_average_score": 0.8,
            "confidence_level": 0.8,
        }

        knowledge_suggestions = request.knowledge_suggestions or []

        # Perform the analysis
        result = await current_agent.code_analyzer.analyze_performance_patterns(
            evaluation_insights, knowledge_suggestions
        )

        # Extract codebase metrics
        codebase_analysis = result.get("codebase_analysis", {})
        complexity_metrics = codebase_analysis.get("complexity_metrics", {})

        codebase_metrics = {
            "total_functions": complexity_metrics.get("total_functions", 0),
            "total_classes": complexity_metrics.get("total_classes", 0),
            "total_lines": complexity_metrics.get("total_lines", 0),
            "average_complexity": complexity_metrics.get("average_complexity", 0),
            "high_complexity_functions": complexity_metrics.get(
                "high_complexity_functions", []
            ),
        }

        return AnalysisResponse(
            improvement_potential=result.get("improvement_potential", 0),
            improvement_opportunities=result.get("improvement_opportunities", []),
            recommendations=result.get("recommendations", []),
            codebase_metrics=codebase_metrics,
            analysis_id=analysis_id,
            timestamp=timestamp,
        )

    except Exception as e:
        logger.error(f"Error performing code analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error performing code analysis: {str(e)}"
        )


@app.get("/memories", response_model=List[MemoryItem], tags=["Memory"])
async def get_memories(
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Retrieve stored memories from the agent's long-term memory system.

    - **limit**: Maximum number of memories to return (default: 10)
    - **offset**: Number of memories to skip (for pagination)
    - **search**: Optional search query to filter memories
    """
    try:
        if not hasattr(current_agent, "memory"):
            return []

        memories = []

        if search:
            # Search for relevant memories
            search_results = await current_agent.memory.search_memories(
                search, top_k=limit + offset
            )
            for result in search_results:
                metadata = result.get("metadata", {})
                # Get timestamp from metadata or use current time as fallback
                timestamp_str = metadata.get("timestamp")
                timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

                memories.append(
                    MemoryItem(
                        id=result.get("id", "unknown"),
                        content=result.get("content", ""),
                        timestamp=timestamp,
                        metadata=metadata,
                    )
                )
        else:
            # Get all memories by querying the collection directly
            try:
                collection = current_agent.memory.collection
                results = collection.get(limit=limit + offset, include=["documents", "metadatas"])

                if results and results.get("documents"):
                    for i, doc in enumerate(results["documents"]):
                        metadata = results["metadatas"][i] if "metadatas" in results and i < len(results["metadatas"]) else {}
                        # Get timestamp from metadata or use current time as fallback
                        timestamp_str = metadata.get("timestamp")
                        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

                        memories.append(
                            MemoryItem(
                                id=results["ids"][i] if "ids" in results else f"mem_{i}",
                                content=doc,
                                timestamp=timestamp,
                                metadata=metadata,
                            )
                        )
                else:
                    logger.warning(f"No documents in results. Results keys: {results.keys() if results else 'None'}")
            except Exception as e:
                logger.error(f"Could not retrieve all memories: {e}", exc_info=True)

        return memories[offset : offset + limit]

    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving memories: {str(e)}"
        )


@app.get("/knowledge", response_model=List[KnowledgeItem], tags=["Knowledge"])
async def get_knowledge(
    limit: int = 10,
    offset: int = 0,
    category: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent),
):
    """
    Retrieve knowledge items from the agent's knowledge base.

    - **limit**: Maximum number of items to return (default: 10)
    - **offset**: Number of items to skip (for pagination)
    - **category**: Optional category filter
    """
    try:
        if not hasattr(current_agent, "knowledge_base"):
            return []

        knowledge_items = []
        all_items = current_agent.knowledge_base.knowledge

        # Filter by category if specified
        if category:
            filtered_items = {
                k: v
                for k, v in all_items.items()
                if v.get("category", "").lower() == category.lower()
            }
        else:
            filtered_items = all_items

        # Convert to response format
        for item_id, item_data in list(filtered_items.items())[offset : offset + limit]:
            knowledge_items.append(
                KnowledgeItem(
                    id=item_id,
                    content=item_data.get("content", ""),
                    category=item_data.get("category", "general"),
                    priority=item_data.get("priority", 0.5),
                    timestamp=datetime.now(),  # Would need actual timestamp
                )
            )

        return knowledge_items

    except Exception as e:
        logger.error(f"Error retrieving knowledge: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving knowledge: {str(e)}"
        )


@app.get("/analysis-history", tags=["Self-Improvement"])
async def get_analysis_history(
    limit: int = 10, current_agent: SelfImprovingAgent = Depends(get_agent)
):
    """
    Get the history of code analyses performed by the agent.
    """
    try:
        if not hasattr(current_agent, "code_analyzer"):
            return []

        history = current_agent.code_analyzer.get_analysis_history()
        return history[-limit:] if limit > 0 else history

    except Exception as e:
        logger.error(f"Error retrieving analysis history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving analysis history: {str(e)}"
        )


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agent_initialized": (
            agent is not None and agent.initialized if agent else False
        ),
        "github_available": github_modifier is not None,
    }


@app.get("/github/status", response_model=GitHubStatus, tags=["GitHub"])
async def get_github_status():
    """
    Get GitHub integration status.

    Returns information about GitHub connection, repository status, and configuration.
    """
    try:
        if not github_modifier:
            return GitHubStatus(
                github_connected=False,
                repository_name=None,
                local_repo_available=False,
                auto_pr_enabled=False,
                open_prs_count=0,
            )

        # Get repository status
        repo_status = await github_modifier.get_repository_status()

        return GitHubStatus(
            github_connected=repo_status.get("github_connected", False),
            repository_name=repo_status.get("repository_info", {}).get("full_name"),
            local_repo_available=repo_status.get("local_repo_available", False),
            auto_pr_enabled=repo_status.get("auto_pr_enabled", False),
            open_prs_count=len(repo_status.get("open_pull_requests", [])),
        )

    except Exception as e:
        logger.error(f"Error getting GitHub status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting GitHub status: {str(e)}"
        )


@app.get("/github/repository", response_model=RepositoryInfo, tags=["GitHub"])
async def get_repository_info():
    """
    Get information about the connected GitHub repository.
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        repo_info = await github_modifier.github_integration.get_repository_info()

        if "error" in repo_info:
            raise HTTPException(status_code=500, detail=repo_info["error"])

        return RepositoryInfo(
            name=repo_info["name"],
            full_name=repo_info["full_name"],
            description=repo_info.get("description"),
            language=repo_info.get("language"),
            stars=repo_info["stars"],
            forks=repo_info["forks"],
            open_issues=repo_info["open_issues"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repository info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting repository info: {str(e)}"
        )


@app.post("/github/issue", response_model=CreateIssueResponse, tags=["GitHub"])
async def create_github_issue(request: CreateIssueRequest):
    """
    Create a new GitHub issue.

    This endpoint allows creating GitHub issues programmatically, useful for
    integrating with Discord feature requests or other external systems.

    The issue will be created in the configured GitHub repository with the
    provided title, description, and optional labels.

    Note: Assignees requires proper GitHub permissions and the users must
    have write access to the repository.
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=503,
                detail="GitHub integration not available or repository not connected"
            )

        logger.info(f"Creating GitHub issue: {request.title}")

        # Create the issue using the GitHub integration
        issue_result = await github_modifier.github_integration.create_issue(
            title=request.title,
            body=request.description,
            labels=request.labels
        )

        # Check for errors in the result
        if "error" in issue_result:
            logger.error(f"Failed to create issue: {issue_result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create issue: {issue_result['error']}"
            )

        # Handle assignees if provided
        if request.assignees:
            try:
                issue_number = issue_result.get("issue_number")
                if issue_number:
                    repository = github_modifier.github_integration.repository
                    issue = repository.get_issue(issue_number)
                    # Add assignees to the issue
                    issue.add_to_assignees(*request.assignees)
                    logger.info(f"Added assignees {request.assignees} to issue #{issue_number}")
            except Exception as e:
                logger.warning(f"Failed to add assignees to issue: {e}")
                # Don't fail the request if assignees fail, just log a warning

        logger.info(f"Successfully created issue #{issue_result['issue_number']}")

        return CreateIssueResponse(
            issue_number=issue_result["issue_number"],
            issue_url=issue_result["url"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating GitHub issue: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating GitHub issue: {str(e)}"
        )


@app.post("/self-improve", response_model=ImprovementResponse, tags=["Self-Improvement"])
async def create_code_improvements(
    request: ImprovementRequest, background_tasks: BackgroundTasks
):
    """
    Run the full self-improvement loop: analyze → modify → validate → PR.

    This endpoint will:
    1. Analyze the current codebase for improvement opportunities
    2. Generate specific code improvements
    3. Validate the improvements for safety
    4. Optionally create a pull request with the improvements
    """
    try:
        if not github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        logger.info("Starting automated code improvement process...")

        # Run the improvement analysis
        result = await github_modifier.analyze_and_improve_codebase(
            evaluation_insights=request.evaluation_insights,
            knowledge_suggestions=request.knowledge_suggestions,
            create_pr=request.create_pr,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        summary = result.get("summary", {})
        pr_result = result.get("pr_result", {})

        return ImprovementResponse(
            improvements_generated=summary.get("improvements_generated", 0),
            improvements_validated=summary.get("improvements_validated", 0),
            pr_created=summary.get("pr_created", False),
            pr_number=pr_result.get("pr_number"),
            pr_url=pr_result.get("pr_url"),
            improvement_potential=summary.get("improvement_potential", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating code improvements: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error creating code improvements: {str(e)}"
        )


@app.post("/github/demo-pr", tags=["GitHub"])
async def create_demo_pr():
    """
    Create a demonstration pull request with documentation improvements.

    This is a safe demo endpoint that creates a PR with README enhancements.
    """
    try:
        if not github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        if not github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        logger.info("Creating demonstration pull request...")

        pr_result = await github_modifier.create_documentation_improvement_pr()

        if "error" in pr_result:
            raise HTTPException(status_code=500, detail=pr_result["error"])

        return {
            "message": "Demo pull request created successfully",
            "pr_number": pr_result.get("pr_number"),
            "pr_url": pr_result.get("pr_url"),
            "branch_name": pr_result.get("branch_name"),
            "files_updated": pr_result.get("files_updated", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating demo PR: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating demo PR: {str(e)}")


@app.get("/github/pull-requests", tags=["GitHub"])
async def get_pull_requests():
    """
    Get list of open pull requests in the repository.
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        prs = await github_modifier.github_integration.get_open_pull_requests()

        return {"open_pull_requests": prs, "count": len(prs)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pull requests: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting pull requests: {str(e)}"
        )


@app.get("/github/commits", tags=["GitHub"])
async def get_recent_commits(limit: int = 10):
    """
    Get recent commits from the repository.

    - **limit**: Maximum number of commits to retrieve (default: 10)
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(
                status_code=404, detail="GitHub repository not connected"
            )

        commits = await github_modifier.github_integration.get_commit_history(
            limit=limit
        )

        return {"recent_commits": commits, "count": len(commits)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent commits: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting recent commits: {str(e)}"
        )


@app.get("/github/improvement-history", tags=["GitHub"])
async def get_improvement_history():
    """
    Get history of automated improvements made by the AI agent.
    """
    try:
        if not github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        history = github_modifier.get_improvement_history()

        return {"improvement_history": history, "count": len(history)}

    except Exception as e:
        logger.error(f"Error getting improvement history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting improvement history: {str(e)}"
        )


@app.get("/discord/status", tags=["Discord"])
async def get_discord_status():
    """
    Get Discord bot status and connection information.
    """
    try:
        if not discord_integration:
            return {
                "enabled": False,
                "connected": False,
                "message": "Discord integration not enabled"
            }

        is_ready = (
            discord_integration.client and
            discord_integration.client.user is not None
        )

        status_info = {
            "enabled": True,
            "connected": is_ready,
            "bot_name": discord_integration.client.user.name if is_ready else None,
            "bot_id": str(discord_integration.client.user.id) if is_ready else None,
            "guild_count": len(discord_integration.client.guilds) if is_ready else 0,
            "allowed_channels": len(discord_integration.allowed_channel_ids),
            "status_channel_configured": discord_integration.status_channel_id is not None,
            "mention_required": discord_integration.mention_required,
        }

        return status_info

    except Exception as e:
        logger.error(f"Error getting Discord status: {e}")
        return {
            "enabled": False,
            "connected": False,
            "error": str(e)
        }


@app.post("/web-search", response_model=WebSearchResponse, tags=["Web Search"])
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


@app.get("/web-search/status", tags=["Web Search"])
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


# Health check endpoints with recovery status
@app.get("/health", tags=["System"])
async def health_check():
    """
    Comprehensive health check endpoint with recovery status.
    
    Returns overall system health and component status.
    """
    try:
        # Get recovery status
        recovery_status = error_recovery_manager.get_recovery_status()
        
        # Get agent health if available
        agent_health = {}
        if agent:
            agent_health = await agent.check_system_health()
        
        # Get LLM provider health
        llm_health = {}
        try:
            llm_health = llm_manager.get_provider_health_status()
        except Exception as e:
            llm_health = {"error": str(e)}
        
        # Get GitHub integration health
        github_health = {}
        if github_modifier:
            try:
                github_health = github_modifier.github_integration.get_status()
            except Exception as e:
                github_health = {"error": str(e)}
        
        # Get Discord integration health
        discord_health = {}
        if discord_integration:
            try:
                discord_status = await discord_integration.get_status() if hasattr(discord_integration, 'get_status') else {}
                discord_health = {
                    "enabled": config.discord_enabled,
                    "connected": discord_status.get("connected", False),
                }
            except Exception as e:
                discord_health = {"error": str(e)}
        
        # Determine overall health
        all_healthy = True
        degraded_mode = recovery_status.get("degraded_mode", False)
        
        if degraded_mode:
            overall_status = "degraded"
            all_healthy = False
        elif agent_health.get("overall") != "healthy":
            overall_status = agent_health.get("overall", "unknown")
            all_healthy = False
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "degraded_mode": degraded_mode,
            "components": {
                "agent": agent_health,
                "llm_providers": llm_health,
                "github": github_health,
                "discord": discord_health,
                "error_recovery": {
                    "circuit_breakers": recovery_status.get("circuit_breakers", {}),
                    "active_checkpoints": recovery_status.get("active_checkpoints", 0),
                    "recovery_history_count": recovery_status.get("recovery_history_count", 0),
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/health/recovery", tags=["System"])
async def recovery_status():
    """
    Get detailed error recovery status.
    
    Returns information about circuit breakers, error patterns, and recovery history.
    """
    try:
        recovery_status = error_recovery_manager.get_recovery_status()
        recovery_history = error_recovery_manager.get_recovery_history(limit=10)
        health_checks = await error_recovery_manager.perform_health_checks()
        
        return {
            "recovery_status": recovery_status,
            "health_checks": health_checks,
            "recent_recoveries": recovery_history,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/system/trigger-recovery", tags=["System"])
async def trigger_recovery():
    """
    Trigger recovery operations for failed components.
    
    This endpoint can be used to manually trigger recovery attempts.
    """
    try:
        # Process pending GitHub operations if any
        if github_modifier and github_modifier.github_integration:
            try:
                results = await github_modifier.github_integration.process_pending_operations()
                return {
                    "message": "Recovery triggered",
                    "github_operations_processed": len(results),
                    "results": results
                }
            except Exception as e:
                logger.error(f"Error processing GitHub operations: {e}")
                return {
                    "message": "Recovery partially completed",
                    "error": str(e)
                }
        
        return {
            "message": "No pending operations to process"
        }
    except Exception as e:
        logger.error(f"Error triggering recovery: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering recovery: {str(e)}"
        )

@app.post("/system/enable-degraded-mode", tags=["System"])
async def enable_degraded_mode():
    """
    Manually enable degraded mode.
    
    This can be useful for maintenance or when issues are detected.
    """
    try:
        error_recovery_manager.set_degraded_mode(True)
        if agent:
            agent.degraded_mode = True
        
        return {
            "message": "Degraded mode enabled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error enabling degraded mode: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error enabling degraded mode: {str(e)}"
        )

@app.post("/system/disable-degraded-mode", tags=["System"])
async def disable_degraded_mode():
    """
    Manually disable degraded mode.
    
    This can be used to attempt to return to normal operation.
    """
    try:
        error_recovery_manager.set_degraded_mode(False)
        if agent:
            agent.degraded_mode = False
        
        return {
            "message": "Degraded mode disabled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error disabling degraded mode: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error disabling degraded mode: {str(e)}"
        )


if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        global server_shutdown
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        server_shutdown = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the server
    uvicorn.run(
        "api_server:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
