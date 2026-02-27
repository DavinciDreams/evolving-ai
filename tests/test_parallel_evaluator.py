"""
Tests for the consolidated evaluator implementation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from evolving_agent.core.evaluator import OutputEvaluator, EvaluationCriteria


async def test_consolidated_evaluation():
    """Test that consolidated evaluation scores all criteria in one LLM call."""
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

    mock_response = '{"scores": {"accuracy": 0.9, "completeness": 0.85, "clarity": 0.88, "relevance": 0.92, "creativity": 0.7, "efficiency": 0.8, "safety": 0.95}, "strengths": ["Proper error handling", "Recursive implementation"], "weaknesses": [], "suggestions": ["Add docstring"]}'

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        result = await evaluator.evaluate_output(
            query=query,
            output=output,
            context=context,
            expected_criteria=criteria,
        )

        # Should make exactly 1 LLM call (consolidated)
        assert mock_gen.call_count == 1

    # Verify all criteria were evaluated
    assert set(result.criteria_scores.keys()) == set(criteria)

    # All scores in valid range
    for score in result.criteria_scores.values():
        assert 0.0 <= score <= 1.0

    # Overall score in valid range
    assert 0.0 <= result.overall_score <= 1.0

    # Metadata should indicate consolidated evaluation
    assert result.metadata.get("consolidated_evaluation") is True


async def test_evaluation_with_invalid_criteria():
    """Test that evaluation handles a mix of valid/invalid criteria gracefully."""
    evaluator = OutputEvaluator()

    query = "Simple test query"
    output = "Simple test output"
    mixed_criteria = ["accuracy", "invalid_criterion", "clarity"]

    # The consolidated call will ask the LLM to score all criteria including the invalid one.
    # The LLM might return a score for it, or not. Either way, fallback defaults to 0.7.
    mock_response = '{"scores": {"accuracy": 0.8, "clarity": 0.75, "invalid_criterion": 0.6}, "strengths": ["OK"], "weaknesses": [], "suggestions": []}'

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        result = await evaluator.evaluate_output(
            query=query,
            output=output,
            expected_criteria=mixed_criteria,
        )

    # All requested criteria should have scores
    assert "accuracy" in result.criteria_scores
    assert "clarity" in result.criteria_scores
    assert "invalid_criterion" in result.criteria_scores

    # Scores in valid range
    for score in result.criteria_scores.values():
        assert 0.0 <= score <= 1.0


async def test_evaluation_llm_failure_fallback():
    """Test that evaluation falls back to defaults when LLM fails entirely."""
    evaluator = OutputEvaluator()

    criteria = [c.value for c in EvaluationCriteria]

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("LLM unavailable")

        result = await evaluator.evaluate_output(
            query="Test",
            output="Test output",
            expected_criteria=criteria,
        )

    # Should get default scores (0.7 for all criteria)
    assert set(result.criteria_scores.keys()) == set(criteria)
    for score in result.criteria_scores.values():
        assert score == pytest.approx(0.7, abs=0.01)

    # All criteria should be marked as failed
    assert len(result.metadata.get("failed_criteria", [])) == len(criteria)


async def test_evaluation_malformed_json_fallback():
    """Test fallback parsing when LLM returns non-JSON."""
    evaluator = OutputEvaluator()

    criteria = ["accuracy", "clarity"]

    mock_response = 'Here are my scores:\n"accuracy": 0.85\n"clarity": 0.9\nOverall good response.'

    with patch('evolving_agent.core.evaluator.llm_manager.generate_response', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        result = await evaluator.evaluate_output(
            query="Test",
            output="Test output",
            expected_criteria=criteria,
        )

    # Fallback parser should extract scores via regex
    assert "accuracy" in result.criteria_scores
    assert "clarity" in result.criteria_scores
    assert 0.0 <= result.criteria_scores["accuracy"] <= 1.0
    assert 0.0 <= result.criteria_scores["clarity"] <= 1.0
