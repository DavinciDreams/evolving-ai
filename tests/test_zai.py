"""
Test script for Z AI provider integration.
"""

import asyncio
import sys

from evolving_agent.utils.config import config
from evolving_agent.utils.llm_interface import llm_manager


async def test_zai_provider():
    """Test the Z AI provider with GLM-4.7."""
    print("Testing Z AI provider integration with GLM-4.7 (coding endpoint)...")
    print(f"Z AI API Key configured: {'Yes' if config.zai_api_key else 'No'}")
    print(f"Default LLM Provider: {config.default_llm_provider}")
    print(f"Default Model: {config.default_model}")

    if not config.zai_api_key or config.zai_api_key == "your_zai_api_key_here":
        print("\nERROR: Z AI API key not configured!")
        print("Please set ZAI_API_KEY in your .env file")
        return False

    try:
        print("\n1. Testing code generation (using coding endpoint)...")
        response = await llm_manager.generate_response(
            prompt="Write a Python function to calculate fibonacci numbers. Keep it simple.",
            provider="zai",
            temperature=0.7,
            max_tokens=200,
        )
        print(f"Response: {response}")

        print("\n2. Testing chat response for code explanation...")
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "Explain what a decorator is in Python in one sentence."},
        ]
        chat_response = await llm_manager.generate_chat_response(
            messages=messages, provider="zai", temperature=0.5, max_tokens=100
        )
        print(f"Chat Response: {chat_response}")

        print("\n✅ Z AI provider test successful!")
        return True

    except Exception as e:
        print(f"\n❌ Z AI provider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    success = await test_zai_provider()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
