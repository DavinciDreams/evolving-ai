# 🌐 Self-Improving AI Agent - API Documentation

## Overview

The Self-Improving AI Agent now includes a comprehensive REST API with Swagger documentation, allowing you to interact with the agent through HTTP endpoints instead of just command-line interfaces.

## 🚀 Quick Start

### 1. Install Dependencies

First, make sure you have the FastAPI dependencies installed:

```bash
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
python api_server.py
```

The server will start on `http://localhost:8000`

### 3. Access Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📋 Available Endpoints

### General Endpoints

#### `GET /` - Root Information
Returns basic API information and links to documentation.

#### `GET /health` - Health Check
Returns the health status of the API server and agent.

#### `GET /status` - Agent Status
Returns detailed information about the agent's current state:
- Initialization status
- Session ID
- Total interactions
- Memory count
- Knowledge base size

### Interaction Endpoints

#### `POST /chat` - Chat with Agent
Send queries to the agent and receive intelligent responses.

**Request Body:**
```json
{
  "query": "What are the best practices for code optimization?",
  "context_hints": ["performance", "maintainability"]
}
```

**Response:**
```json
{
  "response": "Here are the key best practices for code optimization...",
  "query_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-06-28T20:30:00Z",
  "evaluation_score": 0.85,
  "memory_stored": true,
  "knowledge_updated": true
}
```

### Self-Improvement Endpoints

#### `POST /analyze` - Code Analysis
Trigger the agent's code analysis and get improvement recommendations.

**Request Body:**
```json
{
  "evaluation_insights": {
    "score_trend": "improving",
    "recent_average_score": 0.85,
    "confidence_level": 0.9
  },
  "knowledge_suggestions": [
    {
      "message": "Consider implementing caching",
      "priority": 0.8,
      "category": "performance"
    }
  ]
}
```

**Response:**
```json
{
  "improvement_potential": 0.65,
  "improvement_opportunities": [
    {
      "type": "performance_improvement",
      "priority": 0.8,
      "description": "Optimize response generation",
      "suggested_action": "Implement caching mechanisms"
    }
  ],
  "recommendations": [
    "Optimize response generation pipeline",
    "Implement knowledge-based improvements"
  ],
  "codebase_metrics": {
    "total_functions": 227,
    "total_classes": 29,
    "total_lines": 5922,
    "average_complexity": 6.7
  },
  "analysis_id": "456e7890-e12b-34d5-a678-426614174001",
  "timestamp": "2025-06-28T20:35:00Z"
}
```

#### `GET /analysis-history` - Analysis History
Retrieve the history of code analyses performed by the agent.

### Memory & Knowledge Endpoints

#### `GET /memories` - Retrieve Memories
Get stored memories from the agent's long-term memory system.

**Query Parameters:**
- `limit`: Maximum number of memories (default: 10)
- `offset`: Skip number of memories (for pagination)
- `search`: Search query to filter memories

#### `GET /knowledge` - Retrieve Knowledge
Get knowledge items from the agent's knowledge base.

**Query Parameters:**
- `limit`: Maximum number of items (default: 10)
- `offset`: Skip number of items (for pagination)
- `category`: Filter by knowledge category

## GitHub Integration Endpoints

The API provides comprehensive GitHub integration features for automated code improvement and pull request management.

### GET /github/status
Get the current status of GitHub integration.

**Response Model**: `GitHubStatus`
```json
{
  "github_connected": true,
  "repository_name": "username/repository",
  "local_repo_available": true,
  "auto_pr_enabled": true,
  "open_prs_count": 2
}
```

### GET /github/repository
Get detailed information about the connected GitHub repository.

**Response Model**: `RepositoryInfo`
```json
{
  "name": "evolving-ai-agent",
  "full_name": "username/evolving-ai-agent",
  "description": "A self-improving AI agent",
  "language": "Python",
  "stars": 15,
  "forks": 3,
  "open_issues": 2
}
```

### POST /github/improve
Analyze the codebase and create improvements, optionally as a pull request.

**Request Model**: `ImprovementRequest`
```json
{
  "create_pr": true,
  "evaluation_insights": [
    "The error handling could be improved",
    "Memory usage optimization needed"
  ],
  "knowledge_suggestions": [
    "Implement async operations for better performance"
  ]
}
```

**Response Model**: `ImprovementResponse`
```json
{
  "improvements_generated": 5,
  "improvements_validated": 4,
  "pr_created": true,
  "pr_number": 123,
  "pr_url": "https://github.com/username/repo/pull/123",
  "improvement_potential": 0.85
}
```

### POST /github/demo-pr
Create a demonstration pull request with documentation improvements. This is a safe endpoint that only creates documentation enhancements.

```json
{
  "message": "Demo pull request created successfully",
  "pr_number": 124,
  "pr_url": "https://github.com/username/repo/pull/124",
  "branch_name": "demo-improvements-20241224_123456",
  "files_updated": ["README.md"]
}
```

