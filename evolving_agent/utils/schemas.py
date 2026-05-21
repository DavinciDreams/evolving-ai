"""Pydantic models for the API server request/response contracts."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    conversation_id: Optional[str] = Field(
        None, description="Optional conversation ID for tracking multi-turn conversations"
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


# --- OpenAI-compatible models ---


class ChatCompletionMessage(BaseModel):
    """A single message in the OpenAI chat completions format."""

    role: str = Field(
        ...,
        description="The role of the message author (system, user, assistant)",
    )
    content: str = Field(
        ...,
        description="The content of the message",
    )
    name: Optional[str] = Field(
        None,
        description="Optional name of the message author",
    )


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = Field(
        "evolving-ai",
        description="Model identifier (informational; the agent uses its configured provider)",
    )
    messages: List[ChatCompletionMessage] = Field(
        ...,
        description="List of messages in the conversation",
        min_length=1,
    )
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature (0.0-2.0)",
        ge=0.0,
        le=2.0,
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum tokens in the response",
        ge=1,
    )
    stream: Optional[bool] = Field(
        False,
        description="Streaming is not supported; must be false or omitted",
    )
    n: Optional[int] = Field(
        1,
        description="Number of completions (only 1 supported)",
    )
    stop: Optional[List[str]] = Field(
        None,
        description="Stop sequences (accepted for compatibility)",
    )
    user: Optional[str] = Field(
        None,
        description="End-user identifier for tracking",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "evolving-ai",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What are best practices for code optimization?"},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
            }
        }
    }


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = Field(0, description="Choice index")
    message: ChatCompletionMessage = Field(
        ..., description="The assistant's response message"
    )
    finish_reason: str = Field(
        "stop", description="The reason the model stopped generating"
    )


class ChatCompletionUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = Field(0, description="Tokens in the prompt")
    completion_tokens: int = Field(0, description="Tokens in the completion")
    total_tokens: int = Field(0, description="Total tokens used")


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(..., description="Unique completion identifier")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model identifier used")
    choices: List[ChatCompletionChoice] = Field(
        ..., description="Completion choices"
    )
    usage: ChatCompletionUsage = Field(
        ..., description="Token usage statistics"
    )
