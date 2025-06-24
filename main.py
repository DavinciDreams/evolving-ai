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
        logger.info("Shutting down agent...")


def print_help():
    """Print available commands."""
    print("""
Available commands:
- help: Show this help message
- status: Show agent status
- memory: Show memory statistics
- quit/exit: Exit the program

You can also type any question or task for the agent to process.
""")


if __name__ == "__main__":
    asyncio.run(main())