### GET /github/pull-requests
Get a list of open pull requests in the repository.

```json
{
  "open_pull_requests": [
    {
      "number": 123,
      "title": "AI Agent: Code improvements",
      "url": "https://github.com/username/repo/pull/123",
      "created_at": "2024-12-24T12:34:56Z"
    }
  ],
  "count": 1
}
```

### GET /github/commits
Get recent commits from the repository.

**Query Parameters**:
- `limit` (optional): Maximum number of commits to retrieve (default: 10)

```json
{
  "recent_commits": [
    {
      "sha": "abc123",
      "message": "Implement new feature",
      "author": "AI Agent",
      "date": "2024-12-24T12:34:56Z"
    }
  ],
  "count": 1
}
```

### GET /github/improvement-history
Get the history of automated improvements made by the AI agent.

```json
{
  "improvement_history": [
    {
      "timestamp": "2024-12-24T12:34:56Z",
      "type": "code_optimization",
      "branch": "improvements-20241224_123456",
      "pr_number": 123,
      "pr_url": "https://github.com/username/repo/pull/123",
      "files_updated": ["core/agent.py", "utils/helpers.py"]
    }
  ],
  "count": 1
}
```

## 🧪 Testing the API

### 1. Test Script
Run the comprehensive test script:

```bash
python test_api_endpoints.py
```

### 2. Manual Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Agent status
curl http://localhost:8000/status

# Chat with agent
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, how are you?"}'

# Trigger code analysis
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_insights": {
      "score_trend": "stable",
      "recent_average_score": 0.8
    }
  }'
```

### 3. Python Client Example

```python
import httpx
import asyncio

async def chat_example():
    async with httpx.AsyncClient() as client:
        # Check status
        status = await client.get("http://localhost:8000/status")
        print(f"Agent status: {status.json()}")
        
        # Send a query
        response = await client.post(
            "http://localhost:8000/chat",
            json={"query": "Explain the benefits of microservices architecture"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data['response']}")
        else:
            print(f"Error: {response.text}")

# Run the example
asyncio.run(chat_example())
```

## 🔧 Configuration

### Environment Variables

Make sure your `.env` file contains the necessary API keys:

```bash
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### Server Configuration

You can modify the server configuration in `api_server.py`:

```python
# Change host and port
uvicorn.run(
    "api_server:app",
    host="0.0.0.0",  # Listen on all interfaces
    port=8000,       # Change port as needed
    reload=True,     # Auto-reload on code changes
    log_level="info"
)
```

### CORS Configuration

For production, configure CORS settings appropriately:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specify allowed origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Limit methods as needed
    allow_headers=["*"],
)
```

## 📊 Features

### ✅ Implemented Features

1. **Interactive Chat API** - Send queries and receive intelligent responses
2. **Code Analysis API** - Trigger self-improvement analysis
3. **Memory Retrieval** - Access stored memories and interactions
4. **Knowledge Base Access** - Browse extracted knowledge
5. **Agent Status Monitoring** - Check agent health and statistics
6. **Comprehensive Documentation** - Swagger UI and ReDoc
7. **Error Handling** - Proper HTTP status codes and error messages
8. **Async Support** - Full async/await implementation
9. **Type Safety** - Pydantic models for request/response validation

### 🔮 Potential Enhancements

1. **Authentication** - Add API key or OAuth authentication
2. **Rate Limiting** - Implement request rate limiting
3. **Websockets** - Real-time communication for streaming responses
4. **File Upload** - Allow uploading documents for analysis
5. **Batch Operations** - Process multiple queries at once
6. **Metrics API** - Detailed performance and usage metrics
7. **Configuration API** - Dynamic configuration updates
8. **Export Endpoints** - Export memories/knowledge in various formats

## 🛡️ Security Considerations

1. **Input Validation** - All inputs are validated using Pydantic models
2. **Error Handling** - Proper error isolation and logging
3. **Rate Limiting** - Consider implementing for production use
4. **Authentication** - Add authentication for production deployment
5. **HTTPS** - Use HTTPS in production environments
6. **CORS** - Configure CORS settings appropriately

## 🚀 Production Deployment

### Using Gunicorn (Recommended)

```bash
pip install gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```bash
# Production settings
ENVIRONMENT=production
LOG_LEVEL=warning
CORS_ORIGINS=https://yourdomain.com
API_KEY_REQUIRED=true
```

## 📖 API Documentation Features

The Swagger documentation includes:

- **Interactive Testing** - Test all endpoints directly from the browser
- **Request/Response Examples** - Complete examples for all endpoints
- **Schema Documentation** - Detailed model documentation
- **Error Code Reference** - HTTP status codes and error messages
- **Authentication Info** - When authentication is implemented

Access the documentation at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
