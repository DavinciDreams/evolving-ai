"""
Test OpenRouter with correct model names.
"""

import asyncio
import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_openrouter_models():
    """Test OpenRouter with different model names."""

    import os

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set.")

    # Test different model names
    models = [
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-3.5-turbo",
        "google/gemma-2-9b-it:free",
    ]

    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/evolving-ai-agent",
        "X-Title": "Self-Improving AI Agent",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        for model in models:
            try:
                print(f"Testing model: {model}")

                test_payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Hello! Just testing. Please respond with 'Working!'",
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 20,
                }

                response = await client.post(
                    endpoint, headers=headers, json=test_payload, timeout=30.0
                )

                print(f"Status Code: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "No content")
                    )
                    print(f"✅ SUCCESS! Model: {model}")
                    print(f"Response: {content}")
                    return model
                else:
                    print(f"❌ Failed with status: {response.status_code}")
                    error_msg = (
                        response.text[:200]
                        if len(response.text) > 200
                        else response.text
                    )
                    print(f"Error: {error_msg}")

            except Exception as e:
                print(f"❌ Error testing {model}: {e}")

            print("-" * 60)

    return None


if __name__ == "__main__":
    result = asyncio.run(test_openrouter_models())
    if result:
        print(f"\n🎉 Working model found: {result}")
    else:
        print("\n😞 No working model found")
