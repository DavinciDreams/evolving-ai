#!/usr/bin/env python3
"""
Local runner for the Self-Improving AI Agent.

This script provides a simple interactive chat loop for running the agent
locally without Docker. It handles initialization, user input, and cleanup.
"""

import asyncio
import sys
from typing import Optional

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.utils.config import config
from evolving_agent.utils.logging import setup_logger


logger = setup_logger(__name__)


def print_banner():
    """Print the welcome banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                     Self-Improving AI Agent - Local Runner               ║
║                                                                           ║
║  A sophisticated AI code analysis assistant with self-improvement        ║
║  capabilities, long-term memory, knowledge base, and Claude tool use.    ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_config_info():
    """Print current configuration information."""
    print("\n" + "=" * 73)
    print("Configuration:")
    print("=" * 73)
    print(f"  LLM Provider:     {config.default_llm_provider}")
    print(f"  Model:            {config.default_model}")
    print(f"  Evaluation Model: {config.evaluation_model}")
    print(f"  Temperature:      {config.temperature}")
    print(f"  Max Tokens:       {config.max_tokens}")
    print(f"  Tool Use:         {'Enabled' if config.enable_tool_use else 'Disabled'}")
    print(f"  Self-Modification: {'Enabled' if config.enable_self_modification else 'Disabled'}")
    print(f"  Web Search:       {'Enabled' if config.web_search_enabled else 'Disabled'}")
    print(f"  Evaluation:       {'Enabled' if config.enable_evaluation else 'Disabled'}")
    print("=" * 73 + "\n")


def print_help():
    """Print help information."""
    help_text = """
Available Commands:
  /help           - Show this help message
  /config         - Show current configuration
  /status         - Show agent status
  /quit, /exit    - Exit the program

Special Features:
  - The agent can use Claude's tool calling to search the web, query memory,
    and query the knowledge base when Claude is the selected provider.
  - Web search is available for programming-related current information.
  - The agent learns from interactions and improves over time.
"""
    print(help_text)


def print_status(agent: SelfImprovingAgent):
    """Print agent status information."""
    print("\n" + "=" * 73)
    print("Agent Status:")
    print("=" * 73)
    print(f"  Initialized:      {agent.initialized}")
    print(f"  Session ID:       {agent.session_id}")
    print(f"  Interactions:     {agent.interaction_count}")
    print(f"  Improvement Cycles: {agent.improvement_cycle_count}")
    print(f"  Tool Use:         {'Enabled' if config.enable_tool_use else 'Disabled'}")
    print(f"  Web Search:       {'Available' if agent.web_search else 'Not Available'}")
    print(f"  GitHub Integration: {'Available' if agent.github_modifier else 'Not Available'}")
    print("=" * 73 + "\n")


async def run_interactive_loop(agent: SelfImprovingAgent):
    """Run the interactive chat loop."""
    print("\n" + "=" * 73)
    print("Interactive Mode")
    print("=" * 73)
    print("Type your questions or commands below.")
    print("Type /help for available commands or /quit to exit.\n")

    conversation_id = None

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Handle empty input
            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("/quit", "/exit"):
                print("\nGoodbye!")
                break

            if user_input.lower() == "/help":
                print_help()
                continue

            if user_input.lower() == "/config":
                print_config_info()
                continue

            if user_input.lower() == "/status":
                print_status(agent)
                continue

            # Process the query
            print("\nAgent: ", end="", flush=True)
            response = await agent.run(
                query=user_input,
                conversation_id=conversation_id
            )
            print(response + "\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Type /quit to exit or continue with a new query.")
            continue

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"\nError: {e}\n")
            print("Please try again or type /quit to exit.\n")


async def main():
    """Main entry point for the local runner."""
    print_banner()
    print_config_info()

    # Check for API key
    if not config.anthropic_api_key and config.default_llm_provider == "anthropic":
        print("WARNING: ANTHROPIC_API_KEY not set in environment or .env file.")
        print("Please set your API key and try again.")
        print("\nYou can create a .env file with your API key:")
        print("  ANTHROPIC_API_KEY=your_api_key_here\n")
        sys.exit(1)

    # Initialize the agent
    print("Initializing agent...")
    agent = SelfImprovingAgent()

    try:
        await agent.initialize()
        print("Agent initialized successfully!\n")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        print(f"\nError initializing agent: {e}")
        print("Please check your configuration and try again.\n")
        sys.exit(1)

    # Run the interactive loop
    try:
        await run_interactive_loop(agent)
    finally:
        # Cleanup
        print("\nShutting down...")
        # Note: The agent doesn't have a cleanup method, but we can
        # ensure any pending operations are completed
        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)
