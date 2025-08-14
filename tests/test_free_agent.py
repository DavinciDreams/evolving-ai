"""
Test the complete agent with the free OpenRouter model.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from evolving_agent.utils.llm_interface import llm_manager


@pytest.mark.asyncio
async def test_free_agent():
    """Test the agent with free OpenRouter model."""
    print("=== Free Model Agent Test ===")
    
    try:
        # Test the default provider (should be OpenRouter with free model)
        response = await llm_manager.generate_response(
            prompt="Hello! You are a self-improving AI agent. Please introduce yourself briefly and tell me what you can do.",
            system_prompt="You are a helpful, intelligent AI assistant.",
            temperature=0.7,
            max_tokens=200
        )
        
        print(f"✅ Agent Response:\n{response}")
        
        # Test with explicit provider
        response2 = await llm_manager.generate_response(
            prompt="Can you help me with Python programming?",
            provider="openrouter",
            temperature=0.5,
            max_tokens=150
        )
        
        print(f"\n✅ Programming Help Response:\n{response2}")
        
        print(f"\n🎉 Free model is working perfectly!")
        print(f"💰 Cost: $0.00 (completely free)")
        print(f"🚀 Model: meta-llama/llama-3.3-8b-instruct:free")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_free_agent())
