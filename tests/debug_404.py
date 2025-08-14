"""
Debug OpenRouter 404 issue with fresh instances.
"""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

# Force reload environment
load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolving_agent.utils.llm_interface import LLMManager, OpenRouterInterface


async def debug_404_issue():
    """Debug the persistent 404 issue."""
    print("=== Debugging 404 Issue ===")

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("DEFAULT_MODEL", "meta-llama/llama-3.3-8b-instruct:free")

    print(f"API Key: {api_key[:10] if api_key else 'None'}...")
    print(f"Model: {model}")

    # Test 1: Direct HTTP request (known to work)
    print("\n🧪 Test 1: Direct HTTP Request")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/evolving-ai-agent",
        "X-Title": "Self-Improving AI Agent",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'Direct HTTP works!'"}],
        "temperature": 0.1,
        "max_tokens": 20,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success: {data['choices'][0]['message']['content']}")
            else:
                print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

    # Test 2: Fresh OpenRouterInterface instance
    print("\n🧪 Test 2: Fresh OpenRouterInterface")
    try:
        interface = OpenRouterInterface(api_key, model)
        print(f"Interface model: {interface.model}")
        print(f"Interface headers: {interface.headers}")

        response = await interface.generate_response(
            prompt="Say 'Interface works!'", temperature=0.1, max_tokens=20
        )
        print(f"✅ Success: {response}")
    except Exception as e:
        print(f"❌ Failed: {e}")

        # Let's inspect the exact request being made
        print(f"Attempting to debug the request...")
        try:
            # Manual inspection of what the interface is doing
            messages = [{"role": "user", "content": "Say 'Manual works!'"}]
            payload_debug = {
                "model": interface.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 20,
            }

            print(f"Debug payload: {payload_debug}")
            print(f"Debug headers: {interface.headers}")
            print(f"Debug URL: {interface.base_url}/chat/completions")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{interface.base_url}/chat/completions",
                    headers=interface.headers,
                    json=payload_debug,
                )
                print(f"Debug response status: {response.status_code}")
                print(f"Debug response headers: {dict(response.headers)}")
                if response.status_code != 200:
                    print(f"Debug response text: {response.text}")
                else:
                    data = response.json()
                    print(
                        f"✅ Manual debug success: {data['choices'][0]['message']['content']}"
                    )

        except Exception as e2:
            print(f"❌ Manual debug failed: {e2}")

    # Test 3: Fresh LLMManager instance
    print("\n🧪 Test 3: Fresh LLMManager")
    try:
        manager = LLMManager()
        manager.refresh_interfaces()

        response = await manager.generate_response(
            prompt="Say 'Manager works!'",
            provider="openrouter",
            temperature=0.1,
            max_tokens=20,
        )
        print(f"✅ Success: {response}")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    asyncio.run(debug_404_issue())
