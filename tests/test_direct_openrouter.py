"""
Direct HTTP test for OpenRouter API.
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

import pytest
@pytest.mark.asyncio
async def test_direct_openrouter():
    """Test OpenRouter API with direct HTTP request."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("❌ No OpenRouter API key found")
        return
    
    print(f"✓ API Key: {api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/evolving-ai-agent",
        "X-Title": "Self-Improving AI Agent"
    }
    
    payload = {
        "model": "meta-llama/llama-3.3-8b-instruct:free",
        "messages": [
            {"role": "user", "content": "Hello! Please respond with 'OpenRouter is working!'"}
        ],
        "temperature": 0.1,
        "max_tokens": 50
    }
    
    print(f"✓ Model: {payload['model']}")
    print(f"✓ Headers: {headers}")
    print(f"✓ Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with httpx.AsyncClient() as client:
            print("\n🧪 Making request to https://openrouter.ai/api/v1/chat/completions...")
            
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            print(f"✓ Status Code: {response.status_code}")
            print(f"✓ Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success! Response: {data['choices'][0]['message']['content']}")
            else:
                print(f"❌ Error Status: {response.status_code}")
                print(f"❌ Error Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_openrouter())
