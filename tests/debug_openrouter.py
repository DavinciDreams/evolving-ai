"""
Debug OpenRouter API requests to find the exact issue.
"""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

# Force reload environment
load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolving_agent.utils.config import config
from evolving_agent.utils.llm_interface import OpenRouterInterface


async def debug_openrouter():
    """Debug OpenRouter API requests."""
    print("=== OpenRouter Debug ===")
    
    # Check current config
    print(f"Config default provider: {config.default_llm_provider}")
    print(f"Config default model: {config.default_model}")
    print(f"Config OpenRouter key: {config.openrouter_api_key[:10] if config.openrouter_api_key else 'None'}...")
    
    # Test with explicit working model
    working_model = "meta-llama/llama-3.3-8b-instruct:free"
    print(f"\n✓ Testing with known working model: {working_model}")
    
    api_key = config.openrouter_api_key
    if not api_key:
        print("❌ No API key!")
        return
    
    # Create interface with explicit model
    interface = OpenRouterInterface(api_key, working_model)
    print(f"Interface model: {interface.model}")
    print(f"Interface base_url: {interface.base_url}")
    
    # Test the exact request
    try:
        print("\n🧪 Making test request...")
        response = await interface.generate_response(
            prompt="Hello! Please just say 'Working!'",
            temperature=0.1,
            max_tokens=20
        )
        print(f"✅ SUCCESS: {response}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        
        # Try direct HTTP request for comparison
        print("\n🔍 Trying direct HTTP request...")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/evolving-ai-agent",
            "X-Title": "Self-Improving AI Agent"
        }
        
        payload = {
            "model": working_model,
            "messages": [{"role": "user", "content": "Hello! Please just say 'Working!'"}],
            "temperature": 0.1,
            "max_tokens": 20
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                print(f"Direct HTTP Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Direct HTTP SUCCESS: {data['choices'][0]['message']['content']}")
                else:
                    print(f"❌ Direct HTTP ERROR: {response.status_code} - {response.text}")
                    
        except Exception as e2:
            print(f"❌ Direct HTTP Exception: {e2}")


if __name__ == "__main__":
    asyncio.run(debug_openrouter())
