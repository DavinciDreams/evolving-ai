"""
Main Self-Improving AI Agent class.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..knowledge.base import KnowledgeBase
from ..knowledge.updater import KnowledgeUpdater
from ..self_modification.code_analyzer import CodeAnalyzer
from ..self_modification.modifier import CodeModifier
from ..self_modification.validator import CodeValidator
from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from ..utils.persistent_storage import persistent_data_manager
from ..utils.error_recovery import error_recovery_manager
from .context_manager import ContextManager
from .evaluator import EvaluationResult, OutputEvaluator
from .memory import LongTermMemory, MemoryEntry
from ..integrations.web_search import WebSearchIntegration




class SelfImprovingAgent:
    """
    A sophisticated AI agent with self-improvement capabilities.

    Features:
    - Long-term memory with vector embeddings
    - Dynamic context retrieval
    - Self-evaluation and improvement
    - Knowledge base updates
    - Code self-modification
    """

    def __init__(self):
        # Logger instance for this agent
        self.logger = setup_logger(__name__)
        # Core components
        self.memory = LongTermMemory()
        self.context_manager = None  # Will be initialized after memory
        self.evaluator = OutputEvaluator()
        self.knowledge_base = KnowledgeBase()
        self.knowledge_updater = None  # Will be initialized after knowledge base
        
        # Self-modification components
        self.code_analyzer = CodeAnalyzer()
        self.code_modifier = None  # Will be initialized with proper parameters
        self.code_validator = CodeValidator()
        
        # Persistent storage
        self.data_manager = persistent_data_manager
        
        # Web search integration
        self.web_search = None  # Will be initialized if enabled
        
        # State tracking
        self.initialized = False
        self.session_id = None
        self.interaction_count = 0
        self.improvement_cycle_count = 0
        
        # Status update callbacks (for Discord/external integrations)
        self._status_callbacks: List = []
        
        # Error recovery and graceful degradation
        self.degraded_mode = False
        self.component_health: Dict[str, bool] = {}
        self.recovery_status: Dict[str, Any] = {}
        self.active_operations: Dict[str, Dict] = {}
        self.operation_checkpoints: Dict[str, Dict] = {}
        self.error_count: Dict[str, int] = {}
        self.max_error_threshold = 5

    async def initialize(self):
        """Initialize all agent components with error recovery."""
        try:
            self.logger.info("Initializing Self-Improving Agent...")

            # Ensure directories exist
            config.ensure_directories()

            # Initialize persistent data manager with error recovery
            try:
                await self.data_manager.initialize()
                self.component_health["persistent_storage"] = True
                self.logger.info("Persistent data manager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize persistent storage: {e}")
                self.component_health["persistent_storage"] = False
                self._handle_component_failure("persistent_storage", str(e))

            # Initialize core components
            try:
                await self.memory.initialize()
                self.component_health["memory"] = True
                self.logger.info("Memory system initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize memory: {e}")
                self.component_health["memory"] = False
                self._handle_component_failure("memory", str(e))
                # Continue in degraded mode
                self.degraded_mode = True

            self.context_manager = ContextManager(self.memory)
            self.logger.info("Context manager initialized")

            try:
                await self.knowledge_base.initialize()
                self.component_health["knowledge_base"] = True
                self.logger.info("Knowledge base initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize knowledge base: {e}")
                self.component_health["knowledge_base"] = False
                self._handle_component_failure("knowledge_base", str(e))

            self.knowledge_updater = KnowledgeUpdater(
                self.knowledge_base, self.memory
            )
            self.logger.info("Knowledge updater initialized")

            # Initialize self-modification components if enabled
            if config.enable_self_modification:
                try:
                    self.code_modifier = CodeModifier(
                        analyzer=self.code_analyzer, validator=self.code_validator
                    )
                    self.component_health["self_modification"] = True
                    self.logger.info("Self-modification system initialized")
                except Exception as e:
                    self.logger.error(f"Failed to initialize self-modification: {e}")
                    self.component_health["self_modification"] = False
                    self._handle_component_failure("self_modification", str(e))

            # Initialize web search integration if enabled
            if config.web_search_enabled:
                try:
                    self.web_search = WebSearchIntegration(
                        tavily_api_key=config.tavily_api_key,
                        serpapi_key=config.serpapi_key,
                        default_provider=config.web_search_default_provider,
                        max_results=config.web_search_max_results,
                    )
                    await self.web_search.initialize()
                    self.component_health["web_search"] = True
                    self.logger.info("Web search integration initialized")
                except Exception as e:
                    self.logger.error(f"Failed to initialize web search: {e}")
                    self.component_health["web_search"] = False
                    self._handle_component_failure("web_search", str(e))

            # Register health checks
            self._register_health_checks()

            # Create session
            self.session_id = (
                f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            # Store initialization memory
            try:
                if hasattr(self, "_store_session_start") and callable(getattr(self, "_store_session_start", None)):
                    await self._store_session_start()
                else:
                    if hasattr(self, "logger"):
                        self.logger.warning("Session start storage method '_store_session_start' is not implemented.")
                    else:
                        print("Session start storage method '_store_session_start' is not implemented.")
            except Exception as e:
                if hasattr(self, "logger"):
                    self.logger.error(f"Failed to store session start: {e}")
                else:
                    print(f"Failed to store session start: {e}")

            self.initialized = True
            self.logger.info("Agent initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise
    
    def _register_health_checks(self):
        """Register health checks for all components."""
        async def check_memory():
            return self.component_health.get("memory", False) and await self._check_memory_health()
        
        async def check_llm():
            try:
                providers = await llm_manager.get_available_providers()
                return len(providers) > 0
            except Exception:
                return False
        
        error_recovery_manager.register_health_check("agent_memory", check_memory)
        error_recovery_manager.register_health_check("agent_llm", check_llm)
    
    async def _check_memory_health(self) -> bool:
        """Check if memory is healthy."""
        try:
            stats = await self.memory.get_memory_stats()
            return stats is not None
        except Exception:
            return False
    
    def _handle_component_failure(self, component: str, error: str):
        """Handle component failure with graceful degradation."""
        self.error_count[component] = self.error_count.get(component, 0) + 1
        
        # Check if we should enter degraded mode
        if self.error_count[component] >= self.max_error_threshold:
            self.logger.warning(f"Component {component} has failed {self.error_count[component]} times, entering degraded mode")
            self.degraded_mode = True
            error_recovery_manager.set_degraded_mode(True)
        
        # Record error for recovery tracking
        error_recovery_manager.track_error_pattern(
            f"agent_{component}",
            type(Exception(error)).__name__,
            {"error": error, "component": component}
        )
    
    def _handle_component_recovery(self, component: str):
        """Handle component recovery."""
        self.error_count[component] = 0
        self.component_health[component] = True
        self.logger.info(f"Component {component} has recovered")
        
        # Check if we can exit degraded mode
        if all(self.component_health.values()):
            self.degraded_mode = False
            error_recovery_manager.set_degraded_mode(False)
            self.logger.info("All components recovered, exiting degraded mode")
    
    def create_operation_checkpoint(self, operation_id: str = None, data: Dict = None):
        """Create a checkpoint for a long-running operation."""
        if operation_id is None:
            operation_id = str(uuid.uuid4())
        
        checkpoint_data = {
            "operation_id": operation_id,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "interaction_count": self.interaction_count,
            "data": data or {}
        }
        
        self.operation_checkpoints[operation_id] = checkpoint_data
        error_recovery_manager.create_checkpoint(operation_id, checkpoint_data)
        
        return operation_id
    
    def get_operation_checkpoint(self, operation_id: str) -> Optional[Dict]:
        """Get a checkpoint for an operation."""
        return self.operation_checkpoints.get(operation_id)
    
    def complete_operation_checkpoint(self, operation_id: str, result: Any = None):
        """Mark an operation checkpoint as completed."""
        if operation_id in self.operation_checkpoints:
            self.operation_checkpoints[operation_id]["status"] = "completed"
            self.operation_checkpoints[operation_id]["completed_at"] = datetime.now().isoformat()
            if result is not None:
                self.operation_checkpoints[operation_id]["result"] = result
            
            error_recovery_manager.complete_checkpoint(operation_id)
    
    def fail_operation_checkpoint(self, operation_id: str, error: str):
        """Mark an operation checkpoint as failed."""
        if operation_id in self.operation_checkpoints:
            self.operation_checkpoints[operation_id]["status"] = "failed"
            self.operation_checkpoints[operation_id]["error"] = error
            self.operation_checkpoints[operation_id]["failed_at"] = datetime.now().isoformat()
            
            error_recovery_manager.fail_checkpoint(operation_id, error)
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get comprehensive recovery status."""
        return {
            "degraded_mode": self.degraded_mode,
            "component_health": self.component_health,
            "error_counts": self.error_count,
            "active_operations": len(self.active_operations),
            "active_checkpoints": len(self.operation_checkpoints),
            "session_id": self.session_id,
            "interaction_count": self.interaction_count,
            "timestamp": datetime.now().isoformat()
        }

    def register_status_callback(self, callback) -> None:
        """Register a callback for status updates.

        Args:
            callback: Async function that takes (event_type: str, data: Dict[str, Any])
        """
        self._status_callbacks.append(callback)
        self.logger.info(f"Registered status callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    async def search_web(
        self, query: str, max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search the web for information.

        Args:
            query: Search query
            max_results: Optional maximum number of results

        Returns:
            Dictionary containing search results and metadata
        """
        if not self.web_search:
            self.logger.warning("Web search not enabled")
            return {
                "query": query,
                "results": [],
                "error": "Web search not enabled",
            }

        try:
            self.logger.info(f"Searching web for: {query[:100]}")
            results = await self.web_search.search_and_summarize(
                query, max_results=max_results or config.web_search_max_results
            )

            # Store search in memory for future reference
            search_memory = MemoryEntry(
                content=f"Web search: {query}\n\nResults: {len(results.get('sources', []))} sources found",
                memory_type="web_search",
                metadata={
                    "query": query,
                    "source_count": len(results.get("sources", [])),
                    "provider": results.get("provider"),
                    "session_id": self.session_id,
                },
            )
            await self.memory.add_memory(search_memory)

            return results

        except Exception as e:
            self.logger.error(f"Web search failed: {e}")
            return {
                "query": query,
                "results": [],
                "error": str(e),
            }

    async def _notify_status(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all registered callbacks of a status event.

        Args:
            event_type: Type of status event
            data: Event data dictionary
        """
        if not self._status_callbacks:
            return

        self.logger.debug(f"Notifying {len(self._status_callbacks)} callbacks of event: {event_type}")

        for callback in self._status_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Status callback error for {event_type}: {e}")

    async def run(
        self, query: str, context_hints: Optional[List[str]] = None
    ) -> str:

        """
        Main processing method for the agent.

        Args:
            query: The user query or task
            context_hints: Optional hints for context retrieval

        Returns:
            The agent's response
        """
        if not self.initialized:
            raise RuntimeError(
                "Agent not initialized. Call initialize() first."
            )

        try:
            self.logger.info(f"Processing query: {query[:100]}...")
            self.interaction_count += 1

            # Step 1: Retrieve relevant context
            context = await self.context_manager.get_relevant_context(
                query=query, context_types=context_hints
            )

            # Step 2: Generate initial response
            initial_response = await self._generate_response(query, context)

            # Step 3: Evaluate the response (if enabled)
            if config.enable_evaluation:
                evaluation = await self.evaluator.evaluate_output(
                    query=query, output=initial_response, context=context
                )

                # Step 4: Improve response based on evaluation
                final_response = await self._improve_response(
                    query, initial_response, evaluation, context
                )
            else:
                # Skip evaluation and use initial response
                final_response = initial_response
                # Create a dummy evaluation for storage
                from .evaluator import EvaluationResult
                evaluation = EvaluationResult(
                    overall_score=0.8,
                    criteria_scores={},
                    strengths=[],
                    weaknesses=[],
                    improvement_suggestions=[],
                    feedback="Evaluation disabled",
                    confidence=1.0,
                    metadata={"evaluation_disabled": True}
                )

            # Step 5: Store interaction and learn
            interaction_id = await self.data_manager.save_interaction(
                query=query,
                response=final_response,
                evaluation_score=evaluation.overall_score,
                context_used=context,
                metadata={
                    "interaction_count": self.interaction_count,
                    "session_id": self.session_id,
                    "improvement_applied": final_response != initial_response,
                },
            )

            # Save detailed evaluation
            await self.data_manager.save_evaluation(
                interaction_id=interaction_id,
                overall_score=evaluation.overall_score,
                criteria_scores=evaluation.criteria_scores,
                feedback=evaluation.feedback,
                improvement_suggestions=evaluation.improvement_suggestions,
                confidence=evaluation.confidence,
            )

            await self._store_interaction(
                query, final_response, context, evaluation
            )

            # Step 6: Update knowledge base
            if config.auto_update_knowledge:
                knowledge_added_count = await self.knowledge_updater.update_from_interaction(
                    query, final_response, evaluation
                )

                # Notify about significant knowledge updates (only if knowledge was actually added)
                if (
                    config.discord_status_on_knowledge_update
                    and knowledge_added_count > 0
                    and evaluation.overall_score >= 0.8
                ):
                    await self._notify_status(
                        "knowledge_update",
                        {
                            "query": query[:200],
                            "evaluation_score": evaluation.overall_score,
                            "interaction_count": self.interaction_count,
                            "knowledge_added": knowledge_added_count,
                        }
                    )

            # Step 7: Consider self-modification (periodically)
            if (
                config.enable_self_modification and self.interaction_count % 10 == 0
            ):  # Every 10 interactions
                await self._consider_self_modification()

            self.logger.info(
                f"Query processed successfully. "
                f"Evaluation score: {evaluation.overall_score:.2f}"
            )
            return final_response

        except Exception as e:
            self.logger.error(f"Failed to process query: {e}")
            # Store error for learning
            # Store error for learning
            try:
                await self._store_error(query, str(e))
            except AttributeError:
                self.logger.error(f"'SelfImprovingAgent' object has no attribute '_store_error'")
            raise

    async def _generate_response(
        self, query: str, context: Dict[str, Any]
    ) -> str:

        """Generate initial response using context."""
        try:
            # Prepare context information
            context_text = self._format_context_for_prompt(context)

            # Create system prompt
            web_search_info = ""
            if self.web_search:
                web_search_info = (
                    "\n\nIMPORTANT: You have access to web search capabilities. "
                    "When you need current information, recent events, or data beyond your training, "
                    "you can indicate that you would like to search the web by mentioning it in your response. "
                    "For example: 'I should search the web for current information about [topic].' "
                    "However, the search will need to be triggered separately - you cannot directly invoke it."
                )

            system_prompt = (
                "You are a self-improving AI with the ability to analyze and modify your own code.\n"
                "You have access to long-term memory and a knowledge base, enabling you to learn from past interactions and improve over time.\n"
                f"Current session: {self.session_id}\n"
                f"Interaction count: {self.interaction_count}\n"
                f"{web_search_info}\n"
                "Use the provided context to give a comprehensive, accurate, and helpful response.\n"
                "Be specific, actionable, and consider lessons learned from previous interactions."
            )

            # Create user prompt
            user_prompt = (
                f"Query: {query}\n\n"
                f"Relevant Context:\n{context_text}\n\n"
                "Please provide a detailed response that addresses the query while "
                "incorporating relevant insights from the context."
            )

            # Generate response with fallback
            # Use generate_response and handle fallback manually
            try:
                response = await llm_manager.generate_response(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    provider=config.default_llm_provider,
                )
                error = None
            except Exception as e:
                self.logger.error(f"Primary LLM provider failed: {e}")
                # Try fallback provider if available
                fallback_provider = (
                    "openrouter"
                    if config.default_llm_provider != "openrouter"
                    else "anthropic"
                )
                try:
                    response = await llm_manager.generate_response(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                        provider=fallback_provider,
                    )
                    error = None
                except Exception as e2:
                    self.logger.error(f"Fallback LLM provider failed: {e2}")
                    response = None
                    error = str(e2)

            if response is None:
                raise Exception(f"No available LLM providers: {error}")

            return response.strip()

        except Exception as e:
            self.logger.error(f"Failed to generate response: {e}")
            raise

    def _format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context information for inclusion in prompts."""
        try:
            formatted_parts = []

            for context_type, context_data in context.items():
                if context_type == "system_state":
                    continue  # Skip system state in prompt

                formatted_parts.append(f"\n{context_type.replace('_', ' ').title()}:")

                if isinstance(context_data, dict):
                    if "summary" in context_data:
                        formatted_parts.append(f"  Summary: {context_data['summary']}")

                    if "items" in context_data:
                        for i, item in enumerate(context_data["items"][:3], 1):
                            content = item.get("content", "")[:200]
                            score = item.get("relevance_score", 0)
                            formatted_parts.append(
                                f"  {i}. {content}... (relevance: {score:.2f})"
                            )

                elif isinstance(context_data, list):
                    for i, item in enumerate(context_data[:3], 1):
                        if isinstance(item, dict):
                            content = item.get("content", str(item))[:200]
                        else:
                            content = str(item)[:200]
                        formatted_parts.append(f"  {i}. {content}...")

            return "\n".join(formatted_parts)

        except Exception as e:
            self.logger.error(f"Failed to format context: {e}")
            return "Context formatting error"


    async def _store_interaction(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        evaluation: EvaluationResult,
    ):
        """Store interaction data for future learning."""
        try:
            # Store main interaction
            interaction_content = f"Query: {query}\n\nResponse: {response}"
            interaction_metadata = {
                "session_id": self.session_id,
                "interaction_count": self.interaction_count,
                "evaluation_score": evaluation.overall_score,
                "context_categories": list(context.keys()),
            }

            interaction_memory = MemoryEntry(
                content=interaction_content,
                memory_type="interaction",
                metadata=interaction_metadata,
            )

            await self.memory.add_memory(interaction_memory)

            # Store evaluation results
            evaluation_memory = await self.evaluator.create_evaluation_memory(
                evaluation, query, response
            )
            await self.memory.add_memory(evaluation_memory)

            # Store context usage
            await self.context_manager.store_interaction_context(
                query, response, context, {"evaluation": evaluation.overall_score}
            )

            self.logger.info("Interaction stored successfully")

        except Exception as e:
            self.logger.error(f"Failed to store interaction: {e}")

    async def _store_error(self, query: str, error: str):
        """Store error information for learning."""
        try:
            error_content = f"Query: {query}\n\nError: {error}"
            error_memory = MemoryEntry(
                content=error_content,
                memory_type="error",
                metadata={
                    "session_id": getattr(self, "session_id", None),
                    "interaction_count": getattr(self, "interaction_count", None),
                    "error_message": error,
                },
            )
            if hasattr(self, "memory") and self.memory:
                await self.memory.add_memory(error_memory)
            self.logger.info("Error information stored for learning")
        except Exception as e:
            self.logger.error(f"Failed to store error: {e}")

    async def _store_session_start(self):
        """Store session initialization information."""
        try:
            session_content = f"Session started: {self.session_id}"

            # Get config snapshot but only store basic info in metadata
            config_snapshot = config.get_all_config()

            session_memory = MemoryEntry(
                content=session_content,
                memory_type="session",
                metadata={
                    "session_id": self.session_id,
                    "initialization_timestamp": datetime.now().isoformat(),
                    "llm_provider": config_snapshot.get(
                        "default_llm_provider", "unknown"
                    ),
                    "model": config_snapshot.get("default_model", "unknown"),
                    "self_modification_enabled": config_snapshot.get(
                        "enable_self_modification", False
                    ),
                    "auto_update_knowledge": config_snapshot.get(
                        "auto_update_knowledge", False
                    ),
                },
            )

            await self.memory.add_memory(session_memory)

        except Exception as e:
            self.logger.error(f"Failed to store session start: {e}")

    async def _consider_self_modification(self):
        """Consider and potentially implement self-modifications."""
        try:
            if not config.enable_self_modification:
                return

            self.logger.info("Considering self-modification opportunities...")
            self.improvement_cycle_count += 1

            # Analyze recent performance
            evaluation_insights = await self.evaluator.get_evaluation_insights()

            # Get knowledge update suggestions
            knowledge_suggestions = (
                await self.knowledge_updater.get_improvement_suggestions()
            )

            # Analyze code for potential improvements
            code_analysis = await self.code_analyzer.analyze_performance_patterns(
                evaluation_insights, knowledge_suggestions
            )

            # If significant improvement opportunities exist, consider modifications
            if (
                code_analysis.get("improvement_potential", 0) > 0.7
                and evaluation_insights.get("recent_average_score", 1.0) < 0.7
            ):

                self.logger.info("Significant improvement potential detected")

                # Generate and validate modifications
                if self.code_modifier:
                    await self.code_modifier.consider_modifications(
                        code_analysis, evaluation_insights, knowledge_suggestions
                    )

            # Store self-modification cycle information
            modification_memory = MemoryEntry(
                content=f"Self-modification cycle {self.improvement_cycle_count}",
                memory_type="self_modification",
                metadata={
                    "cycle_count": self.improvement_cycle_count,
                    "evaluation_insights": evaluation_insights,
                    "code_analysis": code_analysis,
                    "session_id": self.session_id,
                },
            )

            await self.memory.add_memory(modification_memory)

            # Notify status callbacks about self-improvement cycle
            if config.discord_status_on_improvement:
                await self._notify_status(
                    "self_improvement",
                    {
                        "cycle_count": self.improvement_cycle_count,
                        "improvement_potential": code_analysis.get("improvement_potential", 0),
                        "recent_score": evaluation_insights.get("recent_average_score", "N/A"),
                        "improvements": code_analysis.get("improvements", []),
                    }
                )

        except Exception as e:
            self.logger.error(f"Failed during self-modification consideration: {e}")

    async def print_status(self):
        """Print current agent status."""
        try:
            memory_stats = await self.memory.get_memory_stats()
            evaluation_insights = await self.evaluator.get_evaluation_insights()
            print(
                f"""
Agent Status:
=============
Session ID: {self.session_id}
Interactions: {self.interaction_count}
Improvement Cycles: {self.improvement_cycle_count}

Memory:
- Total memories: {memory_stats.get('total_memories', 0)}
- Memory types: {memory_stats.get('memory_types', {})}

Performance:
- Recent average score: {evaluation_insights.get('recent_average_score', 'N/A')}
- Trend: {evaluation_insights.get('score_trend', 'N/A')}
- Confidence: {evaluation_insights.get('confidence_level', 'N/A')}

Configuration:
- LLM Provider: {config.default_llm_provider}
- Model: {config.default_model}
- Self-modification: {config.enable_self_modification}
            """
            )
        except Exception as e:
            print(f"Error getting status: {e}")

    async def print_memory_stats(self):
        """Print detailed memory statistics."""
        try:
            stats = await self.memory.get_memory_stats()
            print(
                f"""
Memory Statistics:
==================
Total memories: {stats.get('total_memories', 0)}
Collection: {stats.get('collection_name', 'N/A')}
Directory: {stats.get('persist_directory', 'N/A')}

Memory Types:
{json.dumps(stats.get('memory_types', {}), indent=2)}
            """
            )
        except Exception as e:
            print(f"Error getting memory stats: {e}")

    async def _improve_response(
        self,
        query: str,
        initial_response: str,
        evaluation: "EvaluationResult",
        context: dict,
    ) -> str:
        """Improve response based on evaluation feedback."""
        try:
            # If the response is already good, return it
            if evaluation.overall_score >= 0.8:
                self.logger.info("Response quality is high, no improvement needed")
                return initial_response

            # If there are specific improvement suggestions, apply them
            if getattr(evaluation, "improvement_suggestions", None):
                self.logger.info("Applying improvement suggestions")
                improvement_prompt = (
                    f"Original Query: {query}\n\n"
                    f"Initial Response: {initial_response}\n\n"
                    "Evaluation Feedback:\n"
                    f"- Overall Score: {getattr(evaluation, 'overall_score', 0):.2f}\n"
                    f"- Weaknesses: {'; '.join(getattr(evaluation, 'weaknesses', []))}\n"
                    f"- Improvement Suggestions: {'; '.join(getattr(evaluation, 'improvement_suggestions', []))}\n"
                    "Please provide an improved version of the response that addresses the feedback.\n"
                    "Focus on fixing the identified weaknesses and implementing the suggestions."
                )

                improved_response = await llm_manager.generate_response(
                    prompt=improvement_prompt,
                    temperature=getattr(config, "temperature", 0.7) * 0.8,
                    max_tokens=getattr(config, "max_tokens", 2048),
                )

                return improved_response.strip()

            return initial_response

        except Exception as e:
            self.logger.error(f"Failed to improve response: {e}")
            return initial_response

    async def cleanup(self):
        """Clean up agent resources with error recovery."""
        try:
            self.logger.info("Cleaning up agent resources...")
            
            # Save final recovery status
            final_status = self.get_recovery_status()
            
            agent_state = {
                "session_id": self.session_id,
                "interaction_count": self.interaction_count,
                "improvement_cycle_count": self.improvement_cycle_count,
                "final_timestamp": datetime.now().isoformat(),
                "recovery_status": final_status,
                "component_health": self.component_health,
            }
            
            try:
                await self.data_manager.save_agent_state(agent_state)
            except Exception as e:
                self.logger.error(f"Failed to save agent state: {e}")
            
            try:
                await self.data_manager.cleanup()
            except Exception as e:
                self.logger.error(f"Failed to cleanup data manager: {e}")
            
            try:
                if self.memory and self.session_id:
                    session_end_memory = MemoryEntry(
                        content=(
                            f"Session {self.session_id} ended with "
                            f"{self.interaction_count} interactions"
                        ),
                        memory_type="session_end",
                        metadata={
                            "session_id": self.session_id,
                            "total_interactions": self.interaction_count,
                            "improvement_cycles": self.improvement_cycle_count,
                            "degraded_mode": self.degraded_mode,
                        },
                    )
                    await self.memory.add_memory(session_end_memory)
            except Exception as e:
                self.logger.error(f"Failed to store session end: {e}")
            
            # Clean up checkpoints
            error_recovery_manager.cleanup_old_checkpoints()
            
            self.logger.info("Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        health_status = {
            "overall": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Check each component
        health_status["components"]["memory"] = await self._check_memory_health()
        
        try:
            providers = await llm_manager.get_available_providers()
            health_status["components"]["llm"] = len(providers) > 0
        except Exception:
            health_status["components"]["llm"] = False
        
        health_status["components"]["context_manager"] = not self.context_manager.is_degraded_mode()
        health_status["components"]["knowledge_base"] = self.component_health.get("knowledge_base", True)
        health_status["components"]["self_modification"] = self.component_health.get("self_modification", True)
        
        # Determine overall health
        if all(health_status["components"].values()):
            health_status["overall"] = "healthy"
        elif any(health_status["components"].values()):
            health_status["overall"] = "degraded"
        else:
            health_status["overall"] = "unhealthy"
        
        return health_status



