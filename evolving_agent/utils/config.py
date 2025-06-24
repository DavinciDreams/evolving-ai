"""
Configuration management for the self-improving agent.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration manager for the agent."""
    
    def __init__(self, env_file: Optional[str] = None):
        """Initialize configuration."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key."""
        return os.getenv("OPENAI_API_KEY", "")
    
    @property
    def anthropic_api_key(self) -> str:
        """Get Anthropic API key."""
        return os.getenv("ANTHROPIC_API_KEY", "")
    
    @property
    def log_level(self) -> str:
        """Get logging level."""
        return os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def log_file(self) -> str:
        """Get log file path."""
        return os.getenv("LOG_FILE", "agent.log")
    
    @property
    def memory_persist_directory(self) -> str:
        """Get memory persistence directory."""
        return os.getenv("MEMORY_PERSIST_DIRECTORY", "./memory_db")
    
    @property
    def memory_collection_name(self) -> str:
        """Get memory collection name."""
        return os.getenv("MEMORY_COLLECTION_NAME", "agent_memory")
    
    @property
    def max_memory_entries(self) -> int:
        """Get maximum memory entries."""
        return int(os.getenv("MAX_MEMORY_ENTRIES", "10000"))
    
    @property
    def default_llm_provider(self) -> str:
        """Get default LLM provider."""
        return os.getenv("DEFAULT_LLM_PROVIDER", "openai")
    
    @property
    def default_model(self) -> str:
        """Get default model."""
        return os.getenv("DEFAULT_MODEL", "gpt-4")
    
    @property
    def evaluation_model(self) -> str:
        """Get evaluation model."""
        return os.getenv("EVALUATION_MODEL", "gpt-4")
    
    @property
    def temperature(self) -> float:
        """Get temperature setting."""
        return float(os.getenv("TEMPERATURE", "0.7"))
    
    @property
    def max_tokens(self) -> int:
        """Get max tokens setting."""
        return int(os.getenv("MAX_TOKENS", "2048"))
    
    @property
    def enable_self_modification(self) -> bool:
        """Get self-modification setting."""
        return os.getenv("ENABLE_SELF_MODIFICATION", "true").lower() == "true"
    
    @property
    def backup_directory(self) -> str:
        """Get backup directory."""
        return os.getenv("BACKUP_DIRECTORY", "./backups")
    
    @property
    def max_modification_attempts(self) -> int:
        """Get max modification attempts."""
        return int(os.getenv("MAX_MODIFICATION_ATTEMPTS", "3"))
    
    @property
    def require_validation(self) -> bool:
        """Get validation requirement setting."""
        return os.getenv("REQUIRE_VALIDATION", "true").lower() == "true"
    
    @property
    def knowledge_base_path(self) -> str:
        """Get knowledge base path."""
        return os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")
    
    @property
    def auto_update_knowledge(self) -> bool:
        """Get auto update knowledge setting."""
        return os.getenv("AUTO_UPDATE_KNOWLEDGE", "true").lower() == "true"
    
    @property
    def knowledge_similarity_threshold(self) -> float:
        """Get knowledge similarity threshold."""
        return float(os.getenv("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.8"))
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as a dictionary."""
        return {
            "openai_api_key": "***" if self.openai_api_key else "",
            "anthropic_api_key": "***" if self.anthropic_api_key else "",
            "log_level": self.log_level,
            "log_file": self.log_file,
            "memory_persist_directory": self.memory_persist_directory,
            "memory_collection_name": self.memory_collection_name,
            "max_memory_entries": self.max_memory_entries,
            "default_llm_provider": self.default_llm_provider,
            "default_model": self.default_model,
            "evaluation_model": self.evaluation_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enable_self_modification": self.enable_self_modification,
            "backup_directory": self.backup_directory,
            "max_modification_attempts": self.max_modification_attempts,
            "require_validation": self.require_validation,
            "knowledge_base_path": self.knowledge_base_path,
            "auto_update_knowledge": self.auto_update_knowledge,
            "knowledge_similarity_threshold": self.knowledge_similarity_threshold,
        }
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.memory_persist_directory,
            self.backup_directory,
            self.knowledge_base_path,
            os.path.dirname(self.log_file) if os.path.dirname(self.log_file) else "."
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
