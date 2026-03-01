"""
Configuration management for the self-improving agent.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

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
    def openrouter_api_key(self) -> str:
        """Get OpenRouter API key."""
        return os.getenv("OPENROUTER_API_KEY", "")

    @property
    def zai_api_key(self) -> str:
        """Get Z AI API key."""
        return os.getenv("ZAI_API_KEY", "")

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
        return os.getenv("DEFAULT_LLM_PROVIDER", "anthropic")

    @property
    def default_model(self) -> str:
        """Get default model."""
        return os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")

    @property
    def evaluation_model(self) -> str:
        """Get evaluation model."""
        return os.getenv("EVALUATION_MODEL", "claude-3-5-sonnet-20241022")

    @property
    def evaluation_provider(self) -> str:
        """Get evaluation LLM provider."""
        return os.getenv("EVALUATION_PROVIDER", "")

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
    def enable_evaluation(self) -> bool:
        """Get evaluation enabled setting."""
        return os.getenv("ENABLE_EVALUATION", "true").lower() == "true"

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

    # Discord Integration Configuration
    @property
    def discord_bot_token(self) -> str:
        """Get Discord bot token."""
        return os.getenv("DISCORD_BOT_TOKEN", "")

    @property
    def discord_enabled(self) -> bool:
        """Get Discord integration enabled setting."""
        return os.getenv("DISCORD_ENABLED", "false").lower() == "true"

    @property
    def discord_channel_ids(self) -> list:
        """Get Discord channel IDs."""
        channels = os.getenv("DISCORD_CHANNEL_IDS", "")
        return [c.strip() for c in channels.split(",") if c.strip()]

    @property
    def discord_status_channel_id(self) -> str:
        """Get Discord status channel ID."""
        return os.getenv("DISCORD_STATUS_CHANNEL_ID", "")

    @property
    def discord_mention_required(self) -> bool:
        """Get Discord mention required setting."""
        return os.getenv("DISCORD_MENTION_REQUIRED", "false").lower() == "true"

    @property
    def discord_max_message_length(self) -> int:
        """Get Discord max message length."""
        return int(os.getenv("DISCORD_MAX_MESSAGE_LENGTH", "2000"))

    @property
    def discord_typing_indicator(self) -> bool:
        """Get Discord typing indicator setting."""
        return os.getenv("DISCORD_TYPING_INDICATOR", "true").lower() == "true"

    @property
    def discord_embed_responses(self) -> bool:
        """Get Discord embed responses setting."""
        return os.getenv("DISCORD_EMBED_RESPONSES", "true").lower() == "true"

    @property
    def discord_command_prefix(self) -> str:
        """Get Discord command prefix."""
        return os.getenv("DISCORD_COMMAND_PREFIX", "")

    @property
    def discord_rate_limit_messages(self) -> int:
        """Get Discord rate limit messages."""
        return int(os.getenv("DISCORD_RATE_LIMIT_MESSAGES", "10"))

    @property
    def discord_cooldown_seconds(self) -> int:
        """Get Discord cooldown seconds."""
        return int(os.getenv("DISCORD_COOLDOWN_SECONDS", "2"))

    @property
    def discord_status_updates_enabled(self) -> bool:
        """Get Discord status updates enabled setting."""
        return os.getenv("DISCORD_STATUS_UPDATES_ENABLED", "true").lower() == "true"

    @property
    def discord_status_on_improvement(self) -> bool:
        """Get Discord status on improvement setting."""
        return os.getenv("DISCORD_STATUS_ON_IMPROVEMENT", "true").lower() == "true"

    @property
    def discord_status_on_knowledge_update(self) -> bool:
        """Get Discord status on knowledge update setting."""
        return os.getenv("DISCORD_STATUS_ON_KNOWLEDGE_UPDATE", "true").lower() == "true"

    @property
    def discord_status_on_high_quality(self) -> bool:
        """Get Discord status on high quality interaction setting."""
        return os.getenv("DISCORD_STATUS_ON_HIGH_QUALITY", "false").lower() == "true"

    @property
    def github_branch(self) -> str:
        """Get GitHub target branch."""
        return os.getenv("GITHUB_BRANCH", "main")

    @property
    def api_server_url(self) -> str:
        """Get API server URL for internal calls."""
        return os.getenv("API_SERVER_URL", "http://localhost:8000")

    # Web Search Integration Configuration
    @property
    def web_search_enabled(self) -> bool:
        """Get web search enabled setting."""
        return os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"

    @property
    def web_search_default_provider(self) -> str:
        """Get default web search provider."""
        return os.getenv("WEB_SEARCH_DEFAULT_PROVIDER", "duckduckgo")

    @property
    def web_search_max_results(self) -> int:
        """Get max web search results."""
        return int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))

    @property
    def tavily_api_key(self) -> str:
        """Get Tavily API key."""
        return os.getenv("TAVILY_API_KEY", "")

    @property
    def serpapi_key(self) -> str:
        """Get SerpAPI key."""
        return os.getenv("SERPAPI_KEY", "")

    # Tool Use Configuration
    @property
    def enable_tool_use(self) -> bool:
        """Get tool use enabled setting."""
        return os.getenv("ENABLE_TOOL_USE", "true").lower() == "true"

    @property
    def max_tool_iterations(self) -> int:
        """Get maximum tool-use iterations per request."""
        return int(os.getenv("MAX_TOOL_ITERATIONS", "15"))

    @property
    def tool_sandbox_dir(self) -> str:
        """Get sandbox directory for tool file/command operations.

        In Docker this should be /app. Tools will restrict file reads,
        directory listings, and command execution to this directory.
        An empty string disables sandboxing (local dev default).
        """
        return os.getenv("TOOL_SANDBOX_DIR", "")

    # TPMJS Integration Configuration
    @property
    def tpmjs_api_key(self) -> str:
        """Get TPMJS API key."""
        return os.getenv("TPMJS_API_KEY", "")

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as a dictionary."""
        return {
            "openai_api_key": "***" if self.openai_api_key else "",
            "anthropic_api_key": "***" if self.anthropic_api_key else "",
            "openrouter_api_key": "***" if self.openrouter_api_key else "",
            "zai_api_key": "***" if self.zai_api_key else "",
            "log_level": self.log_level,
            "log_file": self.log_file,
            "memory_persist_directory": self.memory_persist_directory,
            "memory_collection_name": self.memory_collection_name,
            "max_memory_entries": self.max_memory_entries,
            "default_llm_provider": self.default_llm_provider,
            "default_model": self.default_model,
            "evaluation_model": self.evaluation_model,
            "evaluation_provider": self.evaluation_provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enable_self_modification": self.enable_self_modification,
            "backup_directory": self.backup_directory,
            "max_modification_attempts": self.max_modification_attempts,
            "require_validation": self.require_validation,
            "knowledge_base_path": self.knowledge_base_path,
            "auto_update_knowledge": self.auto_update_knowledge,
            "knowledge_similarity_threshold": self.knowledge_similarity_threshold,
            "discord_bot_token": "***" if self.discord_bot_token else "",
            "discord_enabled": self.discord_enabled,
            "discord_channel_ids": self.discord_channel_ids,
            "discord_status_channel_id": self.discord_status_channel_id,
            "discord_mention_required": self.discord_mention_required,
            "discord_max_message_length": self.discord_max_message_length,
            "discord_typing_indicator": self.discord_typing_indicator,
            "discord_embed_responses": self.discord_embed_responses,
            "discord_command_prefix": self.discord_command_prefix,
            "discord_rate_limit_messages": self.discord_rate_limit_messages,
            "discord_cooldown_seconds": self.discord_cooldown_seconds,
            "discord_status_updates_enabled": self.discord_status_updates_enabled,
            "discord_status_on_improvement": self.discord_status_on_improvement,
            "discord_status_on_knowledge_update": self.discord_status_on_knowledge_update,
            "discord_status_on_high_quality": self.discord_status_on_high_quality,
            "github_branch": self.github_branch,
            "api_server_url": self.api_server_url,
            "web_search_enabled": self.web_search_enabled,
            "web_search_default_provider": self.web_search_default_provider,
            "web_search_max_results": self.web_search_max_results,
            "tavily_api_key": "***" if self.tavily_api_key else "",
            "serpapi_key": "***" if self.serpapi_key else "",
            "enable_tool_use": self.enable_tool_use,
            "max_tool_iterations": self.max_tool_iterations,
            "tool_sandbox_dir": self.tool_sandbox_dir,
            "tpmjs_api_key": "***" if self.tpmjs_api_key else "",
        }

    def ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.memory_persist_directory,
            self.backup_directory,
            self.knowledge_base_path,
            os.path.dirname(self.log_file) if os.path.dirname(self.log_file) else ".",
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
