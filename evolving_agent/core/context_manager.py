"""
Dynamic context management for intelligent query processing.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import asyncio

from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from ..utils.error_recovery import error_recovery_manager
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
    """Manages dynamic context retrieval and processing with error recovery."""

    def __init__(self, memory: LongTermMemory):
        self.memory = memory
        self.active_contexts: Dict[str, Any] = {}
        self.context_cache: Dict[str, Tuple[List[MemoryEntry], datetime]] = {}
        self.cache_ttl = timedelta(minutes=30)
        
        # Degraded mode support
        self.degraded_mode = False
        self.degraded_cache: Dict[str, Any] = {}
        self.memory_unavailable_count = 0
        self.memory_failure_threshold = 3
        
        # Cache warming
        self.cache_warming_enabled = True
        self.warm_cache_keys: List[str] = []
        self.cache_warm_interval = timedelta(minutes=15)
        self.last_cache_warm: Optional[datetime] = None
        
        # Error recovery
        self.recovery_attempts: Dict[str, int] = {}
        self.max_recovery_attempts = 3

    async def get_relevant_context(
        self,
        query: str,
        context_types: Optional[List[str]] = None,
        max_context_items: int = 10,
        similarity_threshold: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Get relevant context for a query using dynamic retrieval with error recovery.

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

            # Check degraded mode
            if self.degraded_mode:
                logger.info("Operating in degraded mode, using cached context")
                return self._get_degraded_context(query)

            # Generate context queries with error recovery
            context_queries = await self._generate_context_queries_with_recovery(query, context_types)

            # Retrieve memories for each context query
            all_contexts = {}
            for ctx_query in context_queries:
                contexts = await self._retrieve_context_memories_with_recovery(
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

            # Update degraded cache with successful results
            self._update_degraded_cache(query, organized_context)

            logger.info(f"Retrieved {len(organized_context)} context categories")
            return organized_context

        except Exception as e:
            logger.error(f"Failed to get relevant context: {e}")
            # Try to return degraded context
            return self._get_degraded_context(query)
    
    async def _generate_context_queries_with_recovery(
        self, main_query: str, context_types: Optional[List[str]] = None
    ) -> List[ContextQuery]:
        """Generate context queries with error recovery."""
        try:
            return await self._generate_context_queries(main_query, context_types)
        except Exception as e:
            logger.error(f"Error generating context queries: {e}")
            # Return fallback queries
            return [
                ContextQuery(
                    query=main_query,
                    context_type="fallback",
                    priority=0.5,
                    timestamp=datetime.now(),
                    metadata={"fallback": True, "error": str(e)}
                )
            ]
    
    async def _retrieve_context_memories_with_recovery(
        self, context_query: ContextQuery, similarity_threshold: float, max_items: int
    ) -> List[Tuple[MemoryEntry, float]]:
        """Retrieve context memories with error recovery."""
        try:
            return await self._retrieve_context_memories(
                context_query, similarity_threshold, max_items
            )
        except Exception as e:
            logger.error(f"Error retrieving context memories: {e}")
            self.memory_unavailable_count += 1
            
            # Check if we should enter degraded mode
            if self.memory_unavailable_count >= self.memory_failure_threshold:
                self._enable_degraded_mode()
            
            # Try to return cached data
            cache_key = f"{context_query.query}_{context_query.context_type}"
            if cache_key in self.context_cache:
                logger.info(f"Using cached data for {cache_key}")
                return self.context_cache[cache_key][0]
            
            return []
    
    def _enable_degraded_mode(self):
        """Enable degraded mode when memory is unavailable."""
        self.degraded_mode = True
        error_recovery_manager.set_degraded_mode(True)
        logger.warning("Memory unavailable, entering degraded mode")
    
    def _disable_degraded_mode(self):
        """Disable degraded mode when memory is available again."""
        self.degraded_mode = False
        self.memory_unavailable_count = 0
        error_recovery_manager.set_degraded_mode(False)
        logger.info("Memory available, exiting degraded mode")
    
    def _get_degraded_context(self, query: str) -> Dict[str, Any]:
        """Get context in degraded mode using cached data."""
        logger.info(f"Returning degraded context for query: {query[:50]}...")
        
        # Try to find similar query in degraded cache
        for cached_query, cached_context in self.degraded_cache.items():
            if query.lower() in cached_query.lower() or cached_query.lower() in query.lower():
                logger.info(f"Found similar cached context: {cached_query[:50]}...")
                return cached_context
        
        # Return minimal context if no match
        return {
            "system_state": {
                "timestamp": datetime.now().isoformat(),
                "mode": "degraded",
                "message": "Operating in degraded mode with limited context"
            },
            "recent_interactions": [],
            "degraded": True
        }
    
    def _update_degraded_cache(self, query: str, context: Dict[str, Any]):
        """Update degraded cache with new context."""
        # Keep only last 10 queries in degraded cache
        if len(self.degraded_cache) >= 10:
            oldest_key = next(iter(self.degraded_cache))
            del self.degraded_cache[oldest_key]
        
        self.degraded_cache[query] = context
    
    async def warm_cache(self, queries: List[str]):
        """Warm the cache with common queries for faster recovery."""
        if not self.cache_warming_enabled:
            return
        
        logger.info(f"Warming cache with {len(queries)} queries")
        
        for query in queries:
            try:
                await self.get_relevant_context(
                    query=query,
                    max_context_items=5,
                    similarity_threshold=0.5
                )
            except Exception as e:
                logger.warning(f"Cache warming failed for query '{query}': {e}")
        
        self.last_cache_warm = datetime.now()
        logger.info("Cache warming completed")
    
    async def auto_warm_cache(self):
        """Automatically warm cache based on recent queries."""
        if not self.cache_warming_enabled:
            return
        
        # Check if cache warming is needed
        if self.last_cache_warm:
            time_since_warm = datetime.now() - self.last_cache_warm
            if time_since_warm < self.cache_warm_interval:
                return
        
        # Get recent queries from degraded cache
        recent_queries = list(self.degraded_cache.keys())[:5]
        if recent_queries:
            await self.warm_cache(recent_queries)
    
    def enable_cache_warming(self, enabled: bool):
        """Enable or disable cache warming."""
        self.cache_warming_enabled = enabled
        logger.info(f"Cache warming {'enabled' if enabled else 'disabled'}")
    
    def is_degraded_mode(self) -> bool:
        """Check if operating in degraded mode."""
        return self.degraded_mode
    
    async def check_memory_health(self) -> bool:
        """Check if memory is healthy and available."""
        try:
            # Try a simple memory operation
            stats = await self.memory.get_memory_stats()
            return stats is not None
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            self.memory_unavailable_count += 1
            if self.memory_unavailable_count >= self.memory_failure_threshold:
                self._enable_degraded_mode()
            return False

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
\1                Generate a specific search query to find relevant {ctx_type.replace('_', ' ')}.
\1                Context type: {ctx_type}
                Main query: {main_query}
\1                Return only the search query, no explanations:
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

            # Search memories — don't filter by memory_type since stored types
            # (interaction, evaluation, error, etc.) don't match context query
            # types (similar_tasks, past_solutions, etc.). Vector similarity
            # search already finds relevant results across all memory types.
            memories = await self.memory.search_memories(
                query=context_query.query,
                n_results=max_items * 2,  # Get more for filtering
                memory_type=None,
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
\1            {combined_content}
\1            Focus on the key patterns, insights, and actionable information.
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
        self.degraded_cache.clear()
        logger.info("Context cache cleared")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current context manager status."""
        return {
            "degraded_mode": self.degraded_mode,
            "cache_size": len(self.context_cache),
            "degraded_cache_size": len(self.degraded_cache),
            "memory_unavailable_count": self.memory_unavailable_count,
            "cache_warming_enabled": self.cache_warming_enabled,
            "last_cache_warm": self.last_cache_warm.isoformat() if self.last_cache_warm else None,
            "active_contexts": len(self.active_contexts)
        }
