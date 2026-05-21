"""Self-improvement endpoints: /analyze, /analysis-history, /self-improve."""

import uuid
from datetime import datetime

import evolving_agent.utils.app_state as state
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import get_agent, verify_api_key
from evolving_agent.utils.logging import setup_logger
from evolving_agent.utils.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ImprovementRequest,
    ImprovementResponse,
)

logger = setup_logger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse, tags=["Self-Improvement"], dependencies=[Depends(verify_api_key)])
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


@router.get("/analysis-history", tags=["Self-Improvement"])
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


@router.post("/self-improve", response_model=ImprovementResponse, tags=["Self-Improvement"], dependencies=[Depends(verify_api_key)])
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
        if not config.enable_self_modification:
            raise HTTPException(
                status_code=403, detail="Self-modification is disabled"
            )

        if not state.github_modifier:
            raise HTTPException(
                status_code=503, detail="GitHub integration not available"
            )

        logger.info("Starting automated code improvement process...")

        # Run the improvement analysis
        result = await state.github_modifier.analyze_and_improve_codebase(
            evaluation_insights=request.evaluation_insights,
            knowledge_suggestions=request.knowledge_suggestions,
            create_pr=request.create_pr,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        summary = result.get("summary", {})
        github_result = result.get("github_result", {})

        return ImprovementResponse(
            improvements_generated=summary.get("improvements_generated", 0),
            improvements_validated=summary.get("improvements_validated", 0),
            pr_created=summary.get("pr_created", False),
            pr_number=github_result.get("number"),
            pr_url=github_result.get("url"),
            improvement_potential=summary.get("improvement_potential", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating code improvements: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error creating code improvements: {str(e)}"
        )
