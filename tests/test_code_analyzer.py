#!/usr/bin/env python3
"""
Test script for the code analyzer self-improvement pipeline.
"""

import asyncio
import json
from pathlib import Path

from evolving_agent.self_modification.code_analyzer import CodeAnalyzer
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


import pytest


@pytest.mark.asyncio
async def test_code_analyzer_pipeline():
    """Test the complete code analyzer self-improvement pipeline."""
    print("🔍 Testing Code Analyzer Self-Improvement Pipeline")
    print("=" * 60)
    
    try:
        # Initialize the code analyzer
        analyzer = CodeAnalyzer()
        
        # Create sample evaluation insights (simulating real evaluation data)
        evaluation_insights = {
            "score_trend": "declining",
            "recent_average_score": 0.65,
            "confidence_level": 0.7,
            "common_weaknesses": [
                "Response accuracy could be improved",
                "Processing efficiency is suboptimal",
                "Error handling completeness needs work"
            ]
        }
        
        # Create sample knowledge suggestions
        knowledge_suggestions = [
            {
                "message": "Consider implementing caching for frequently accessed data",
                "priority": 0.8,
                "category": "performance"
            },
            {
                "message": "Add more comprehensive async error handling",
                "priority": 0.9,
                "category": "reliability"
            },
            {
                "message": "Implement batch processing for better efficiency",
                "priority": 0.7,
                "category": "optimization"
            }
        ]
        
        print("📊 Running performance pattern analysis...")
        
        # Run the main analysis
        analysis_result = await analyzer.analyze_performance_patterns(
            evaluation_insights=evaluation_insights,
            knowledge_suggestions=knowledge_suggestions
        )
        
        # Display results
        print("\n✅ Analysis completed!")
        print(f"Improvement Potential: {analysis_result.get('improvement_potential', 0):.2f}")
        
        # Show codebase analysis summary
        codebase_analysis = analysis_result.get("codebase_analysis", {})
        complexity_metrics = codebase_analysis.get("complexity_metrics", {})
        
        print(f"\n📈 Codebase Metrics:")
        print(f"  Total Functions: {complexity_metrics.get('total_functions', 0)}")
        print(f"  Total Classes: {complexity_metrics.get('total_classes', 0)}")
        print(f"  Total Lines of Code: {complexity_metrics.get('total_lines', 0)}")
        print(f"  Average Complexity: {complexity_metrics.get('average_complexity', 0):.2f}")
        
        # Show high complexity functions
        high_complexity = complexity_metrics.get("high_complexity_functions", [])
        if high_complexity:
            print(f"\n⚠️  High Complexity Functions ({len(high_complexity)}):")
            for func in high_complexity[:5]:  # Show top 5
                print(f"  - {func.get('function', 'Unknown')} in {func.get('module', 'Unknown')}: {func.get('complexity', 0)}")
        
        # Show improvement opportunities
        opportunities = analysis_result.get("improvement_opportunities", [])
        print(f"\n🎯 Improvement Opportunities ({len(opportunities)}):")
        for i, opp in enumerate(opportunities[:5], 1):  # Show top 5
            print(f"  {i}. {opp.get('type', 'Unknown').replace('_', ' ').title()}")
            print(f"     Priority: {opp.get('priority', 0):.2f}")
            print(f"     Description: {opp.get('description', 'No description')}")
            print(f"     Action: {opp.get('suggested_action', 'No action specified')}")
            print()
        
        # Show recommendations
        recommendations = analysis_result.get("recommendations", [])
        print(f"💡 Recommendations ({len(recommendations)}):")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")
        return None


