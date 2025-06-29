# Self-Improving AI Agent

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![GitHub Integration](https://img.shields.io/badge/GitHub-Integration-orange.svg)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A sophisticated AI agent with self-improvement capabilities, long-term memory, dynamic context queries, GitHub integration, and autonomous code modification abilities.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [GitHub Integration 🐙](#github-integration-)
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Self-Improvement Cycle](#self-improvement-cycle)
- [License](#license)

## Features

- **Long-term Memory**: Persistent vector-based memory system using ChromaDB
- **Dynamic Context Queries**: Intelligent context retrieval based on current objectives
- **Self-Evaluation**: Built-in mechanisms to evaluate and improve outputs
- **Knowledge Base Updates**: Automatic updates to knowledge base from experiences
- **Code Self-Modification**: Ability to analyze and modify its own codebase
- **GitHub Integration**: Access own codebase and create pull requests with improvements
- **Multi-LLM Support**: Compatible with OpenAI, Anthropic, OpenRouter, and other providers
- **RESTful API**: FastAPI-based web server with Swagger documentation

## Architecture

```
evolving_agent/
├── core/                   # Core agent functionality
│   ├── agent.py           # Main agent orchestrator
│   ├── memory.py          # Long-term memory with ChromaDB
│   ├── evaluator.py       # Output evaluation system
│   └── context_manager.py # Dynamic context management
├── knowledge/             # Knowledge base management
│   ├── base.py           # Knowledge base operations
│   └── updater.py        # Knowledge update mechanisms
├── self_modification/     # Self-improvement capabilities
│   ├── code_analyzer.py  # Code analysis and complexity detection
│   ├── modifier.py       # Code modification engine
│   └── validator.py      # Code validation and safety checks
├── utils/                # Utility functions and integrations
│   ├── llm_interface.py  # Multi-LLM communication
│   ├── github_integration.py # GitHub API integration
│   ├── github_enhanced_modifier.py # GitHub-enabled self-modification
│   ├── logging.py        # Enhanced logging with structured output
│   ├── config.py         # Configuration management
│   └── persistent_storage.py # Data persistence utilities
├── tests/                # Comprehensive test suite
└── api_server.py         # FastAPI web server with Swagger docs
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create environment file:**
```bash
cp .env.example .env
```

3. **Configure your API keys and GitHub integration in `.env`:**
   - Add your LLM provider API keys (OpenAI, Anthropic, OpenRouter)
   - Add GitHub token and repository info for self-improvement features
   - See `.env.example` for all configuration options

4. **Run the agent (CLI mode):**
```bash
python main.py
```

5. **Or start the API server:**
```bash
# Start the server
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# API documentation available at:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

## Configuration

Set your API keys and preferences in `.env`:

### LLM Provider Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key (default provider)
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `DEFAULT_LLM_PROVIDER`: Choose your preferred provider (anthropic, openai, openrouter)

### GitHub Integration (Optional)
- `GITHUB_TOKEN`: GitHub Personal Access Token for repository access
- `GITHUB_REPO`: Repository name in format "owner/repository-name"
- `GITHUB_BRANCH`: Default branch for improvements (default: main)

### System Configuration
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `MEMORY_PERSIST_DIRECTORY`: Directory for persistent memory storage
- `ENABLE_SELF_MODIFICATION`: Enable/disable code self-modification

## Usage

### CLI Mode
```python
from evolving_agent.core.agent import SelfImprovingAgent

# Initialize the agent
agent = SelfImprovingAgent()
await agent.initialize()

# Process a query
result = await agent.process_query("Analyze this problem and improve my approach")

# The agent will:
# 1. Process the input with dynamic context
# 2. Generate an initial response
# 3. Evaluate its own output
# 4. Store insights in memory and knowledge base
# 5. Potentially create GitHub PRs with code improvements
```

### API Mode
```bash
# Start the server
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# Chat with the agent
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "How can I optimize my Python code?"}'

# Trigger code analysis and improvements
curl -X POST "http://localhost:8000/github/improve" \
  -H "Content-Type: application/json" \
  -d '{"create_pr": true}'

# Check GitHub integration status
curl "http://localhost:8000/github/status"
```

### GitHub Integration Usage
When GitHub is configured, the agent can:
- Analyze its own codebase for improvements
- Create pull requests with optimized code
- Track improvement history and learn from feedback

Example: The agent might detect a complex function, refactor it for better performance, and automatically create a PR with the improvement.

## Self-Improvement Cycle

### Core Learning Loop
1. **Input Processing**: Receives task and retrieves relevant context from memory
2. **Initial Response**: Generates response using current capabilities and knowledge
3. **Self-Evaluation**: Analyzes response quality and identifies improvement areas
4. **Memory Update**: Stores interaction and insights in long-term memory
5. **Knowledge Update**: Updates knowledge base with new insights and patterns

### Advanced GitHub-Enabled Improvements
6. **Code Analysis**: Examines own code for potential optimizations
7. **Improvement Generation**: Creates optimized code versions
8. **GitHub Workflow**: Creates branches and pull requests with improvements
9. **Human Feedback Integration**: Learns from code review feedback
10. **Validation**: Ensures modifications don't break functionality
11. **Continuous Learning**: Updates improvement strategies based on feedback

### Autonomous Capabilities
- **Performance Monitoring**: Tracks response quality and processing time
- **Pattern Recognition**: Identifies recurring issues and improvement opportunities  
- **Code Optimization**: Automatically refactors inefficient code patterns
- **Documentation Updates**: Keeps documentation in sync with code changes
- **Test Generation**: Creates tests for new functionality

## GitHub Integration 🐙

The agent can now interact with its own GitHub repository to create autonomous improvements:

### Features
- **Repository Access**: Read and analyze own source code
- **Branch Management**: Create improvement branches automatically
- **Pull Request Creation**: Submit code improvements via PRs
- **Commit History**: Track changes and improvements over time
- **Code Analysis**: Identify optimization opportunities in codebase
- **Human Feedback Loop**: Learn from code review feedback

### API Endpoints
- `GET /github/status` - GitHub integration status
- `GET /github/repository` - Repository information
- `GET /github/pull-requests` - List open pull requests
- `GET /github/commits` - Recent commit history
- `POST /github/improve` - Analyze and create code improvements
- `POST /github/demo-pr` - Create demonstration PR

### Workflow
1. **🔍 Analysis**: Agent analyzes its own codebase for improvements
2. **🛠️ Generation**: Creates optimized code versions
3. **🌿 Branch Creation**: Creates feature branch automatically  
4. **📝 Commit**: Commits improvements with descriptive messages
5. **🔄 Pull Request**: Creates PR with detailed description
6. **👨‍💻 Review**: Human review and feedback
7. **🤖 Learning**: Agent learns from feedback for future improvements

### Setup
1. Create a GitHub Personal Access Token:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token (classic) with `repo`, `workflow`, `write:packages` scopes

2. Configure in `.env`:
   ```bash
   GITHUB_TOKEN=your_personal_access_token
   GITHUB_REPO=owner/repository-name
   ```

3. The agent will automatically detect GitHub integration and enable advanced features

## License

MIT License
