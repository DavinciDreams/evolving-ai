"""
Knowledge base updater for automatic learning and improvement.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core.evaluator import EvaluationResult
from ..core.memory import LongTermMemory, MemoryEntry
from ..utils.config import config
from ..utils.llm_interface import llm_manager
from ..utils.logging import setup_logger
from .base import KnowledgeBase, KnowledgeEntry

logger = setup_logger(__name__)


class KnowledgeUpdater:
    """Automatic knowledge base updater."""
    
    def __init__(self, knowledge_base: KnowledgeBase, memory: LongTermMemory):
        self.knowledge_base = knowledge_base
        self.memory = memory
        self.update_history: List[Dict[str, Any]] = []
        self.pending_updates: List[Dict[str, Any]] = []
    
    async def update_from_interaction(
        self,
        query: str,
        response: str,
        evaluation: EvaluationResult
    ):
        """Update knowledge base from a successful interaction."""
        try:
            logger.info("Analyzing interaction for knowledge updates...")
            
            # Only update from high-quality interactions
            if evaluation.overall_score < 0.7:
                logger.info("Interaction quality too low for knowledge update")
                return
            
            # Extract potential knowledge from the interaction
            knowledge_candidates = await self._extract_knowledge_candidates(
                query, response, evaluation
            )
            
            # Process each candidate
            for candidate in knowledge_candidates:
                await self._process_knowledge_candidate(candidate)
            
            logger.info(f"Processed {len(knowledge_candidates)} knowledge candidates")
            
        except Exception as e:
            logger.error(f"Failed to update knowledge from interaction: {e}")
    
    async def _extract_knowledge_candidates(
        self,
        query: str,
        response: str,
        evaluation: EvaluationResult
    ) -> List[Dict[str, Any]]:
        """Extract potential knowledge from an interaction."""
        try:
            extraction_prompt = f"""
            Analyze the following successful interaction and extract reusable knowledge.
            
            Query: {query}
            Response: {response}
            Evaluation Score: {evaluation.overall_score:.2f}
            Strengths: {', '.join(evaluation.strengths)}
            
            Extract 1-3 pieces of reusable knowledge that could help with similar future queries.
            Focus on:
            1. Problem-solving approaches that worked well
            2. Patterns or insights that emerged
            3. Best practices that were applied
            
            Return as JSON array with format:
            [
                {{
                    "content": "The extracted knowledge",
                    "category": "problem_solving|learning_patterns|best_practices|domain_knowledge",
                    "tags": ["relevant", "tags"],
                    "confidence": 0.8,
                    "rationale": "Why this knowledge is valuable"
                }}
            ]
            
            Only extract knowledge that is genuinely reusable and not too specific to this exact query.
            """
            
            response_text = await llm_manager.generate_response(
                prompt=extraction_prompt,
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse the response
            try:
                candidates = json.loads(response_text)
                if isinstance(candidates, list):
                    return candidates
                else:
                    return [candidates]  # Single candidate
            except json.JSONDecodeError:
                # Fallback parsing
                return await self._fallback_knowledge_extraction(query, response, evaluation)
            
        except Exception as e:
            logger.error(f"Failed to extract knowledge candidates: {e}")
            return []
    
    async def _fallback_knowledge_extraction(
        self,
        query: str,
        response: str,
        evaluation: EvaluationResult
    ) -> List[Dict[str, Any]]:
        """Fallback method for knowledge extraction when JSON parsing fails."""
        try:
            # Simple heuristic-based extraction
            candidates = []
            
            # If the response contains actionable insights
            if any(word in response.lower() for word in ["approach", "method", "technique", "strategy"]):
                candidates.append({
                    "content": f"Successful approach for queries like '{query[:50]}...': {response[:200]}...",
                    "category": "problem_solving",
                    "tags": ["approach", "method"],
                    "confidence": evaluation.overall_score * 0.8,
                    "rationale": "Extracted from successful interaction"
                })
            
            # If the response contains patterns or insights
            if any(word in response.lower() for word in ["pattern", "insight", "because", "since"]):
                candidates.append({
                    "content": f"Pattern observed: {response[:200]}...",
                    "category": "learning_patterns",
                    "tags": ["pattern", "insight"],
                    "confidence": evaluation.overall_score * 0.7,
                    "rationale": "Pattern identified in successful response"
                })
            
            return candidates[:2]  # Limit to 2 candidates
            
        except Exception as e:
            logger.error(f"Fallback knowledge extraction failed: {e}")
            return []
    
    async def _process_knowledge_candidate(self, candidate: Dict[str, Any]):
        """Process a knowledge candidate for potential addition."""
        try:
            # Validate candidate
            required_fields = ["content", "category", "confidence"]
            if not all(field in candidate for field in required_fields):
                logger.warning(f"Invalid knowledge candidate: {candidate}")
                return
            
            # Create knowledge entry
            entry = KnowledgeEntry(
                content=candidate["content"],
                category=candidate["category"],
                tags=candidate.get("tags", []),
                confidence=float(candidate["confidence"]),
                source="auto_extraction",
                metadata={
                    "extraction_timestamp": datetime.now().isoformat(),
                    "rationale": candidate.get("rationale", ""),
                    "auto_generated": True
                }
            )
            
            # Check if similar knowledge already exists
            similar = await self.knowledge_base.find_similar_knowledge(
                entry.content, threshold=0.8
            )
            
            if similar:
                logger.info(f"Similar knowledge exists, skipping: {entry.id}")
                return
            
            # Add to knowledge base if confidence is high enough
            if entry.confidence >= 0.6:
                await self.knowledge_base.add_knowledge(entry)
                logger.info(f"Added knowledge entry: {entry.id}")
                
                # Record the update
                self.update_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "knowledge_id": entry.id,
                    "action": "added",
                    "confidence": entry.confidence,
                    "category": entry.category
                })
            else:
                # Add to pending updates for review
                self.pending_updates.append({
                    "candidate": candidate,
                    "entry": entry.to_dict(),
                    "timestamp": datetime.now().isoformat()
                })
                logger.info(f"Added to pending updates (low confidence): {entry.confidence}")
            
        except Exception as e:
            logger.error(f"Failed to process knowledge candidate: {e}")
    
    async def update_from_errors(self):
        """Update knowledge base from error patterns."""
        try:
            logger.info("Analyzing error patterns for knowledge updates...")
            
            # Search for recent error memories
            error_memories = await self.memory.search_memories(
                query="error problem issue",
                n_results=20,
                memory_type="error"
            )
            
            if not error_memories:
                logger.info("No error memories found")
                return
            
            # Analyze error patterns
            error_analysis = await self._analyze_error_patterns(error_memories)
            
            # Create knowledge entries for common error solutions
            for pattern in error_analysis.get("patterns", []):
                if pattern.get("frequency", 0) >= 2:  # Occurred at least twice
                    await self._create_error_knowledge(pattern)
            
        except Exception as e:
            logger.error(f"Failed to update from errors: {e}")
    
    async def _analyze_error_patterns(
        self,
        error_memories: List[Tuple[MemoryEntry, float]]
    ) -> Dict[str, Any]:
        """Analyze patterns in error memories."""
        try:
            # Extract error content
            error_contents = [memory.content for memory, _ in error_memories]
            combined_errors = "\n\n".join(error_contents[:10])  # Limit to 10 most relevant
            
            analysis_prompt = f"""
            Analyze the following error patterns and extract common issues and solutions:
            
            {combined_errors}
            
            Identify:
            1. Common error types or patterns
            2. Recurring causes
            3. Known solutions or workarounds
            
            Return as JSON:
            {{
                "patterns": [
                    {{
                        "type": "error type",
                        "description": "what causes this error",
                        "frequency": 3,
                        "solution": "how to solve it",
                        "prevention": "how to prevent it"
                    }}
                ]
            }}
            """
            
            response = await llm_manager.generate_response(
                prompt=analysis_prompt,
                temperature=0.2,
                max_tokens=600
            )
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning("Failed to parse error analysis JSON")
                return {"patterns": []}
            
        except Exception as e:
            logger.error(f"Failed to analyze error patterns: {e}")
            return {"patterns": []}
    
    async def _create_error_knowledge(self, pattern: Dict[str, Any]):
        """Create knowledge entry from error pattern."""
        try:
            content = f"""
            Error Pattern: {pattern.get('type', 'Unknown')}
            
            Description: {pattern.get('description', '')}
            
            Solution: {pattern.get('solution', '')}
            
            Prevention: {pattern.get('prevention', '')}
            
            Frequency: {pattern.get('frequency', 1)} occurrences
            """
            
            entry = KnowledgeEntry(
                content=content.strip(),
                category="error_resolution",
                tags=["error", "solution", "troubleshooting"],
                confidence=min(0.8, 0.5 + (pattern.get('frequency', 1) * 0.1)),
                source="error_analysis",
                metadata={
                    "pattern_type": pattern.get('type', ''),
                    "frequency": pattern.get('frequency', 1),
                    "auto_generated": True,
                    "analysis_timestamp": datetime.now().isoformat()
                }
            )
            
            await self.knowledge_base.add_knowledge(entry)
            logger.info(f"Created error knowledge entry: {entry.id}")
            
        except Exception as e:
            logger.error(f"Failed to create error knowledge: {e}")
    
    async def update_from_optimizations(self):
        """Update knowledge base from successful optimizations."""
        try:
            logger.info("Analyzing optimization patterns...")
            
            # Search for high-scoring evaluations
            evaluation_memories = await self.memory.search_memories(
                query="optimization improve performance",
                n_results=15,
                memory_type="evaluation"
            )
            
            # Filter for high-scoring evaluations
            high_score_evaluations = [
                memory for memory, _ in evaluation_memories
                if memory.metadata.get("overall_score", 0) >= 0.8
            ]
            
            if len(high_score_evaluations) >= 3:
                optimization_knowledge = await self._extract_optimization_patterns(
                    high_score_evaluations
                )
                
                if optimization_knowledge:
                    await self.knowledge_base.add_knowledge(optimization_knowledge)
                    logger.info("Added optimization knowledge")
            
        except Exception as e:
            logger.error(f"Failed to update from optimizations: {e}")
    
    async def _extract_optimization_patterns(
        self,
        evaluations: List[MemoryEntry]
    ) -> Optional[KnowledgeEntry]:
        """Extract optimization patterns from successful evaluations."""
        try:
            # Combine evaluation content
            eval_contents = [eval_mem.content for eval_mem in evaluations[:5]]
            combined_content = "\n\n".join(eval_contents)
            
            extraction_prompt = f"""
            Extract optimization patterns from these successful evaluations:
            
            {combined_content}
            
            Identify common factors that led to high performance scores.
            Focus on actionable patterns that can be applied to future tasks.
            
            Return a concise summary of the key optimization principles discovered.
            """
            
            pattern_summary = await llm_manager.generate_response(
                prompt=extraction_prompt,
                temperature=0.3,
                max_tokens=400
            )
            
            return KnowledgeEntry(
                content=f"Optimization Patterns:\n\n{pattern_summary}",
                category="optimization",
                tags=["optimization", "performance", "best_practices"],
                confidence=0.8,
                source="optimization_analysis",
                metadata={
                    "evaluation_count": len(evaluations),
                    "auto_generated": True,
                    "analysis_timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to extract optimization patterns: {e}")
            return None
    
    async def get_improvement_suggestions(self) -> List[Dict[str, Any]]:
        """Get suggestions for improving the knowledge base."""
        try:
            knowledge_stats = await self.knowledge_base.get_knowledge_stats()
            
            suggestions = []
            
            # Check for imbalanced categories
            categories = knowledge_stats.get("categories", {})
            if categories:
                total_entries = sum(categories.values())
                for category, count in categories.items():
                    ratio = count / total_entries
                    if ratio < 0.1:  # Less than 10% of total
                        suggestions.append({
                            "type": "category_balance",
                            "message": f"Category '{category}' has few entries ({count}). Consider adding more knowledge in this area.",
                            "priority": 0.6
                        })
            
            # Check confidence distribution
            confidence_dist = knowledge_stats.get("confidence_distribution", {})
            low_confidence_ratio = confidence_dist.get("low", 0) / max(knowledge_stats.get("total_entries", 1), 1)
            if low_confidence_ratio > 0.3:
                suggestions.append({
                    "type": "confidence_improvement",
                    "message": "Many knowledge entries have low confidence. Consider reviewing and validating them.",
                    "priority": 0.8
                })
            
            # Check for pending updates
            if len(self.pending_updates) > 5:
                suggestions.append({
                    "type": "pending_review",
                    "message": f"{len(self.pending_updates)} knowledge updates are pending review.",
                    "priority": 0.7
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to get improvement suggestions: {e}")
            return []
    
    async def review_pending_updates(self) -> Dict[str, Any]:
        """Review and process pending knowledge updates."""
        try:
            if not self.pending_updates:
                return {"message": "No pending updates to review"}
            
            reviewed = []
            approved = 0
            rejected = 0
            
            for update in self.pending_updates[:10]:  # Review up to 10
                candidate = update["candidate"]
                
                # Auto-approve if confidence improved or has supporting evidence
                if candidate.get("confidence", 0) >= 0.7:
                    entry = KnowledgeEntry.from_dict(update["entry"])
                    await self.knowledge_base.add_knowledge(entry)
                    approved += 1
                    reviewed.append(update)
                elif len(self.pending_updates) > 20:  # Reject old low-confidence updates
                    rejected += 1
                    reviewed.append(update)
            
            # Remove reviewed updates
            for update in reviewed:
                self.pending_updates.remove(update)
            
            return {
                "reviewed": len(reviewed),
                "approved": approved,
                "rejected": rejected,
                "remaining": len(self.pending_updates)
            }
            
        except Exception as e:
            logger.error(f"Failed to review pending updates: {e}")
            return {"error": str(e)}
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get knowledge update statistics."""
        return {
            "total_updates": len(self.update_history),
            "pending_updates": len(self.pending_updates),
            "recent_updates": len([
                update for update in self.update_history
                if (datetime.now() - datetime.fromisoformat(update["timestamp"])).days <= 7
            ])
        }
