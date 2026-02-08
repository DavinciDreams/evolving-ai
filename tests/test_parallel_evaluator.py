#!/usr/bin/env python3
"""
Test script for the parallel evaluator implementation.
"""

import asyncio
import sys
import os
import time

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from evolving_agent.core.evaluator import OutputEvaluator, EvaluationCriteria


async def test_parallel_evaluation():
    """Test that the parallel evaluation works correctly."""
    print("Testing parallel evaluation implementation...")
    
    # Create evaluator instance
    evaluator = OutputEvaluator()
    
    # Test data
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
        "difficulty": "beginner"
    }
    
    # Test criteria
    criteria = [c.value for c in EvaluationCriteria]
    
    print(f"Evaluating with criteria: {criteria}")
    
    # Run evaluation
    start_time = time.time()
    result = await evaluator.evaluate_output(
        query=query,
        output=output,
        context=context,
        expected_criteria=criteria
    )
    end_time = time.time()
    
    # Print results
    print(f"\nEvaluation completed in {end_time - start_time:.2f} seconds")
    print(f"Overall score: {result.overall_score:.2f}")
    print(f"Confidence: {result.confidence:.2f}")
    
    print("\nCriteria scores:")
    for criterion, score in result.criteria_scores.items():
        print(f"  {criterion}: {score:.2f}")
    
    print("\nStrengths:")
    for strength in result.strengths:
        print(f"  - {strength}")
    
    print("\nWeaknesses:")
    for weakness in result.weaknesses:
        print(f"  - {weakness}")
    
    print("\nImprovement suggestions:")
    for suggestion in result.improvement_suggestions:
        print(f"  - {suggestion}")
    
    # Check metadata for parallel execution info
    metadata = result.metadata
    print(f"\nMetadata:")
    print(f"  Parallel execution: {metadata.get('parallel_execution', False)}")
    print(f"  Evaluation time: {metadata.get('evaluation_time_seconds', 0):.2f} seconds")
    print(f"  Failed criteria: {metadata.get('failed_criteria', [])}")
    
    # Verify all criteria were evaluated
    expected_criteria = set(criteria)
    evaluated_criteria = set(result.criteria_scores.keys())
    
    if expected_criteria == evaluated_criteria:
        print("\n✅ All criteria were evaluated successfully")
    else:
        missing = expected_criteria - evaluated_criteria
        print(f"\n❌ Missing criteria evaluation: {missing}")
        return False
    
    # Check scores are in valid range
    valid_scores = all(0.0 <= score <= 1.0 for score in result.criteria_scores.values())
    if valid_scores:
        print("✅ All scores are in valid range [0.0, 1.0]")
    else:
        print("❌ Some scores are outside valid range")
        return False
    
    # Check overall score is in valid range
    if 0.0 <= result.overall_score <= 1.0:
        print("✅ Overall score is in valid range [0.0, 1.0]")
    else:
        print("❌ Overall score is outside valid range")
        return False
    
    print("\n✅ Parallel evaluation test completed successfully!")
    return True


async def test_error_handling():
    """Test error handling in parallel evaluation."""
    print("\nTesting error handling...")
    
    evaluator = OutputEvaluator()
    
    # Test with invalid criteria (should trigger error handling)
    query = "Simple test query"
    output = "Simple test output"
    
    # Include a mix of valid and invalid criteria
    mixed_criteria = ["accuracy", "invalid_criterion", "clarity"]
    
    try:
        result = await evaluator.evaluate_output(
            query=query,
            output=output,
            expected_criteria=mixed_criteria
        )
        
        # Check that valid criteria were evaluated
        valid_criteria = {"accuracy", "clarity"}
        evaluated_criteria = set(result.criteria_scores.keys())
        
        if valid_criteria.issubset(evaluated_criteria):
            print("✅ Valid criteria were evaluated despite invalid ones")
        else:
            print("❌ Valid criteria were not evaluated properly")
            return False
        
        # Check that failed criteria are tracked
        failed_criteria = result.metadata.get('failed_criteria', [])
        if 'invalid_criterion' in failed_criteria:
            print("✅ Invalid criterion properly tracked as failed")
        else:
            print("❌ Invalid criterion not tracked as failed")
            return False
        
        print("✅ Error handling test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed with exception: {e}")
        return False


async def main():
    """Run all tests."""
    print("Starting parallel evaluator tests...")
    
    # Test basic parallel evaluation
    test1_passed = await test_parallel_evaluation()
    
    # Test error handling
    test2_passed = await test_error_handling()
    
    # Overall result
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! Parallel evaluator is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)