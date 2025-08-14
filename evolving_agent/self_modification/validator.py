"""
Code validation system for self-modifications.
"""

import ast
import importlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class ValidationResult:
    """Result of code validation."""
    
    def __init__(
        self,
        is_valid: bool,
        errors: List[str] = None,
        warnings: List[str] = None,
        performance_impact: Optional[float] = None,
        safety_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.performance_impact = performance_impact
        self.safety_score = safety_score
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "performance_impact": self.performance_impact,
            "safety_score": self.safety_score,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class CodeValidator:
    """Validates code modifications for safety and correctness."""
    
    def __init__(self):
        self.validation_history: List[ValidationResult] = []
        self.safety_rules = self._load_safety_rules()
        self.performance_benchmarks: Dict[str, float] = {}
    
    def _load_safety_rules(self) -> Dict[str, Any]:
        """Load safety rules for code validation."""
        return {
            "forbidden_imports": [
                "os.system", "subprocess.call", "eval", "exec",
                "shutil.rmtree", "__import__"
            ],
            "forbidden_functions": [
                "delattr", "setattr", "globals", "locals"
            ],
            "required_patterns": [
                "error_handling",  # Functions should have error handling
                "logging",         # Important operations should be logged
                "type_hints"       # Functions should have type hints
            ],
            "max_complexity": 15,  # Maximum cyclomatic complexity
            "max_function_length": 100,  # Maximum lines per function
            "required_docstrings": True
        }
    
    async def validate_modification(
        self,
        original_code: str,
        modified_code: str,
        modification_type: str = "general"
    ) -> ValidationResult:
        """Validate a code modification."""
        try:
            logger.info(f"Validating {modification_type} modification...")
            
            errors = []
            warnings = []
            
            # Step 1: Syntax validation
            syntax_valid, syntax_errors = self._validate_syntax(modified_code)
            if not syntax_valid:
                errors.extend(syntax_errors)
                return ValidationResult(False, errors, warnings)
            
            # Step 2: Safety validation
            safety_valid, safety_issues = await self._validate_safety(modified_code)
            if not safety_valid:
                errors.extend(safety_issues["errors"])
                warnings.extend(safety_issues["warnings"])
            
            # Step 3: Structure validation
            structure_valid, structure_issues = self._validate_structure(modified_code)
            if not structure_valid:
                warnings.extend(structure_issues)
            
            # Step 4: Performance validation
            performance_impact = await self._estimate_performance_impact(
                original_code, modified_code
            )
            
            # Step 5: Functional validation
            functional_valid, functional_errors = await self._validate_functionality(
                modified_code, modification_type
            )
            if not functional_valid:
                errors.extend(functional_errors)
            
            # Calculate safety score
            safety_score = self._calculate_safety_score(modified_code, safety_issues)
            
            # Determine overall validity
            is_valid = (
                syntax_valid and 
                safety_valid and 
                functional_valid and
                len(errors) == 0 and
                safety_score >= 0.7
            )
            
            result = ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                performance_impact=performance_impact,
                safety_score=safety_score,
                metadata={
                    "modification_type": modification_type,
                    "code_length": len(modified_code),
                    "validation_timestamp": datetime.now().isoformat()
                }
            )
            
            self.validation_history.append(result)
            
            logger.info(f"Validation completed. Valid: {is_valid}, Safety: {safety_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationResult(False, [f"Validation error: {str(e)}"])
    
    def _validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Validate Python syntax."""
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            return False, [f"Syntax error: {str(e)}"]
        except Exception as e:
            return False, [f"Parse error: {str(e)}"]
    
    async def _validate_safety(self, code: str) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate code safety."""
        try:
            errors = []
            warnings = []
            
            # Check for forbidden imports
            for forbidden in self.safety_rules["forbidden_imports"]:
                if forbidden in code:
                    errors.append(f"Forbidden import/function detected: {forbidden}")
            
            # Check for forbidden function calls
            for forbidden in self.safety_rules["forbidden_functions"]:
                if f"{forbidden}(" in code:
                    warnings.append(f"Potentially unsafe function: {forbidden}")
            
            # Check for eval/exec patterns
            if "eval(" in code or "exec(" in code:
                errors.append("Dynamic code execution (eval/exec) is forbidden")
            
            # Check for file system operations
            if any(pattern in code for pattern in ["open(", "with open", "file("]):
                if "w" in code or "a" in code:
                    warnings.append("File write operations detected - ensure proper permissions")
            
            # Check for network operations
            if any(pattern in code for pattern in ["urllib", "requests", "socket", "http"]):
                warnings.append("Network operations detected - ensure security")
            
            # Parse AST for deeper analysis
            try:
                tree = ast.parse(code)
                ast_errors, ast_warnings = self._analyze_ast_safety(tree)
                errors.extend(ast_errors)
                warnings.extend(ast_warnings)
            except:
                warnings.append("Could not perform deep AST safety analysis")
            
            return len(errors) == 0, {"errors": errors, "warnings": warnings}
            
        except Exception as e:
            logger.error(f"Safety validation failed: {e}")
            return False, {"errors": [f"Safety validation error: {str(e)}"], "warnings": []}
    
    def _analyze_ast_safety(self, tree: ast.AST) -> Tuple[List[str], List[str]]:
        """Analyze AST for safety issues."""
        errors = []
        warnings = []
        
        try:
            for node in ast.walk(tree):
                # Check for dangerous attribute access
                if isinstance(node, ast.Attribute):
                    if node.attr in ["__globals__", "__locals__", "__code__"]:
                        errors.append(f"Dangerous attribute access: {node.attr}")
                
                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.safety_rules["forbidden_functions"]:
                            errors.append(f"Forbidden function call: {node.func.id}")
                    elif isinstance(node.func, ast.Attribute):
                        if node.func.attr in ["system", "popen", "spawn"]:
                            errors.append(f"System call detected: {node.func.attr}")
                
                # Check for imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_names = []
                    if isinstance(node, ast.Import):
                        module_names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        module_names = [node.module] if node.module else []
                    
                    for module_name in module_names:
                        if module_name in ["os", "sys", "subprocess"]:
                            warnings.append(f"System module import: {module_name}")
            
            return errors, warnings
            
        except Exception as e:
            return [f"AST analysis error: {str(e)}"], []
    
    def _validate_structure(self, code: str) -> Tuple[bool, List[str]]:
        """Validate code structure and quality."""
        try:
            warnings = []
            
            # Parse code
            tree = ast.parse(code)
            
            # Check complexity
            complexity_issues = self._check_complexity(tree)
            warnings.extend(complexity_issues)
            
            # Check documentation
            doc_issues = self._check_documentation(tree)
            warnings.extend(doc_issues)
            
            # Check type hints
            type_hint_issues = self._check_type_hints(tree)
            warnings.extend(type_hint_issues)
            
            # Check error handling
            error_handling_issues = self._check_error_handling(tree)
            warnings.extend(error_handling_issues)
            
            return True, warnings
            
        except Exception as e:
            return False, [f"Structure validation error: {str(e)}"]
    
    def _check_complexity(self, tree: ast.AST) -> List[str]:
        """Check cyclomatic complexity."""
        issues = []
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    complexity = self._calculate_complexity(node)
                    if complexity > self.safety_rules["max_complexity"]:
                        issues.append(
                            f"Function '{node.name}' has high complexity: {complexity}"
                        )
                    
                    # Check function length
                    if hasattr(node, 'end_lineno') and node.end_lineno:
                        length = node.end_lineno - node.lineno
                        if length > self.safety_rules["max_function_length"]:
                            issues.append(
                                f"Function '{node.name}' is too long: {length} lines"
                            )
            
            return issues
            
        except Exception as e:
            return [f"Complexity check error: {str(e)}"]
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
            elif isinstance(child, ast.Try):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
        
        return complexity
    
    def _check_documentation(self, tree: ast.AST) -> List[str]:
        """Check for proper documentation."""
        issues = []
        
        if not self.safety_rules["required_docstrings"]:
            return issues
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        issues.append(f"{type(node).__name__} '{node.name}' missing docstring")
            
            return issues
            
        except Exception as e:
            return [f"Documentation check error: {str(e)}"]
    
    def _check_type_hints(self, tree: ast.AST) -> List[str]:
        """Check for type hints."""
        issues = []
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check return type hint
                    if not node.returns and node.name != "__init__":
                        issues.append(f"Function '{node.name}' missing return type hint")
                    
                    # Check parameter type hints
                    for arg in node.args.args:
                        if not arg.annotation and arg.arg != "self":
                            issues.append(f"Parameter '{arg.arg}' in '{node.name}' missing type hint")
            
            return issues
            
        except Exception as e:
            return [f"Type hint check error: {str(e)}"]
    
    def _check_error_handling(self, tree: ast.AST) -> List[str]:
        """Check for proper error handling."""
        issues = []
        
        try:
            functions_with_try = set()
            all_functions = set()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    all_functions.add(node.name)
                elif isinstance(node, ast.Try):
                    # Find parent function
                    for parent in ast.walk(tree):
                        if (isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                            any(child is node for child in ast.walk(parent))):
                            functions_with_try.add(parent.name)
                            break
            
            # Check if critical functions have error handling
            functions_without_try = all_functions - functions_with_try
            for func_name in functions_without_try:
                if any(keyword in func_name.lower() for keyword in 
                      ["save", "load", "delete", "modify", "update", "create"]):
                    issues.append(f"Critical function '{func_name}' lacks error handling")
            
            return issues
            
        except Exception as e:
            return [f"Error handling check error: {str(e)}"]
    
    async def _estimate_performance_impact(
        self,
        original_code: str,
        modified_code: str
    ) -> float:
        """Estimate performance impact of modification."""
        try:
            # Simple metrics: line count, complexity changes
            original_lines = len(original_code.splitlines())
            modified_lines = len(modified_code.splitlines())
            
            line_impact = (modified_lines - original_lines) / max(original_lines, 1)
            
            # Estimate based on added constructs
            performance_keywords = ["for", "while", "if", "async", "await"]
            original_keywords = sum(original_code.count(kw) for kw in performance_keywords)
            modified_keywords = sum(modified_code.count(kw) for kw in performance_keywords)
            
            keyword_impact = (modified_keywords - original_keywords) / max(original_keywords, 1)
            
            # Combine impacts (negative = improvement, positive = degradation)
            total_impact = (line_impact * 0.3) + (keyword_impact * 0.7)
            
            return max(-1.0, min(1.0, total_impact))
            
        except Exception as e:
            logger.error(f"Performance estimation failed: {e}")
            return 0.0
    
    async def _validate_functionality(
        self,
        code: str,
        modification_type: str
    ) -> Tuple[bool, List[str]]:
        """Validate that the code functions correctly."""
        try:
            errors = []
            
            # Create temporary file for testing
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name
            
            try:
                # Try to compile the code
                with open(temp_file_path, 'r') as f:
                    code_content = f.read()
                    compile(code_content, temp_file_path, 'exec')
                
                # Try to import if it's a module
                if modification_type == "module":
                    spec = importlib.util.spec_from_file_location("test_module", temp_file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                
            except ImportError as e:
                errors.append(f"Import error: {str(e)}")
            except Exception as e:
                errors.append(f"Execution error: {str(e)}")
            finally:
                # Clean up
                try:
                    Path(temp_file_path).unlink()
                except:
                    pass
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Functional validation failed: {e}")
            return False, [f"Functional validation error: {str(e)}"]
    
    def _calculate_safety_score(
        self,
        code: str,
        safety_issues: Dict[str, List[str]]
    ) -> float:
        """Calculate a safety score for the code."""
        try:
            base_score = 1.0
            
            # Deduct for errors (major impact)
            error_penalty = len(safety_issues.get("errors", [])) * 0.3
            
            # Deduct for warnings (minor impact)
            warning_penalty = len(safety_issues.get("warnings", [])) * 0.1
            
            # Bonus for good practices
            bonus = 0.0
            if 'try:' in code and 'except' in code:
                bonus += 0.1  # Has error handling
            if '"""' in code or "'''" in code:
                bonus += 0.05  # Has documentation
            if 'logger' in code or 'logging' in code:
                bonus += 0.05  # Has logging
            
            final_score = base_score - error_penalty - warning_penalty + bonus
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logger.error(f"Safety score calculation failed: {e}")
            return 0.0
    
    async def validate_integration(
        self,
        modified_files: List[str],
        test_scenarios: Optional[List[str]] = None
    ) -> ValidationResult:
        """Validate integration of multiple modified files."""
        try:
            logger.info("Validating integration of modified files...")
            
            errors = []
            warnings = []
            
            # Check import dependencies
            import_issues = self._check_import_dependencies(modified_files)
            warnings.extend(import_issues)
            
            # Run integration tests if provided
            if test_scenarios:
                test_results = await self._run_integration_tests(test_scenarios)
                if not test_results["passed"]:
                    errors.extend(test_results["errors"])
            
            # Check for breaking changes
            breaking_changes = await self._detect_breaking_changes(modified_files)
            if breaking_changes:
                warnings.extend(breaking_changes)
            
            is_valid = len(errors) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                metadata={
                    "integration_test": True,
                    "modified_files": len(modified_files),
                    "test_scenarios": len(test_scenarios) if test_scenarios else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Integration validation failed: {e}")
            return ValidationResult(False, [f"Integration validation error: {str(e)}"])
    
    def _check_import_dependencies(self, modified_files: List[str]) -> List[str]:
        """Check for import dependency issues."""
        issues = []
        
        try:
            # This is a simplified check - in practice, you'd want more sophisticated analysis
            for file_path in modified_files:
                if Path(file_path).exists():
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for relative imports that might break
                    if 'from .' in content or 'from ..' in content:
                        issues.append(f"Relative imports in {file_path} may need review")
            
            return issues
            
        except Exception as e:
            return [f"Import dependency check error: {str(e)}"]
    
    async def _run_integration_tests(self, test_scenarios: List[str]) -> Dict[str, Any]:
        """Run integration test scenarios."""
        try:
            results = {"passed": True, "errors": [], "test_count": len(test_scenarios)}
            
            for scenario in test_scenarios:
                try:
                    # This would run actual test scenarios
                    # For now, just validate they're properly formatted
                    if not scenario or len(scenario.strip()) == 0:
                        results["errors"].append("Empty test scenario")
                        results["passed"] = False
                except Exception as e:
                    results["errors"].append(f"Test scenario error: {str(e)}")
                    results["passed"] = False
            
            return results
            
        except Exception as e:
            return {"passed": False, "errors": [f"Integration test error: {str(e)}"], "test_count": 0}
    
    async def _detect_breaking_changes(self, modified_files: List[str]) -> List[str]:
        """Detect potential breaking changes."""
        warnings = []
        
        try:
            for file_path in modified_files:
                if Path(file_path).exists():
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for signature changes in public methods
                    if 'def ' in content and '__init__' in content:
                        warnings.append(f"Constructor modification in {file_path} may break compatibility")
                    
                    # Check for removed public methods/classes
                    # This is simplified - real implementation would compare with backup
                    
            return warnings
            
        except Exception as e:
            return [f"Breaking change detection error: {str(e)}"]
    
    def get_validation_history(self) -> List[Dict[str, Any]]:
        """Get validation history."""
        return [result.to_dict() for result in self.validation_history]
    
    def get_safety_rules(self) -> Dict[str, Any]:
        """Get current safety rules."""
        return self.safety_rules.copy()
    
    def update_safety_rules(self, new_rules: Dict[str, Any]):
        """Update safety rules."""
        self.safety_rules.update(new_rules)
        logger.info("Safety rules updated")