async def test_specific_module_analysis():
    """Test analysis of a specific module."""
    print("\n" + "=" * 60)
    print("🔬 Testing Specific Module Analysis")
    print("=" * 60)
    
    try:
        analyzer = CodeAnalyzer()
        
        # Analyze the agent module specifically
        module_name = "evolving_agent.core.agent"
        print(f"📝 Analyzing module: {module_name}")
        
        module_analysis = await analyzer.analyze_specific_module(module_name)
        
        if "error" in module_analysis:
            print(f"❌ Module analysis failed: {module_analysis['error']}")
            return None
        
        print(f"\n✅ Module analysis completed!")
        print(f"File Path: {module_analysis.get('file_path', 'Unknown')}")
        
        # Show functions
        functions = module_analysis.get("functions", [])
        print(f"\n🔧 Functions ({len(functions)}):")
        for func in functions[:10]:  # Show first 10
            name = func.get("name", "Unknown")
            is_async = func.get("is_async", False)
            lines = func.get("source_lines", "?")
            async_marker = " (async)" if is_async else ""
            print(f"  - {name}{async_marker} ({lines} lines)")
        
        # Show classes
        classes = module_analysis.get("classes", [])
        print(f"\n🏗️  Classes ({len(classes)}):")
        for cls in classes:
            name = cls.get("name", "Unknown")
            methods = cls.get("methods", [])
            inheritance = cls.get("inheritance", [])
            inheritance_info = f" extends {', '.join(inheritance)}" if inheritance else ""
            print(f"  - {name}{inheritance_info} ({len(methods)} methods)")
        
        return module_analysis
        
    except Exception as e:
        logger.error(f"Specific module analysis failed: {e}")
        print(f"❌ Specific module analysis failed: {e}")
        return None


async def test_analysis_history():
    """Test analysis history tracking."""
    print("\n" + "=" * 60)
    print("📚 Testing Analysis History")
    print("=" * 60)
    
    try:
        analyzer = CodeAnalyzer()
        
        # Run a couple of analyses to build history
        evaluation_insights1 = {
            "score_trend": "stable",
            "recent_average_score": 0.8,
            "confidence_level": 0.8,
            "common_weaknesses": ["Minor efficiency issues"]
        }
        
        evaluation_insights2 = {
            "score_trend": "improving",
            "recent_average_score": 0.85,
            "confidence_level": 0.9,
            "common_weaknesses": []
        }
        
        print("📊 Running first analysis...")
        await analyzer.analyze_performance_patterns(evaluation_insights1, [])
        
        print("📊 Running second analysis...")
        await analyzer.analyze_performance_patterns(evaluation_insights2, [])
        
        # Get history
        history = analyzer.get_analysis_history()
        print(f"\n📈 Analysis History ({len(history)} entries):")
        
        for i, entry in enumerate(history, 1):
            timestamp = entry.get("timestamp", "Unknown")
            improvement_potential = entry.get("improvement_potential", 0)
            opportunities_count = len(entry.get("improvement_opportunities", []))
            
            print(f"  {i}. {timestamp}")
            print(f"     Improvement Potential: {improvement_potential:.2f}")
            print(f"     Opportunities Found: {opportunities_count}")
        
        # Get performance metrics
        metrics = analyzer.get_performance_metrics()
        print(f"\n📊 Performance Metrics:")
        if metrics:
            for key, value in metrics.items():
                print(f"  {key}: {value}")
        else:
            print("  No performance metrics recorded yet")
        
        return history
        
    except Exception as e:
        logger.error(f"Analysis history test failed: {e}")
        print(f"❌ Analysis history test failed: {e}")
        return None


async def main():
    """Run all code analyzer tests."""
    print("🚀 Starting Code Analyzer Self-Improvement Pipeline Tests")
    print("=" * 80)
    
    try:
        # Test 1: Main performance pattern analysis
        result1 = await test_code_analyzer_pipeline()
        
        # Test 2: Specific module analysis
        result2 = await test_specific_module_analysis()
        
        # Test 3: Analysis history
        result3 = await test_analysis_history()
        
        print("\n" + "=" * 80)
        print("📋 Test Summary")
        print("=" * 80)
        print(f"✅ Performance Pattern Analysis: {'PASSED' if result1 else 'FAILED'}")
        print(f"✅ Specific Module Analysis: {'PASSED' if result2 else 'FAILED'}")
        print(f"✅ Analysis History: {'PASSED' if result3 else 'FAILED'}")
        
        if result1:
            improvement_potential = result1.get("improvement_potential", 0)
            opportunities_count = len(result1.get("improvement_opportunities", []))
            recommendations_count = len(result1.get("recommendations", []))
            
            print(f"\n🎯 Key Results:")
            print(f"   Improvement Potential: {improvement_potential:.2f}")
            print(f"   Opportunities Identified: {opportunities_count}")
            print(f"   Recommendations Generated: {recommendations_count}")
        
        print("\n🎉 Code Analyzer Self-Improvement Pipeline Test Complete!")
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
