"""
Enhanced self-modification system with GitHub integration.
"""

import ast
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from evolving_agent.self_modification.code_analyzer import CodeAnalyzer
from evolving_agent.self_modification.modifier import CodeModifier
from evolving_agent.self_modification.validator import CodeValidator
from evolving_agent.utils.github_integration import GitHubIntegration
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)


class GitHubEnabledSelfModifier:
    """
    Self-modification system enhanced with GitHub integration.
    Can analyze code, generate improvements, and create pull requests automatically.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        repo_name: Optional[str] = None,
        local_repo_path: Optional[str] = None
    ):
        """
        Initialize the GitHub-enabled self-modifier.
        
        Args:
            github_token: GitHub personal access token
            repo_name: Repository name in format "owner/repo"
            local_repo_path: Path to local repository
        """
        self.code_analyzer = CodeAnalyzer()
        self.code_modifier = CodeModifier(self.code_analyzer, CodeValidator())
        self.code_validator = CodeValidator()
        
        # GitHub integration
        self.github_integration = GitHubIntegration(
            github_token=github_token,
            repo_name=repo_name,
            local_repo_path=local_repo_path
        )
        
        # State tracking
        self.improvement_history: List[Dict[str, Any]] = []
        self.auto_pr_enabled = True
        
    async def initialize(self) -> bool:
        """
        Initialize the self-modifier and GitHub integration.
        
        Returns:
            True if initialization successful
        """
        try:
            # Initialize GitHub integration
            github_success = await self.github_integration.initialize()
            if github_success:
                logger.info("GitHub integration initialized successfully")
            else:
                logger.warning("GitHub integration failed, continuing without it")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GitHubEnabledSelfModifier: {e}")
            return False
    
    async def analyze_and_improve_codebase(
        self,
        evaluation_insights: Optional[Dict[str, Any]] = None,
        knowledge_suggestions: Optional[List[Dict[str, Any]]] = None,
        create_pr: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze the codebase and generate improvements, optionally creating a PR.
        
        Args:
            evaluation_insights: Evaluation insights to consider
            knowledge_suggestions: Knowledge-based suggestions
            create_pr: Whether to create a pull request with improvements
            
        Returns:
            Dictionary with analysis results and improvement actions
        """
        try:
            logger.info("Starting comprehensive codebase analysis and improvement...")
            
            # Step 1: Analyze performance patterns
            analysis_result = await self.code_analyzer.analyze_performance_patterns(
                evaluation_insights or {},
                knowledge_suggestions or []
            )
            
            logger.info(f"Analysis completed. Improvement potential: {analysis_result.get('improvement_potential', 0):.2f}")
            
            # Step 2: Generate specific code improvements
            improvements = await self._generate_code_improvements(analysis_result)
            
            logger.info(f"Generated {len(improvements)} code improvements")
            
            # Step 3: Validate improvements
            validated_improvements = await self._validate_improvements(improvements)
            
            logger.info(f"Validated {len(validated_improvements)} improvements")
            
            # Step 4: Create pull request if requested and GitHub is available
            pr_result = {}
            if create_pr and self.auto_pr_enabled and validated_improvements:
                if self.github_integration.repository:
                    pr_result = await self.pr_manager.create_improvement_pr(
                        validated_improvements,
                        analysis_result
                    )
                    
                    if "error" not in pr_result:
                        logger.info(f"Created improvement PR #{pr_result['pr_number']}")
                    else:
                        logger.error(f"Failed to create PR: {pr_result['error']}")
                else:
                    logger.warning("GitHub repository not available, skipping PR creation")
            
            # Step 5: Record improvement attempt
            improvement_record = {
                "timestamp": datetime.now().isoformat(),
                "analysis_result": analysis_result,
                "improvements_generated": len(improvements),
                "improvements_validated": len(validated_improvements),
                "pr_created": "pr_number" in pr_result,
                "pr_result": pr_result
            }
            
            self.improvement_history.append(improvement_record)
            
            return {
                "analysis_result": analysis_result,
                "improvements": validated_improvements,
                "pr_result": pr_result,
                "summary": {
                    "improvement_potential": analysis_result.get('improvement_potential', 0),
                    "opportunities_found": len(analysis_result.get('improvement_opportunities', [])),
                    "improvements_generated": len(improvements),
                    "improvements_validated": len(validated_improvements),
                    "pr_created": "pr_number" in pr_result
                }
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_and_improve_codebase: {e}")
            return {"error": str(e)}
    
    async def _generate_code_improvements(
        self,
        analysis_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate specific code improvements based on analysis results.
        
        Args:
            analysis_result: Results from code analysis
            
        Returns:
            List of code improvements
        """
        improvements = []
        
        try:
            # Get high complexity functions for refactoring
            codebase_analysis = analysis_result.get('codebase_analysis', {})
            complexity_metrics = codebase_analysis.get('complexity_metrics', {})
            high_complexity_functions = complexity_metrics.get('high_complexity_functions', [])
            
            # Generate improvements for high complexity functions
            for func_info in high_complexity_functions[:3]:  # Limit to top 3
                improvement = await self._generate_function_improvement(func_info)
                if improvement:
                    improvements.append(improvement)
            
            # Generate improvements based on opportunities
            opportunities = analysis_result.get('improvement_opportunities', [])
            for opportunity in opportunities[:5]:  # Limit to top 5
                improvement = await self._generate_opportunity_improvement(opportunity)
                if improvement:
                    improvements.append(improvement)
            
            logger.info(f"Generated {len(improvements)} specific code improvements")
            return improvements
            
        except Exception as e:
            logger.error(f"Error generating code improvements: {e}")
            return []
    
    async def _generate_function_improvement(
        self,
        func_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement for a high-complexity function.
        
        Args:
            func_info: Information about the function
            
        Returns:
            Improvement dictionary or None
        """
        try:
            module_path = func_info.get('module', '')
            function_name = func_info.get('function', '')
            complexity = func_info.get('complexity', 0)
            
            if not module_path or not function_name:
                return None
            
            # Read the current file content
            file_path = module_path.replace('\\', '/')
            if not file_path.endswith('.py'):
                file_path += '.py'
            
            # For now, generate a documentation improvement
            # In a real implementation, this would analyze the function and generate specific refactoring
            improvement = {
                "type": "function_refactor",
                "file_path": file_path,
                "function_name": function_name,
                "current_complexity": complexity,
                "description": f"Refactor high-complexity function {function_name} (complexity: {complexity})",
                "suggestion": f"Consider breaking down {function_name} into smaller, more focused functions",
                "priority": min(complexity / 20.0, 1.0),  # Normalize to 0-1 scale
                "category": "complexity_reduction"
            }
            
            return improvement
            
        except Exception as e:
            logger.error(f"Error generating function improvement: {e}")
            return None
    
    async def _generate_opportunity_improvement(
        self,
        opportunity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement based on an opportunity.
        
        Args:
            opportunity: Improvement opportunity
            
        Returns:
            Improvement dictionary or None
        """
        try:
            opp_type = opportunity.get('type', '')
            priority = opportunity.get('priority', 0)
            description = opportunity.get('description', '')
            suggested_action = opportunity.get('suggested_action', '')
            
            # Generate specific improvements based on opportunity type
            if 'performance' in opp_type.lower():
                return {
                    "type": "performance_improvement",
                    "description": description,
                    "suggested_action": suggested_action,
                    "priority": priority,
                    "category": "performance",
                    "implementation": "Add caching or optimize algorithms"
                }
            
            elif 'error' in opp_type.lower() or 'exception' in opp_type.lower():
                return {
                    "type": "error_handling_improvement",
                    "description": description,
                    "suggested_action": suggested_action,
                    "priority": priority,
                    "category": "reliability",
                    "implementation": "Add comprehensive try-catch blocks and error logging"
                }
            
            elif 'test' in opp_type.lower():
                return {
                    "type": "testing_improvement",
                    "description": description,
                    "suggested_action": suggested_action,
                    "priority": priority,
                    "category": "testing",
                    "implementation": "Add unit tests for edge cases and error conditions"
                }
            
            else:
                return {
                    "type": "general_improvement",
                    "description": description,
                    "suggested_action": suggested_action,
                    "priority": priority,
                    "category": "general",
                    "implementation": suggested_action
                }
            
        except Exception as e:
            logger.error(f"Error generating opportunity improvement: {e}")
            return None
    
    async def _validate_improvements(
        self,
        improvements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate proposed improvements for safety and feasibility.
        
        Args:
            improvements: List of proposed improvements
            
        Returns:
            List of validated improvements
        """
        validated = []
        
        for improvement in improvements:
            try:
                # Basic validation
                if not improvement.get('description') or not improvement.get('priority'):
                    continue
                
                # Priority filtering (only high-priority improvements)
                if improvement.get('priority', 0) < 0.5:
                    continue
                
                # Type-specific validation
                improvement_type = improvement.get('type', '')
                
                if improvement_type == 'function_refactor':
                    # Validate function refactoring
                    if improvement.get('current_complexity', 0) > 10:  # Only refactor truly complex functions
                        validated.append(improvement)
                
                elif improvement_type in ['performance_improvement', 'error_handling_improvement', 'testing_improvement']:
                    # These are generally safe improvements
                    validated.append(improvement)
                
                elif improvement_type == 'general_improvement':
                    # General improvements need higher priority
                    if improvement.get('priority', 0) > 0.7:
                        validated.append(improvement)
                
            except Exception as e:
                logger.error(f"Error validating improvement: {e}")
                continue
        
        logger.info(f"Validated {len(validated)} out of {len(improvements)} improvements")
        return validated
    
    async def get_repository_status(self) -> Dict[str, Any]:
        """Get comprehensive repository status including GitHub and local repo info."""
        try:
            status = {}
            
            # Check GitHub connection
            status["github_connected"] = (
                self.github_integration.github_client is not None and
                self.github_integration.repository is not None
            )
            
            # Get repository info
            if status["github_connected"]:
                status["repository_info"] = await self.github_integration.get_repository_info()
                
                # Get open PRs
                status["open_pull_requests"] = await self.github_integration.get_open_pull_requests()
            
            # Check local repo
            status["local_repo_available"] = self.github_integration.local_repo is not None
            
            # Configuration
            status["auto_pr_enabled"] = True  # Could be configurable
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting repository status: {e}")
            return {"error": str(e)}
    
    
    async def create_documentation_improvement_pr(self) -> Dict[str, Any]:
        """Create a demonstration PR with documentation improvements."""
        try:
            if not self.github_integration.repository:
                return {"error": "No GitHub repository connected"}
            
            # Create a new branch for the demo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"demo-improvements-{timestamp}"
            
            logger.info(f"Creating demo branch: {branch_name}")
            
            # Create branch
            branch_result = await self.github_integration.create_branch(branch_name)
            if "error" in branch_result:
                return {"error": f"Failed to create branch: {branch_result['error']}"}
            
            # Get current README content
            readme_content = await self.github_integration.get_file_content("README.md")
            if not readme_content or "error" in readme_content:
                readme_content = "# Self-Improving AI Agent\n\nA sophisticated AI agent with self-improvement capabilities.\n"
            else:
                readme_content = readme_content.get("content", "")
            
            # Create improved README content
            improved_readme = self._generate_improved_readme(readme_content)
            
            # Update README.md
            update_result = await self.github_integration.update_file(
                file_path="README.md",
                new_content=improved_readme,
                commit_message="🤖 AI Agent: Improve README documentation",
                branch=branch_name
            )
            
            if "error" in update_result:
                return {"error": f"Failed to update README: {update_result['error']}"}
            
            # Create pull request
            pr_title = "🤖 AI Agent: Documentation Improvements"
            pr_body = """## Automated Documentation Improvements

This pull request was automatically created by the self-improving AI agent to enhance the project documentation.

### Changes Made:
- ✨ Enhanced README.md with improved structure and content
- 📚 Added comprehensive feature descriptions
- 🚀 Improved installation and usage instructions
- 🔧 Added configuration examples

### AI Agent Information:
- **Generated**: Automatically by the evolving AI agent
- **Purpose**: Continuous improvement of project documentation
- **Safe**: This PR only contains documentation improvements

*This is a demonstration of the AI agent's ability to analyze and improve its own codebase.*"""
            
            pr_result = await self.github_integration.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch="main"
            )
            
            if "error" in pr_result:
                return {"error": f"Failed to create PR: {pr_result['error']}"}
            
            # Log the improvement
            improvement_record = {
                "timestamp": datetime.now().isoformat(),
                "type": "documentation_improvement",
                "branch": branch_name,
                "pr_number": pr_result.get("pr_number"),
                "pr_url": pr_result.get("pr_url"),
                "files_updated": ["README.md"]
            }
            
            self.improvement_history.append(improvement_record)
            
            logger.info(f"Successfully created demo PR #{pr_result.get('pr_number')}")
            
            return {
                "success": True,
                "pr_number": pr_result.get("pr_number"),
                "pr_url": pr_result.get("pr_url"),
                "branch_name": branch_name,
                "files_updated": ["README.md"]
            }
            
        except Exception as e:
            logger.error(f"Error creating demo PR: {e}")
            return {"error": str(e)}
    
    
    def _generate_improved_readme(self, current_content: str) -> str:
        """Generate an improved README with better structure and content."""
        
        improved_readme = """# 🤖 Self-Improving AI Agent

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
   cd evolving-ai-agent
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

4. **Initialize the system**:
   ```bash
   python main.py
   ```

## 🚀 Usage

### Running the Agent
```bash
# Run the main agent
python main.py

# Start the API server
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

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

# The agent can now:
# - Analyze its own code
# - Create improvement pull requests
# - Track development history
```

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
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest

# Test specific components
python test_complete_system.py
python test_api_endpoints.py

# Test GitHub integration
python test_github_integration.py
```

## 📚 Architecture

```
evolving_agent/
├── core/           # Core agent functionality
├── knowledge/      # Knowledge management
├── self_modification/ # Code analysis and modification
└── utils/          # Utilities and integrations
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

*This documentation was enhanced by the AI agent's self-improvement system.*"""
        
        return improved_readme


    def get_improvement_history(self) -> List[Dict[str, Any]]:
        """Get the history of improvements made by the agent."""
        return self.improvement_history.copy()
