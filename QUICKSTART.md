# Quick Start Guide

## Setup Instructions

1. **Configure API Keys** (Required for full functionality):
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

2. **Run the Agent**:
   ```bash
   python main.py
   ```

3. **Run Tests**:
   ```bash
   python evolving_agent/tests/test_basic.py
   # or
   pytest evolving_agent/tests/
   ```

## Available Commands

Once the agent is running, you can use these commands:
- `help` - Show available commands
- `status` - Show agent status and performance metrics
- `memory` - Show memory statistics
- `quit` or `exit` - Exit the program

## Example Interactions

Try these example queries to test the agent:
- "Help me understand machine learning concepts"
- "How can I optimize this Python code?"
- "What are best practices for error handling?"
- "Analyze this problem and suggest solutions"

## Debug Mode

To run in debug mode in VS Code:
1. Open VS Code
2. Go to Run and Debug (Ctrl+Shift+D)
3. Select "Run Self-Improving Agent"
4. Press F5

## Features Overview

The agent will:
1. **Process your query** with dynamic context retrieval
2. **Generate an initial response** using the best available LLM
3. **Evaluate its own output** across multiple criteria
4. **Improve the response** based on self-evaluation
5. **Store the interaction** in long-term memory
6. **Update its knowledge base** automatically
7. **Consider self-modifications** periodically (if enabled)

## Monitoring

The agent logs all activities. Check `agent.log` for detailed logs, or watch the console output for real-time feedback.

## Configuration

Key settings in `.env`:
- `ENABLE_SELF_MODIFICATION=true` - Enables code self-modification
- `AUTO_UPDATE_KNOWLEDGE=true` - Enables automatic knowledge base updates
- `LOG_LEVEL=INFO` - Controls logging verbosity
- `DEFAULT_LLM_PROVIDER=openai` - Primary LLM provider

## Safety

The agent includes multiple safety mechanisms:
- Code validation before any modifications
- Automatic backups before changes
- Safety scoring for all modifications
- Configurable modification limits
- Comprehensive error handling

## Next Steps

1. Configure your API keys for full functionality
2. Try various types of queries to see the agent learn and improve
3. Monitor the `memory_db/` and `knowledge_base/` directories to see how it builds knowledge
4. Check the agent's self-improvement suggestions with the `status` command
5. Review logs to understand the decision-making process
