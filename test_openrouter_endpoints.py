"""
Test OpenRouter API endpoint to verify the correct URL.
"""

import asyncio
import httpx
import json


async def test_openrouter_endpoints():
    """Test different OpenRouter API endpoints."""
    
    api_key = "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"
    
    # Test different possible endpoints
    endpoints = [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://openrouter.ai/api/v1/completions", 
        "https://api.openrouter.ai/api/v1/chat/completions",
        "https://api.openrouter.ai/v1/chat/completions"
    ]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/evolving-ai-agent",
        "X-Title": "Self-Improving AI Agent",
        "Content-Type": "application/json"
    }
    
    test_payload = {
        "model": "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
        "messages": [{"role": "user", "content": "Hello, just testing the API endpoint."}],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            try:
                print(f"Testing endpoint: {endpoint}")
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=test_payload,
                    timeout=30.0
                )
                
                print(f"Status Code: {response.status_code}")
                if response.status_code == 200:
                    print(f"✅ SUCCESS! Endpoint works: {endpoint}")
                    data = response.json()
                    print(f"Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'No content')}")
                    return endpoint
                else:
                    print(f"❌ Failed with status: {response.status_code}")
                    print(f"Response: {response.text[:200]}...")
                
            except Exception as e:
                print(f"❌ Error testing {endpoint}: {e}")
            
            print("-" * 50)
    
    return None


if __name__ == "__main__":
    result = asyncio.run(test_openrouter_endpoints())
    if result:
        print(f"\n🎉 Working endpoint found: {result}")
    else:
        print("\n😞 No working endpoint found")
