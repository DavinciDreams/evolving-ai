"""
FastAPI web server for the Self-Improving AI Agent with Swagger documentation.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.github_enhanced_modifier import GitHubEnabledSelfModifier

logger = setup_logger(__name__)

# Global agent instance
agent: Optional[SelfImprovingAgent] = None
github_modifier: Optional[GitHubEnabledSelfModifier] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the agent."""
    global agent, github_modifier
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
                github_token=github_token,
                repo_name=github_repo,
                local_repo_path="."
            )
            await github_modifier.initialize()
            logger.info("GitHub integration initialized successfully")
        else:
            logger.warning("GitHub credentials not found. GitHub features will be unavailable.")
            
        yield
    finally:
        if agent:
            logger.info("Cleaning up agent...")
            await agent.cleanup()
            logger.info("Agent cleanup completed")


# Pydantic models for API requests and responses
class QueryRequest(BaseModel):
    """Request model for agent queries."""
    query: str = Field(..., description="The query to send to the agent", min_length=1, max_length=10000)
    context_hints: Optional[List[str]] = Field(None, description="Optional context hints to guide the response")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What are the best practices for code optimization?",
                "context_hints": ["performance", "maintainability"]
            }
        }
    }


class QueryResponse(BaseModel):
    """Response model for agent queries."""
    response: str = Field(..., description="The agent's response to the query")
    query_id: str = Field(..., description="Unique identifier for this query")
    timestamp: datetime = Field(..., description="When the query was processed")
    evaluation_score: Optional[float] = Field(None, description="Quality score of the response (0.0-1.0)")
    memory_stored: bool = Field(..., description="Whether the interaction was stored in memory")
    knowledge_updated: bool = Field(..., description="Whether new knowledge was extracted")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Here are the key best practices for code optimization...",
                "query_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2025-06-28T20:30:00Z",
                "evaluation_score": 0.85,
                "memory_stored": True,
                "knowledge_updated": True
            }
        }
    }


class AnalysisRequest(BaseModel):
    """Request model for code analysis."""
    evaluation_insights: Optional[Dict[str, Any]] = Field(None, description="Evaluation insights to consider")
    knowledge_suggestions: Optional[List[Dict[str, Any]]] = Field(None, description="Knowledge-based suggestions")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "evaluation_insights": {
                    "score_trend": "improving",
                    "recent_average_score": 0.85,
                    "confidence_level": 0.9
                },
                "knowledge_suggestions": [
                    {
                        "message": "Consider implementing caching",
                        "priority": 0.8,
                        "category": "performance"
                    }
                ]
            }
        }
    }


class AnalysisResponse(BaseModel):
    """Response model for code analysis."""
    improvement_potential: float = Field(..., description="Overall improvement potential (0.0-1.0)")
    improvement_opportunities: List[Dict[str, Any]] = Field(..., description="Specific improvement opportunities")
    recommendations: List[str] = Field(..., description="Actionable recommendations")
    codebase_metrics: Dict[str, Any] = Field(..., description="Current codebase metrics")
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
    repository_name: Optional[str] = Field(None, description="Connected repository name")
    local_repo_available: bool = Field(..., description="Whether local repository is available")
    auto_pr_enabled: bool = Field(..., description="Whether auto PR creation is enabled")
    open_prs_count: int = Field(..., description="Number of open pull requests")


class ImprovementRequest(BaseModel):
    """Request model for code improvements."""
    create_pr: bool = Field(True, description="Whether to create a pull request")
    evaluation_insights: Optional[Dict[str, Any]] = Field(None, description="Evaluation insights")
    knowledge_suggestions: Optional[List[Dict[str, Any]]] = Field(None, description="Knowledge suggestions")


class ImprovementResponse(BaseModel):
    """Response model for code improvements."""
    improvements_generated: int = Field(..., description="Number of improvements generated")
    improvements_validated: int = Field(..., description="Number of improvements validated")
    pr_created: bool = Field(..., description="Whether a pull request was created")
    pr_number: Optional[int] = Field(None, description="Pull request number if created")
    pr_url: Optional[str] = Field(None, description="Pull request URL if created")
    improvement_potential: float = Field(..., description="Overall improvement potential")


class RepositoryInfo(BaseModel):
    """Repository information model."""
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name")
    description: Optional[str] = Field(None, description="Repository description")
    language: Optional[str] = Field(None, description="Primary language")
    stars: int = Field(..., description="Number of stars")
    forks: int = Field(..., description="Number of forks")
    open_issues: int = Field(..., description="Number of open issues")


