#!/usr/bin/env python3
"""
Debug OpenRouter API request formatting.
"""

import asyncio
import json
import os
import sys

import httpx

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from evolving_agent.utils.config import config


async def test_openrouter_request():
    """Test OpenRouter API request with various formats."""
    print("=== OpenRouter API Debug Test ===")

    api_key = config.openrouter_api_key
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ No valid OpenRouter API key found")
        return

    # Test different endpoints and formats
    endpoints_to_test = [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://openrouter.ai/api/v1/completions",
    ]

    models_to_test = [
        "meta-llama/llama-3.3-8b-instruct:free",
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku",
        "google/gemini-pro",
    ]

    for endpoint in endpoints_to_test:
        print(f"\n🔍 Testing endpoint: {endpoint}")

        for model in models_to_test:
            print(f"  📝 Testing model: {model}")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/evolving-ai-agent",
                "X-Title": "Self-Improving AI Agent",
            }

            # Test payload for chat completions
            if "chat" in endpoint:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 50,
                    "temperature": 0.7,
                }
            else:
                # Test payload for completions
                payload = {
                    "model": model,
                    "prompt": "Hello",
                    "max_tokens": 50,
                    "temperature": 0.7,
                }

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    print(f"    📤 Sending request...")
                    print(
                        f"    📋 Headers: {json.dumps({k: v[:20] + '...' if k == 'Authorization' else v for k, v in headers.items()}, indent=6)}"
                    )
                    print(f"    📋 Payload: {json.dumps(payload, indent=6)}")

                    response = await client.post(
                        endpoint, headers=headers, json=payload
                    )

                    print(f"    📥 Status: {response.status_code}")

                    if response.status_code == 200:
                        data = response.json()
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0].get("message", {}).get(
                                "content"
                            ) or data["choices"][0].get("text", "")
                            print(f"    ✅ Success! Response: {content[:50]}...")
                            return  # Found working configuration
                        else:
                            print(f"    ⚠️  Unexpected response format: {data}")
                    else:
                        print(f"    ❌ Error: {response.status_code}")
                        print(f"    📄 Response: {response.text[:200]}...")

                        # Check if it's a model availability issue
                        if response.status_code == 404:
                            try:
                                error_data = response.json()
                                if "model" in str(error_data).lower():
                                    print(f"    💡 Likely model availability issue")
                            except:
                                pass

            except Exception as e:
                print(f"    ❌ Exception: {str(e)[:100]}...")

    print("\n🔍 Testing model list endpoint...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                models = response.json()
                print(f"✅ Available models endpoint works")
                print(f"📊 Found {len(models.get('data', []))} models")

                # Show some free models
                free_models = [
                    m
                    for m in models.get("data", [])
                    if "free" in m.get("id", "").lower()
                ]
                if free_models:
                    print("🆓 Free models found:")
                    for model in free_models[:5]:
                        print(f"  - {model.get('id', 'Unknown')}")
            else:
                print(f"❌ Models endpoint error: {response.status_code}")
                print(f"📄 Response: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ Models endpoint exception: {str(e)[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_openrouter_request())
