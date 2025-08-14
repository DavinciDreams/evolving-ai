"""
Swagger API Documentation Summary for Self-Improving AI Agent
"""


def print_swagger_summary():
    """Print a summary of the available API endpoints and their Swagger documentation."""

    print("🌐 Self-Improving AI Agent - Swagger API Documentation")
    print("=" * 80)

    print(
        """
📖 INTERACTIVE DOCUMENTATION AVAILABLE:
   • Swagger UI: http://localhost:8000/docs
   • ReDoc: http://localhost:8000/redoc
   • OpenAPI JSON: http://localhost:8000/openapi.json

🚀 TO START THE SERVER:
   python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload

📋 API ENDPOINTS OVERVIEW:
"""
    )

    endpoints = [
        {
            "method": "GET",
            "path": "/",
            "summary": "Root Information",
            "description": "Basic API information and navigation links",
        },
        {
            "method": "GET",
            "path": "/health",
            "summary": "Health Check",
            "description": "API server and agent health status",
        },
        {
            "method": "GET",
            "path": "/status",
            "summary": "Agent Status",
            "description": "Detailed agent state, memory count, knowledge count",
        },
        {
            "method": "POST",
            "path": "/chat",
            "summary": "Chat with Agent",
            "description": "Send queries and receive intelligent responses",
        },
        {
            "method": "POST",
            "path": "/analyze",
            "summary": "Code Analysis",
            "description": "Trigger self-improvement analysis and get recommendations",
        },
        {
            "method": "GET",
            "path": "/memories",
            "summary": "Retrieve Memories",
            "description": "Access stored memories with search and pagination",
        },
        {
            "method": "GET",
            "path": "/knowledge",
            "summary": "Retrieve Knowledge",
            "description": "Browse knowledge base with category filtering",
        },
        {
            "method": "GET",
            "path": "/analysis-history",
            "summary": "Analysis History",
            "description": "View history of code analyses performed",
        },
    ]

    for endpoint in endpoints:
        method_color = "🟢" if endpoint["method"] == "GET" else "🔵"
        print(
            f"{method_color} {endpoint['method']:4} {endpoint['path']:20} - {endpoint['summary']}"
        )
        print(f"      {endpoint['description']}")
        print()

    print("🔧 SWAGGER FEATURES IMPLEMENTED:")
    print("   ✅ Interactive API testing directly in browser")
    print("   ✅ Complete request/response schema documentation")
    print("   ✅ Example requests and responses for all endpoints")
    print("   ✅ Detailed parameter descriptions and validation")
    print("   ✅ Error response documentation")
    print("   ✅ Model schema definitions with examples")
    print("   ✅ API versioning and contact information")
    print("   ✅ OpenAPI 3.0 specification compliance")

    print("\n📱 EXAMPLE API USAGE:")
    print(
        """
# Health Check
curl http://localhost:8000/health

# Chat with Agent
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{"query": "What are microservices best practices?"}'

# Trigger Code Analysis  
curl -X POST http://localhost:8000/analyze \\
  -H "Content-Type: application/json" \\
  -d '{
    "evaluation_insights": {
      "score_trend": "improving", 
      "recent_average_score": 0.85
    }
  }'

# Get Memories
curl "http://localhost:8000/memories?limit=5&search=optimization"

# Get Knowledge Base
curl "http://localhost:8000/knowledge?category=performance&limit=10"
"""
    )

    print("🛡️ PYDANTIC MODEL VALIDATION:")
    print("   • QueryRequest - Validates chat queries and context hints")
    print("   • QueryResponse - Structures agent responses with metadata")
    print("   • AnalysisRequest - Validates code analysis parameters")
    print("   • AnalysisResponse - Structures analysis results and metrics")
    print("   • MemoryItem - Represents stored memory entries")
    print("   • KnowledgeItem - Represents knowledge base entries")
    print("   • AgentStatus - Provides comprehensive agent state info")

    print("\n🔍 SWAGGER UI FEATURES:")
    print("   • Try out API endpoints directly in the browser")
    print("   • View detailed request/response schemas")
    print("   • Download OpenAPI specification")
    print("   • Interactive parameter testing")
    print("   • Real-time API documentation")
    print("   • Authentication support (when implemented)")

    print("\n🎯 NEXT STEPS:")
    print("   1. Start the API server: python -m uvicorn api_server:app --port 8000")
    print("   2. Open browser to: http://localhost:8000/docs")
    print("   3. Try the interactive API documentation")
    print("   4. Test endpoints with real agent responses")
    print("   5. Integrate with your applications using the OpenAPI spec")


if __name__ == "__main__":
    print_swagger_summary()
