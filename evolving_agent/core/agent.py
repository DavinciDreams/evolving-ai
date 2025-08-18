"""
Main Self-Improving AI Agent class.
"""

import json
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
from .context_manager import ContextManager
from .evaluator import EvaluationResult, OutputEvaluator
from .memory import LongTermMemory, MemoryEntry




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

        # State tracking
        self.initialized = False
        self.session_id = None
        self.interaction_count = 0
        self.improvement_cycle_count = 0

    async def initialize(self):
        """Initialize all agent components."""
        try:
            self.logger.info("Initializing Self-Improving Agent...")

            # Ensure directories exist
            config.ensure_directories()

            # Initialize persistent data manager
            await self.data_manager.initialize()
            self.logger.info("Persistent data manager initialized")

            # Initialize core components
            await self.memory.initialize()
            self.logger.info("Memory system initialized")

            self.context_manager = ContextManager(self.memory)
            self.logger.info("Context manager initialized")

            await self.knowledge_base.initialize()
            self.logger.info("Knowledge base initialized")

            self.knowledge_updater = KnowledgeUpdater(
                self.knowledge_base, self.memory
            )

            self.logger.info("Knowledge updater initialized")

            # Initialize self-modification components if enabled
            if config.enable_self_modification:
                self.code_modifier = CodeModifier(
                    analyzer=self.code_analyzer, validator=self.code_validator
                )
                self.logger.info("Self-modification system initialized")

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

            # Step 3: Evaluate the response
            evaluation = await self.evaluator.evaluate_output(
                query=query, output=initial_response, context=context
            )

            # Step 4: Improve response based on evaluation
            final_response = await self._improve_response(
                query, initial_response, evaluation, context
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
                await self.knowledge_updater.update_from_interaction(
                    query, final_response, evaluation
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
            system_prompt = (
                "You are a self-improving AI with the ability to analyze and modify your own code.\n"
                "You have access to long-term memory and a knowledge base, enabling you to learn from past interactions and improve over time.\n"
                f"Current session: {self.session_id}\n"
                f"Interaction count: {self.interaction_count}\n"
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


    try:
        self.logger.info("Cleaning up agent resources...")
        agent_state = {
            "session_id": self.session_id,
            "interaction_count": self.interaction_count,
            "improvement_cycle_count": self.improvement_cycle_count,
            "final_timestamp": datetime.now().isoformat(),
        }
        await self.data_manager.save_agent_state(agent_state)
        await self.data_manager.cleanup()
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
                },
            )
            await self.memory.add_memory(session_end_memory)
        self.logger.info("Agent cleanup completed")
    except Exception as e:
        self.logger.error(f"Error during cleanup: {e}")



