# 🤖 Self-Improving AI Agent

A sophisticated AI agent with advanced self-improvement capabilities, long-term memory, and autonomous code evolution.

## 🌟 Key Features

### 🧠 Advanced AI Capabilities

- **Long-term Memory**: Persistent memory system using ChromaDB vector embeddings
- **Dynamic Context Management**: Intelligent context retrieval and management
- **Self-Evaluation**: Continuous output evaluation and improvement cycles
- **Knowledge Base**: Automatic knowledge acquisition and updates

### 🔄 Self-Improvement Engine

- **Code Analysis**: Automated analysis of its own codebase
- **Autonomous Modifications**: Safe self-modification with validation
- **GitHub Integration**: Automatic pull request creation for improvements
- **Performance Monitoring**: Continuous performance tracking and optimization

### 🚀 Production Features

- **FastAPI Web Server**: RESTful API with Swagger documentation
- **Multiple LLM Providers**: Support for OpenAI, Anthropic, OpenRouter, and more
- **Robust Error Handling**: Comprehensive error management and recovery
- **Configurable Environment**: Flexible configuration system

## 📋 Requirements

- Python 3.8+
- ChromaDB for vector storage
- FastAPI for web server
- Multiple LLM provider APIs

## 🛠️ Installation

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd evolving ai
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## 🚀 Usage

### Main Entry Points

- **Run the main agent:**

  ```bash
  python main.py
  ```

- **Start the API server:**

  ```bash
  python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
  ```

- **Organize or clean up the project structure:**

  ```bash
  python organize_project.py
  ```

- **Generate or summarize Swagger API docs:**

  ```bash
  python swagger_summary.py
  ```

- **Run the complete system demo:**

  ```bash
  python demo_complete_system.py
  ```

### Self-Improvement System

To enable autonomous self-improvement and code modification, set the following in your `.env` file:

```env
ENABLE_SELF_MODIFICATION=true
```

When enabled, the agent will:

- Analyze its own codebase for improvements
- Propose and validate modifications
- Optionally create GitHub pull requests for validated changes
- **Autofix code style using `isort` and `black` before committing improvements**

**Linting Autofix Step:**
Before each code improvement is committed, the agent automatically runs [`isort`](https://pycqa.github.io/isort/) and [`black`](https://black.readthedocs.io/en/stable/) to ensure code style consistency.
If autofix fails for a file, that file is skipped and not committed.

**Manual Linting:**
To manually run the same linting autofix on your codebase:

```bash
isort path/to/your/file.py
black path/to/your/file.py
# Or recursively for the whole project:
isort .
black .
```

**Workflow:**

1. Set `ENABLE_SELF_MODIFICATION=true` in `.env`
2. Run `python main.py` or start the API server
3. The agent will autonomously analyze, modify, autofix (isort + black), and validate its code according to the self-improvement cycle

See [`docs/SELF_IMPROVEMENT_DEMO.md`](docs/SELF_IMPROVEMENT_DEMO.md) for a detailed walkthrough.

### API Endpoints

Access the interactive API documentation at: `http://localhost:8000/docs`

Key endpoints:

- `/chat` - Interact with the agent
- `/analyze` - Code analysis and suggestions
- `/memory` - Memory management
- `/knowledge` - Knowledge base operations
- `/github/*` - GitHub integration features

### GitHub Integration

```bash
# Set up GitHub integration
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO_URL="https://github.com/username/repository"
```

With these set, the agent can:

- Analyze its own code
- Create improvement pull requests
- Track development history

## 🔧 Configuration

Key configuration options in `.env`:

```env
# LLM Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
OPENROUTER_API_KEY=your_openrouter_key

# GitHub Integration
GITHUB_TOKEN=your_github_token
GITHUB_REPO_URL=your_repository_url

# Agent Settings
AGENT_NAME=EvolveAI
AGENT_ROLE=Senior Software Engineer

# Self-Improvement
ENABLE_SELF_MODIFICATION=true
```

## 🧪 Testing

Run all tests:

```bash
python -m pytest
```

Run individual test scripts:

```bash
python tests/test_complete_system.py
python tests/test_api_endpoints.py
python tests/test_github_integration.py
python tests/test_end_to_end_self_improvement.py
python tests/test_core_improvements.py
python tests/test_agent_improvements.py
python tests/test_fallback_system.py
# ...and others in the tests/ directory
```

## 📚 Project Structure

```
evolving_agent/
├── core/                # Core agent functionality
├── knowledge/           # Knowledge management
├── self_modification/   # Code analysis and modification
├── utils/               # Utilities and integrations
├── tests/               # Test suite
knowledge_base/          # Knowledge base data
api_server.py            # FastAPI server entry point
main.py                  # Main agent entry point
organize_project.py      # Project organization/cleanup
swagger_summary.py       # Swagger/OpenAPI summary
demo_complete_system.py  # Demo script
requirements.txt         # Python dependencies
.env.example             # Example environment config
docs/                    # Documentation
```

## 🤝 Contributing

This AI agent continuously improves itself, but manual contributions are welcome:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

The AI agent will analyze and potentially incorporate your improvements into its own evolution cycle.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔮 Future Roadmap

- [ ] Enhanced self-modification capabilities
- [ ] Multi-agent collaboration
- [ ] Advanced reasoning systems
- [ ] Expanded integration ecosystem
- [ ] Production deployment tools

---

*This documentation was enhanced by the AI agent's self-improvement system.*