"""
Test all available providers to find which ones work.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from evolving_agent.utils.llm_interface import llm_manager

# Force reload environment
load_dotenv(override=True)

import pytest


@pytest.mark.asyncio
async def test_all_providers():
    """Test all available providers to see which ones work."""
    print("=== Provider Availability Test ===")

    # Refresh the configuration
    llm_manager.refresh_interfaces()

    providers = list(llm_manager.interfaces.keys())
    print(f"✓ Available providers: {providers}")

    working_providers = []

    for provider in providers:
        print(f"\n🧪 Testing {provider}...")

        try:
            response = await llm_manager.generate_response(
                prompt="Hello! Please just say 'Working!' to test the API.",
                provider=provider,
                temperature=0.1,
                max_tokens=20,
            )

            print(f"✅ {provider}: {response}")
            working_providers.append(provider)

        except Exception as e:
            print(f"❌ {provider}: {str(e)[:100]}...")

    print(f"\n🎯 Summary:")
    print(f"Working providers: {working_providers}")
    print(f"Failed providers: {[p for p in providers if p not in working_providers]}")

    if working_providers:
        print(
            f"\n✅ Recommended: Use '{working_providers[0]}' as your default provider"
        )

        # Update config suggestion
        print(f"\n💡 To fix, update your .env file:")
        print(f"DEFAULT_LLM_PROVIDER={working_providers[0]}")

    else:
        print(f"\n❌ No working providers found. You may need to:")
        print(f"1. Add credits to your Anthropic account")
        print(f"2. Wait for OpenRouter rate limit reset (daily)")
        print(f"3. Add a valid OpenAI API key")


if __name__ == "__main__":
    asyncio.run(test_all_providers())
