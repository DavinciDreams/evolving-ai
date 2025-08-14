"""
Long-term memory management using vector embeddings and ChromaDB.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
import numpy as np
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class MemoryMetadataHandler:
    """Handles memory metadata operations"""
    
    @staticmethod
    def sanitize_for_chroma(metadata: Dict[str, Any]) -> Dict[str, Union[str, int, float, bool, None]]:
        """Sanitize metadata for ChromaDB storage."""
        sanitized = {}
        
        for key, value in metadata.items():
            if value is None or isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[f"{key}_json"] = json.dumps(value)
            elif isinstance(value, (list, tuple)):
                sanitized[f"{key}_json"] = json.dumps(list(value))
            else:
                sanitized[key] = str(value)
        
        return sanitized

    @staticmethod
    def prepare_metadata(entry: 'MemoryEntry') -> Dict[str, Any]:
        """Prepare metadata for storage."""
        metadata = {
            "memory_type": entry.memory_type,
            "timestamp": entry.timestamp.isoformat(),
            **entry.metadata
        }
        return MemoryMetadataHandler.sanitize_for_chroma(metadata)


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

    @classmethod
    def from_chroma_result(cls, doc_id: str, content: str, metadata: Dict[str, Any]) -> "MemoryEntry":
        """Create memory entry from ChromaDB result."""
        filtered_metadata = {k: v for k, v in metadata.items() 
                           if k not in ["memory_type", "timestamp"]}
        return cls(
            content=content,
            memory_type=metadata.get("memory_type", "general"),
            metadata=filtered_metadata,
            timestamp=datetime.fromisoformat(metadata["timestamp"]),
            entry_id=doc_id
        )


class MemorySearchProcessor:
    """Handles memory search operations"""
    
    def __init__(self, collection):
        self.collection = collection

    def _calculate_similarity(self, distance: float) -> float:
        """Calculate similarity score from distance."""
        return 1 - distance

    def _create_memory_entry(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> MemoryEntry:
        """Create memory entry from search result data."""
        return MemoryEntry.from_chroma_result(doc_id, content, metadata)

    async def process_results(self, results: Dict[str, Any], similarity_threshold: float) -> List[Tuple[MemoryEntry, float]]:
        """Process and filter search results."""
        if not results["ids"]:
            return []
            
        memories = []
        for i, result in enumerate(zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
            results["documents"][0]
        )):
            doc_id, distance, metadata, content = result
            similarity = self._calculate_similarity(distance)
            
            if similarity >= similarity_threshold:
                entry = self._create_memory_entry(doc_id, content, metadata)
                memories.append((entry, similarity))
                
        return memories

    def get_where_clause(self, memory_type: Optional[str]) -> Optional[Dict[str, str]]:
        """Generate where clause for search query."""
        return {"memory_type": memory_type} if memory_type else None


class MemoryOperations:
    """Handles core memory operations"""
    
    def __init__(self, collection, embedding_model):
        self.collection = collection
        self.embedding_model = embedding_model
        self.metadata_handler = MemoryMetadataHandler()

    async def generate_embedding(self, content: str) -> List[float]:
        """Generate embedding for content."""
        return self.embedding_model.encode(content).tolist()

    async def add_memory(self, entry: MemoryEntry) -> str:
        """Add a memory entry."""
        entry.embedding = await self.generate_embedding(entry.content)
        sanitized_metadata = self.metadata_handler.prepare_metadata(entry)
        
        self.collection.add(
            ids=[entry.id],
            embeddings=[entry.embedding],
            documents=[entry.content],
            metadatas=[sanitized_metadata]
        )
        return entry.id

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory."""
        results = self.collection.get(ids=[memory_id])
        if not results["ids"]:
            return None
        return MemoryEntry.from_chroma_result(
            memory_id,
            results["documents"][0],
            results["metadatas"][0]
        )

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        self.collection.delete(ids=[memory_id])
        return True

    async def get_memory_type_distribution(self) -> Dict[str, int]:
        """Get distribution of memory types."""
        memory_types = {}
        all_data = self.collection.get()
        
        if all_data["metadatas"]:
            for metadata in all_data["metadatas"]:
                mem_type = metadata.get("memory_type", "general")
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1
                
        return memory_types

    async def get_entries_to_delete(self, num_entries: int) -> List[str]:
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


class LongTermMemory:
    """Long-term memory system using ChromaDB for vector storage."""
    
    def __init__(self):
        self.embedding_model = None
        self.client = None
        self.collection = None
        self.initialized = False
        self.search_processor = None
        self.memory_ops = None

    async def initialize(self):
        """Initialize the memory system."""
        try:
            await self._init_components()
            self.initialized = True
            logger.info("Long-term memory system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize memory system: {e}")
            raise

    async def _init_components(self):
        """Initialize all memory system components."""
        await self._init_directories()
        await self._init_embedding_model()
        await self._init_chroma_client()
        await self._init_collection()
        self._init_processors()

    def _init_processors(self):
        """Initialize search and memory processors."""
        self.search_processor = MemorySearchProcessor(self.collection)
        self.memory_ops = MemoryOperations(self.collection, self.embedding_model)

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

    async def _handle_memory_operation(self, operation_name: str, operation_func: callable, *args, **kwargs):
        """Generic handler for memory operations with error handling."""
        self._ensure_initialized()
        try:
            result = await operation_func(*args, **kwargs)
            logger.info(f"Successfully completed {operation_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to {operation_name}: {e}")
            raise
    
    def _ensure_initialized(self):
        """Ensure memory system is initialized."""
        if not self.initialized:
            raise RuntimeError("Memory system not initialized. Call initialize() first.")

    async def add_memory(self, entry: MemoryEntry) -> str:
        """Add a memory entry to the database."""
        return await self._handle_memory_operation(
            "add memory entry",
            self.memory_ops.add_memory,
            entry
        )

    async def search_memories(
        self,
        query: str,
        n_results: int = 5,
        memory_type: Optional[str] = None,
        similarity_threshold: float = 0.5
    ) -> List[Tuple[MemoryEntry, float]]:
        """Search for relevant memories based on query."""
        query_embedding = await self.memory_ops.generate_embedding(query)
        where_clause = self.search_processor.get_where_clause(memory_type)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_clause
        )
        
        return await self.search_processor.process_results(results, similarity_threshold)

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID."""
        return await self._handle_memory_operation(
            "get memory",
            self.memory_ops.get_memory,
            memory_id
        )

    async def update_memory(self, memory_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        if not await self.get_memory(memory_id):
            return False
        await self.delete_memory(memory_id)
        entry.id = memory_id
        await self.add_memory(entry)
        return True

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        return await self._handle_memory_operation(
            "delete memory",
            self.memory_ops.delete_memory,
            memory_id
        )

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""
        count = self.collection.count()
        memory_types = await self.memory_ops.get_memory_type_distribution()
        
        return {
            "total_memories": count,
            "memory_types": memory_types,
            "collection_name": config.memory_collection_name,
            "persist_directory": config.memory_persist_directory
        }

    async def cleanup_old_memories(self, max_entries: Optional[int] = None) -> int:
        """Clean up old memories to maintain performance."""
        max_entries = max_entries or config.max_memory_entries
        current_count = self.collection.count()
        
        if current_count <= max_entries:
            return 0
            
        entries_to_delete = await self.memory_ops.get_entries_to_delete(current_count - max_entries)
        self.collection.delete(ids=entries_to_delete)
        return len(entries_to_delete)