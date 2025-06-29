"""
Code analysis system for self-improvement.
"""

import ast
import inspect
import importlib
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

from ..utils.config import config
from ..utils.logging import setup_logger
from ..utils.llm_interface import llm_manager

logger = setup_logger(__name__)


class CodeAnalyzer:
    """Analyzes code for potential improvements and modifications."""
    
    def __init__(self):
        self.analysis_history: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, Any] = {}
        self.code_cache: Dict[str, str] = {}
    
    async def analyze_performance_patterns(
        self,
        evaluation_insights: Dict[str, Any],
        knowledge_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze code performance patterns for improvement opportunities."""
        try:
            logger.info("Analyzing code performance patterns...")
            
            # Get current codebase analysis
            codebase_analysis = await self._analyze_current_codebase()
            
            # Analyze evaluation patterns
            evaluation_analysis = self._analyze_evaluation_patterns(evaluation_insights)
            
            # Identify improvement opportunities
            improvement_opportunities = await self._identify_improvement_opportunities(
                codebase_analysis, evaluation_analysis, knowledge_suggestions
            )
            
            # Calculate improvement potential
            improvement_potential = self._calculate_improvement_potential(
                improvement_opportunities, evaluation_insights
            )
            
            analysis_result = {
                "timestamp": datetime.now().isoformat(),
                "codebase_analysis": codebase_analysis,
                "evaluation_analysis": evaluation_analysis,
                "improvement_opportunities": improvement_opportunities,
                "improvement_potential": improvement_potential,
                "recommendations": await self._generate_recommendations(improvement_opportunities)
            }
            
            # Store analysis
            self.analysis_history.append(analysis_result)
            
            logger.info(f"Code analysis completed. Improvement potential: {improvement_potential:.2f}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze performance patterns: {e}")
            return {"error": str(e), "improvement_potential": 0.0}
    
    async def _analyze_current_codebase(self) -> Dict[str, Any]:
        """Analyze the current codebase structure and patterns."""
        try:
            project_root = Path(__file__).parent.parent
            analysis = {
                "modules": {},
                "complexity_metrics": {},
                "dependency_analysis": {},
                "potential_bottlenecks": []
            }
            
            # Analyze Python files in the project
            for py_file in project_root.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        code_content = f.read()
                        self.code_cache[str(py_file)] = code_content
                    
                    # Parse AST
                    tree = ast.parse(code_content)
                    module_analysis = self._analyze_module(tree, py_file)
                    analysis["modules"][str(py_file.relative_to(project_root))] = module_analysis
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze {py_file}: {e}")
            
            # Calculate overall complexity
            analysis["complexity_metrics"] = self._calculate_complexity_metrics(analysis["modules"])
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze codebase: {e}")
            return {}
    
    def _analyze_module(self, tree: ast.AST, file_path: Path) -> Dict[str, Any]:
        """Analyze a single Python module."""
        try:
            analysis = {
                "functions": [],
                "classes": [],
                "complexity_score": 0,
                "lines_of_code": 0,
                "imports": [],
                "async_functions": 0,
                "error_handling": 0
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_analysis = self._analyze_function(node)
                    analysis["functions"].append(func_analysis)
                    analysis["complexity_score"] += func_analysis.get("complexity", 0)
                    if func_analysis.get("is_async", False):
                        analysis["async_functions"] += 1
                
                elif isinstance(node, ast.AsyncFunctionDef):
                    func_analysis = self._analyze_function(node)
                    func_analysis["is_async"] = True
                    analysis["functions"].append(func_analysis)
                    analysis["complexity_score"] += func_analysis.get("complexity", 0)
                    analysis["async_functions"] += 1
                
                elif isinstance(node, ast.ClassDef):
                    class_analysis = self._analyze_class(node)
                    analysis["classes"].append(class_analysis)
                    analysis["complexity_score"] += class_analysis.get("complexity", 0)
                
                elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    analysis["imports"].append(ast.unparse(node))
                
                elif isinstance(node, ast.Try):
                    analysis["error_handling"] += 1
            
            # Count lines of code
            if str(file_path) in self.code_cache:
                analysis["lines_of_code"] = len(self.code_cache[str(file_path)].splitlines())
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze module {file_path}: {e}")
            return {}
    
    def _analyze_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Analyze a function for complexity and patterns."""
        try:
            analysis = {
                "name": node.name,
                "lines": node.end_lineno - node.lineno + 1 if node.end_lineno else 1,
                "complexity": 1,  # Base complexity
                "parameters": len(node.args.args),
                "has_docstring": ast.get_docstring(node) is not None,
                "has_type_hints": False,
                "nested_loops": 0,
                "conditional_complexity": 0,
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            }
            
            # Check for type hints
            if node.returns or any(arg.annotation for arg in node.args.args):
                analysis["has_type_hints"] = True
            
            # Calculate cyclomatic complexity
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    analysis["complexity"] += 1
                    if isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                        analysis["nested_loops"] += 1
                    else:
                        analysis["conditional_complexity"] += 1
                elif isinstance(child, (ast.And, ast.Or)):
                    analysis["complexity"] += 1
                elif isinstance(child, ast.Try):
                    analysis["complexity"] += 1
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze function {node.name}: {e}")
            return {"name": node.name, "complexity": 1}
    
    def _analyze_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Analyze a class for complexity and patterns."""
        try:
            analysis = {
                "name": node.name,
                "methods": [],
                "complexity": 0,
                "has_docstring": ast.get_docstring(node) is not None,
                "inheritance": len(node.bases),
                "async_methods": 0
            }
            
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_analysis = self._analyze_function(item)
                    analysis["methods"].append(method_analysis)
                    analysis["complexity"] += method_analysis.get("complexity", 0)
                    if method_analysis.get("is_async", False):
                        analysis["async_methods"] += 1
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze class {node.name}: {e}")
            return {"name": node.name, "complexity": 0}
    
    def _calculate_complexity_metrics(self, modules: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall complexity metrics."""
        try:
            total_complexity = 0
            total_functions = 0
            total_classes = 0
            total_lines = 0
            high_complexity_functions = []
            
            for module_path, module_data in modules.items():
                total_complexity += module_data.get("complexity_score", 0)
                total_functions += len(module_data.get("functions", []))
                total_classes += len(module_data.get("classes", []))
                total_lines += module_data.get("lines_of_code", 0)
                
                # Identify high complexity functions
                for func in module_data.get("functions", []):
                    if func.get("complexity", 0) > 10:  # High complexity threshold
                        high_complexity_functions.append({
                            "module": module_path,
                            "function": func["name"],
                            "complexity": func["complexity"]
                        })
            
            return {
                "total_complexity": total_complexity,
                "average_complexity": total_complexity / max(total_functions, 1),
                "total_functions": total_functions,
                "total_classes": total_classes,
                "total_lines": total_lines,
                "high_complexity_functions": high_complexity_functions
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate complexity metrics: {e}")
            return {}
    
    def _analyze_evaluation_patterns(self, evaluation_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze patterns in evaluation results."""
        try:
            analysis = {
                "performance_trend": evaluation_insights.get("score_trend", "stable"),
                "average_score": evaluation_insights.get("recent_average_score", 0.5),
                "confidence_level": evaluation_insights.get("confidence_level", 0.5),
                "common_weaknesses": evaluation_insights.get("common_weaknesses", []),
                "improvement_areas": []
            }
            
            # Identify improvement areas based on weaknesses
            for weakness in analysis["common_weaknesses"]:
                if "accuracy" in weakness.lower():
                    analysis["improvement_areas"].append("response_accuracy")
                elif "completeness" in weakness.lower():
                    analysis["improvement_areas"].append("response_completeness")
                elif "clarity" in weakness.lower():
                    analysis["improvement_areas"].append("response_clarity")
                elif "efficiency" in weakness.lower():
                    analysis["improvement_areas"].append("processing_efficiency")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze evaluation patterns: {e}")
            return {}
    
    async def _identify_improvement_opportunities(
        self,
        codebase_analysis: Dict[str, Any],
        evaluation_analysis: Dict[str, Any],
        knowledge_suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify specific improvement opportunities."""
        try:
            opportunities = []
            
            # Code complexity opportunities
            complexity_metrics = codebase_analysis.get("complexity_metrics", {})
            if complexity_metrics.get("average_complexity", 0) > 8:
                opportunities.append({
                    "type": "complexity_reduction",
                    "description": "High average function complexity detected",
                    "priority": 0.8,
                    "affected_functions": complexity_metrics.get("high_complexity_functions", []),
                    "suggested_action": "Refactor complex functions into smaller, more manageable pieces"
                })
            
            # Performance opportunities based on evaluation
            if evaluation_analysis.get("average_score", 1.0) < 0.7:
                opportunities.append({
                    "type": "performance_improvement",
                    "description": "Low evaluation scores indicate performance issues",
                    "priority": 0.9,
                    "improvement_areas": evaluation_analysis.get("improvement_areas", []),
                    "suggested_action": "Optimize response generation and evaluation processes"
                })
            
            # Knowledge-based opportunities
            for suggestion in knowledge_suggestions:
                if suggestion.get("priority", 0) > 0.7:
                    opportunities.append({
                        "type": "knowledge_based",
                        "description": suggestion.get("message", ""),
                        "priority": suggestion.get("priority", 0.5),
                        "suggested_action": "Implement knowledge-based improvements"
                    })
            
            # Error handling opportunities
            total_error_handling = sum(
                module.get("error_handling", 0)
                for module in codebase_analysis.get("modules", {}).values()
            )
            total_functions = complexity_metrics.get("total_functions", 1)
            
            if total_error_handling / total_functions < 0.3:  # Less than 30% functions have error handling
                opportunities.append({
                    "type": "error_handling",
                    "description": "Insufficient error handling coverage",
                    "priority": 0.7,
                    "suggested_action": "Add comprehensive error handling to critical functions"
                })
            
            # Sort by priority
            opportunities.sort(key=lambda x: x.get("priority", 0), reverse=True)
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Failed to identify improvement opportunities: {e}")
            return []
    
    def _calculate_improvement_potential(
        self,
        opportunities: List[Dict[str, Any]],
        evaluation_insights: Dict[str, Any]
    ) -> float:
        """Calculate overall improvement potential score."""
        try:
            if not opportunities:
                return 0.1  # Always some potential for improvement
            
            # Weight opportunities by priority
            weighted_score = sum(opp.get("priority", 0) for opp in opportunities) / len(opportunities)
            
            # Adjust based on current performance
            current_score = evaluation_insights.get("recent_average_score", 0.8)
            performance_gap = max(0, 1.0 - current_score)
            
            # Combine weighted opportunities with performance gap
            improvement_potential = (weighted_score * 0.6) + (performance_gap * 0.4)
            
            return min(improvement_potential, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate improvement potential: {e}")
            return 0.1
    
    async def _generate_recommendations(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate specific recommendations for code improvements."""
        try:
            if not opportunities:
                return ["No specific improvements identified at this time."]
            
            recommendations = []
            
            # Group opportunities by type
            by_type = {}
            for opp in opportunities:
                opp_type = opp.get("type", "general")
                if opp_type not in by_type:
                    by_type[opp_type] = []
                by_type[opp_type].append(opp)
            
            # Generate recommendations for each type
            for opp_type, opps in by_type.items():
                if opp_type == "complexity_reduction":
                    recommendations.append(
                        f"Refactor {len(opps)} high-complexity functions to improve maintainability"
                    )
                elif opp_type == "performance_improvement":
                    recommendations.append(
                        "Optimize response generation pipeline for better evaluation scores"
                    )
                elif opp_type == "error_handling":
                    recommendations.append(
                        "Enhance error handling coverage across the codebase"
                    )
                elif opp_type == "knowledge_based":
                    recommendations.extend([opp.get("suggested_action", "") for opp in opps])
            
            return recommendations[:5]  # Limit to top 5 recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return ["Review code for potential improvements"]
    
    async def analyze_specific_module(self, module_name: str) -> Dict[str, Any]:
        """Analyze a specific module in detail."""
        try:
            # Import and analyze the module
            module = importlib.import_module(module_name)
            
            analysis = {
                "module_name": module_name,
                "file_path": inspect.getfile(module),
                "functions": [],
                "classes": [],
                "issues": []
            }
            
            # Analyze module members
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and obj.__module__ == module_name:
                    func_analysis = await self._analyze_function_runtime(obj)
                    analysis["functions"].append(func_analysis)
                elif inspect.isclass(obj) and obj.__module__ == module_name:
                    class_analysis = await self._analyze_class_runtime(obj)
                    analysis["classes"].append(class_analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze module {module_name}: {e}")
            return {"error": str(e)}
    
    async def _analyze_function_runtime(self, func) -> Dict[str, Any]:
        """Analyze function at runtime."""
        try:
            analysis = {
                "name": func.__name__,
                "docstring": func.__doc__ or "",
                "signature": str(inspect.signature(func)),
                "is_async": inspect.iscoroutinefunction(func),
                "source_available": True
            }
            
            try:
                analysis["source_lines"] = len(inspect.getsourcelines(func)[0])
            except:
                analysis["source_available"] = False
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze function {func.__name__}: {e}")
            return {"name": func.__name__, "error": str(e)}
    
    async def _analyze_class_runtime(self, cls) -> Dict[str, Any]:
        """Analyze class at runtime."""
        try:
            analysis = {
                "name": cls.__name__,
                "docstring": cls.__doc__ or "",
                "methods": [],
                "inheritance": [base.__name__ for base in cls.__bases__]
            }
            
            # Analyze methods
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                method_analysis = await self._analyze_function_runtime(method)
                analysis["methods"].append(method_analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze class {cls.__name__}: {e}")
            return {"name": cls.__name__, "error": str(e)}
    
    def get_analysis_history(self) -> List[Dict[str, Any]]:
        """Get the history of code analyses."""
        return self.analysis_history.copy()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self.performance_metrics.copy()
    
    async def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a specific file for improvement opportunities.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Dictionary containing analysis results and suggestions
        """
        try:
            logger.info(f"Analyzing file: {file_path}")
            
            if not Path(file_path).exists():
                return {
                    "file_path": file_path,
                    "error": "File not found",
                    "suggestions": [],
                    "metrics": {}
                }
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic metrics
            lines = content.split('\n')
            metrics = {
                "lines_of_code": len([line for line in lines if line.strip() and not line.strip().startswith('#')]),
                "total_lines": len(lines),
                "functions": len([line for line in lines if line.strip().startswith('def ')]),
                "classes": len([line for line in lines if line.strip().startswith('class ')]),
                "imports": len([line for line in lines if line.strip().startswith(('import ', 'from '))]),
                "complexity": self._estimate_complexity(content)
            }
            
            # Generate suggestions based on analysis
            suggestions = []
            
            # Check for long functions
            if metrics["lines_of_code"] > 200:
                suggestions.append("Consider breaking down large functions into smaller, more focused functions")
            
            # Check for missing docstrings
            if '"""' not in content and "'''" not in content:
                suggestions.append("Add comprehensive docstrings to improve code documentation")
            
            # Check for error handling
            if 'try:' not in content:
                suggestions.append("Consider adding error handling with try/except blocks")
            
            # Check for type hints
            if '-> ' not in content and 'typing' not in content:
                suggestions.append("Add type hints to improve code clarity and IDE support")
            
            # Check for async patterns
            if 'async def' in content and 'await' not in content:
                suggestions.append("Review async function implementations for proper await usage")
            
            # Check for logging
            if 'logger' not in content and 'logging' not in content:
                suggestions.append("Add logging for better debugging and monitoring")
            
            # Performance suggestions
            if metrics["complexity"] > 10:
                suggestions.append("High complexity detected - consider refactoring for better maintainability")
            
            return {
                "file_path": file_path,
                "metrics": metrics,
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")
            return {
                "file_path": file_path,
                "error": str(e),
                "suggestions": [],
                "metrics": {}
            }
    
    def _estimate_complexity(self, content: str) -> int:
        """Estimate code complexity based on control structures."""
        complexity_keywords = ['if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except:', 'with ']
        complexity = 1  # Base complexity
        
        for keyword in complexity_keywords:
            complexity += content.count(keyword)
        
        return complexity

    async def analyze_codebase(self) -> Dict[str, Any]:
        """
        Analyze the entire codebase for improvement opportunities.
        
        Returns:
            Dictionary containing comprehensive codebase analysis
        """
        try:
            logger.info("Starting comprehensive codebase analysis...")
            
            # Core files to analyze
            core_files = [
                "evolving_agent/core/agent.py",
                "evolving_agent/core/memory.py", 
                "evolving_agent/core/evaluator.py",
                "evolving_agent/core/context_manager.py",
                "evolving_agent/utils/llm_interface.py",
                "evolving_agent/self_modification/code_analyzer.py",
                "evolving_agent/self_modification/modifier.py"
            ]
            
            file_analyses = []
            total_suggestions = 0
            total_functions = 0
            complex_functions = []
            
            for file_path in core_files:
                if Path(file_path).exists():
                    analysis = await self.analyze_file(file_path)
                    file_analyses.append(analysis)
                    total_suggestions += len(analysis.get('suggestions', []))
                    total_functions += analysis.get('metrics', {}).get('functions', 0)
                    
                    # Track complex files
                    if analysis.get('metrics', {}).get('complexity', 0) > 15:
                        complex_functions.append({
                            'file': file_path,
                            'complexity': analysis.get('metrics', {}).get('complexity', 0)
                        })
            
            return {
                "timestamp": datetime.now().isoformat(),
                "files_analyzed": len(file_analyses),
                "total_functions": total_functions,
                "total_suggestions": total_suggestions,
                "complex_functions": complex_functions,
                "improvement_opportunities": file_analyses,
                "summary": f"Analyzed {len(file_analyses)} files with {total_suggestions} improvement suggestions"
            }
            
        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "files_analyzed": 0,
                "total_suggestions": 0
            }
