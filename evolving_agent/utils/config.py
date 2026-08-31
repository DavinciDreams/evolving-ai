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
    def openai_base_url(self) -> str:
        """Get OpenAI-compatible API base URL."""
        return os.getenv("OPENAI_BASE_URL", "").rstrip("/")

    @property
    def openai_model(self) -> str:
        """Get OpenAI or OpenAI-compatible model name."""
        return os.getenv("OPENAI_MODEL", "gpt-4")

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
    def zai_base_url(self) -> str:
        """Get Z AI base URL."""
        return os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4")

    @property
    def zai_model(self) -> str:
        """Get Z AI model name."""
        return os.getenv("ZAI_MODEL", "glm-5.1")

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
    def memory_backend(self) -> str:
        """Get the authoritative memory backend.

        HAM is the production default. ``chroma`` remains available only for
        local tests and the controlled migration/rollback window.
        """
        return os.getenv("MEMORY_BACKEND", "ham").strip().lower()

    @property
    def legacy_memory_read_only(self) -> bool:
        """Whether the legacy Chroma backend must reject writes."""
        return os.getenv("LEGACY_MEMORY_READ_ONLY", "true").lower() == "true"

    @property
    def ham_api_url(self) -> str:
        """Get the transport-neutral HAM REST API base URL."""
        return os.getenv("HAM_API_URL", "https://ham.flobots.xyz").rstrip("/")

    @property
    def ham_api_key(self) -> str:
        """Get Katbot's managed HAM service credential."""
        return os.getenv("HAM_API_KEY", "")

    @property
    def ham_project(self) -> str:
        """Get the dedicated HAM project slug for Evolving AI."""
        return os.getenv("HAM_PROJECT", "evolving-ai")

    @property
    def ham_scope(self) -> str:
        """Get the single least-privilege scope requested by Katbot."""
        return os.getenv("HAM_SCOPE", "project:evolving-ai")

    @property
    def ham_repo(self) -> str:
        """Get repository provenance attached to Katbot memories."""
        return os.getenv("HAM_REPO", "DavinciDreams/evolving-ai")

    @property
    def ham_expected_agent_id(self) -> str:
        """Get the server-bound AgentPrincipal expected on HAM writes."""
        return os.getenv("HAM_EXPECTED_AGENT_ID", "katbot-evolving-ai")

    @property
    def ham_timeout_seconds(self) -> float:
        """Get the timeout for HAM REST requests."""
        return float(os.getenv("HAM_TIMEOUT_SECONDS", "30"))

    @property
    def persistent_data_dir(self) -> str:
        """Get persistent data directory for sessions, state, and SQLite data."""
        return os.getenv(
            "PERSISTENT_DATA_DIR",
            str(Path(self.memory_persist_directory).parent / "persistent_data"),
        )

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
        return os.getenv("DEFAULT_LLM_PROVIDER", "zai")

    @property
    def default_model(self) -> str:
        """Get default model."""
        return os.getenv("DEFAULT_MODEL", "glm-5.1")

    @property
    def default_model_override(self) -> str:
        """Explicit cross-provider model override; empty means provider default."""
        return os.getenv("DEFAULT_MODEL", "")

    @property
    def selected_model(self) -> str:
        """Resolve the exact model shared by chat and bounded learning."""
        from ..integrations.provider_config import resolve_provider

        return resolve_provider(self).model

    @property
    def evaluation_model(self) -> str:
        """Get evaluation model."""
        return os.getenv("EVALUATION_MODEL", "glm-5.1")

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
        return os.getenv("ENABLE_SELF_MODIFICATION", "false").lower() == "true"

    @property
    def auto_pr_enabled(self) -> bool:
        """Get automatic PR/issue creation setting for self-improvement."""
        return os.getenv("AUTO_PR_ENABLED", "false").lower() == "true"

    @property
    def backup_directory(self) -> str:
        """Get backup directory."""
        return os.getenv("BACKUP_DIRECTORY", "./backups")

    @property
    def max_modification_attempts(self) -> int:
        """Get max modification attempts."""
        return int(os.getenv("MAX_MODIFICATION_ATTEMPTS", "3"))

    @property
    def self_improvement_max_functions(self) -> int:
        """Get max high-complexity functions to consider per self-improvement cycle."""
        return int(os.getenv("SELF_IMPROVEMENT_MAX_FUNCTIONS", "3"))

    @property
    def self_improvement_max_opportunities(self) -> int:
        """Get max improvement opportunities to consider per self-improvement cycle."""
        return int(os.getenv("SELF_IMPROVEMENT_MAX_OPPORTUNITIES", "5"))

    @property
    def require_validation(self) -> bool:
        """Get validation requirement setting."""
        return os.getenv("REQUIRE_VALIDATION", "true").lower() == "true"

    @property
    def enable_evaluation(self) -> bool:
        """Get evaluation enabled setting."""
        return os.getenv("ENABLE_EVALUATION", "false").lower() == "true"

    @property
    def knowledge_base_path(self) -> str:
        """Get knowledge base path."""
        return os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")

    @property
    def auto_update_knowledge(self) -> bool:
        """Get auto update knowledge setting."""
        return os.getenv("AUTO_UPDATE_KNOWLEDGE", "false").lower() == "true"

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
    def discord_attachment_threshold(self) -> int:
        """Response length at which Discord delivery switches to an attachment."""
        return int(os.getenv("DISCORD_ATTACHMENT_THRESHOLD", "12000"))

    @property
    def discord_max_attachment_bytes(self) -> int:
        """Conservative upper bound for a Discord response attachment."""
        return int(os.getenv("DISCORD_MAX_ATTACHMENT_BYTES", "7500000"))

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

    # E2B Sandbox Configuration
    @property
    def e2b_api_key(self) -> str:
        """Get E2B sandbox API key."""
        return os.getenv("E2B_API_KEY", "")

    # Scratchpad Configuration
    @property
    def scratchpad_dir(self) -> str:
        """Get scratchpad directory for the agent's persistent workspace."""
        return os.getenv("SCRATCHPAD_DIR", "./scratchpad")

    # Self-improvement tuning
    @property
    def iterative_revision_max_rounds(self) -> int:
        """Max revision rounds in the CAI-style iterative improvement loop."""
        return min(max(int(os.getenv("ITERATIVE_REVISION_MAX_ROUNDS", "1")), 0), 3)

    @property
    def iterative_revision_target_score(self) -> float:
        """Stop iterating when response score reaches this threshold."""
        return float(os.getenv("ITERATIVE_REVISION_TARGET_SCORE", "0.75"))

    @property
    def best_of_n_count(self) -> int:
        """Number of candidate responses to generate for Best-of-N selection."""
        return int(os.getenv("BEST_OF_N_COUNT", "2"))

    @property
    def enable_best_of_n(self) -> bool:
        """Enable Best-of-N sampling for low-confidence responses."""
        return os.getenv("ENABLE_BEST_OF_N", "false").lower() == "true"

    @property
    def reflexion_interval(self) -> int:
        """Number of interactions between Reflexion lesson-extraction runs."""
        return int(os.getenv("REFLEXION_INTERVAL", "50"))

    @property
    def enable_ensemble_judge(self) -> bool:
        """Enable multi-persona ensemble scoring in the evaluator."""
        return os.getenv("ENABLE_ENSEMBLE_JUDGE", "false").lower() == "true"

    # TPMJS Integration Configuration
    @property
    def tpmjs_api_key(self) -> str:
        """Get TPMJS API key."""
        return os.getenv("TPMJS_API_KEY", "")

    @property
    def api_key(self) -> str:
        """Get the project-steward API key (legacy ``API_KEY`` is supported)."""
        return os.getenv("PROJECT_API_KEY", "") or os.getenv("API_KEY", "")

    @property
    def api_auth_required(self) -> bool:
        """Whether non-public API routes require project authentication."""
        return os.getenv("API_AUTH_REQUIRED", "true").lower() == "true"

    @property
    def tpmjs_enabled(self) -> bool:
        """Whether the optional TPMJS registry should be probed and exposed."""
        return os.getenv("TPMJS_ENABLED", "false").lower() == "true"

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
            "memory_backend": self.memory_backend,
            "legacy_memory_read_only": self.legacy_memory_read_only,
            "ham_api_url": self.ham_api_url,
            "ham_api_key": "***" if self.ham_api_key else "",
            "ham_project": self.ham_project,
            "ham_scope": self.ham_scope,
            "ham_repo": self.ham_repo,
            "ham_expected_agent_id": self.ham_expected_agent_id,
            "persistent_data_dir": self.persistent_data_dir,
            "memory_collection_name": self.memory_collection_name,
            "max_memory_entries": self.max_memory_entries,
            "default_llm_provider": self.default_llm_provider,
            "default_model": self.default_model,
            "evaluation_model": self.evaluation_model,
            "evaluation_provider": self.evaluation_provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enable_self_modification": self.enable_self_modification,
            "auto_pr_enabled": self.auto_pr_enabled,
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
            "e2b_api_key": "***" if self.e2b_api_key else "",
            "scratchpad_dir": self.scratchpad_dir,
            "tpmjs_api_key": "***" if self.tpmjs_api_key else "",
            "tpmjs_enabled": self.tpmjs_enabled,
            "api_auth_required": self.api_auth_required,
            "iterative_revision_max_rounds": self.iterative_revision_max_rounds,
            "iterative_revision_target_score": self.iterative_revision_target_score,
            "best_of_n_count": self.best_of_n_count,
            "enable_best_of_n": self.enable_best_of_n,
            "reflexion_interval": self.reflexion_interval,
            "enable_ensemble_judge": self.enable_ensemble_judge,
        }

    def ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.memory_persist_directory,
            self.persistent_data_dir,
            self.backup_directory,
            self.knowledge_base_path,
            self.scratchpad_dir,
            os.path.dirname(self.log_file) if os.path.dirname(self.log_file) else ".",
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
