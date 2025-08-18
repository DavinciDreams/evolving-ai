"""High-level orchestrator for agent self-improvement.

Coordinates code analysis, modification, and validation steps using
modules from evolving_agent.self_modification.

Exposes:
    - run_self_improvement_cycle(agent): Executes a full self-improvement cycle.
"""

from typing import Any, Dict
import asyncio

from evolving_agent.self_modification.code_analyzer import CodeAnalyzer
from evolving_agent.self_modification.modifier import CodeModifier
from evolving_agent.self_modification.validator import CodeValidator

async def run_self_improvement_cycle(agent: Any) -> Dict[str, Any]:
    """
    Executes a self-improvement cycle for the given agent.

    Steps:
        1. Analyzes the agent's code.
        2. Applies modifications based on analysis.
        3. Validates the changes.
        4. Returns a summary of the process.

    Args:
        agent: The agent object to be improved.

    Returns:
        A dictionary summarizing the analysis, modification, and validation results.
    """
    analyzer = CodeAnalyzer()
    validator = CodeValidator()
    modifier = CodeModifier(analyzer, validator)

    # Step 1: Analyze agent code (simulate evaluation_insights and knowledge_suggestions)
    # These would typically come from agent evaluation and knowledge modules
    evaluation_insights = getattr(agent, "evaluation_insights", {})
    knowledge_suggestions = getattr(agent, "knowledge_suggestions", [])

    code_analysis = await analyzer.analyze_codebase()

    # Step 2: Apply modifications
    await modifier.consider_modifications(code_analysis, evaluation_insights, knowledge_suggestions)

    # Step 3: Gather validation results (from modifier proposals)
    modification_history = modifier.get_modification_history()
    validation_history = validator.get_validation_history()

    summary = {
        "analysis": code_analysis,
        "modification_history": modification_history,
        "validation_history": validation_history,
    }
    return summary