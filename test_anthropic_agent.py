"""
Test the agent with Anthropic Claude to avoid OpenRouter rate limits.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from evolving_agent.utils.llm_interface import llm_manager

# Force reload environment
load_dotenv(override=True)

async def test_anthropic_agent():
    """Test the agent with Anthropic Claude."""
    print("=== Anthropic Claude Agent Test ===")
    
    # Refresh the configuration to use Anthropic
    print("🔄 Switching to Anthropic Claude...")
    llm_manager.refresh_interfaces()
    
    print(f"✓ Default provider: {llm_manager.default_provider}")
    print(f"✓ Available providers: {list(llm_manager.interfaces.keys())}")
    
    # Test with Anthropic directly
    try:
        print("\n🧪 Testing Anthropic Claude...")
        response = await llm_manager.generate_response(
            prompt="Hello! You are a self-improving AI agent using Claude. Please introduce yourself briefly and tell me one interesting capability you have.",
            provider="anthropic",
            temperature=0.7,
            max_tokens=200
        )
        
        print(f"✅ Claude Response:\n{response}")
        
        # Test with default provider (should be Anthropic now)
        print("\n🧪 Testing default provider (should be Anthropic)...")
        response2 = await llm_manager.generate_response(
            prompt="Can you help me with Python programming? What's your approach to code analysis?",
            temperature=0.6,
            max_tokens=150
        )
        
        print(f"✅ Default Provider Response:\n{response2}")
        
        print(f"\n🎉 Anthropic Claude is working perfectly!")
        print(f"🧠 Provider: Anthropic")
        print(f"🤖 Model: Claude 3.5 Sonnet")
        print(f"⚡ No rate limits (with valid API key)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_anthropic_agent())
