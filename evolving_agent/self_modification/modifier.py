"""
Code modification engine for self-improvement.
"""

import asyncio
import difflib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from .code_analyzer import CodeAnalyzer
from .validator import CodeValidator, ValidationResult

logger = setup_logger(__name__)


class ModificationProposal:
    """Represents a proposed code modification."""
    
    def __init__(
        self,
        file_path: str,
        original_code: str,
        modified_code: str,
        modification_type: str,
        rationale: str,
        priority: float = 0.5,
        estimated_impact: Optional[float] = None
    ):
        self.id = f"mod_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(file_path) % 10000}"
        self.file_path = file_path
        self.original_code = original_code
        self.modified_code = modified_code
        self.modification_type = modification_type
        self.rationale = rationale
        self.priority = priority
        self.estimated_impact = estimated_impact
        self.created_at = datetime.now()
        self.status = "proposed"  # proposed, approved, rejected, applied
        self.validation_result: Optional[ValidationResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "modification_type": self.modification_type,
            "rationale": self.rationale,
            "priority": self.priority,
            "estimated_impact": self.estimated_impact,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "validation_result": self.validation_result.to_dict() if self.validation_result else None
        }


class CodeModifier:
    """Manages code modifications for self-improvement."""
    
    def __init__(self, analyzer: CodeAnalyzer, validator: CodeValidator):
        self.analyzer = analyzer
        self.validator = validator
        self.proposals: List[ModificationProposal] = []
        self.applied_modifications: List[Dict[str, Any]] = []
        self.backup_directory = Path(config.backup_directory)
    
    async def consider_modifications(
        self,
        code_analysis: Dict[str, Any],
        evaluation_insights: Dict[str, Any],
        knowledge_suggestions: List[Dict[str, Any]]
    ):
        """Consider and propose code modifications based on analysis."""
        try:
            logger.info("Considering code modifications...")
            
            # Generate modification proposals
            proposals = await self._generate_modification_proposals(
                code_analysis, evaluation_insights, knowledge_suggestions
            )
            
            # Validate each proposal
            for proposal in proposals:
                await self._validate_proposal(proposal)
            
            # Sort by priority and safety
            valid_proposals = [p for p in proposals if p.validation_result and p.validation_result.is_valid]
            valid_proposals.sort(key=lambda p: (p.priority, p.validation_result.safety_score), reverse=True)
            
            # Apply top proposals if conditions are met
            if valid_proposals and self._should_apply_modifications(evaluation_insights):
                await self._apply_modifications(valid_proposals[:3])  # Apply top 3
            
            # Store all proposals for review
            self.proposals.extend(proposals)
            
            logger.info(f"Generated {len(proposals)} proposals, {len(valid_proposals)} valid")
            
        except Exception as e:
            logger.error(f"Failed to consider modifications: {e}")
    
    async def _generate_modification_proposals(
        self,
        code_analysis: Dict[str, Any],
        evaluation_insights: Dict[str, Any],
        knowledge_suggestions: List[Dict[str, Any]]
    ) -> List[ModificationProposal]:
        """Generate specific modification proposals."""
        try:
            proposals = []
            
            # Get improvement opportunities from analysis
            opportunities = code_analysis.get("improvement_opportunities", [])
            
            for opportunity in opportunities:
                if opportunity.get("priority", 0) > 0.7:  # High priority only
                    proposal = await self._create_proposal_from_opportunity(opportunity, code_analysis)
                    if proposal:
                        proposals.append(proposal)
            
            # Generate proposals from evaluation insights
            if evaluation_insights.get("recent_average_score", 1.0) < 0.7:
                performance_proposals = await self._generate_performance_proposals(evaluation_insights)
                proposals.extend(performance_proposals)
            
            # Generate proposals from knowledge suggestions
            for suggestion in knowledge_suggestions:
                if suggestion.get("type") == "category_balance":
                    continue  # Skip knowledge base suggestions for code modifications
                
                knowledge_proposal = await self._create_proposal_from_knowledge(suggestion)
                if knowledge_proposal:
                    proposals.append(knowledge_proposal)
            
            return proposals
            
        except Exception as e:
            logger.error(f"Failed to generate modification proposals: {e}")
            return []
    
    async def _create_proposal_from_opportunity(
        self,
        opportunity: Dict[str, Any],
        code_analysis: Dict[str, Any]
    ) -> Optional[ModificationProposal]:
        """Create a modification proposal from an improvement opportunity."""
        try:
            opp_type = opportunity.get("type")
            
            if opp_type == "complexity_reduction":
                return await self._create_complexity_reduction_proposal(opportunity)
            elif opp_type == "error_handling":
                return await self._create_error_handling_proposal(opportunity)
            elif opp_type == "performance_improvement":
                return await self._create_performance_improvement_proposal(opportunity)
            else:
                logger.info(f"No specific handler for opportunity type: {opp_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create proposal from opportunity: {e}")
            return None
    
    async def _create_complexity_reduction_proposal(
        self,
        opportunity: Dict[str, Any]
    ) -> Optional[ModificationProposal]:
        """Create proposal for reducing code complexity."""
        try:
            affected_functions = opportunity.get("affected_functions", [])
            if not affected_functions:
                return None
            
            # Pick the highest complexity function
            target_function = max(affected_functions, key=lambda f: f.get("complexity", 0))
            module_path = target_function.get("module", "")
            function_name = target_function.get("function", "")
            
            if not module_path or not function_name:
                return None
            
            # Load the original code
            project_root = Path(__file__).parent.parent
            full_path = project_root / module_path
            
            if not full_path.exists():
                return None
            
            with open(full_path, 'r', encoding='utf-8') as f:
                original_code = f.read()
            
            # Generate refactored code
            modified_code = await self._refactor_complex_function(
                original_code, function_name, target_function.get("complexity", 0)
            )
            
            if not modified_code or modified_code == original_code:
                return None
            
            return ModificationProposal(
                file_path=str(full_path),
                original_code=original_code,
                modified_code=modified_code,
                modification_type="complexity_reduction",
                rationale=f"Reduce complexity of function '{function_name}' from {target_function.get('complexity', 0)}",
                priority=0.8,
                estimated_impact=-0.2  # Negative = improvement
            )
            
        except Exception as e:
            logger.error(f"Failed to create complexity reduction proposal: {e}")
            return None
    
    async def _refactor_complex_function(
        self,
        original_code: str,
        function_name: str,
        complexity: int
    ) -> str:
        """Refactor a complex function to reduce complexity."""
        try:
            refactor_prompt = f"""
            Refactor the following Python code to reduce the complexity of the function '{function_name}'.
            Current complexity: {complexity}
            Target: Reduce to under 10
            
            Guidelines:
            1. Break down complex functions into smaller helper functions
            2. Reduce nested conditions and loops
            3. Extract common patterns
            4. Maintain all existing functionality
            5. Keep the same function signature
            6. Add proper error handling and logging
            7. Include type hints and docstrings
            
            Original code:
            ```python
            {original_code}
            ```
            
            Return ONLY the refactored Python code, no explanations.
            """
            
            refactored_code = await llm_manager.generate_response(
                prompt=refactor_prompt,
                temperature=0.3,
                max_tokens=2000
            )
            
            # Clean up the response
            if refactored_code.startswith("```python"):
                refactored_code = refactored_code.split("```python")[1]
            if refactored_code.endswith("```"):
                refactored_code = refactored_code.rsplit("```", 1)[0]
            
            return refactored_code.strip()
            
        except Exception as e:
            logger.error(f"Failed to refactor complex function: {e}")
            return original_code
    
    async def _create_error_handling_proposal(
        self,
        opportunity: Dict[str, Any]
    ) -> Optional[ModificationProposal]:
        """Create proposal for improving error handling."""
        try:
            # Find a file that needs error handling improvement
            project_root = Path(__file__).parent.parent
            
            # Look for core modules that should have better error handling
            target_files = [
                "core/agent.py",
                "core/memory.py", 
                "utils/llm_interface.py"
            ]
            
            for target_file in target_files:
                file_path = project_root / target_file
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        original_code = f.read()
                    
                    # Check if it needs improvement
                    if self._needs_error_handling_improvement(original_code):
                        modified_code = await self._improve_error_handling(original_code)
                        
                        if modified_code and modified_code != original_code:
                            return ModificationProposal(
                                file_path=str(file_path),
                                original_code=original_code,
                                modified_code=modified_code,
                                modification_type="error_handling",
                                rationale=f"Improve error handling coverage in {target_file}",
                                priority=0.7,
                                estimated_impact=0.1  # Small positive impact for robustness
                            )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create error handling proposal: {e}")
            return None
    
    def _needs_error_handling_improvement(self, code: str) -> bool:
        """Check if code needs error handling improvement."""
        try_count = code.count("try:")
        except_count = code.count("except")
        function_count = code.count("def ") + code.count("async def ")
        
        # If less than 30% of functions have error handling
        return try_count < (function_count * 0.3) and function_count > 2
    
    async def _improve_error_handling(self, original_code: str) -> str:
        """Improve error handling in code."""
        try:
            improvement_prompt = f"""
            Improve the error handling in the following Python code:
            
            Guidelines:
            1. Add try/except blocks around risky operations
            2. Use specific exception types where appropriate
            3. Add proper logging for errors
            4. Ensure graceful degradation
            5. Don't change the core functionality
            6. Keep existing imports and structure
            
            Original code:
            ```python
            {original_code}
            ```
            
            Return ONLY the improved Python code with better error handling.
            """
            
            improved_code = await llm_manager.generate_response(
                prompt=improvement_prompt,
                temperature=0.2,
                max_tokens=2000
            )
            
            # Clean up response
            if improved_code.startswith("```python"):
                improved_code = improved_code.split("```python")[1]
            if improved_code.endswith("```"):
                improved_code = improved_code.rsplit("```", 1)[0]
            
            return improved_code.strip()
            
        except Exception as e:
            logger.error(f"Failed to improve error handling: {e}")
            return original_code
    
    async def _create_performance_improvement_proposal(
        self,
        opportunity: Dict[str, Any]
    ) -> Optional[ModificationProposal]:
        """Create proposal for performance improvement."""
        try:
            improvement_areas = opportunity.get("improvement_areas", [])
            
            if "processing_efficiency" in improvement_areas:
                # Focus on the main agent processing
                project_root = Path(__file__).parent.parent
                agent_file = project_root / "core" / "agent.py"
                
                if agent_file.exists():
                    with open(agent_file, 'r', encoding='utf-8') as f:
                        original_code = f.read()
                    
                    modified_code = await self._optimize_processing_efficiency(original_code)
                    
                    if modified_code and modified_code != original_code:
                        return ModificationProposal(
                            file_path=str(agent_file),
                            original_code=original_code,
                            modified_code=modified_code,
                            modification_type="performance_improvement",
                            rationale="Optimize processing efficiency in main agent",
                            priority=0.9,
                            estimated_impact=-0.3  # Significant improvement expected
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create performance improvement proposal: {e}")
            return None
    
    async def _optimize_processing_efficiency(self, original_code: str) -> str:
        """Optimize code for better processing efficiency."""
        try:
            optimization_prompt = f"""
            Optimize the following Python code for better processing efficiency:
            
            Focus on:
            1. Reducing redundant operations
            2. Improving async/await usage
            3. Optimizing data structures and algorithms
            4. Adding caching where appropriate
            5. Minimizing I/O operations
            6. Keep all existing functionality intact
            
            Original code:
            ```python
            {original_code}
            ```
            
            Return ONLY the optimized Python code.
            """
            
            optimized_code = await llm_manager.generate_response(
                prompt=optimization_prompt,
                temperature=0.2,
                max_tokens=2500
            )
            
            # Clean up response
            if optimized_code.startswith("```python"):
                optimized_code = optimized_code.split("```python")[1]
            if optimized_code.endswith("```"):
                optimized_code = optimized_code.rsplit("```", 1)[0]
            
            return optimized_code.strip()
            
        except Exception as e:
            logger.error(f"Failed to optimize processing efficiency: {e}")
            return original_code
    
    async def _generate_performance_proposals(
        self,
        evaluation_insights: Dict[str, Any]
    ) -> List[ModificationProposal]:
        """Generate proposals specifically for performance improvement."""
        proposals = []
        
        try:
            common_weaknesses = evaluation_insights.get("common_weaknesses", [])
            
            # Focus on the most common performance issues
            for weakness in common_weaknesses:
                if "efficiency" in weakness.lower():
                    proposal = await self._create_efficiency_improvement_proposal(weakness)
                    if proposal:
                        proposals.append(proposal)
                elif "accuracy" in weakness.lower():
                    proposal = await self._create_accuracy_improvement_proposal(weakness)
                    if proposal:
                        proposals.append(proposal)
            
            return proposals
            
        except Exception as e:
            logger.error(f"Failed to generate performance proposals: {e}")
            return []
    
    async def _create_efficiency_improvement_proposal(self, weakness: str) -> Optional[ModificationProposal]:
        """Create proposal for efficiency improvement."""
        # This would be implemented based on specific efficiency issues
        # For now, return None as this is a complex area requiring specific analysis
        return None
    
    async def _create_accuracy_improvement_proposal(self, weakness: str) -> Optional[ModificationProposal]:
        """Create proposal for accuracy improvement."""
        # This would be implemented based on specific accuracy issues
        # For now, return None as this is a complex area requiring specific analysis
        return None
    
    async def _create_proposal_from_knowledge(
        self,
        suggestion: Dict[str, Any]
    ) -> Optional[ModificationProposal]:
        """Create proposal from knowledge base suggestion."""
        # Most knowledge suggestions don't directly translate to code modifications
        # This would be implemented for specific types of knowledge that can be codified
        return None
    
    async def _validate_proposal(self, proposal: ModificationProposal):
        """Validate a modification proposal."""
        try:
            logger.info(f"Validating proposal {proposal.id}...")
            
            validation_result = await self.validator.validate_modification(
                proposal.original_code,
                proposal.modified_code,
                proposal.modification_type
            )
            
            proposal.validation_result = validation_result
            
            if validation_result.is_valid:
                proposal.status = "approved"
                logger.info(f"Proposal {proposal.id} approved with safety score {validation_result.safety_score:.2f}")
            else:
                proposal.status = "rejected"
                logger.info(f"Proposal {proposal.id} rejected: {validation_result.errors}")
            
        except Exception as e:
            logger.error(f"Failed to validate proposal {proposal.id}: {e}")
            proposal.status = "rejected"
    
    def _should_apply_modifications(self, evaluation_insights: Dict[str, Any]) -> bool:
        """Determine if modifications should be applied automatically."""
        try:
            # Only apply if performance is significantly degraded
            recent_score = evaluation_insights.get("recent_average_score", 0.8)
            confidence = evaluation_insights.get("confidence_level", 0.5)
            
            # Conservative approach: only auto-apply if score is low and confidence is high
            return recent_score < 0.6 and confidence > 0.8 and config.enable_self_modification
            
        except Exception as e:
            logger.error(f"Failed to determine if modifications should be applied: {e}")
            return False
    
    async def _apply_modifications(self, proposals: List[ModificationProposal]):
        """Apply approved modification proposals."""
        try:
            logger.info(f"Applying {len(proposals)} modifications...")
            
            # Create backups first
            await self._create_backups(proposals)
            
            # Apply modifications
            applied_count = 0
            for proposal in proposals:
                if await self._apply_single_modification(proposal):
                    applied_count += 1
                
                # Limit to prevent too many changes at once
                if applied_count >= config.max_modification_attempts:
                    break
            
            logger.info(f"Applied {applied_count} modifications successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply modifications: {e}")
    
    async def _create_backups(self, proposals: List[ModificationProposal]):
        """Create backups of files before modification."""
        try:
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for proposal in proposals:
                file_path = Path(proposal.file_path)
                if file_path.exists():
                    backup_path = self.backup_directory / f"{file_path.name}_{timestamp}.backup"
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
            
        except Exception as e:
            logger.error(f"Failed to create backups: {e}")
            raise
    
    async def _apply_single_modification(self, proposal: ModificationProposal) -> bool:
        """Apply a single modification proposal."""
        try:
            file_path = Path(proposal.file_path)
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            # Write the modified code
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(proposal.modified_code)
            
            # Validate the change if required
            if config.require_validation:
                validation = await self.validator.validate_modification(
                    proposal.original_code,
                    proposal.modified_code,
                    proposal.modification_type
                )
                
                if not validation.is_valid:
                    # Rollback
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(proposal.original_code)
                    logger.error(f"Modification validation failed, rolled back: {proposal.id}")
                    return False
            
            # Record the successful modification
            self.applied_modifications.append({
                "proposal_id": proposal.id,
                "file_path": str(file_path),
                "modification_type": proposal.modification_type,
                "timestamp": datetime.now().isoformat(),
                "rationale": proposal.rationale
            })
            
            proposal.status = "applied"
            logger.info(f"Applied modification {proposal.id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply modification {proposal.id}: {e}")
            return False
    
    def get_modification_history(self) -> Dict[str, Any]:
        """Get history of modifications."""
        return {
            "total_proposals": len(self.proposals),
            "applied_modifications": len(self.applied_modifications),
            "proposals_by_status": {
                status: len([p for p in self.proposals if p.status == status])
                for status in ["proposed", "approved", "rejected", "applied"]
            },
            "recent_modifications": self.applied_modifications[-5:],  # Last 5
            "proposals": [p.to_dict() for p in self.proposals[-10:]]  # Last 10 proposals
        }
    
    async def rollback_modification(self, modification_id: str) -> bool:
        """Rollback a specific modification."""
        try:
            # Find the modification
            modification = None
            for mod in self.applied_modifications:
                if mod.get("proposal_id") == modification_id:
                    modification = mod
                    break
            
            if not modification:
                logger.error(f"Modification not found: {modification_id}")
                return False
            
            # Find corresponding proposal
            proposal = None
            for p in self.proposals:
                if p.id == modification_id:
                    proposal = p
                    break
            
            if not proposal:
                logger.error(f"Proposal not found for modification: {modification_id}")
                return False
            
            # Restore original code
            file_path = Path(modification["file_path"])
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(proposal.original_code)
            
            # Update status
            proposal.status = "rolled_back"
            
            logger.info(f"Rolled back modification {modification_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback modification {modification_id}: {e}")
            return False
    
    def generate_diff_report(self, proposal: ModificationProposal) -> str:
        """Generate a diff report for a modification proposal."""
        try:
            original_lines = proposal.original_code.splitlines(keepends=True)
            modified_lines = proposal.modified_code.splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"{proposal.file_path} (original)",
                tofile=f"{proposal.file_path} (modified)",
                lineterm=""
            )
            
            return "\n".join(diff)
            
        except Exception as e:
            logger.error(f"Failed to generate diff report: {e}")
            return f"Diff generation failed: {str(e)}"
    
    async def apply_improvement(
        self, 
        file_path: str, 
        suggestion: str, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Apply a specific improvement suggestion to a file.
        
        Args:
            file_path: Path to the file to improve
            suggestion: The improvement suggestion to apply
            context: Context from the analysis result
            
        Returns:
            Dictionary with improvement details or None if failed
        """
        try:
            logger.info(f"Applying improvement to {file_path}: {suggestion}")
            
            # Read the current file content
            if not Path(file_path).exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Generate improved content based on the suggestion
            improved_content = await self._generate_improved_content(
                original_content, suggestion, context
            )
            
            if not improved_content or improved_content == original_content:
                logger.warning(f"No improvement generated for {file_path}")
                return None
            
            # Create a modification proposal
            proposal = ModificationProposal(
                file_path=file_path,
                original_code=original_content,
                modified_code=improved_content,
                modification_type="improvement",
                rationale=suggestion,
                priority=0.7  # Medium-high priority for explicit improvements
            )
            
            # Validate the improvement
            await self._validate_proposal(proposal)
            
            if not proposal.validation_result or not proposal.validation_result.is_valid:
                logger.warning(f"Improvement validation failed for {file_path}")
                return None
            
            return {
                "file_path": file_path,
                "content": improved_content,
                "description": suggestion,
                "original_content": original_content,
                "validation_score": proposal.validation_result.safety_score,
                "proposal_id": proposal.id
            }
            
        except Exception as e:
            logger.error(f"Failed to apply improvement to {file_path}: {e}")
            return None
    
    async def _generate_improved_content(
        self, 
        original_content: str, 
        suggestion: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Generate improved content based on a suggestion."""
        try:
            # Use LLM to generate improved code
            prompt = f"""
Please improve the following code based on this suggestion: {suggestion}

Original code:
```python
{original_content}
```

Context from analysis:
- File metrics: {context.get('metrics', {})}
- Other suggestions: {context.get('suggestions', [])}

Instructions:
1. Apply the specific suggestion while maintaining all existing functionality
2. Ensure the code remains syntactically correct and follows Python best practices
3. Add appropriate comments if adding new functionality
4. Preserve all existing imports and dependencies
5. Return only the improved code without any explanations

Improved code:
"""
            
            response = await llm_manager.generate_response(
                prompt,
                model_preference=['anthropic', 'openrouter', 'openai'],
                max_tokens=4000,
                temperature=0.3  # Lower temperature for code generation
            )
            
            if not response:
                return None
            
            # Extract code from response (remove markdown if present)
            improved_code = response.strip()
            if improved_code.startswith('```python'):
                improved_code = improved_code[9:]
            if improved_code.endswith('```'):
                improved_code = improved_code[:-3]
            
            return improved_code.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate improved content: {e}")
            return None