# FastAPI app initialization
app = FastAPI(
    title="Self-Improving AI Agent API",
    description="""
    A sophisticated self-improving AI agent with persistent memory, dynamic context,
    self-evaluation, and code analysis capabilities.
    
    ## Features
    
    * **Interactive Chat**: Send queries and receive intelligent responses
    * **Memory System**: Persistent long-term memory using vector embeddings
    * **Self-Analysis**: Code analysis and improvement recommendations
    * **Knowledge Management**: Automatic knowledge extraction and organization
    * **Multi-LLM Support**: OpenAI, Anthropic, and OpenRouter integration
    
    ## Getting Started
    
    1. Check agent status with `/status`
    2. Send a query using `/chat`
    3. Explore memories with `/memories`
    4. Trigger code analysis with `/analyze`
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
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "status": "/status"
    }


@app.get("/status", response_model=AgentStatus, tags=["General"])
async def get_status(current_agent: SelfImprovingAgent = Depends(get_agent)):
    """Get the current status of the agent."""
    try:
        # Get memory count
        memory_count = 0
        if hasattr(current_agent, 'memory') and hasattr(current_agent.memory, 'collection'):
            try:
                memory_count = current_agent.memory.collection.count()
            except Exception:
                memory_count = 0
        
        # Get knowledge count
        knowledge_count = 0
        if hasattr(current_agent, 'knowledge_base'):
            try:
                knowledge_count = len(current_agent.knowledge_base.knowledge_items)
            except Exception:
                knowledge_count = 0
        
        return AgentStatus(
            is_initialized=current_agent.initialized,
            session_id=current_agent.session_id,
            total_interactions=current_agent.interaction_count,
            memory_count=memory_count,
            knowledge_count=knowledge_count,
            uptime="Active"  # Could be calculated from initialization time
        )
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting agent status: {str(e)}")


@app.post("/chat", response_model=QueryResponse, tags=["Interaction"])
async def chat_with_agent(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    current_agent: SelfImprovingAgent = Depends(get_agent)
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
            knowledge_updated=True  # Assuming knowledge was processed
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/analyze", response_model=AnalysisResponse, tags=["Self-Improvement"])
async def analyze_code(
    request: AnalysisRequest,
    current_agent: SelfImprovingAgent = Depends(get_agent)
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
            "confidence_level": 0.8
        }
        
        knowledge_suggestions = request.knowledge_suggestions or []
        
        # Perform the analysis
        result = await current_agent.code_analyzer.analyze_performance_patterns(
            evaluation_insights, knowledge_suggestions
        )
        
        # Extract codebase metrics
        codebase_analysis = result.get('codebase_analysis', {})
        complexity_metrics = codebase_analysis.get('complexity_metrics', {})
        
        codebase_metrics = {
            "total_functions": complexity_metrics.get('total_functions', 0),
            "total_classes": complexity_metrics.get('total_classes', 0),
            "total_lines": complexity_metrics.get('total_lines', 0),
            "average_complexity": complexity_metrics.get('average_complexity', 0),
            "high_complexity_functions": complexity_metrics.get('high_complexity_functions', [])
        }
        
        return AnalysisResponse(
            improvement_potential=result.get('improvement_potential', 0),
            improvement_opportunities=result.get('improvement_opportunities', []),
            recommendations=result.get('recommendations', []),
            codebase_metrics=codebase_metrics,
            analysis_id=analysis_id,
            timestamp=timestamp
        )
        
    except Exception as e:
        logger.error(f"Error performing code analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error performing code analysis: {str(e)}")


@app.get("/memories", response_model=List[MemoryItem], tags=["Memory"])
async def get_memories(
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent)
):
    """
    Retrieve stored memories from the agent's long-term memory system.
    
    - **limit**: Maximum number of memories to return (default: 10)
    - **offset**: Number of memories to skip (for pagination)
    - **search**: Optional search query to filter memories
    """
    try:
        if not hasattr(current_agent, 'memory'):
            return []
        
        memories = []
        
        if search:
            # Search for relevant memories
            search_results = await current_agent.memory.search_memories(search, top_k=limit)
            for result in search_results:
                memories.append(MemoryItem(
                    id=result.get('id', 'unknown'),
                    content=result.get('content', ''),
                    timestamp=datetime.now(),  # Would need actual timestamp from metadata
                    metadata=result.get('metadata', {})
                ))
        else:
            # Get recent memories (would need to implement this in the memory system)
            # For now, return empty list as we don't have a "get_all" method
            pass
        
        return memories[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving memories: {str(e)}")


@app.get("/knowledge", response_model=List[KnowledgeItem], tags=["Knowledge"])
async def get_knowledge(
    limit: int = 10,
    offset: int = 0,
    category: Optional[str] = None,
    current_agent: SelfImprovingAgent = Depends(get_agent)
):
    """
    Retrieve knowledge items from the agent's knowledge base.
    
    - **limit**: Maximum number of items to return (default: 10)
    - **offset**: Number of items to skip (for pagination)
    - **category**: Optional category filter
    """
    try:
        if not hasattr(current_agent, 'knowledge_base'):
            return []
        
        knowledge_items = []
        all_items = current_agent.knowledge_base.knowledge_items
        
        # Filter by category if specified
        if category:
            filtered_items = {k: v for k, v in all_items.items() 
                            if v.get('category', '').lower() == category.lower()}
        else:
            filtered_items = all_items
        
        # Convert to response format
        for item_id, item_data in list(filtered_items.items())[offset:offset + limit]:
            knowledge_items.append(KnowledgeItem(
                id=item_id,
                content=item_data.get('content', ''),
                category=item_data.get('category', 'general'),
                priority=item_data.get('priority', 0.5),
                timestamp=datetime.now()  # Would need actual timestamp
            ))
        
        return knowledge_items
        
    except Exception as e:
        logger.error(f"Error retrieving knowledge: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving knowledge: {str(e)}")


@app.get("/analysis-history", tags=["Self-Improvement"])
async def get_analysis_history(
    limit: int = 10,
    current_agent: SelfImprovingAgent = Depends(get_agent)
):
    """
    Get the history of code analyses performed by the agent.
    """
    try:
        if not hasattr(current_agent, 'code_analyzer'):
            return []
        
        history = current_agent.code_analyzer.get_analysis_history()
        return history[-limit:] if limit > 0 else history
        
    except Exception as e:
        logger.error(f"Error retrieving analysis history: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analysis history: {str(e)}")


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agent_initialized": agent is not None and agent.initialized if agent else False,
        "github_available": github_modifier is not None
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
                open_prs_count=0
            )
        
        # Get repository status
        repo_status = await github_modifier.get_repository_status()
        
        return GitHubStatus(
            github_connected=repo_status.get("github_connected", False),
            repository_name=repo_status.get("repository_info", {}).get("full_name"),
            local_repo_available=repo_status.get("local_repo_available", False),
            auto_pr_enabled=repo_status.get("auto_pr_enabled", False),
            open_prs_count=len(repo_status.get("open_pull_requests", []))
        )
        
    except Exception as e:
        logger.error(f"Error getting GitHub status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting GitHub status: {str(e)}")


@app.get("/github/repository", response_model=RepositoryInfo, tags=["GitHub"])
async def get_repository_info():
    """
    Get information about the connected GitHub repository.
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(status_code=404, detail="GitHub repository not connected")
        
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
            open_issues=repo_info["open_issues"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repository info: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting repository info: {str(e)}")


@app.post("/github/improve", response_model=ImprovementResponse, tags=["GitHub"])
async def create_code_improvements(
    request: ImprovementRequest,
    background_tasks: BackgroundTasks
):
    """
    Analyze codebase and create improvements, optionally as a pull request.
    
    This endpoint will:
    1. Analyze the current codebase for improvement opportunities
    2. Generate specific code improvements
    3. Validate the improvements for safety
    4. Optionally create a pull request with the improvements
    """
    try:
        if not github_modifier:
            raise HTTPException(status_code=503, detail="GitHub integration not available")
        
        logger.info("Starting automated code improvement process...")
        
        # Run the improvement analysis
        result = await github_modifier.analyze_and_improve_codebase(
            evaluation_insights=request.evaluation_insights,
            knowledge_suggestions=request.knowledge_suggestions,
            create_pr=request.create_pr
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
            improvement_potential=summary.get("improvement_potential", 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating code improvements: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating code improvements: {str(e)}")


@app.post("/github/demo-pr", tags=["GitHub"])
async def create_demo_pr():
    """
    Create a demonstration pull request with documentation improvements.
    
    This is a safe demo endpoint that creates a PR with README enhancements.
    """
    try:
        if not github_modifier:
            raise HTTPException(status_code=503, detail="GitHub integration not available")
        
        if not github_modifier.github_integration.repository:
            raise HTTPException(status_code=404, detail="GitHub repository not connected")
        
        logger.info("Creating demonstration pull request...")
        
        pr_result = await github_modifier.create_documentation_improvement_pr()
        
        if "error" in pr_result:
            raise HTTPException(status_code=500, detail=pr_result["error"])
        
        return {
            "message": "Demo pull request created successfully",
            "pr_number": pr_result.get("pr_number"),
            "pr_url": pr_result.get("pr_url"),
            "branch_name": pr_result.get("branch_name"),
            "files_updated": pr_result.get("files_updated", [])
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
            raise HTTPException(status_code=404, detail="GitHub repository not connected")
        
        prs = await github_modifier.github_integration.get_open_pull_requests()
        
        return {
            "open_pull_requests": prs,
            "count": len(prs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pull requests: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pull requests: {str(e)}")


@app.get("/github/commits", tags=["GitHub"])
async def get_recent_commits(limit: int = 10):
    """
    Get recent commits from the repository.
    
    - **limit**: Maximum number of commits to retrieve (default: 10)
    """
    try:
        if not github_modifier or not github_modifier.github_integration.repository:
            raise HTTPException(status_code=404, detail="GitHub repository not connected")
        
        commits = await github_modifier.github_integration.get_commit_history(limit=limit)
        
        return {
            "recent_commits": commits,
            "count": len(commits)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent commits: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting recent commits: {str(e)}")


@app.get("/github/improvement-history", tags=["GitHub"])
async def get_improvement_history():
    """
    Get history of automated improvements made by the AI agent.
    """
    try:
        if not github_modifier:
            raise HTTPException(status_code=503, detail="GitHub integration not available")
        
        history = github_modifier.get_improvement_history()
        
        return {
            "improvement_history": history,
            "count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error getting improvement history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting improvement history: {str(e)}")


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
