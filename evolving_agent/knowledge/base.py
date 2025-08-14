"""
Knowledge base management system.
"""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class KnowledgeEntry:
    """Represents a knowledge base entry."""

    def __init__(
        self,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        entry_id: Optional[str] = None,
    ):
        self.id = entry_id or self._generate_id(content)
        self.content = content
        self.category = category
        self.tags = tags or []
        self.confidence = confidence
        self.source = source
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.access_count = 0
        self.last_accessed = None

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for the knowledge entry."""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge entry to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        """Create knowledge entry from dictionary."""
        entry = cls(
            content=data["content"],
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "manual"),
            metadata=data.get("metadata", {}),
            entry_id=data["id"],
        )

        entry.created_at = datetime.fromisoformat(data["created_at"])
        entry.updated_at = datetime.fromisoformat(data["updated_at"])
        entry.access_count = data.get("access_count", 0)
        if data.get("last_accessed"):
            entry.last_accessed = datetime.fromisoformat(data["last_accessed"])

        return entry

    def update_access(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now()


class KnowledgeBase:
    """Knowledge base management system."""

    def __init__(self):
        self.knowledge_file = Path(config.knowledge_base_path) / "knowledge.json"
        self.categories_file = Path(config.knowledge_base_path) / "categories.json"
        self.knowledge: Dict[str, KnowledgeEntry] = {}
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.initialized = False

    async def initialize(self):
        """Initialize the knowledge base."""
        try:
            logger.info("Initializing knowledge base...")

            # Ensure knowledge base directory exists
            config.ensure_directories()
            self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing knowledge
            await self._load_knowledge()
            await self._load_categories()

            # Initialize default categories if empty
            if not self.categories:
                await self._initialize_default_categories()

            self.initialized = True
            logger.info(
                f"Knowledge base initialized with {len(self.knowledge)} entries"
            )

        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
            raise

    def _ensure_initialized(self):
        """Ensure knowledge base is initialized."""
        if not self.initialized:
            raise RuntimeError(
                "Knowledge base not initialized. Call initialize() first."
            )

    async def _load_knowledge(self):
        """Load knowledge from file."""
        try:
            if self.knowledge_file.exists():
                with open(self.knowledge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for entry_data in data.get("entries", []):
                    entry = KnowledgeEntry.from_dict(entry_data)
                    self.knowledge[entry.id] = entry

                logger.info(f"Loaded {len(self.knowledge)} knowledge entries")
            else:
                logger.info("No existing knowledge file found, starting fresh")

        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")
            self.knowledge = {}

    async def _load_categories(self):
        """Load categories from file."""
        try:
            if self.categories_file.exists():
                with open(self.categories_file, "r", encoding="utf-8") as f:
                    self.categories = json.load(f)

                logger.info(f"Loaded {len(self.categories)} categories")
            else:
                self.categories = {}

        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            self.categories = {}

    async def _initialize_default_categories(self):
        """Initialize default knowledge categories."""
        default_categories = {
            "problem_solving": {
                "description": "Solutions and approaches to various problems",
                "tags": ["solution", "approach", "methodology"],
                "priority": 0.9,
            },
            "learning_patterns": {
                "description": "Patterns and insights from learning experiences",
                "tags": ["pattern", "insight", "learning"],
                "priority": 0.8,
            },
            "error_resolution": {
                "description": "Information about errors and their resolutions",
                "tags": ["error", "bug", "fix", "resolution"],
                "priority": 0.85,
            },
            "optimization": {
                "description": "Performance and efficiency improvements",
                "tags": ["optimization", "performance", "efficiency"],
                "priority": 0.7,
            },
            "best_practices": {
                "description": "Best practices and recommendations",
                "tags": ["best_practice", "recommendation", "guideline"],
                "priority": 0.75,
            },
            "domain_knowledge": {
                "description": "Domain-specific knowledge and expertise",
                "tags": ["domain", "expertise", "knowledge"],
                "priority": 0.8,
            },
        }

        self.categories = default_categories
        await self._save_categories()

    async def add_knowledge(self, entry: KnowledgeEntry) -> str:
        """Add a knowledge entry."""
        self._ensure_initialized()

        try:
            # Check if similar knowledge already exists
            existing = await self.find_similar_knowledge(entry.content)

            if existing and existing[0][1] > config.knowledge_similarity_threshold:
                # Update existing entry instead of creating duplicate
                existing_entry = existing[0][0]
                await self.update_knowledge(existing_entry.id, entry)
                logger.info(f"Updated existing knowledge entry: {existing_entry.id}")
                return existing_entry.id

            # Add new entry
            self.knowledge[entry.id] = entry
            await self._save_knowledge()

            logger.info(f"Added new knowledge entry: {entry.id}")
            return entry.id

        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            raise

    async def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeEntry]:
        """Get knowledge entry by ID."""
        self._ensure_initialized()

        entry = self.knowledge.get(knowledge_id)
        if entry:
            entry.update_access()
            await self._save_knowledge()

        return entry

    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        max_results: int = 10,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Search knowledge base."""
        self._ensure_initialized()

        try:
            matching_entries = []

            for entry in self.knowledge.values():
                # Filter by category
                if category and entry.category != category:
                    continue

                # Filter by confidence
                if entry.confidence < min_confidence:
                    continue

                # Filter by tags
                if tags and not any(tag in entry.tags for tag in tags):
                    continue

                # Calculate relevance score
                relevance = self._calculate_relevance(query, entry)

                if relevance > 0.3:  # Minimum relevance threshold
                    matching_entries.append((entry, relevance))
                    entry.update_access()

            # Sort by relevance
            matching_entries.sort(key=lambda x: x[1], reverse=True)

            # Save access updates
            if matching_entries:
                await self._save_knowledge()

            return matching_entries[:max_results]

        except Exception as e:
            logger.error(f"Failed to search knowledge: {e}")
            return []

    def _calculate_relevance(self, query: str, entry: KnowledgeEntry) -> float:
        """Calculate relevance score between query and knowledge entry."""
        try:
            query_lower = query.lower()
            content_lower = entry.content.lower()

            # Simple relevance scoring
            score = 0.0

            # Exact phrase matches
            if query_lower in content_lower:
                score += 0.8

            # Word matches
            query_words = set(query_lower.split())
            content_words = set(content_lower.split())

            if query_words:
                word_overlap = len(query_words.intersection(content_words)) / len(
                    query_words
                )
                score += word_overlap * 0.6

            # Tag matches
            query_words_in_tags = any(
                word in " ".join(entry.tags).lower() for word in query_words
            )
            if query_words_in_tags:
                score += 0.3

            # Category relevance
            if entry.category in query_lower:
                score += 0.2

            # Boost by confidence and access frequency
            score *= entry.confidence
            score += min(
                entry.access_count * 0.01, 0.1
            )  # Small boost for frequently accessed

            return min(score, 1.0)

        except Exception as e:
            logger.error(f"Failed to calculate relevance: {e}")
            return 0.0

    async def find_similar_knowledge(
        self, content: str, threshold: float = 0.8
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Find similar knowledge entries."""
        self._ensure_initialized()

        try:
            similar_entries = []

            for entry in self.knowledge.values():
                similarity = self._calculate_similarity(content, entry.content)

                if similarity >= threshold:
                    similar_entries.append((entry, similarity))

            similar_entries.sort(key=lambda x: x[1], reverse=True)
            return similar_entries

        except Exception as e:
            logger.error(f"Failed to find similar knowledge: {e}")
            return []

    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two pieces of content."""
        try:
            # Simple Jaccard similarity
            words1 = set(content1.lower().split())
            words2 = set(content2.lower().split())

            if not words1 and not words2:
                return 1.0

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            return len(intersection) / len(union) if union else 0.0

        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0

    async def update_knowledge(
        self, knowledge_id: str, updated_entry: KnowledgeEntry
    ) -> bool:
        """Update existing knowledge entry."""
        self._ensure_initialized()

        try:
            if knowledge_id not in self.knowledge:
                return False

            # Preserve original metadata
            original = self.knowledge[knowledge_id]
            updated_entry.id = knowledge_id
            updated_entry.created_at = original.created_at
            updated_entry.access_count = original.access_count
            updated_entry.last_accessed = original.last_accessed
            updated_entry.updated_at = datetime.now()

            self.knowledge[knowledge_id] = updated_entry
            await self._save_knowledge()

            logger.info(f"Updated knowledge entry: {knowledge_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update knowledge: {e}")
            return False

    async def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge entry."""
        self._ensure_initialized()

        try:
            if knowledge_id in self.knowledge:
                del self.knowledge[knowledge_id]
                await self._save_knowledge()
                logger.info(f"Deleted knowledge entry: {knowledge_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete knowledge: {e}")
            return False

    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        self._ensure_initialized()

        try:
            category_counts = {}
            confidence_distribution = {"high": 0, "medium": 0, "low": 0}
            source_counts = {}

            for entry in self.knowledge.values():
                # Category counts
                category_counts[entry.category] = (
                    category_counts.get(entry.category, 0) + 1
                )

                # Confidence distribution
                if entry.confidence >= 0.8:
                    confidence_distribution["high"] += 1
                elif entry.confidence >= 0.5:
                    confidence_distribution["medium"] += 1
                else:
                    confidence_distribution["low"] += 1

                # Source counts
                source_counts[entry.source] = source_counts.get(entry.source, 0) + 1

            return {
                "total_entries": len(self.knowledge),
                "categories": category_counts,
                "confidence_distribution": confidence_distribution,
                "sources": source_counts,
                "file_path": str(self.knowledge_file),
            }

        except Exception as e:
            logger.error(f"Failed to get knowledge stats: {e}")
            return {"error": str(e)}

    async def _save_knowledge(self):
        """Save knowledge to file."""
        try:
            data = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_entries": len(self.knowledge),
                },
                "entries": [entry.to_dict() for entry in self.knowledge.values()],
            }

            with open(self.knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")
            raise

    async def _save_categories(self):
        """Save categories to file."""
        try:
            with open(self.categories_file, "w", encoding="utf-8") as f:
                json.dump(self.categories, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save categories: {e}")
            raise

    async def add_category(
        self, name: str, description: str, tags: List[str], priority: float = 0.5
    ):
        """Add a new knowledge category."""
        self._ensure_initialized()

        self.categories[name] = {
            "description": description,
            "tags": tags,
            "priority": priority,
        }

        await self._save_categories()
        logger.info(f"Added category: {name}")

    def get_categories(self) -> Dict[str, Dict[str, Any]]:
        """Get all knowledge categories."""
        return self.categories.copy()
