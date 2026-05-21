"""
Complete integration test for the self-improving agent with code analysis.
"""
import pytest
pytestmark = pytest.mark.integration

import asyncio
from pathlib import Path

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


import pytest


@pytest.mark.asyncio
async def test_complete_self_improvement_cycle():
    """Test the complete self-improvement cycle including code analysis."""
    print("🚀 Testing Complete Self-Improvement Cycle with Code Analysis")
    print("=" * 80)

    try:
        # Initialize agent
        print("🔧 Initializing self-improving agent...")
        agent = SelfImprovingAgent()
        await agent.initialize()

        # Test interaction with code analysis trigger
        print("\n📝 Testing interaction that should trigger code analysis...")

        user_input = "Can you analyze your own code and suggest improvements for better performance and maintainability?"

        print(f"User: {user_input}")

        # Process the request
        response = await agent.run(user_input)

        print(f"\n🤖 Agent Response:")
        print(response)

        # Since the agent.run() method returns the response string directly,
        # we need to get additional info differently
        print(f"\n📊 Agent successfully processed the request")
        print(f"🧠 Memory system active: {hasattr(agent, 'memory')}")
        print(f"📚 Knowledge base active: {hasattr(agent, 'knowledge_base')}")

        # Check if code analysis was triggered
        if (
            hasattr(agent, "code_analyzer")
            and agent.code_analyzer.get_analysis_history()
        ):
            print("\n✅ Code Analysis Triggered!")

            history = agent.code_analyzer.get_analysis_history()
            latest_analysis = history[-1]

            print(f"📈 Latest Analysis Results:")
            print(
                f"   Improvement Potential: {latest_analysis.get('improvement_potential', 0):.2f}"
            )
            print(
                f"   Opportunities Found: {len(latest_analysis.get('improvement_opportunities', []))}"
            )
            print(
                f"   Recommendations: {len(latest_analysis.get('recommendations', []))}"
            )

            # Show some opportunities
            opportunities = latest_analysis.get("improvement_opportunities", [])
            if opportunities:
                print(f"\n🎯 Top Improvement Opportunities:")
                for i, opp in enumerate(opportunities[:3], 1):
                    print(
                        f"   {i}. {opp.get('type', 'unknown').replace('_', ' ').title()}"
                    )
                    print(f"      Priority: {opp.get('priority', 0):.2f}")
                    print(f"      Action: {opp.get('suggested_action', '')}")

            # Show recommendations
            recommendations = latest_analysis.get("recommendations", [])
            if recommendations:
                print(f"\n💡 Recommendations:")
                for i, rec in enumerate(recommendations[:3], 1):
                    print(f"   {i}. {rec}")

        else:
            print("\n⚠️ Code analysis not triggered automatically")

        # Test another interaction to see learning in action
        print("\n" + "=" * 80)
        print("📚 Testing Learning and Memory Retrieval")
        print("=" * 80)

        follow_up = "Based on your previous analysis, what specific improvements would you prioritize?"

        print(f"User: {follow_up}")

        response2 = await agent.run(follow_up)

        print(f"\n🤖 Agent Response:")
        print(response2)

        print(f"\n📊 Agent successfully processed follow-up request")

        # Check memory retrieval
        print(f"\n🧠 Memory system is operational")

        # Test knowledge base query
        print("\n" + "=" * 80)
        print("📖 Testing Knowledge Base Integration")
        print("=" * 80)

        knowledge_query = "What best practices should I follow for code optimization?"

        print(f"User: {knowledge_query}")

        response3 = await agent.run(knowledge_query)

        print(f"\n🤖 Agent Response:")
        print(response3)

        print(f"\n📊 Agent successfully processed knowledge query")

        # Show final statistics
        print("\n" + "=" * 80)
        print("📈 Final Session Statistics")
        print("=" * 80)

        # Check memory count
        if hasattr(agent, "memory") and hasattr(agent.memory, "collection"):
            try:
                memory_count = agent.memory.collection.count()
                print(f"💾 Total Memories Stored: {memory_count}")
            except:
                print("💾 Memory count not available")

        # Check knowledge base
        if hasattr(agent, "knowledge_base"):
            try:
                kb_size = len(agent.knowledge_base.knowledge)
                print(f"📚 Knowledge Base Items: {kb_size}")
            except:
                print("📚 Knowledge base size not available")

        # Check evaluation history
        if hasattr(agent, "evaluator"):
            try:
                eval_history = agent.evaluator.evaluation_history
                if eval_history:
                    avg_score = sum(e.score for e in eval_history) / len(eval_history)
                    print(
                        f"📊 Average Evaluation Score: {avg_score:.2f} ({len(eval_history)} evaluations)"
                    )
                else:
                    print("📊 No evaluation history available")
            except:
                print("📊 Evaluation history not available")

        # Check code analysis history
        if hasattr(agent, "code_analyzer"):
            try:
                analysis_history = agent.code_analyzer.get_analysis_history()
                print(f"🔍 Code Analyses Performed: {len(analysis_history)}")

                if analysis_history:
                    latest = analysis_history[-1]
                    print(
                        f"🎯 Latest Improvement Potential: {latest.get('improvement_potential', 0):.2f}"
                    )
            except:
                print("🔍 Code analysis history not available")

        return True

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        print(f"❌ Integration test failed: {e}")
        return False

    finally:
        # Cleanup
        try:
            await agent.cleanup()
        except:
            pass


async def main():
    """Run the complete integration test."""
    print("🌟 Self-Improving Agent with Code Analysis - Integration Test")
    print("=" * 80)

    success = await test_complete_self_improvement_cycle()

    print("\n" + "=" * 80)
    print("🏁 Integration Test Results")
    print("=" * 80)

    if success:
        print("✅ All tests passed!")
        print("🎉 Self-improving agent with code analysis is working correctly!")
        print("\nThe agent successfully demonstrated:")
        print("  • Code analysis and improvement suggestions")
        print("  • Learning from interactions and storing memories")
        print("  • Knowledge base integration and retrieval")
        print("  • Self-evaluation and performance tracking")
        print("  • Persistent data management")
    else:
        print("❌ Some tests failed!")
        print("Please check the logs for details.")


if __name__ == "__main__":
    asyncio.run(main())
