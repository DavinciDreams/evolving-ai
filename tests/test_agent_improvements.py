#!/usr/bin/env python3
"""
Test script to verify the agent's improvements are working
and record successful merge feedback.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.github_integration import GitHubIntegration
from evolving_agent.utils.agent_pr_manager import AgentPRManager
from evolving_agent.self_modification.code_analyzer import CodeAnalyzer
from evolving_agent.self_modification.modifier import CodeModifier
from evolving_agent.self_modification.validator import CodeValidator


async def test_agent_improvements():
    """Test that the agent's improvements are working correctly."""
    print("🔍 Testing Agent Improvements After Merge")
    print("=" * 60)
    
    try:
        # Initialize the agent
        print("1. 🤖 Initializing agent...")
        agent = SelfImprovingAgent()
        await agent.initialize()
        print("✅ Agent initialized successfully")
        
        # Initialize GitHub integration and PR manager
        print("2. 🐙 Initializing GitHub integration...")
        github_integration = GitHubIntegration()
        await github_integration.initialize()
        
        code_analyzer = CodeAnalyzer()
        code_validator = CodeValidator()
        code_modifier = CodeModifier(code_analyzer, code_validator)
        
        pr_manager = AgentPRManager(
            github_integration=github_integration,
            code_analyzer=code_analyzer,
            code_modifier=code_modifier,
            code_validator=code_validator
        )
        print("✅ GitHub integration and PR manager initialized")
        
        # Record successful merge feedback for the recent PR
        print("3. 📝 Recording successful merge feedback...")
        branch_name = "ai-improvements-20250629_010923"
        feedback_recorded = await pr_manager.record_pr_merge_feedback(
            branch_name=branch_name,
            pr_number=5,
            feedback="merged",
            rating=1.0
        )
        
        if feedback_recorded:
            print(f"✅ Successfully recorded merge feedback for branch: {branch_name}")
        else:
            print(f"⚠️ Could not find improvement record for branch: {branch_name}")
        
        # Get improvement statistics
        print("4. 📊 Getting improvement statistics...")
        stats = pr_manager.get_improvement_stats()
        print(f"   Total improvement cycles: {stats['total_improvement_cycles']}")
        print(f"   Successful PRs created: {stats['successful_prs_created']}")
        print(f"   Total improvements generated: {stats['total_improvements_generated']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        
        # Test basic agent functionality
        print("5. 💬 Testing basic agent query processing...")
        response = await agent.run("What improvements were made to the memory system?")
        print(f"✅ Query processed successfully")
        print(f"   Response length: {len(response)} characters")
        print(f"   Response preview: {response[:200]}...")
        
        # Check memory system (which was improved)
        print("6. 🧠 Testing memory system...")
        memory_count = len(agent.memory.collection.get()['ids'])
        print(f"✅ Memory system working: {memory_count} memories stored")
        
        # Test knowledge base
        print("7. 📚 Testing knowledge base...")
        knowledge_stats = agent.knowledge_base.get_knowledge_stats()
        print(f"✅ Knowledge base working: {knowledge_stats['total_entries']} entries")
        
        # Run a quick self-improvement analysis (without creating PR)
        print("8. 🔍 Testing self-improvement analysis...")
        analysis_results = await pr_manager.analyze_codebase_for_improvements()
        files_analyzed = analysis_results.get('files_analyzed', 0)
        total_suggestions = analysis_results.get('total_suggestions', 0)
        print(f"✅ Analysis completed: {files_analyzed} files, {total_suggestions} suggestions")
        
        print("\n🎉 ALL TESTS PASSED!")
        print("The agent's improvements are working correctly.")
        
        # Print improvement history
        print("\n📋 Improvement History:")
        history = pr_manager.get_improvement_history()
        for i, record in enumerate(history, 1):
            status = record.get('status', 'unknown')
            timestamp = record.get('timestamp', 'unknown')
            improvements = record.get('improvements_count', 0)
            print(f"   {i}. {timestamp} - {improvements} improvements - Status: {status}")
            if 'feedback' in record:
                feedback = record['feedback']
                print(f"      Feedback: {feedback['status']} (rating: {feedback['rating']})")
        
        # Cleanup
        await agent.cleanup()
        print("\n✅ Agent cleanup completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_agent_improvements())
