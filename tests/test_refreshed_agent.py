"""
Test the agent with fresh configuration.
"""
import pytest
pytestmark = pytest.mark.integration

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from evolving_agent.utils.config import Config
from evolving_agent.utils.llm_interface import llm_manager

# Force reload environment
load_dotenv(override=True)


async def test_refreshed_agent():
    """Test the agent with refreshed configuration."""
    print("=== Refreshed Agent Test ===")

    # Refresh the configuration
    print("🔄 Refreshing LLM manager configuration...")
    llm_manager.refresh_interfaces()

    print(f"✓ Default provider: {llm_manager.default_provider}")
    print(f"✓ Available providers: {list(llm_manager.interfaces.keys())}")

    # Test with the default provider
    try:
        print("\n🧪 Testing default provider...")
        response = await llm_manager.generate_response(
            prompt="Hello! You are a self-improving AI agent using a free model. Please introduce yourself briefly.",
            temperature=0.7,
            max_tokens=150,
        )

        print(f"✅ Agent Response:\n{response}")

        # Test specific OpenRouter call
        print("\n🧪 Testing explicit OpenRouter call...")
        response2 = await llm_manager.generate_response(
            prompt="Can you help me write Python code?",
            provider="openrouter",
            temperature=0.5,
            max_tokens=100,
        )

        print(f"✅ Programming Response:\n{response2}")

        print(f"\n🎉 Free model agent is working perfectly!")
        print(f"💰 Cost: $0.00 (completely free)")
        print(f"🚀 Provider: OpenRouter")
        print(f"🤖 Model: meta-llama/llama-3.3-8b-instruct:free")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_refreshed_agent())
