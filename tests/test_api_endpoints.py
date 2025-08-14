"""
Test script for the FastAPI server endpoints.
"""

import asyncio
import json
from typing import Any, Dict

import httpx
import pytest


@pytest.mark.asyncio
async def test_api_endpoints():
    """Test all API endpoints."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        print("🌐 Testing Self-Improving AI Agent API Endpoints")
        print("=" * 60)
        
        # Test 1: Root endpoint
        print("\n1. Testing root endpoint...")
        try:
            response = await client.get(f"{base_url}/")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {response.json()}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Connection error: {e}")
            print("Make sure the API server is running: python api_server.py")
            return
        
        # Test 2: Health check
        print("\n2. Testing health check...")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                health_data = response.json()
                print(f"Health: {health_data['status']}")
                print(f"Agent initialized: {health_data['agent_initialized']}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 3: Agent status
        print("\n3. Testing agent status...")
        try:
            response = await client.get(f"{base_url}/status")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                status_data = response.json()
                print(f"Initialized: {status_data['is_initialized']}")
                print(f"Session ID: {status_data['session_id']}")
                print(f"Interactions: {status_data['total_interactions']}")
                print(f"Memories: {status_data['memory_count']}")
                print(f"Knowledge: {status_data['knowledge_count']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 4: Chat endpoint
        print("\n4. Testing chat endpoint...")
        try:
            chat_request = {
                "query": "What are the key principles of software architecture?",
                "context_hints": ["design", "patterns"]
            }
            response = await client.post(
                f"{base_url}/chat",
                json=chat_request,
                timeout=60.0  # Longer timeout for LLM calls
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                chat_data = response.json()
                print(f"Query ID: {chat_data['query_id']}")
                print(f"Response: {chat_data['response'][:200]}...")
                print(f"Memory stored: {chat_data['memory_stored']}")
                print(f"Knowledge updated: {chat_data['knowledge_updated']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 5: Code analysis
        print("\n5. Testing code analysis...")
        try:
            analysis_request = {
                "evaluation_insights": {
                    "score_trend": "improving",
                    "recent_average_score": 0.8,
                    "confidence_level": 0.85
                },
                "knowledge_suggestions": [
                    {
                        "message": "Consider implementing caching for better performance",
                        "priority": 0.8,
                        "category": "performance"
                    }
                ]
            }
            response = await client.post(
                f"{base_url}/analyze",
                json=analysis_request,
                timeout=30.0
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                analysis_data = response.json()
                print(f"Analysis ID: {analysis_data['analysis_id']}")
                print(f"Improvement potential: {analysis_data['improvement_potential']:.2f}")
                print(f"Opportunities found: {len(analysis_data['improvement_opportunities'])}")
                print(f"Recommendations: {len(analysis_data['recommendations'])}")
                
                metrics = analysis_data['codebase_metrics']
                print(f"Codebase metrics:")
                print(f"  Functions: {metrics['total_functions']}")
                print(f"  Classes: {metrics['total_classes']}")
                print(f"  Lines: {metrics['total_lines']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 6: Memories endpoint
        print("\n6. Testing memories endpoint...")
        try:
            response = await client.get(f"{base_url}/memories?limit=5")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                memories = response.json()
                print(f"Retrieved {len(memories)} memories")
                for i, memory in enumerate(memories[:3], 1):
                    print(f"  {i}. {memory['content'][:100]}...")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 7: Knowledge endpoint
        print("\n7. Testing knowledge endpoint...")
        try:
            response = await client.get(f"{base_url}/knowledge?limit=5")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                knowledge_items = response.json()
                print(f"Retrieved {len(knowledge_items)} knowledge items")
                for i, item in enumerate(knowledge_items[:3], 1):
                    print(f"  {i}. [{item['category']}] {item['content'][:100]}...")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 8: Analysis history
        print("\n8. Testing analysis history...")
        try:
            response = await client.get(f"{base_url}/analysis-history?limit=3")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                history = response.json()
                print(f"Retrieved {len(history)} analysis entries")
                for i, entry in enumerate(history, 1):
                    print(f"  {i}. {entry.get('timestamp', 'Unknown')} - Potential: {entry.get('improvement_potential', 0):.2f}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # GitHub Integration endpoints
        print("\n9. Testing GitHub Integration endpoints...")
        github_endpoints = [
            ("GET", "/github/status", None, "Get GitHub integration status"),
            ("GET", "/github/repository", None, "Get repository information"),
            ("GET", "/github/pull-requests", None, "Get open pull requests"),
            ("GET", "/github/commits", None, "Get recent commits"),
            ("GET", "/github/improvement-history", None, "Get improvement history"),
            ("POST", "/github/improve", {
                "create_pr": False,
                "evaluation_insights": ["Test insight"],
                "knowledge_suggestions": ["Test suggestion"]
            }, "Create code improvements (dry run)"),
        ]
        
        for method, endpoint, payload, description in github_endpoints:
            print(f"\nTesting {description}...")
            try:
                if method == "GET":
                    response = await client.get(f"{base_url}{endpoint}")
                elif method == "POST":
                    response = await client.post(f"{base_url}{endpoint}", json=payload)
                
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"Response: {response.json()}")
                else:
                    print(f"Error: {response.text}")
            except Exception as e:
                print(f"Error: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 API endpoint testing completed!")
        print("\n📋 Available endpoints:")
        print("  • GET  /          - Root information")
        print("  • GET  /health    - Health check")
        print("  • GET  /status    - Agent status")
        print("  • POST /chat      - Chat with agent")
        print("  • POST /analyze   - Code analysis")
        print("  • GET  /memories  - Retrieve memories")
        print("  • GET  /knowledge - Retrieve knowledge")
        print("  • GET  /analysis-history - Analysis history")
        print("  • GET  /github/status - GitHub integration status")
        print("  • GET  /github/repository - Repository information")
        print("  • GET  /github/pull-requests - Open pull requests")
        print("  • GET  /github/commits - Recent commits")
        print("  • GET  /github/improvement-history - Improvement history")
        print("  • POST /github/improve - Create code improvements (dry run)")
        print("\n📖 Interactive documentation:")
        print(f"  • Swagger UI: {base_url}/docs")
        print(f"  • ReDoc: {base_url}/redoc")


if __name__ == "__main__":
    asyncio.run(test_api_endpoints())
