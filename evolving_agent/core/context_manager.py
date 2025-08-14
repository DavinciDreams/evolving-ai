"""
Dynamic context management for intelligent query processing.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from .memory import LongTermMemory, MemoryEntry

logger = setup_logger(__name__)


@dataclass
class ContextQuery:
    """Represents a context query with metadata."""

    query: str
    context_type: str
    priority: float
    timestamp: datetime
    metadata: Dict[str, Any]


class ContextManager:
    """Manages dynamic context retrieval and processing."""

    def __init__(self, memory: LongTermMemory):
        self.memory = memory
        self.active_contexts: Dict[str, Any] = {}
        self.context_cache: Dict[str, Tuple[List[MemoryEntry], datetime]] = {}
        self.cache_ttl = timedelta(minutes=30)

    async def get_relevant_context(
        self,
        query: str,
        context_types: Optional[List[str]] = None,
        max_context_items: int = 10,
        similarity_threshold: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Get relevant context for a query using dynamic retrieval.

        Args:
            query: The main query or task
            context_types: Specific types of context to retrieve
            max_context_items: Maximum number of context items to return
            similarity_threshold: Minimum similarity for relevance

        Returns:
            Dictionary containing organized context information
        """
        try:
            logger.info(f"Retrieving context for query: {query[:100]}...")

            # Generate context queries
            context_queries = await self._generate_context_queries(query, context_types)

            # Retrieve memories for each context query
            all_contexts = {}
            for ctx_query in context_queries:
                contexts = await self._retrieve_context_memories(
                    ctx_query, similarity_threshold, max_context_items
                )
                if contexts:
                    all_contexts[ctx_query.context_type] = contexts

            # Organize and rank contexts
            organized_context = await self._organize_contexts(all_contexts, query)

            # Add recent interaction context
            recent_context = await self._get_recent_context()
            if recent_context:
                organized_context["recent_interactions"] = recent_context

            # Add system state context
            system_context = await self._get_system_context()
            organized_context["system_state"] = system_context

            logger.info(f"Retrieved {len(organized_context)} context categories")
            return organized_context

        except Exception as e:
            logger.error(f"Failed to get relevant context: {e}")
            return {}

    async def _generate_context_queries(
        self, main_query: str, context_types: Optional[List[str]] = None
    ) -> List[ContextQuery]:
        """Generate specific context queries based on the main query."""
        try:
            # Default context types if none specified
            if not context_types:
                context_types = [
                    "similar_tasks",
                    "relevant_knowledge",
                    "past_solutions",
                    "learned_patterns",
                    "error_experiences",
                    "optimization_insights",
                ]

            context_queries = []

            # Use LLM to generate specific queries for each context type
            for ctx_type in context_types:
                prompt = f"""
                Given the main query: "{main_query}"
                
                Generate a specific search query to find relevant {ctx_type.replace('_', ' ')}.
                
                Context type: {ctx_type}
                Main query: {main_query}
                
                Return only the search query, no explanations:
                """

                try:
                    search_query = await llm_manager.generate_response(
                        prompt=prompt, temperature=0.3, max_tokens=100
                    )

                    context_queries.append(
                        ContextQuery(
                            query=search_query.strip(),
                            context_type=ctx_type,
                            priority=self._calculate_context_priority(
                                ctx_type, main_query
                            ),
                            timestamp=datetime.now(),
                            metadata={"main_query": main_query},
                        )
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to generate context query for {ctx_type}: {e}"
                    )
                    # Fallback to main query
                    context_queries.append(
                        ContextQuery(
                            query=main_query,
                            context_type=ctx_type,
                            priority=0.5,
                            timestamp=datetime.now(),
                            metadata={"main_query": main_query, "fallback": True},
                        )
                    )

            return context_queries

        except Exception as e:
            logger.error(f"Failed to generate context queries: {e}")
            return []

    def _calculate_context_priority(self, context_type: str, main_query: str) -> float:
        """Calculate priority for different context types."""
        # Priority weights for different context types
        priority_weights = {
            "similar_tasks": 0.9,
            "relevant_knowledge": 0.8,
            "past_solutions": 0.85,
            "learned_patterns": 0.7,
            "error_experiences": 0.75,
            "optimization_insights": 0.6,
        }

        base_priority = priority_weights.get(context_type, 0.5)

        # Adjust based on query keywords
        query_lower = main_query.lower()
        if "error" in query_lower or "problem" in query_lower:
            if context_type == "error_experiences":
                base_priority += 0.2
        elif "optimize" in query_lower or "improve" in query_lower:
            if context_type == "optimization_insights":
                base_priority += 0.2
        elif "learn" in query_lower or "pattern" in query_lower:
            if context_type == "learned_patterns":
                base_priority += 0.2

        return min(base_priority, 1.0)

    async def _retrieve_context_memories(
        self, context_query: ContextQuery, similarity_threshold: float, max_items: int
    ) -> List[Tuple[MemoryEntry, float]]:
        """Retrieve memories for a specific context query."""
        try:
            # Check cache first
            cache_key = f"{context_query.query}_{context_query.context_type}"
            if cache_key in self.context_cache:
                cached_memories, cache_time = self.context_cache[cache_key]
                if datetime.now() - cache_time < self.cache_ttl:
                    return cached_memories[:max_items]

            # Search memories
            memories = await self.memory.search_memories(
                query=context_query.query,
                n_results=max_items * 2,  # Get more for filtering
                memory_type=context_query.context_type,
                similarity_threshold=similarity_threshold,
            )

            # Filter and sort by relevance and recency
            filtered_memories = self._filter_and_rank_memories(
                memories, context_query, max_items
            )

            # Cache results
            self.context_cache[cache_key] = (filtered_memories, datetime.now())

            return filtered_memories

        except Exception as e:
            logger.error(f"Failed to retrieve context memories: {e}")
            return []

    def _filter_and_rank_memories(
        self,
        memories: List[Tuple[MemoryEntry, float]],
        context_query: ContextQuery,
        max_items: int,
    ) -> List[Tuple[MemoryEntry, float]]:
        """Filter and rank memories based on relevance and recency."""
        try:
            # Calculate combined scores (similarity + recency + priority)
            scored_memories = []
            current_time = datetime.now()

            for memory, similarity in memories:
                # Recency score (newer = higher score)
                time_diff = current_time - memory.timestamp
                recency_score = max(
                    0, 1 - (time_diff.total_seconds() / (30 * 24 * 3600))
                )  # 30 days decay

                # Combined score
                combined_score = (
                    similarity * 0.6
                    + recency_score * 0.2
                    + context_query.priority * 0.2
                )

                scored_memories.append((memory, combined_score))

            # Sort by combined score and return top items
            scored_memories.sort(key=lambda x: x[1], reverse=True)
            return scored_memories[:max_items]

        except Exception as e:
            logger.error(f"Failed to filter and rank memories: {e}")
            return memories[:max_items]

    async def _organize_contexts(
        self, all_contexts: Dict[str, List[Tuple[MemoryEntry, float]]], main_query: str
    ) -> Dict[str, Any]:
        """Organize contexts into a structured format."""
        try:
            organized = {}

            for context_type, memories in all_contexts.items():
                if not memories:
                    continue

                # Extract content and metadata
                context_items = []
                for memory, score in memories:
                    context_items.append(
                        {
                            "content": memory.content,
                            "relevance_score": score,
                            "timestamp": memory.timestamp.isoformat(),
                            "memory_type": memory.memory_type,
                            "metadata": memory.metadata,
                        }
                    )

                # Summarize if too many items
                if len(context_items) > 5:
                    summary = await self._summarize_context_items(
                        context_items, context_type
                    )
                    organized[context_type] = {
                        "summary": summary,
                        "items": context_items[:3],  # Keep top 3
                        "total_items": len(context_items),
                    }
                else:
                    organized[context_type] = {
                        "items": context_items,
                        "total_items": len(context_items),
                    }

            return organized

        except Exception as e:
            logger.error(f"Failed to organize contexts: {e}")
            return all_contexts

    async def _summarize_context_items(
        self, context_items: List[Dict[str, Any]], context_type: str
    ) -> str:
        """Summarize context items if there are too many."""
        try:
            # Prepare content for summarization
            content_list = [item["content"] for item in context_items]
            combined_content = "\n\n".join(content_list)

            prompt = f"""
            Summarize the following {context_type.replace('_', ' ')} in 2-3 sentences:
            
            {combined_content}
            
            Focus on the key patterns, insights, and actionable information.
            """

            summary = await llm_manager.generate_response(
                prompt=prompt, temperature=0.3, max_tokens=200
            )

            return summary.strip()

        except Exception as e:
            logger.error(f"Failed to summarize context items: {e}")
            return f"Multiple {context_type.replace('_', ' ')} entries available."

    async def _get_recent_context(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent interaction context."""
        try:
            # Search for recent memories
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Get all recent memories (this is a simplified version)
            # In a real implementation, you'd want a more efficient query
            recent_memories = await self.memory.search_memories(
                query="",  # Empty query to get all
                n_results=20,
                similarity_threshold=0.0,
            )

            # Filter by time and format
            recent_context = []
            for memory, _ in recent_memories:
                if memory.timestamp >= cutoff_time:
                    recent_context.append(
                        {
                            "content": memory.content,
                            "timestamp": memory.timestamp.isoformat(),
                            "memory_type": memory.memory_type,
                        }
                    )

            # Sort by timestamp (newest first)
            recent_context.sort(key=lambda x: x["timestamp"], reverse=True)

            return recent_context[:10]  # Return last 10

        except Exception as e:
            logger.error(f"Failed to get recent context: {e}")
            return []

    async def _get_system_context(self) -> Dict[str, Any]:
        """Get current system state context."""
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "memory_stats": await self.memory.get_memory_stats(),
                "config": {
                    "llm_provider": config.default_llm_provider,
                    "model": config.default_model,
                    "self_modification_enabled": config.enable_self_modification,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get system context: {e}")
            return {"error": str(e)}

    async def store_interaction_context(
        self,
        query: str,
        response: str,
        context_used: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Store interaction context for future reference."""
        try:
            # Create memory entry for the interaction
            interaction_content = f"Query: {query}\n\nResponse: {response}"

            interaction_metadata = {
                "interaction_type": "query_response",
                "context_categories": list(context_used.keys()),
                **(metadata or {}),
            }

            memory_entry = MemoryEntry(
                content=interaction_content,
                memory_type="interaction",
                metadata=interaction_metadata,
            )

            await self.memory.add_memory(memory_entry)
            logger.info("Stored interaction context")

        except Exception as e:
            logger.error(f"Failed to store interaction context: {e}")

    def clear_cache(self):
        """Clear the context cache."""
        self.context_cache.clear()
        logger.info("Context cache cleared")
