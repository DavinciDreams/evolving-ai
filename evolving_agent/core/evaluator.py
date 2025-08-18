"""
Output evaluation system for self-improvement.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from .memory import MemoryEntry

logger = setup_logger(__name__)


class EvaluationCriteria(Enum):
    """Evaluation criteria for outputs."""

    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    RELEVANCE = "relevance"
    CREATIVITY = "creativity"
    EFFICIENCY = "efficiency"
    SAFETY = "safety"


@dataclass
class EvaluationResult:
    """Result of an output evaluation."""

    overall_score: float
    criteria_scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    feedback: str
    confidence: float
    metadata: Dict[str, Any]


class OutputEvaluator:
    """Evaluates agent outputs and suggests improvements."""

    def __init__(self):
        self.evaluation_history: List[Tuple[str, str, EvaluationResult]] = []
        self.criteria_weights = self._get_default_criteria_weights()

    def _get_default_criteria_weights(self) -> Dict[str, float]:
        """Get default weights for evaluation criteria."""
        return {
            EvaluationCriteria.ACCURACY.value: 0.25,
            EvaluationCriteria.COMPLETENESS.value: 0.20,
            EvaluationCriteria.CLARITY.value: 0.15,
            EvaluationCriteria.RELEVANCE.value: 0.20,
            EvaluationCriteria.CREATIVITY.value: 0.05,
            EvaluationCriteria.EFFICIENCY.value: 0.10,
            EvaluationCriteria.SAFETY.value: 0.05,
        }

    async def evaluate_output(
        self,
        query: str,
        output: str,
        context: Optional[Dict[str, Any]] = None,
        expected_criteria: Optional[List[str]] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> EvaluationResult:
        """
        Evaluate an output against multiple criteria.

        Args:
            query: The original query/task
            output: The generated output to evaluate
            context: Context used for generation
            expected_criteria: Specific criteria to focus on
            custom_weights: Custom weights for criteria

        Returns:
            EvaluationResult with scores and suggestions
        """
        try:
            logger.info("Evaluating output...")

            # Use custom weights if provided
            weights = custom_weights or self.criteria_weights
            criteria_to_evaluate = expected_criteria or list(weights.keys())

            # Evaluate each criterion
            criteria_scores = {}
            all_feedback = {}

            for criterion in criteria_to_evaluate:
                score, feedback = await self._evaluate_criterion(
                    query, output, criterion, context
                )
                criteria_scores[criterion] = score
                all_feedback[criterion] = feedback

            # Calculate overall score
            overall_score = sum(
                criteria_scores.get(criterion, 0) * weights.get(criterion, 0)
                for criterion in criteria_scores
            ) / sum(weights.get(criterion, 0) for criterion in criteria_scores)

            # Extract strengths and weaknesses
            strengths, weaknesses = self._extract_strengths_weaknesses(
                criteria_scores, all_feedback
            )

            # Generate improvement suggestions
            improvement_suggestions = await self._generate_improvement_suggestions(
                query, output, criteria_scores, all_feedback
            )

            # Calculate confidence based on consistency of scores
            confidence = self._calculate_confidence(criteria_scores)

            evaluation_result = EvaluationResult(
                overall_score=overall_score,
                criteria_scores=criteria_scores,
                strengths=strengths,
                weaknesses=weaknesses,
                improvement_suggestions=improvement_suggestions,
                feedback=(
                    " ".join(all_feedback)
                    if all_feedback
                    else "No specific feedback provided."
                ),
                confidence=confidence,
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "criteria_evaluated": criteria_to_evaluate,
                    "weights_used": weights,
                    "context_available": context is not None,
                },
            )

            # Store evaluation history
            self.evaluation_history.append((query, output, evaluation_result))

            logger.info(f"Evaluation completed. Overall score: {overall_score:.2f}")
            return evaluation_result

        except Exception as e:
            logger.error(f"Failed to evaluate output: {e}")
            raise

    async def _evaluate_criterion(
        self,
        query: str,
        output: str,
        criterion: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """Evaluate output against a specific criterion."""
        try:
            # Prepare context information
            context_info = ""
            if context:
                context_info = f"\nContext used: {json.dumps(context, indent=2)}"

            # Create evaluation prompt based on criterion
            prompt = self._create_evaluation_prompt(
                query, output, criterion, context_info
            )

            # Get evaluation from LLM
            evaluation_response = await llm_manager.generate_response(
                prompt=prompt,
                provider=config.default_llm_provider,
                temperature=0.3,
                max_tokens=500,
            )

            # Parse evaluation response
            score, feedback = self._parse_evaluation_response(
                evaluation_response, criterion
            )

            return score, feedback

        except Exception as e:
            logger.error(f"Failed to evaluate criterion {criterion}: {e}")
            return 0.5, {"error": str(e)}

    def _create_evaluation_prompt(
        self, query: str, output: str, criterion: str, context_info: str
    ) -> str:
        """Create evaluation prompt for a specific criterion."""
        criterion_descriptions = {
            "accuracy": "How factually correct and error-free is the output?",
            "completeness": "How thoroughly does the output address all aspects of the query?",
            "clarity": "How clear, well-structured, and easy to understand is the output?",
            "relevance": "How relevant and on-topic is the output to the original query?",
            "creativity": "How creative, innovative, or insightful is the output?",
            "efficiency": "How concise and efficient is the output while maintaining quality?",
            "safety": "How safe and appropriate is the output? Are there any harmful elements?",
        }

        description = criterion_descriptions.get(
            criterion, f"Evaluate the {criterion} of the output"
        )

        return f"""
        Evaluate the following output based on {criterion.upper()}.
