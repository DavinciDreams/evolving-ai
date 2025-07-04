<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Self-Improving AI Agent Development Instructions

## Project Overview
This is a sophisticated self-improving AI agent with the following key capabilities:
- Long-term memory using vector embeddings (ChromaDB)
- Dynamic context retrieval and management
- Self-evaluation and output improvement
- Automatic knowledge base updates
- Code self-modification and optimization

## Code Style Guidelines
- Use Python 3.8+ features and type hints for all functions
- Follow async/await patterns for I/O operations
- Include comprehensive error handling with try/except blocks
- Add detailed docstrings for all classes and methods
- Use loguru for logging with appropriate log levels
- Follow the existing module structure and import patterns

## Architecture Patterns
- **Dependency Injection**: Pass dependencies through constructors
- **Async Operations**: Use async/await for all I/O and LLM calls
- **Error Isolation**: Wrap risky operations in try/except blocks
- **Configuration Management**: Use the config module for all settings
- **Memory Management**: Store important interactions and evaluations

## Key Components
1. **Core Agent** (`core/agent.py`): Main orchestrator
2. **Memory System** (`core/memory.py`): Long-term memory with ChromaDB
3. **Context Manager** (`core/context_manager.py`): Dynamic context retrieval
4. **Evaluator** (`core/evaluator.py`): Output evaluation and improvement
5. **Knowledge Base** (`knowledge/`): Knowledge management and updates
6. **Self-Modification** (`self_modification/`): Code analysis and modification

## Best Practices
- Always validate inputs and handle edge cases
- Use appropriate similarity thresholds for memory/knowledge retrieval
- Implement proper cleanup in destructors and cleanup methods
- Follow the evaluation → improvement → learning cycle
- Maintain backwards compatibility when modifying existing code
- Use comprehensive logging for debugging and monitoring

## Security Considerations
- Validate all code modifications before applying
- Use sandboxed environments for code execution when possible
- Implement safety checks for self-modification operations
- Never execute user-provided code without validation
- Maintain backups before applying modifications

## Testing Guidelines
- Write unit tests for all core functionality
- Test async operations with pytest-asyncio
- Mock external dependencies (LLM APIs, file operations)
- Test error conditions and edge cases
- Validate memory and knowledge base operations

## Performance Considerations
- Use async operations for concurrent processing
- Implement caching for frequently accessed data
- Optimize memory usage for large vector databases
- Monitor and log performance metrics
- Use appropriate batch sizes for bulk operations
