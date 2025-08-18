"""
Main entry point for the Self-Improving AI Agent.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add the project root to the path to ensure imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.logging import setup_logger
from logging import Logger

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)


async def main():
    """Main function to run the self-improving agent."""
    logger.info("Initializing Self-Improving AI Agent...")

    try:
        # Initialize the agent
        agent = SelfImprovingAgent()
        await agent.initialize()

        logger.info("Agent initialized successfully!")

        # Interactive mode
        print("Self-Improving AI Agent is ready!")
        print("Type 'quit' to exit, 'help' for commands")

        while True:
            user_input = input("\n> ").strip()

            if user_input.lower() in ["quit", "exit"]:
                break
            elif user_input.lower() == "help":
                print_help()
                continue
            elif user_input.lower() == "status":
                await agent.print_status()
                continue
            elif user_input.lower() == "memory":
                await agent.print_memory_stats()
                continue
            elif user_input.lower() == "analyze":
                # Trigger self-analysis and print results
                try:
                    evaluation_insights = await agent.evaluator.get_evaluation_insights()
                    knowledge_suggestions = await agent.knowledge_updater.get_improvement_suggestions() if agent.knowledge_updater else []
                    result = await agent.code_analyzer.analyze_performance_patterns(
                        evaluation_insights, knowledge_suggestions
                    )
                    print("\nSelf-Analysis Results:")
                    print(f"Improvement Potential: {result.get('improvement_potential', 0):.2f}")
                    print("Opportunities:")
                    for opp in result.get("improvement_opportunities", []):
                        print(f"- {opp}")
                    print("Recommendations:")
                    for rec in result.get("recommendations", []):
                        print(f"- {rec}")
                except Exception as e:
                    logger.error(f"Error during self-analysis: {e}")
                    print(f"Error during self-analysis: {e}")
                continue
            elif user_input.lower() == "stats":
                stats = await agent.data_manager.get_session_statistics()
                print(f"\nSession Statistics:\n{format_statistics(stats)}")
                continue
            elif user_input.lower() == "interactions":
                interactions = await agent.data_manager.get_recent_interactions(5)
                print(f"\nRecent Interactions:\n{format_interactions(interactions)}")
                continue
            elif not user_input:
                continue

            # Process the input
            try:
                result = await agent.run(user_input)
                print(f"\nAgent Response:\n{result}")
            except Exception as e:
                logger.error(f"Error processing input: {e}")
                print(f"Error: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        print(f"Failed to start agent: {e}")

    finally:
        # Cleanup agent resources
        if "agent" in locals():
            try:
                await agent.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        logger.info("Shutting down agent...")


def print_help():
    """Print available commands."""
    print(
        """
Available commands:
- help: Show this help message
- status: Show agent status and performance
- memory: Show memory statistics
- analyze: Run self-analysis and print improvement recommendations
- stats: Show session statistics
- interactions: Show recent interactions
- quit/exit: Exit the program

You can also type any question or task for the agent to process.
"""
    )


def format_statistics(stats):
    """Format session statistics for display."""
    if not stats:
        return "No statistics available"

    return f"""
Session ID: {stats.get('session_id', 'N/A')}
Duration: {stats.get('session_duration_minutes', 0):.1f} minutes
Total Interactions: {stats.get('total_interactions', 0)}
Current Interactions: {stats.get('current_interactions', 0)}
Average Score: {stats.get('average_evaluation_score', 0):.2f}
Successful Evaluations: {stats.get('successful_evaluations', 0)}
Failed Evaluations: {stats.get('failed_evaluations', 0)}
Modifications Made: {stats.get('modifications_made', 0)}
Memories Added: {stats.get('memories_added', 0)}
Knowledge Added: {stats.get('knowledge_added', 0)}
"""


def format_interactions(interactions):
    """Format recent interactions for display."""
    if not interactions:
        return "No recent interactions"

    formatted = ""
    for i, interaction in enumerate(interactions[:5], 1):
        score = interaction.get("evaluation_score", "N/A")
        timestamp = interaction.get("timestamp", "N/A")
        query = (
            interaction.get("query", "")[:50] + "..."
            if len(interaction.get("query", "")) > 50
            else interaction.get("query", "")
        )

        formatted += f"{i}. [{timestamp}] Score: {score} - {query}\n"

    return formatted


if __name__ == "__main__":
    asyncio.run(main())
