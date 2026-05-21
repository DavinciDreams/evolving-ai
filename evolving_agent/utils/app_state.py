"""Shared mutable application state — set during lifespan startup."""

from typing import Optional

from evolving_agent.core.agent import SelfImprovingAgent
from evolving_agent.self_modification.github_enhanced_modifier import GitHubEnabledSelfModifier
from evolving_agent.integrations.discord_integration import DiscordIntegration

agent: Optional[SelfImprovingAgent] = None
github_modifier: Optional[GitHubEnabledSelfModifier] = None
discord_integration: Optional[DiscordIntegration] = None
server_shutdown: bool = False
