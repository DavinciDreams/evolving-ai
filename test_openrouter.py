"""
Test OpenRouter API connection specifically.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolving_agent.utils.config import config
from evolving_agent.utils.llm_interface import OpenRouterInterface


async def test_openrouter():
    """Test OpenRouter API connection directly."""
    print("=== Testing OpenRouter API ===")
    
    if not config.openrouter_api_key:
        print("❌ No OpenRouter API key found")
        return
    
    print(f"✓ OpenRouter API key: {config.openrouter_api_key[:10]}...")
    print(f"✓ Model: {config.default_model}")
    
    try:
        # Initialize OpenRouter interface
        interface = OpenRouterInterface(
            config.openrouter_api_key,
            "meta-llama/llama-3.3-8b-instruct:free"  # Use working free model
        )
        
        print("✓ Interface created successfully")
        
        # Test simple request
        print("\n🧪 Testing simple request...")
        response = await interface.generate_response(
            prompt="Hello! Please respond with 'OpenRouter is working!'",
            temperature=0.1,
            max_tokens=50
        )
        
        print(f"✅ Response: {response}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_openrouter())
