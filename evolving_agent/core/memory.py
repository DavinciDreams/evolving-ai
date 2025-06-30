"""
Long-term memory management using vector embeddings and ChromaDB.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

import chromadb
from chromadb.config import Settings
import numpy as np
from sentence_transformers import SentenceTransformer

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


def sanitize_metadata_for_chroma(metadata: Dict[str, Any]) -> Dict[str, Union[str, int, float, bool, None]]:
    """Sanitize metadata for ChromaDB storage."""
    sanitized = {}
    
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = None
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[f"{key}_json"] = json.dumps(value)
        elif isinstance(value, (list, tuple)):
            sanitized[f"{key}_json"] = json.dumps(list(value))
        else:
            sanitized[key] = str(value)
    
    return sanitized


class MemoryEntry:
    """Represents a single memory entry."""
    
    def __init__(
        self,
        content: str,
        memory_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        entry_id: Optional[str] = None
    ):
        self.id = entry_id or str(uuid.uuid4())
        self.content = content
        self.memory_type = memory_type
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
        self.embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory entry to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create memory entry from dictionary."""
        return cls(
            content=data["content"],
            memory_type=data.get("memory_type", "general"),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            entry_id=data["id"]
        )


class LongTermMemory:
    """Long-term memory system using ChromaDB for vector storage."""
    
    def __init__(self):
        self.embedding_model = None
        self.client = None
        self.collection = None
        self.initialized = False

    async def initialize(self):
        """Initialize the memory system."""
        try:
            await self._init_directories()
            await self._init_embedding_model()
            await self._init_chroma_client()
            await self._init_collection()
            self.initialized = True
            logger.info("Long-term memory system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize memory system: {e}")
            raise

    async def _init_directories(self):
        """Initialize required directories."""
        config.ensure_directories()
        
    async def _init_embedding_model(self):
        """Initialize the embedding model."""
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded")
        
    async def _init_chroma_client(self):
        """Initialize ChromaDB client."""
        self.client = chromadb.PersistentClient(
            path=config.memory_persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
    async def _init_collection(self):
        """Initialize ChromaDB collection."""
        try:
            self.collection = self.client.get_collection(name=config.memory_collection_name)
            logger.info(f"Loaded existing memory collection: {config.memory_collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=config.memory_collection_name,
                metadata={"description": "Agent long-term memory"}
            )
            logger.info(f"Created new memory collection: {config.memory_collection_name}")
    
    def _ensure_initialized(self):
        """Ensure memory system is initialized."""
        if not self.initialized:
            raise RuntimeError("Memory system not initialized. Call initialize() first.")

    async def _generate_embedding(self, content: str) -> List[float]:
        """Generate embedding for content."""
        return self.embedding_model.encode(content).tolist()

    async def _prepare_metadata(self, entry: MemoryEntry) -> Dict[str, Any]:
        """Prepare and sanitize metadata for storage."""
        metadata = {
            "memory_type": entry.memory_type,
            "timestamp": entry.timestamp.isoformat(),
            **entry.metadata
        }
        return sanitize_metadata_for_chroma(metadata)

    async def _add_entry_to_collection(self, entry: MemoryEntry, metadata: Dict[str, Any]):
        """Add entry to ChromaDB collection."""
        self.collection.add(
            ids=[entry.id],
            embeddings=[entry.embedding],
            documents=[entry.content],
            metadatas=[metadata]
        )

    async def add_memory(self, entry: MemoryEntry) -> str:
        """Add a memory entry to the database."""
        self._ensure_initialized()
        
        try:
            entry.embedding = await self._generate_embedding(entry.content)
            sanitized_metadata = await self._prepare_metadata(entry)
            await self._add_entry_to_collection(entry, sanitized_metadata)
            
            logger.info(f"Added memory entry: {entry.id}")
            return entry.id
            
        except Exception as e:
            logger.error(f"Failed to add memory entry: {e}")
            raise

    async def _create_memory_entry_from_results(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> MemoryEntry:
        """Create MemoryEntry object from search results."""
        return MemoryEntry(
            content=content,
            memory_type=metadata.get("memory_type", "general"),
            metadata={k: v for k, v in metadata.items() 
                    if k not in ["memory_type", "timestamp"]},
            timestamp=datetime.fromisoformat(metadata["timestamp"]),
            entry_id=doc_id
        )

    async def _process_search_results(self, results: Dict[str, Any], similarity_threshold: float) -> List[Tuple[MemoryEntry, float]]:
        """Process and filter search results."""
        memories = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                
                if similarity >= similarity_threshold:
                    metadata = results["metadatas"][0][i]
                    content = results["documents"][0][i]
                    entry = await self._create_memory_entry_from_results(doc_id, content, metadata)
                    memories.append((entry, similarity))
        return memories

    async def search_memories(
        self,
        query: str,
        n_results: int = 5,
        memory_type: Optional[str] = None,
        similarity_threshold: float = 0.5
    ) -> List[Tuple[MemoryEntry, float]]:
        """Search for relevant memories based on query."""
        self._ensure_initialized()
        
        try:
            query_embedding = await self._generate_embedding(query)
            where_clause = {"memory_type": memory_type} if memory_type else None
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause
            )
            
            memories = await self._process_search_results(results, similarity_threshold)
            logger.info(f"Found {len(memories)} relevant memories for query")
            return memories
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            raise

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID."""
        self._ensure_initialized()
        
        try:
            results = self.collection.get(ids=[memory_id])
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                content = results["documents"][0]
                return await self._create_memory_entry_from_results(memory_id, content, metadata)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get memory {memory_id}: {e}")
            raise

    async def update_memory(self, memory_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        self._ensure_initialized()
        
        try:
            if not await self.get_memory(memory_id):
                return False
                
            self.collection.delete(ids=[memory_id])
            entry.id = memory_id
            await self.add_memory(entry)
            
            logger.info(f"Updated memory entry: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}")
            raise

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        self._ensure_initialized()
        
        try:
            self.collection.delete(ids=[memory_id])
            logger.info(f"Deleted memory entry: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            raise

    async def _get_memory_type_distribution(self) -> Dict[str, int]:
        """Get distribution of memory types."""
        memory_types = {}
        all_data = self.collection.get()
        
        if all_data["metadatas"]:
            for metadata in all_data["metadatas"]:
                mem_type = metadata.get("memory_type", "general")
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1
                
        return memory_types

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""
        self._ensure_initialized()
        
        try:
            count = self.collection.count()
            memory_types = await self._get_memory_type_distribution()
            
            return {
                "total_memories": count,
                "memory_types": memory_types,
                "collection_name": config.memory_collection_name,
                "persist_directory": config.memory_persist_directory
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            raise

    async def _get_entries_to_delete(self, num_entries: int) -> List[str]:
        """Get IDs of oldest entries to delete."""
        all_data = self.collection.get()
        if not all_data["ids"]:
            return []
            
        entries_with_timestamps = [
            (entry_id, datetime.fromisoformat(metadata["timestamp"]))
            for entry_id, metadata in zip(all_data["ids"], all_data["metadatas"])
        ]
        entries_with_timestamps.sort(key=lambda x: x[1])
        
        return [entry[0] for entry in entries_with_timestamps[:num_entries]]

    async def cleanup_old_memories(self, max_entries: Optional[int] = None) -> int:
        """Clean up old memories to maintain performance."""
        self._ensure_initialized()
        
        try:
            max_entries = max_entries or config.max_memory_entries
            current_count = self.collection.count()
            
            if current_count <= max_entries:
                return 0
                
            entries_to_delete = await self._get_entries_to_delete(current_count - max_entries)
            self.collection.delete(ids=entries_to_delete)
            
            logger.info(f"Cleaned up {len(entries_to_delete)} old memory entries")
            return len(entries_to_delete)
            
        except Exception as e:
            logger.error(f"Failed to cleanup memories: {e}")
            raise