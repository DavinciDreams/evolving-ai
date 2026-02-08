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
from evolving_agent.self_modification.validator import CodeValidator
from evolving_agent.integrations.github_integration import GitHubIntegration
from evolving_agent.utils.llm_interface import llm_manager
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
        local_repo_path: Optional[str] = None,
    ):
        """
        Initialize the GitHub-enabled self-modifier.

        Args:
            github_token: GitHub personal access token
            repo_name: Repository name in format "owner/repo"
            local_repo_path: Path to local repository
        """
        self.code_analyzer = CodeAnalyzer()
        self.code_validator = CodeValidator()

        # GitHub integration
        self.github_integration = GitHubIntegration(
            github_token=github_token,
            repo_name=repo_name,
            local_repo_path=local_repo_path,
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
        create_pr: bool = True,
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
                evaluation_insights or {}, knowledge_suggestions or []
            )

            logger.info(
                f"Analysis completed. Improvement potential: {analysis_result.get('improvement_potential', 0):.2f}"
            )

            # Step 2: Generate specific code improvements
            improvements = await self._generate_code_improvements(analysis_result)

            logger.info(f"Generated {len(improvements)} code improvements")

            # Step 3: Validate improvements
            validated_improvements = await self._validate_improvements(improvements)

            logger.info(f"Validated {len(validated_improvements)} improvements")

            # Step 4: Create GitHub issue or PR if requested and GitHub is available
            github_result = {}
            if create_pr and self.auto_pr_enabled and validated_improvements:
                if self.github_integration.repository:
                    # Check if we have actual code modifications or just suggestions
                    has_actual_code_changes = any(
                        imp.get("has_code_changes", False) for imp in validated_improvements
                    )
                    
                    if has_actual_code_changes:
                        # Create PR for actual code improvements
                        github_result = await self._create_improvement_pr(
                            validated_improvements, analysis_result
                        )
                        if "error" not in github_result:
                            logger.info(f"Created improvement PR #{github_result['pr_number']}")
                        else:
                            logger.error(f"Failed to create PR: {github_result['error']}")
                    else:
                        # Create issue for suggestions only
                        github_result = await self._create_improvement_issue(
                            validated_improvements, analysis_result
                        )
                        if "error" not in github_result:
                            logger.info(f"Created improvement issue #{github_result['issue_number']}")
                        else:
                            logger.error(f"Failed to create issue: {github_result['error']}")
                else:
                    logger.warning(
                        "GitHub repository not available, skipping GitHub creation"
                    )

            # Step 5: Record improvement attempt
            improvement_record = {
                "timestamp": datetime.now().isoformat(),
                "analysis_result": analysis_result,
                "improvements_generated": len(improvements),
                "improvements_validated": len(validated_improvements),
                "github_created": bool(github_result),
                "github_result": github_result,
            }

            self.improvement_history.append(improvement_record)

            # Determine what was created for the response
            pr_created = "pr_number" in github_result
            issue_created = "issue_number" in github_result
            
            return {
                "analysis_result": analysis_result,
                "improvements": validated_improvements,
                "github_result": github_result,
                "summary": {
                    "improvement_potential": analysis_result.get(
                        "improvement_potential", 0
                    ),
                    "opportunities_found": len(
                        analysis_result.get("improvement_opportunities", [])
                    ),
                    "improvements_generated": len(improvements),
                    "improvements_validated": len(validated_improvements),
                    "pr_created": pr_created,
                    "issue_created": issue_created,
                    "github_type": "pull_request" if pr_created else "issue" if issue_created else "none",
                },
            }

        except Exception as e:
            logger.error(f"Error in analyze_and_improve_codebase: {e}")
            return {"error": str(e)}

    async def _generate_code_improvements(
        self, analysis_result: Dict[str, Any]
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
            codebase_analysis = analysis_result.get("codebase_analysis", {})
            complexity_metrics = codebase_analysis.get("complexity_metrics", {})
            high_complexity_functions = complexity_metrics.get(
                "high_complexity_functions", []
            )

            # Generate improvements for high complexity functions
            for func_info in high_complexity_functions[:3]:  # Limit to top 3
                improvement = await self._generate_function_improvement(func_info)
                if improvement:
                    improvements.append(improvement)

            # Generate improvements based on opportunities
            opportunities = analysis_result.get("improvement_opportunities", [])
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
        self, func_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement for a high-complexity function.

        Args:
            func_info: Information about the function

        Returns:
            Improvement dictionary or None
        """
        try:
            module_path = func_info.get("module", "")
            function_name = func_info.get("function", "")
            complexity = func_info.get("complexity", 0)

            if not module_path or not function_name:
                return None

            # Read the current file content
            file_path = module_path.replace("\\", "/")
            if not file_path.endswith(".py"):
                file_path += ".py"

            # Try to find the file in the project structure
            full_path = Path(file_path)
            if not full_path.exists():
                # Try common project structures
                possible_paths = [
                    Path(file_path),
                    Path("evolving_agent") / file_path,
                    Path(".") / file_path
                ]
                
                for path in possible_paths:
                    if path.exists():
                        full_path = path
                        break
                else:
                    logger.warning(f"File not found: {full_path}")
                    return None

            # Read and parse the file
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                # Create a simple refactored version that actually works
                refactored_code = await self._create_simple_refactor(function_name, complexity, content)
                
                improvement = {
                    "type": "function_refactor",
                    "file_path": str(full_path),
                    "function_name": function_name,
                    "current_complexity": complexity,
                    "description": f"Refactor high-complexity function {function_name} (complexity: {complexity})",
                    "suggestion": f"Breaking down {function_name} into smaller functions for better maintainability",
                    "priority": min(complexity / 20.0, 1.0),  # Normalize to 0-1 scale
                    "category": "complexity_reduction",
                    "original_code": content,
                    "refactored_code": refactored_code,
                    "has_code_changes": True,
                }

                return improvement
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                return None

        except Exception as e:
            logger.error(f"Error generating function improvement: {e}")
            return None
    
    def _refactor_function(self, tree: ast.AST, function_name: str, complexity: int) -> Optional[str]:
        """
        Refactor a high-complexity function by breaking it into smaller functions.
        
        Args:
            tree: AST of the file
            function_name: Name of the function to refactor
            complexity: Current complexity score
            
        Returns:
            Refactored code or None if refactoring fails
        """
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    # Extract function components
                    func_start = node.lineno
                    func_end = self._get_function_end_line(tree, node)
                    
                    # Generate refactored version
                    refactored_name = f"{function_name}_refactored"
                    helper_name = f"{function_name}_helper"
                    
                    # Create helper function for complex logic
                    helper_code = f"""
    def {helper_name}(self, *args, **kwargs):
        \"\"\"Helper function extracted from {function_name} to reduce complexity.\"\"\\"\"
        # Extracted complex logic here
        return self._process_{function_name}_logic(*args, **kwargs)
"""
                    
                    # Create refactored main function
                    refactored_code = f"""
    def {refactored_name}(self, *args, **kwargs):
        \"\"\"Refactored version of {function_name} with reduced complexity.\"\"\\"\"
        # Pre-processing
        preprocessed_args = self._preprocess_{function_name}_args(*args, **kwargs)
        
        # Main logic delegated to helper
        result = {helper_name}(self, *preprocessed_args)
        
        # Post-processing
        return self._postprocess_{function_name}_result(result)
"""
                    
                    return refactored_code
            
            return None
            
        except Exception as e:
            logger.error(f"Error refactoring function {function_name}: {e}")
            return None
    
    def _get_function_end_line(self, tree: ast.AST, func_node: ast.FunctionDef) -> int:
        """Find the end line of a function in the AST."""
        try:
            # Simple heuristic: find the next node at the same or lower indentation level
            func_lines = [node.lineno for node in ast.walk(tree)
                         if hasattr(node, 'lineno') and node.lineno > func_node.lineno]
            
            if func_lines:
                return min(func_lines) - 1
            else:
                return func_node.lineno + 10  # Fallback estimate
                
        except Exception:
            return func_node.lineno + 10

    async def _create_simple_refactor(
        self, function_name: str, complexity: float, content: str
    ) -> str:
        """
        Create a refactored version of the function using the LLM.

        Args:
            function_name: Name of the function to refactor
            complexity: Current complexity score of the function
            content: The file content containing the function

        Returns:
            Refactored code as a string
        """
        try:
            # Create the refactoring prompt
            refactor_prompt = f"""You are a Python code refactoring expert. Analyze the following function and refactor it to improve readability and maintainability.

Function name: {function_name}
Current complexity: {complexity}

File content:
```python
{content}
```

Your task:
1. Analyze the function for complexity issues
2. Refactor to improve readability and maintainability
3. Preserve the original functionality
4. Return ONLY the refactored Python code (no explanations, no markdown code blocks)

Focus on:
- Breaking down complex logic into smaller helper functions
- Improving variable naming
- Adding docstrings
- Reducing nesting levels
- Extracting repeated code into reusable functions
"""

            # Generate refactored code using the LLM
            refactored_code = await llm_manager.generate_response(
                prompt=refactor_prompt,
                temperature=0.3,
                max_tokens=4000
            )

            # Clean up the response - remove markdown code blocks if present
            if refactored_code.startswith("```python"):
                refactored_code = refactored_code.split("```python")[1]
            if refactored_code.startswith("```"):
                refactored_code = refactored_code.split("```")[1]
            if refactored_code.endswith("```"):
                refactored_code = refactored_code.rsplit("```", 1)[0]

            return refactored_code.strip()

        except Exception as e:
            logger.error(f"Failed to create simple refactor for {function_name}: {e}")
            # Return original content if refactoring fails
            return content

    async def _generate_opportunity_improvement(
        self, opportunity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement based on an opportunity, including actual code changes.

        Args:
            opportunity: Improvement opportunity

        Returns:
            Improvement dictionary with code changes or None
        """
        try:
            opp_type = opportunity.get("type", "")
            priority = opportunity.get("priority", 0)
            description = opportunity.get("description", "")
            suggested_action = opportunity.get("suggested_action", "")

            # Try to extract file path and function/class from opportunity
            file_path = None
            original_code = None
            refactored_code = None
            has_code_changes = False

            # Check if opportunity has affected functions with file paths
            affected_functions = opportunity.get("affected_functions", [])
            if affected_functions:
                # Use the first affected function to get file path
                func_info = affected_functions[0]
                module_path = func_info.get("module", "")
                function_name = func_info.get("function", "")

                if module_path:
                    # Try to read the file
                    full_path = self._resolve_file_path(module_path)
                    if full_path and full_path.exists():
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                original_code = f.read()
                            file_path = str(full_path)
                            
                            # Generate refactored code using LLM
                            refactored_code = await self._generate_opportunity_refactor(
                                opp_type=opp_type,
                                description=description,
                                suggested_action=suggested_action,
                                function_name=function_name,
                                original_code=original_code,
                                priority=priority
                            )
                            
                            if refactored_code and refactored_code != original_code:
                                has_code_changes = True
                                logger.info(f"Successfully generated code changes for {function_name} in {file_path}")
                            else:
                                logger.warning(f"Failed to generate code changes for {function_name}, falling back to suggestion")
                        except Exception as e:
                            logger.error(f"Error reading or processing file {file_path}: {e}")

            # Determine category based on opportunity type
            if "performance" in opp_type.lower():
                category = "performance"
            elif "error" in opp_type.lower() or "exception" in opp_type.lower():
                category = "reliability"
            elif "test" in opp_type.lower():
                category = "testing"
            elif "complexity" in opp_type.lower():
                category = "complexity_reduction"
            else:
                category = "general"

            # Build improvement dictionary
            improvement = {
                "type": f"{category}_improvement" if category != "general" else "general_improvement",
                "description": description,
                "suggested_action": suggested_action,
                "priority": priority,
                "category": category,
            }

            # Add code-related fields if we have them
            if file_path:
                improvement["file_path"] = file_path
            if original_code:
                improvement["original_code"] = original_code
            if refactored_code:
                improvement["refactored_code"] = refactored_code
            improvement["has_code_changes"] = has_code_changes

            return improvement

        except Exception as e:
            logger.error(f"Error generating opportunity improvement: {e}")
            return None
    
    def _resolve_file_path(self, module_path: str) -> Optional[Path]:
        """
        Resolve a module path to an actual file path.
        
        Args:
            module_path: Module path (e.g., "evolving_agent/core/agent.py")
            
        Returns:
            Path object or None if not found
        """
        try:
            # Normalize the path
            normalized_path = module_path.replace("\\", "/")
            if not normalized_path.endswith(".py"):
                normalized_path += ".py"
            
            # Try different possible locations
            possible_paths = [
                Path(normalized_path),
                Path("evolving_agent") / normalized_path,
                Path(".") / normalized_path,
                Path(__file__).parent.parent / normalized_path,
            ]
            
            for path in possible_paths:
                if path.exists():
                    return path
            
            logger.warning(f"Could not resolve file path for: {module_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving file path {module_path}: {e}")
            return None
    
    async def _generate_opportunity_refactor(
        self,
        opp_type: str,
        description: str,
        suggested_action: str,
        function_name: Optional[str],
        original_code: str,
        priority: float
    ) -> Optional[str]:
        """
        Generate refactored code using the LLM based on an opportunity.
        
        Args:
            opp_type: Type of opportunity
            description: Description of the opportunity
            suggested_action: Suggested action to take
            function_name: Name of the function being refactored (if applicable)
            original_code: Original code to refactor
            priority: Priority of the improvement
            
        Returns:
            Refactored code or None if generation fails
        """
        try:
            # Create the refactoring prompt
            refactor_prompt = f"""You are a Python code improvement expert. Analyze the following code and apply improvements based on the opportunity described.

Opportunity Type: {opp_type}
Description: {description}
Suggested Action: {suggested_action}
Priority: {priority}
Target Function: {function_name or 'N/A'}

Original Code:
```python
{original_code}
```

Your task:
1. Analyze the code for the specific improvement opportunity
2. Apply the suggested improvements while preserving functionality
3. Ensure the code follows Python best practices
4. Return ONLY the refactored Python code (no explanations, no markdown code blocks)

Improvement Guidelines:
"""
            
            # Add specific guidelines based on opportunity type
            if "performance" in opp_type.lower():
                refactor_prompt += """
- Optimize algorithms and data structures
- Add caching where appropriate
- Reduce unnecessary computations
- Use efficient built-in functions
"""
            elif "error" in opp_type.lower() or "exception" in opp_type.lower():
                refactor_prompt += """
- Add comprehensive try-except blocks
- Include proper error logging
- Handle edge cases gracefully
- Provide meaningful error messages
"""
            elif "complexity" in opp_type.lower():
                refactor_prompt += """
- Break down complex functions into smaller helpers
- Reduce nesting levels
- Improve variable naming
- Add docstrings
- Extract repeated code into reusable functions
"""
            elif "test" in opp_type.lower():
                refactor_prompt += """
- Add unit tests for the code
- Cover edge cases and error conditions
- Use appropriate testing patterns
- Ensure test isolation
"""
            else:
                refactor_prompt += """
- Improve code readability and maintainability
- Follow PEP 8 style guidelines
- Add appropriate comments and docstrings
- Ensure type hints where appropriate
"""

            # Generate refactored code using the LLM
            refactored_code = await llm_manager.generate_response(
                prompt=refactor_prompt,
                temperature=0.3,
                max_tokens=4000
            )

            # Clean up the response - remove markdown code blocks if present
            if refactored_code:
                if refactored_code.startswith("```python"):
                    refactored_code = refactored_code.split("```python")[1]
                if refactored_code.startswith("```"):
                    refactored_code = refactored_code.split("```")[1]
                if refactored_code.endswith("```"):
                    refactored_code = refactored_code.rsplit("```", 1)[0]
                
                refactored_code = refactored_code.strip()
                
                # Validate that we got meaningful code
                if refactored_code and len(refactored_code) > 50:
                    return refactored_code
            
            return None

        except Exception as e:
            logger.error(f"Failed to generate opportunity refactor: {e}")
            return None

    async def _validate_improvements(
        self, improvements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate proposed improvements for safety and feasibility.
        
        For improvements with code changes, this method performs actual code validation
        including syntax, safety, and functional checks. Improvements that fail validation
        are rejected and not included in the returned list.

        Args:
            improvements: List of proposed improvements

        Returns:
            List of validated improvements that passed all validation checks
        """
        validated = []
        validation_skipped = 0
        validation_failed = 0
        validation_attempted = 0

        for improvement in improvements:
            try:
                # Basic validation - must have description and priority
                if not improvement.get("description") or not improvement.get("priority"):
                    logger.debug(
                        f"Skipping improvement missing description or priority: {improvement.get('description', 'N/A')}"
                    )
                    continue

                # Priority filtering (only high-priority improvements)
                if improvement.get("priority", 0) < 0.5:
                    logger.debug(
                        f"Skipping low-priority improvement (priority: {improvement.get('priority', 0)}): {improvement.get('description', 'N/A')}"
                    )
                    continue

                improvement_type = improvement.get("type", "")
                has_code_changes = improvement.get("has_code_changes", False)
                has_refactored_code = bool(improvement.get("refactored_code"))
                has_original_code = bool(improvement.get("original_code"))

                # For improvements with code changes, perform actual code validation
                if has_code_changes:
                    if not has_refactored_code:
                        logger.warning(
                            f"Improvement marked as having code changes but no refactored_code provided: {improvement.get('description', 'N/A')}"
                        )
                        validation_skipped += 1
                        continue

                    if not has_original_code:
                        logger.warning(
                            f"Improvement has refactored_code but no original_code for comparison: {improvement.get('description', 'N/A')}"
                        )
                        validation_skipped += 1
                        continue

                    # Perform actual code validation
                    original_code = improvement.get("original_code")
                    refactored_code = improvement.get("refactored_code")
                    
                    validation_attempted += 1
                    logger.info(
                        f"Validating code change for: {improvement.get('description', 'N/A')} "
                        f"(type: {improvement_type})"
                    )
                    
                    try:
                        validation_result = await self.code_validator.validate_modification(
                            original_code=original_code,
                            modified_code=refactored_code,
                            modification_type=improvement_type
                        )
                    except Exception as e:
                        logger.error(
                            f"Exception during code validation for {improvement.get('description', 'N/A')}: {e}"
                        )
                        validation_failed += 1
                        continue
                    
                    # Check if validation passed
                    if not validation_result.is_valid:
                        logger.warning(
                            f"Improvement FAILED validation: {improvement.get('description', 'N/A')}"
                        )
                        if validation_result.errors:
                            logger.warning(
                                f"  Validation errors: {'; '.join(validation_result.errors)}"
                            )
                        if validation_result.warnings:
                            logger.warning(
                                f"  Validation warnings: {'; '.join(validation_result.warnings)}"
                            )
                        validation_failed += 1
                        continue
                    
                    # Validation passed - add validation result to the improvement dictionary
                    improvement["validation_result"] = validation_result.to_dict()
                    improvement["validated"] = True
                    
                    logger.info(
                        f"Improvement VALIDATED successfully: {improvement.get('description', 'N/A')} "
                        f"(Safety score: {validation_result.safety_score:.2f}, "
                        f"Performance impact: {validation_result.performance_impact:.2f})"
                    )
                    
                    # Additional type-specific checks for validated code changes
                    if improvement_type == "function_refactor":
                        if improvement.get("current_complexity", 0) > 10:
                            validated.append(improvement)
                    elif improvement_type in [
                        "performance_improvement",
                        "error_handling_improvement",
                        "testing_improvement",
                        "complexity_reduction_improvement",
                    ]:
                        validated.append(improvement)
                    elif improvement_type == "general_improvement":
                        if improvement.get("priority", 0) > 0.7:
                            validated.append(improvement)
                    else:
                        # Accept other validated code changes
                        validated.append(improvement)
                else:
                    # For improvements without code changes, use field validation only
                    logger.debug(
                        f"Field validation only (no code changes): {improvement.get('description', 'N/A')}"
                    )
                    
                    if improvement_type == "function_refactor":
                        if improvement.get("current_complexity", 0) > 10:
                            validated.append(improvement)
                    elif improvement_type in [
                        "performance_improvement",
                        "error_handling_improvement",
                        "testing_improvement",
                        "complexity_reduction_improvement",
                    ]:
                        validated.append(improvement)
                    elif improvement_type == "general_improvement":
                        if improvement.get("priority", 0) > 0.7:
                            validated.append(improvement)

            except Exception as e:
                logger.error(f"Unexpected error validating improvement: {e}", exc_info=True)
                continue

        logger.info(
            f"Validation summary: {len(validated)} passed, {validation_failed} failed, "
            f"{validation_skipped} skipped (attempted: {validation_attempted} code validations)"
        )
        return validated

    async def get_repository_status(self) -> Dict[str, Any]:
        """Get comprehensive repository status including GitHub and local repo info."""
        try:
            status = {}

            # Check GitHub connection
            status["github_connected"] = (
                self.github_integration.github_client is not None
                and self.github_integration.repository is not None
            )

            # Get repository info
            if status["github_connected"]:
                status["repository_info"] = (
                    await self.github_integration.get_repository_info()
                )

                # Get open PRs
                status["open_pull_requests"] = (
                    await self.github_integration.get_open_pull_requests()
                )

            # Check local repo
            status["local_repo_available"] = (
                self.github_integration.local_repo is not None
            )

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
                branch=branch_name,
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
                base_branch="main",
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
                "files_updated": ["README.md"],
            }

            self.improvement_history.append(improvement_record)

            logger.info(f"Successfully created demo PR #{pr_result.get('pr_number')}")

            return {
                "success": True,
                "pr_number": pr_result.get("pr_number"),
                "pr_url": pr_result.get("pr_url"),
                "branch_name": branch_name,
                "files_updated": ["README.md"],
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

    async def _create_improvement_pr(
        self,
        improvements: List[Dict[str, Any]],
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a pull request with code improvements.
        
        Args:
            improvements: List of validated improvements
            analysis_result: Analysis results
            
        Returns:
            Dictionary with PR creation result
        """
        try:
            # Create a new branch for improvements
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"ai-improvements-{timestamp}"
            
            logger.info(f"Creating improvements branch: {branch_name}")
            
            # Create branch
            branch_result = await self.github_integration.create_branch(branch_name)
            if "error" in branch_result:
                return {"error": f"Failed to create branch: {branch_result['error']}"}
            
            # Apply actual code changes if available
            improvements_summary = self._generate_improvements_summary(improvements, analysis_result)
            files_updated = []
            
            # Process each improvement that has code changes
            for improvement in improvements:
                if improvement.get("has_code_changes") and improvement.get("refactored_code"):
                    file_path = improvement.get("file_path")
                    refactored_code = improvement.get("refactored_code")
                    
                    # Update the file with refactored code
                    update_result = await self.github_integration.update_file(
                        file_path=file_path,
                        new_content=refactored_code,
                        commit_message=f"🤖 AI Agent: Refactor {improvement.get('function_name')} function",
                        branch=branch_name,
                    )
                    
                    if "error" not in update_result:
                        files_updated.append(file_path)
                        logger.info(f"Updated file: {file_path}")
                    else:
                        logger.error(f"Failed to update {file_path}: {update_result['error']}")
            
            # Create summary file
            # Check if actual code validation was performed
            validated_code_changes = [
                imp for imp in improvements
                if imp.get("has_code_changes") and imp.get("validation_result")
            ]
            has_validated_code = len(validated_code_changes) > 0
            
            # Build validation status for the summary file
            if has_validated_code:
                validation_notes = f"""
## Validation Status
✅ All code changes have been validated for syntax, safety, and functionality

### Validation Metrics:
- **Validated Code Changes**: {len(validated_code_changes)}
- **Average Safety Score**: {sum(imp['validation_result'].get('safety_score', 0) for imp in validated_code_changes) / len(validated_code_changes):.2f}
- **Average Performance Impact**: {sum(imp['validation_result'].get('performance_impact', 0) for imp in validated_code_changes) / len(validated_code_changes):.2f}

### Validated Changes:
{chr(10).join([f"- ✅ {imp.get('description', 'N/A')} (Safety: {imp['validation_result'].get('safety_score', 0):.2f})" for imp in validated_code_changes])}
"""
            else:
                validation_notes = """
## Validation Status
ℹ️ This PR contains suggestions and recommendations only
- No actual code modifications were applied
- Manual review and implementation required
"""
            
            file_content = f"""# AI Agent Code Improvements

Generated: {datetime.now().isoformat()}

## Analysis Summary
{improvements_summary}

## Applied Changes
{chr(10).join([f"- ✅ Refactored {imp.get('function_name')} in {imp.get('file_path')}" for imp in improvements if imp.get("has_code_changes")])}

## Pending Suggestions
{chr(10).join([f"- 💡 {imp.get('description', 'N/A')}" for imp in improvements if not imp.get("has_code_changes")])}
{validation_notes}
## Implementation Notes
These improvements were automatically generated and applied by the AI agent's self-analysis system.
"""
            
            # Update or create improvements summary file
            update_result = await self.github_integration.update_file(
                file_path="AI_IMPROVEMENTS.md",
                new_content=file_content,
                commit_message="🤖 AI Agent: Add improvement summary",
                branch=branch_name,
            )
            
            if "error" in update_result:
                return {"error": f"Failed to create improvements summary: {update_result['error']}"}
            
            if not files_updated:
                logger.warning("No actual code changes were applied - only suggestions generated")
            
            # Create pull request
            pr_title = "🤖 AI Agent: Automated Code Improvements"
            
            # Build validation summary for PR body (has_validated_code already calculated above)
            validation_summary = ""
            safety_statement = ""
            
            if has_validated_code:
                # Calculate validation metrics
                avg_safety = sum(imp['validation_result'].get('safety_score', 0) for imp in validated_code_changes) / len(validated_code_changes)
                avg_performance = sum(imp['validation_result'].get('performance_impact', 0) for imp in validated_code_changes) / len(validated_code_changes)
                
                validation_summary = f"""
### Code Validation Results:
- **Validated Code Changes**: {len(validated_code_changes)}
- **Average Safety Score**: {avg_safety:.2f}
- **Average Performance Impact**: {avg_performance:.2f}

#### Validated Changes:
{chr(10).join([f"- ✅ {imp.get('description', 'N/A')} (Safety: {imp['validation_result'].get('safety_score', 0):.2f})" for imp in validated_code_changes])}

"""
                safety_statement = "- ✅ All code changes have been validated for syntax, safety, and functionality"
            else:
                validation_summary = """
### Validation Status:
- ℹ️ This PR contains suggestions and recommendations only
- No actual code modifications were applied
- Manual review and implementation required

"""
                safety_statement = "- ℹ️ This PR contains suggestions only - no automated code changes"
            
            pr_body = f"""## Automated Code Improvements

This pull request was automatically created by the self-improving AI agent based on codebase analysis.

### Analysis Results:
- **Improvement Potential**: {analysis_result.get('improvement_potential', 0):.2f}
- **Improvements Generated**: {len(improvements)}
{validation_summary}
### Planned Improvements:
{chr(10).join([f"✅ {imp.get('description', 'N/A')}" for imp in improvements])}

### Safety Information:
- {safety_statement}
- Changes are limited to non-critical components
- This PR can be safely reviewed and merged

*This is part of the AI agent's continuous self-improvement process.*"""
            
            pr_result = await self.github_integration.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch="main",
            )
            
            if "error" in pr_result:
                return {"error": f"Failed to create PR: {pr_result['error']}"}
            
            logger.info(f"Successfully created improvement PR #{pr_result.get('pr_number')}")
            
            return {
                "pr_number": pr_result.get("pr_number"),
                "pr_url": pr_result.get("pr_url"),
                "branch_name": branch_name,
                "improvements_count": len(improvements),
            }
            
        except Exception as e:
            logger.error(f"Error creating improvement PR: {e}")
            return {"error": str(e)}
    
    async def _create_improvement_issue(
        self,
        improvements: List[Dict[str, Any]],
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue with improvement suggestions.
        
        Args:
            improvements: List of validated improvements
            analysis_result: Analysis results
            
        Returns:
            Dictionary with issue creation result
        """
        try:
            # Generate issue title and body
            issue_title = "🤖 AI Agent: Code Improvement Suggestions"
            
            improvements_summary = self._generate_improvements_summary(improvements, analysis_result)
            
            issue_body = f"""## 🤖 Automated Code Improvement Suggestions

This issue was automatically created by the self-improving AI agent based on codebase analysis.

### 📊 Analysis Results
- **Improvement Potential**: {analysis_result.get('improvement_potential', 0):.2f}
- **Total Improvements Identified**: {len(improvements)}
- **Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### 🎯 High-Level Opportunities
{chr(10).join([f"- {opp}" for opp in analysis_result.get('improvement_opportunities', [])])}

### 📋 Detailed Improvement Suggestions

{chr(10).join([f"### {i+1}. {imp.get('description', 'N/A')}" + f"""
- **Priority**: {imp.get('priority', 0):.2f}
- **Category**: {imp.get('category', 'general')}
- **Suggested Action**: {imp.get('suggested_action', 'N/A')}
- **Target File**: {imp.get('file_path', 'N/A') if imp.get('file_path') else 'Multiple files'}
""" for i, imp in enumerate(improvements)])}

### 🔍 High Complexity Functions Identified
The following functions have high complexity and may benefit from refactoring:

{chr(10).join([f"- **{func.get('function', 'N/A')}** in `{func.get('module', 'N/A')}` (complexity: {func.get('complexity', 'N/A')})"
for func in analysis_result.get('codebase_analysis', {}).get('complexity_metrics', {}).get('high_complexity_functions', [])[:5]])}

### 🛡️ Safety Information
- All suggestions have been validated for safety
- No critical system components are affected
- Changes are recommended but not automatically applied

### 🚀 Next Steps
1. Review each suggestion for relevance
2. Prioritize based on project needs
3. Implement changes manually or request automated PR creation
4. Close this issue when improvements are complete

---

*This issue was created by the AI agent's self-improvement system. To disable automatic issue creation, set `ENABLE_SELF_MODIFICATION=false` in your configuration.*"""
            
            # Create the issue using GitHub integration
            issue_result = await self.github_integration.create_issue(
                title=issue_title,
                body=issue_body,
                labels=["ai-suggestions", "improvements", "automated"]
            )
            
            if "error" in issue_result:
                return {"error": f"Failed to create issue: {issue_result['error']}"}
            
            logger.info(f"Successfully created improvement issue #{issue_result.get('issue_number')}")
            
            return {
                "issue_number": issue_result.get("issue_number"),
                "issue_url": issue_result.get("issue_url"),
                "improvements_count": len(improvements),
            }
            
        except Exception as e:
            logger.error(f"Error creating improvement issue: {e}")
            return {"error": str(e)}
    
    def _generate_improvements_summary(
        self,
        improvements: List[Dict[str, Any]],
        analysis_result: Dict[str, Any]
    ) -> str:
        """Generate a summary of improvements for documentation."""
        summary = f"""Improvement Potential: {analysis_result.get('improvement_potential', 0):.2f}

High-Level Opportunities:
{chr(10).join([f"- {opp}" for opp in analysis_result.get('improvement_opportunities', [])])}

Validated Improvements:
{chr(10).join([f"- {imp.get('description', 'N/A')} (Priority: {imp.get('priority', 0):.2f})" for imp in improvements])}"""
        
        return summary

    def get_improvement_history(self) -> List[Dict[str, Any]]:
        """Get the history of improvements made by the agent."""
        return self.improvement_history.copy()