\1        {description}
\1        ORIGINAL QUERY:
        {query}
\1        OUTPUT TO EVALUATE:
        {output}
        {context_info}
\1        Please provide your evaluation in the following JSON format:
        {{
            "score": <float between 0.0 and 1.0>,
            "reasoning": "<detailed explanation of the score>",
            "specific_issues": ["<list of specific issues found>"],
            "strengths": ["<list of strengths identified>"],
            "suggestions": ["<list of improvement suggestions>"]
        }}
\1        Be objective and provide specific, actionable feedback.
        """

    def _parse_evaluation_response(
        self, response: str, criterion: str
    ) -> Tuple[float, Dict[str, Any]]:
        """Parse the evaluation response from the LLM."""
        try:
            # Try to extract JSON from response
            response = response.strip()
            if not response.startswith("{"):
                # Find JSON in response
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    response = response[start:end]

            evaluation_data = json.loads(response)

            score = float(evaluation_data.get("score", 0.5))
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

            feedback = {
                "reasoning": evaluation_data.get("reasoning", ""),
                "specific_issues": evaluation_data.get("specific_issues", []),
                "strengths": evaluation_data.get("strengths", []),
                "suggestions": evaluation_data.get("suggestions", []),
            }

            return score, feedback

        except Exception as e:
            logger.warning(f"Failed to parse evaluation response for {criterion}: {e}")
            # Fallback parsing
            try:
                # Simple score extraction
                lines = response.split("\n")
                score = 0.5
                for line in lines:
                    if "score" in line.lower():
                        # Extract number
                        import re

                        numbers = re.findall(r"(\d+\.?\d*)", line)
                        if numbers:
                            score = float(numbers[0])
                            if score > 1.0:
                                score = score / 10.0  # Assume 0-10 scale
                            break

                return score, {"reasoning": response, "parse_error": str(e)}

            except Exception:
                return 0.5, {"error": f"Failed to parse evaluation: {e}"}

    def _extract_strengths_weaknesses(
        self, criteria_scores: Dict[str, float], all_feedback: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[str], List[str]]:
        """Extract overall strengths and weaknesses from criteria evaluations."""
        strengths = []
        weaknesses = []

        # Identify strong and weak criteria
        for criterion, score in criteria_scores.items():
            feedback = all_feedback.get(criterion, {})

            if score >= 0.8:  # Strong performance
                criterion_strengths = feedback.get("strengths", [])
                for strength in criterion_strengths:
                    if strength not in strengths:
                        strengths.append(f"{criterion.title()}: {strength}")

            elif score <= 0.4:  # Weak performance
                criterion_issues = feedback.get("specific_issues", [])
                for issue in criterion_issues:
                    if issue not in weaknesses:
                        weaknesses.append(f"{criterion.title()}: {issue}")

        return strengths[:5], weaknesses[:5]  # Limit to top 5 each

    async def _generate_improvement_suggestions(
        self,
        query: str,
        output: str,
        criteria_scores: Dict[str, float],
        all_feedback: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Generate specific improvement suggestions based on evaluation."""
        try:
            # Collect all suggestions from criteria evaluations
            all_suggestions = []
            for criterion, feedback in all_feedback.items():
                suggestions = feedback.get("suggestions", [])
                all_suggestions.extend(suggestions)

            # If we have enough suggestions, return them
            if len(all_suggestions) >= 3:
                return all_suggestions[:5]

            # Generate additional suggestions using LLM
            weak_criteria = [
                criterion for criterion, score in criteria_scores.items() if score < 0.6
            ]

            if weak_criteria:
                prompt = f"""
                Based on the evaluation results, generate 3-5 specific, actionable improvements.
\1                Original Query: {query}
\1                Output: {output}
\1                Weak Areas: {', '.join(weak_criteria)}
\1                Focus on practical changes that address the weak areas holistically.
                Return as a JSON list of strings.
                """

                response = await llm_manager.generate_response(
                    prompt=prompt, temperature=0.5, max_tokens=300
                )

                try:
                    additional_suggestions = json.loads(response)
                    if isinstance(additional_suggestions, list):
                        all_suggestions.extend(additional_suggestions)
                except Exception:
                    # Fallback: split by lines
                    lines = response.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if (
                            line
                            and not line.startswith("[")
                            and not line.startswith("]")
                        ):
                            line = line.lstrip("- ").lstrip("* ").strip('"')
                            if line:
                                all_suggestions.append(line)

            return all_suggestions[:5]

        except Exception as e:
            logger.error(f"Failed to generate improvement suggestions: {e}")
            return ["Review and refine the output for better quality"]

    def _calculate_confidence(self, criteria_scores: Dict[str, float]) -> float:
        """Calculate confidence based on consistency of scores."""
        if not criteria_scores:
            return 0.0

        scores = list(criteria_scores.values())

        # Calculate standard deviation
        import statistics

        if len(scores) == 1:
            return 0.8

        try:
            std_dev = statistics.stdev(scores)
            # Lower standard deviation = higher confidence
            # Map std_dev [0, 0.5] to confidence [1.0, 0.5]
            confidence = max(0.5, 1.0 - (std_dev * 2))
            return confidence
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}", exc_info=True)
            return 0.7

    async def get_evaluation_insights(self) -> Dict[str, Any]:
        """Get insights from evaluation history."""
        try:
            if not self.evaluation_history:
                return {"message": "No evaluation history available"}

            # Analyze trends
            recent_evaluations = self.evaluation_history[-10:]  # Last 10

            overall_scores = [
                eval_result.overall_score for _, _, eval_result in recent_evaluations
            ]
            avg_score = sum(overall_scores) / len(overall_scores)

            # Find most common issues
            all_weaknesses = []
            all_suggestions = []

            for _, _, eval_result in recent_evaluations:
                all_weaknesses.extend(eval_result.weaknesses)
                all_suggestions.extend(eval_result.improvement_suggestions)

            # Count occurrences
            from collections import Counter

            common_weaknesses = Counter(all_weaknesses).most_common(3)
            common_suggestions = Counter(all_suggestions).most_common(3)

            return {
                "total_evaluations": len(self.evaluation_history),
                "recent_average_score": avg_score,
                "score_trend": (
                    "improving"
                    if len(overall_scores) > 1
                    and overall_scores[-1] > overall_scores[0]
                    else "stable"
                ),
                "common_weaknesses": [
                    weakness for weakness, count in common_weaknesses
                ],
                "recommended_improvements": [
                    suggestion for suggestion, count in common_suggestions
                ],
                "confidence_level": sum(
                    eval_result.confidence for _, _, eval_result in recent_evaluations
                )
                / len(recent_evaluations),
            }

        except Exception as e:
            logger.error(f"Failed to get evaluation insights: {e}")
            return {"error": str(e)}

    def update_criteria_weights(self, new_weights: Dict[str, float]):
        """Update the weights for evaluation criteria."""
        # Normalize weights to sum to 1
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            self.criteria_weights = {
                criterion: weight / total_weight
                for criterion, weight in new_weights.items()
            }
            logger.info("Updated evaluation criteria weights")

    async def create_evaluation_memory(
        self, evaluation: EvaluationResult, query: str, output: str
    ) -> MemoryEntry:
        """Create a memory entry from an evaluation result."""
        content = f"""
        Evaluation Result:
        Query: {query}
        Output: {output[:200]}...
        Overall Score: {evaluation.overall_score:.2f}
\1        Strengths: {', '.join(evaluation.strengths)}
        Weaknesses: {', '.join(evaluation.weaknesses)}
        Suggestions: {', '.join(evaluation.improvement_suggestions)}
        """

        return MemoryEntry(
            content=content,
            memory_type="evaluation",
            metadata={
                "overall_score": evaluation.overall_score,
                "criteria_scores": evaluation.criteria_scores,
                "confidence": evaluation.confidence,
                "evaluation_timestamp": evaluation.metadata["timestamp"],
            },
        )
