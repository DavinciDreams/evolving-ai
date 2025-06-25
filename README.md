# Self-Improving AI Agent

A sophisticated AI agent with self-improvement capabilities, long-term memory, dynamic context queries, and autonomous code modification abilities.

## Features

- **Long-term Memory**: Persistent vector-based memory system using ChromaDB
- **Dynamic Context Queries**: Intelligent context retrieval based on current objectives
- **Self-Evaluation**: Built-in mechanisms to evaluate and improve outputs
- **Knowledge Base Updates**: Automatic updates to knowledge base from experiences
- **Code Self-Modification**: Ability to analyze and modify its own codebase
- **Multi-LLM Support**: Compatible with OpenAI, Anthropic, OpenRouter, and other providers

## Architecture

```
evolving_agent/
├── core/                   # Core agent functionality
│   ├── agent.py           # Main agent class
│   ├── memory.py          # Long-term memory management
│   ├── evaluator.py       # Output evaluation system
│   └── context_manager.py # Dynamic context management
├── knowledge/             # Knowledge base management
│   ├── base.py           # Knowledge base operations
│   └── updater.py        # Knowledge update mechanisms
├── self_modification/     # Self-improvement capabilities
│   ├── code_analyzer.py  # Code analysis and understanding
│   ├── modifier.py       # Code modification engine
│   └── validator.py      # Code validation system
├── utils/                # Utility functions
│   ├── llm_interface.py  # LLM communication
│   ├── logging.py        # Enhanced logging
│   └── config.py         # Configuration management
└── tests/                # Test suite
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Configure your API keys in `.env`

4. Initialize the agent:
```bash
python main.py
```

## Configuration

Set your API keys and preferences in `.env`:
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key (default provider)
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `MEMORY_PERSIST_DIRECTORY`: Directory for persistent memory storage

## Usage

```python
from evolving_agent.core.agent import SelfImprovingAgent

# Initialize the agent
agent = SelfImprovingAgent()

# Run the agent with a task
result = await agent.run("Analyze this problem and improve my approach")

# The agent will:
# 1. Process the input with dynamic context
# 2. Generate an initial response
# 3. Evaluate its own output
# 4. Suggest improvements to its knowledge base
# 5. Potentially modify its own code for better performance
```

## Self-Improvement Cycle

1. **Input Processing**: Receives task and retrieves relevant context
2. **Initial Response**: Generates response using current capabilities
3. **Self-Evaluation**: Analyzes response quality and identifies improvements
4. **Knowledge Update**: Updates knowledge base with new insights
5. **Code Analysis**: Examines own code for potential improvements
6. **Self-Modification**: Implements approved code changes
7. **Validation**: Ensures modifications don't break functionality

## License

MIT License
