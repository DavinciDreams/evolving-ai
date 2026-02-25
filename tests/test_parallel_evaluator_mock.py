"""
Tests for the consolidated evaluator with mocked LLM calls.

Verifies that the evaluator makes a single consolidated LLM call instead of
separate calls per criterion, and that results are correctly parsed.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from evolving_agent.core.evaluator import OutputEvaluator, EvaluationCriteria


async def test_consolidated_evaluation_single_call():
    """Test that consolidated evaluation makes exactly 1 LLM call."""
    evaluator = OutputEvaluator()

    query = "Write a Python function that calculates the factorial of a number."
    output = """
    def factorial(n):
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        if n == 0 or n == 1:
            return 1
        return n * factorial(n - 1)
    """

    context = {
        "language": "python",
        "task_type": "coding",
        "difficulty": "beginner",
    }

    criteria = [c.value for c in EvaluationCriteria]

    # Mock response in consolidated format
    mock_response = (
        '{"scores": {"accuracy": 0.85, "completeness": 0.8, "clarity": 0.9, '
        '"relevance": 0.88, "creativity": 0.7, "efficiency": 0.82, "safety": 0.95}, '
        '"strengths": ["Proper error handling", "Recursive implementation", "Clear code structure"], '
        '"weaknesses": [], '
        '"suggestions": ["Add docstring for better documentation"]}'
    )

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        result = await evaluator.evaluate_output(
            query=query,
            output=output,
            context=context,
            expected_criteria=criteria,
        )

        # Consolidated evaluation = exactly 1 LLM call
        assert mock_gen.call_count == 1, (
            f"Expected 1 LLM call (consolidated), got {mock_gen.call_count}"
        )

    # Verify all criteria were evaluated
    assert set(result.criteria_scores.keys()) == set(criteria)

    # All scores in valid range
    for criterion, score in result.criteria_scores.items():
        assert 0.0 <= score <= 1.0, f"{criterion} score {score} out of range"

    # Overall score in valid range
    assert 0.0 <= result.overall_score <= 1.0

    # Confidence in valid range
    assert 0.0 <= result.confidence <= 1.0

    # Metadata
    assert result.metadata.get("consolidated_evaluation") is True
    assert result.metadata.get("evaluation_time_seconds", 0) >= 0


async def test_consolidated_is_fast():
    """Test that consolidated evaluation completes quickly (single call, no parallelism needed)."""
    evaluator = OutputEvaluator()

    query = "Test query for performance"
    output = "Test output for performance"
    criteria = [c.value for c in EvaluationCriteria]

    async def mock_generate_with_delay(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate 100ms network delay
        return (
            '{"scores": {"accuracy": 0.75, "completeness": 0.7, "clarity": 0.8, '
            '"relevance": 0.75, "creativity": 0.65, "efficiency": 0.7, "safety": 0.9}, '
            '"strengths": ["Test strength"], '
            '"weaknesses": ["Test weakness"], '
            '"suggestions": ["Test suggestion"]}'
        )

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', side_effect=mock_generate_with_delay) as mock_gen:
        start_time = time.time()
        result = await evaluator.evaluate_output(
            query=query,
            output=output,
            expected_criteria=criteria,
        )
        elapsed = time.time() - start_time

        # Only 1 call should be made
        assert mock_gen.call_count == 1

    # With 1 call at ~100ms, should complete well under 1 second
    assert elapsed < 1.0, f"Evaluation took {elapsed:.2f}s, expected < 1.0s"

    # Verify result validity
    assert set(result.criteria_scores.keys()) == set(criteria)
    assert 0.0 <= result.overall_score <= 1.0


async def test_strengths_and_suggestions_extracted():
    """Test that strengths, weaknesses, and suggestions are extracted from the consolidated response."""
    evaluator = OutputEvaluator()

    mock_response = (
        '{"scores": {"accuracy": 0.9, "clarity": 0.85}, '
        '"strengths": ["Very accurate", "Well-structured"], '
        '"weaknesses": ["Could be more concise"], '
        '"suggestions": ["Add examples", "Include references"]}'
    )

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        result = await evaluator.evaluate_output(
            query="Test",
            output="Test output",
            expected_criteria=["accuracy", "clarity"],
        )

    # Suggestions should be extracted from consolidated response
    assert len(result.improvement_suggestions) > 0

    # Metadata should be populated
    assert result.metadata.get("consolidated_evaluation") is True
    assert len(result.metadata.get("failed_criteria", [])) == 0
