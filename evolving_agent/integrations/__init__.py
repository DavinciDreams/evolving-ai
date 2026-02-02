"""Integration package for self-improving AI agent."""

from .discord_integration import DiscordIntegration
# from .discord_bot import DiscordBot  # File doesn't exist
from .discord_formatter import DiscordFormatter
from .discord_rate_limiter import RateLimiter
from .web_search import WebSearchIntegration

__all__ = [
    "DiscordIntegration",
    # "DiscordBot",  # File doesn't exist
    "DiscordFormatter",
    "RateLimiter",
    "WebSearchIntegration",
]
