"""
Main entry point for the Self-Improving AI Agent.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import argparse

# Add the project root to the path to ensure imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.logging import setup_logger
from evolving_agent.self_modification.code_analyzer import CodeAnalyzer
from self_improve import run_self_improvement_cycle
import json

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
            
            if user_input.lower() in ['quit', 'exit']:
                break
            elif user_input.lower() == 'help':
                print_help()
                continue
            elif user_input.lower() == 'status':
                await agent.print_status()
                continue
            elif user_input.lower() == 'memory':
                await agent.print_memory_stats()
                continue
            elif user_input.lower() == 'stats':
                stats = await agent.data_manager.get_session_statistics()
                print(f"\nSession Statistics:\n{format_statistics(stats)}")
                continue
            elif user_input.lower() == 'interactions':
                interactions = await agent.data_manager.get_recent_interactions(5)
                print(f"\nRecent Interactions:\n{format_interactions(interactions)}")
                continue
            elif not user_input:
                continue
            elif user_input.lower() == 'analyze':
                try:
                    print("Enter evaluation_insights as JSON (dict):")
                    eval_input = input("> ")
                    evaluation_insights = json.loads(eval_input)
                    print("Enter knowledge_suggestions as JSON (list):")
                    know_input = input("> ")
                    knowledge_suggestions = json.loads(know_input)
                    analyzer = CodeAnalyzer()
                    analysis_result = await analyzer.analyze_performance_patterns(evaluation_insights, knowledge_suggestions)
                    print("\nAnalysis Result:")
                    print(json.dumps(analysis_result, indent=2))
                except Exception as e:
                    logger.error(f"Error during analysis: {e}")
                    print(f"Error: {e}")
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
        if 'agent' in locals():
            try:
                await agent.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        logger.info("Shutting down agent...")


def print_help():
    """Print available commands."""
    print("""
Available commands:
- help: Show this help message
- status: Show agent status and performance
- memory: Show memory statistics
- stats: Show session statistics
- interactions: Show recent interactions
- analyze: Analyze performance patterns using evaluation insights and knowledge suggestions (requires JSON input for both)
- quit/exit: Exit the program

You can also type any question or task for the agent to process.
""")


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
        score = interaction.get('evaluation_score', 'N/A')
        timestamp = interaction.get('timestamp', 'N/A')
        query = interaction.get('query', '')[:50] + "..." if len(interaction.get('query', '')) > 50 else interaction.get('query', '')
        
        formatted += f"{i}. [{timestamp}] Score: {score} - {query}\n"
    
    return formatted


def parse_args():
    parser = argparse.ArgumentParser(
        description="Self-Improving AI Agent CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--self-improve",
        action="store_true",
        help="Run the self-improvement cycle and print the summary result."
    )
    return parser.parse_args()

async def cli_self_improve():
    logger.info("Running self-improvement cycle...")
    agent = SelfImprovingAgent()
    await agent.initialize()
    summary = await run_self_improvement_cycle(agent)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    args = parse_args()
    if args.self_improve:
        asyncio.run(cli_self_improve())
    else:
        asyncio.run(main())
