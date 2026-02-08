"""
Agent Pull Request Manager

This module provides functionality for the AI agent to manage its own
pull requests, track improvements, and handle the self-improvement workflow.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .code_analyzer import CodeAnalyzer
from .modifier import CodeModifier
from .validator import CodeValidator
from ..integrations.github_integration import GitHubIntegration


class AgentPRManager:
    """
    Manages the agent's pull request workflow for self-improvement.

    This class orchestrates the complete self-improvement cycle:
    1. Analyze codebase for improvements
    2. Generate code modifications
    3. Create GitHub branches and pull requests
    4. Track improvement history and feedback
    """

    def __init__(
        self,
        github_integration: GitHubIntegration,
        code_analyzer: CodeAnalyzer,
        code_modifier: CodeModifier,
        code_validator: CodeValidator,
    ):
        self.github = github_integration
        self.analyzer = code_analyzer
        self.modifier = code_modifier
        self.validator = code_validator

        # Track improvement history
        self.improvement_history_file = Path("persistent_data/improvement_history.json")
        self.improvement_history = self._load_improvement_history()

        logger.info("AgentPRManager initialized")

    def _load_improvement_history(self) -> List[Dict[str, Any]]:
        """Load improvement history from persistent storage."""
        if self.improvement_history_file.exists():
            try:
                with open(self.improvement_history_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load improvement history: {e}")
        return []

    def _save_improvement_history(self):
        """Save improvement history to persistent storage."""
        try:
            self.improvement_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.improvement_history_file, "w") as f:
                json.dump(self.improvement_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save improvement history: {e}")

    async def analyze_codebase_for_improvements(self) -> Dict[str, Any]:
        """
        Analyze the entire codebase to identify improvement opportunities.

        Returns:
            Dict containing analysis results and improvement suggestions
        """
        logger.info("Starting comprehensive codebase analysis...")

        try:
            # Analyze the core agent files
            core_files = [
                "evolving_agent/core/agent.py",
                "evolving_agent/core/memory.py",
                "evolving_agent/core/evaluator.py",
                "evolving_agent/core/context_manager.py",
                "evolving_agent/utils/llm_interface.py",
                "evolving_agent/self_modification/code_analyzer.py",
                "evolving_agent/self_modification/modifier.py",
            ]

            analysis_results = []
            total_suggestions = 0

            for file_path in core_files:
                if Path(file_path).exists():
                    try:
                        result = await self.analyzer.analyze_file(file_path)
                        analysis_results.append(result)
                        total_suggestions += len(result.get("suggestions", []))
                        logger.info(
                            f"Analyzed {file_path}: {len(result.get('suggestions', []))} suggestions"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to analyze {file_path}: {e}")

            return {
                "timestamp": datetime.now().isoformat(),
                "files_analyzed": len(analysis_results),
                "total_suggestions": total_suggestions,
                "analysis_results": analysis_results,
                "summary": f"Analyzed {len(analysis_results)} files with {total_suggestions} improvement suggestions",
            }

        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "files_analyzed": 0,
                "total_suggestions": 0,
            }

    async def generate_improvements(
        self, analysis_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate concrete code improvements based on analysis results.

        Args:
            analysis_results: Results from analyze_codebase_for_improvements

        Returns:
            List of improvement implementations
        """
        logger.info("Generating code improvements...")

        improvements = []

        try:
            # Extract high-priority suggestions
            for result in analysis_results.get("analysis_results", []):
                file_path = result.get("file_path")
                suggestions = result.get("suggestions", [])

                # Focus on the most impactful suggestions
                for suggestion in suggestions[:3]:  # Limit to top 3 per file
                    try:
                        improvement = await self._create_improvement(
                            file_path, suggestion, result
                        )
                        if improvement:
                            improvements.append(improvement)
                    except Exception as e:
                        logger.warning(
                            f"Failed to create improvement for {file_path}: {e}"
                        )

            logger.info(f"Generated {len(improvements)} improvements")
            return improvements

        except Exception as e:
            logger.error(f"Failed to generate improvements: {e}")
            return []

    async def _create_improvement(
        self, file_path: str, suggestion: str, analysis_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a specific improvement based on a suggestion."""
        try:
            # Use the modifier to generate the actual code change
            improvement = await self.modifier.apply_improvement(
                file_path=file_path, suggestion=suggestion, context=analysis_result
            )

            # Note: validation is already done within apply_improvement method
            if not improvement:
                logger.warning(f"No improvement generated for {file_path}")
                return None

            return improvement

        except Exception as e:
            logger.error(f"Failed to create improvement for {file_path}: {e}")
            return None

    async def create_improvement_pr(
        self, improvements: List[Dict[str, Any]], analysis_summary: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub pull request with the improvements.

        Args:
            improvements: List of code improvements
            analysis_summary: Summary of the analysis that led to improvements

        Returns:
            PR information or None if failed
        """
        if not improvements:
            logger.warning("No improvements to create PR for")
            return None

        try:
            logger.info(f"Creating PR for {len(improvements)} improvements...")

            # Prepare PR description
            pr_description = self._generate_pr_description(
                improvements, analysis_summary
            )

            # Create the PR through GitHub integration
            pr_result = await self.github.create_improvement_branch_and_pr(
                improvements=improvements, base_branch=None  # Use default branch
            )

            # Record this improvement attempt
            improvement_record = {
                "timestamp": datetime.now().isoformat(),
                "branch_name": pr_result.get("branch_name", "unknown"),
                "improvements_count": len(improvements),
                "analysis_summary": analysis_summary,
                "pr_info": pr_result,
                "status": "submitted",
            }

            self.improvement_history.append(improvement_record)
            self._save_improvement_history()

            logger.info(
                f"Successfully created PR: {pr_result.get('url', 'Unknown URL')}"
            )
            return pr_result

        except Exception as e:
            logger.error(f"Failed to create improvement PR: {e}")
            return None

    def _generate_pr_description(
        self, improvements: List[Dict[str, Any]], analysis_summary: str
    ) -> str:
        """Generate a comprehensive PR description."""
        description = f"""# 🤖 Autonomous Self-Improvement

## Analysis Summary
{analysis_summary}

## Improvements Made ({len(improvements)} total)

"""

        for i, improvement in enumerate(improvements, 1):
            file_path = improvement.get("file_path", "Unknown file")
            description_text = improvement.get("description", "No description")
            description += f"{i}. **{file_path}**: {description_text}\n"

        description += f"""

## Self-Improvement Metrics
- **Files Analyzed**: Multiple core components
- **Improvements Generated**: {len(improvements)}
- **Automation Level**: Fully autonomous
- **Review Requested**: Human validation

## About This PR
This pull request was automatically generated by the AI agent as part of its self-improvement cycle. The agent:

1. 🔍 Analyzed its own codebase
2. 🎯 Identified improvement opportunities
3. 🛠️ Generated code enhancements
4. ✅ Validated changes for safety
5. 📝 Created this PR for human review

The agent learns from feedback on these improvements to enhance future suggestions.

---
*Generated automatically by Self-Improving AI Agent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return description

    async def run_full_improvement_cycle(self) -> Dict[str, Any]:
        """
        Run a complete self-improvement cycle.

        Returns:
            Summary of the improvement cycle results
        """
        logger.info("🚀 Starting full self-improvement cycle...")

        cycle_start = datetime.now()

        try:
            # Step 1: Analyze codebase
            logger.info("Step 1: Analyzing codebase...")
            analysis_results = await self.analyze_codebase_for_improvements()

            if analysis_results.get("total_suggestions", 0) == 0:
                return {
                    "status": "completed",
                    "message": "No improvements identified",
                    "analysis_results": analysis_results,
                    "duration_seconds": (datetime.now() - cycle_start).total_seconds(),
                }

            # Step 2: Generate improvements
            logger.info("Step 2: Generating improvements...")
            improvements = await self.generate_improvements(analysis_results)

            if not improvements:
                return {
                    "status": "completed",
                    "message": "No valid improvements generated",
                    "analysis_results": analysis_results,
                    "duration_seconds": (datetime.now() - cycle_start).total_seconds(),
                }

            # Step 3: Create PR
            logger.info("Step 3: Creating pull request...")
            pr_result = await self.create_improvement_pr(
                improvements, analysis_results.get("summary", "")
            )

            cycle_duration = (datetime.now() - cycle_start).total_seconds()

            if pr_result:
                logger.info(
                    f"✅ Self-improvement cycle completed successfully in {cycle_duration:.1f}s"
                )
                return {
                    "status": "success",
                    "message": f"Created PR with {len(improvements)} improvements",
                    "analysis_results": analysis_results,
                    "improvements_count": len(improvements),
                    "pr_info": pr_result,
                    "duration_seconds": cycle_duration,
                }
            else:
                return {
                    "status": "partial_success",
                    "message": "Improvements generated but PR creation failed",
                    "analysis_results": analysis_results,
                    "improvements_count": len(improvements),
                    "duration_seconds": cycle_duration,
                }

        except Exception as e:
            logger.error(f"Self-improvement cycle failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": (datetime.now() - cycle_start).total_seconds(),
            }

    def get_improvement_history(self) -> List[Dict[str, Any]]:
        """Get the complete improvement history."""
        return self.improvement_history.copy()

    def get_improvement_stats(self) -> Dict[str, Any]:
        """Get statistics about improvement history."""
        total_attempts = len(self.improvement_history)
        successful_prs = len([h for h in self.improvement_history if h.get("pr_info")])
        total_improvements = sum(
            h.get("improvements_count", 0) for h in self.improvement_history
        )

        return {
            "total_improvement_cycles": total_attempts,
            "successful_prs_created": successful_prs,
            "total_improvements_generated": total_improvements,
            "success_rate": (
                successful_prs / total_attempts if total_attempts > 0 else 0
            ),
            "latest_attempt": (
                self.improvement_history[-1] if self.improvement_history else None
            ),
        }

    async def record_pr_merge_feedback(
        self,
        branch_name: str,
        pr_number: Optional[int] = None,
        feedback: str = "merged",
        rating: float = 1.0,
    ) -> bool:
        """
        Record feedback from a merged PR to help the agent learn.

        Args:
            branch_name: The branch that was merged
            pr_number: The PR number (optional)
            feedback: Feedback text ("merged", "rejected", etc.)
            rating: Quality rating (0.0 - 1.0)

        Returns:
            True if feedback was recorded successfully
        """
        try:
            # Find the corresponding improvement record
            for record in self.improvement_history:
                if record.get("branch_name") == branch_name:
                    # Update the record with feedback
                    record["feedback"] = {
                        "timestamp": datetime.now().isoformat(),
                        "status": feedback,
                        "rating": rating,
                        "pr_number": pr_number,
                    }

                    if feedback == "merged":
                        record["status"] = "merged_successfully"
                        logger.info(
                            f"✅ Recorded successful merge for branch {branch_name}"
                        )
                    else:
                        record["status"] = f"feedback_received_{feedback}"
                        logger.info(
                            f"📝 Recorded feedback '{feedback}' for branch {branch_name}"
                        )

                    # Save updated history
                    self._save_improvement_history()
                    return True

            logger.warning(f"No improvement record found for branch {branch_name}")
            return False

        except Exception as e:
            logger.error(f"Failed to record PR feedback: {e}")
            return False
