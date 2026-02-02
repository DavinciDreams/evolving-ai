"""Message formatting utilities for Discord bot."""

import discord
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class DiscordFormatter:
    """Formatter for Discord messages and embeds."""

    # Discord message length limits
    MAX_MESSAGE_LENGTH = 2000
    MAX_EMBED_TITLE = 256
    MAX_EMBED_DESCRIPTION = 4096
    MAX_EMBED_FIELD_NAME = 256
    MAX_EMBED_FIELD_VALUE = 1024
    MAX_EMBED_FIELDS = 25
    MAX_EMBED_FOOTER = 2048

    # Color scheme for different message types
    COLOR_SUCCESS = 0x00FF00  # Green
    COLOR_ERROR = 0xFF0000  # Red
    COLOR_INFO = 0x3498DB  # Blue
    COLOR_WARNING = 0xFFA500  # Orange
    COLOR_AGENT = 0x9B59B6  # Purple (agent brand color)

    @staticmethod
    def format_agent_response(
        response: str,
        query_id: Optional[str] = None,
        evaluation_score: Optional[float] = None,
        processing_time: Optional[float] = None,
        use_embed: bool = True
    ) -> List[Any]:
        """Format agent response for Discord.

        Args:
            response: Agent's response text
            query_id: Optional query identifier
            evaluation_score: Optional quality score
            processing_time: Optional processing time in seconds
            use_embed: Whether to use rich embed formatting

        Returns:
            List of Discord messages (strings or embeds)
        """
        if not use_embed:
            # Plain text mode - just split if too long
            return DiscordFormatter._split_long_message(response)

        # Create rich embed
        embed = discord.Embed(
            description=DiscordFormatter._truncate_text(
                response, DiscordFormatter.MAX_EMBED_DESCRIPTION
            ),
            color=DiscordFormatter.COLOR_AGENT,
            timestamp=datetime.utcnow()
        )

        embed.set_author(
            name="Self-Improving AI Agent",
            icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
        )

        # Add metadata fields if available
        if evaluation_score is not None:
            quality_emoji = DiscordFormatter._get_quality_emoji(evaluation_score)
            embed.add_field(
                name="Quality Score",
                value=f"{quality_emoji} {evaluation_score:.2f}",
                inline=True
            )

        if processing_time is not None:
            embed.add_field(
                name="Processing Time",
                value=f"⏱️ {processing_time:.2f}s",
                inline=True
            )

        if query_id:
            embed.set_footer(text=f"Query ID: {query_id}")

        return [embed]

    @staticmethod
    def format_status_update(event_type: str, data: Dict[str, Any]) -> discord.Embed:
        """Format status update for Discord.

        Args:
            event_type: Type of status update (e.g., 'self_improvement', 'knowledge_update')
            data: Event data dictionary

        Returns:
            Discord embed with formatted status update
        """
        if event_type == "self_improvement":
            return DiscordFormatter._format_self_improvement_status(data)
        elif event_type == "knowledge_update":
            return DiscordFormatter._format_knowledge_update_status(data)
        elif event_type == "agent_startup":
            return DiscordFormatter._format_startup_status(data)
        elif event_type == "high_quality_interaction":
            return DiscordFormatter._format_high_quality_interaction(data)
        else:
            # Generic status update
            return DiscordFormatter._format_generic_status(event_type, data)

    @staticmethod
    def _format_self_improvement_status(data: Dict[str, Any]) -> discord.Embed:
        """Format self-improvement status update."""
        embed = discord.Embed(
            title="🔧 Self-Improvement Cycle Complete",
            description="The agent has analyzed its own code and identified improvements.",
            color=DiscordFormatter.COLOR_SUCCESS,
            timestamp=datetime.utcnow()
        )

        if "improvements" in data:
            improvements_text = "\n".join([f"• {imp}" for imp in data["improvements"][:5]])
            embed.add_field(
                name="Improvements Made",
                value=improvements_text or "Code optimizations applied",
                inline=False
            )

        if "files_modified" in data:
            embed.add_field(
                name="Files Modified",
                value=str(data["files_modified"]),
                inline=True
            )

        if "pr_url" in data:
            embed.add_field(
                name="Pull Request",
                value=f"[View PR]({data['pr_url']})",
                inline=True
            )

        embed.set_footer(text="Self-improvement cycle complete")

        return embed

    @staticmethod
    def _format_knowledge_update_status(data: Dict[str, Any]) -> discord.Embed:
        """Format knowledge base update status."""
        embed = discord.Embed(
            title="📚 Knowledge Base Updated",
            description="New knowledge has been added to the agent's knowledge base.",
            color=DiscordFormatter.COLOR_INFO,
            timestamp=datetime.utcnow()
        )

        if "category" in data:
            embed.add_field(
                name="Category",
                value=data["category"],
                inline=True
            )

        if "entries_added" in data:
            embed.add_field(
                name="Entries Added",
                value=str(data["entries_added"]),
                inline=True
            )

        if "summary" in data:
            embed.add_field(
                name="Summary",
                value=DiscordFormatter._truncate_text(data["summary"], 1024),
                inline=False
            )

        embed.set_footer(text="Knowledge base expansion")

        return embed

    @staticmethod
    def _format_startup_status(data: Dict[str, Any]) -> discord.Embed:
        """Format agent startup status."""
        embed = discord.Embed(
            title="🚀 Agent Online",
            description="The self-improving AI agent is now online and ready to assist.",
            color=DiscordFormatter.COLOR_SUCCESS,
            timestamp=datetime.utcnow()
        )

        if "version" in data:
            embed.add_field(name="Version", value=data["version"], inline=True)

        if "memory_size" in data:
            embed.add_field(name="Memory Entries", value=str(data["memory_size"]), inline=True)

        embed.set_footer(text="Ready to assist")

        return embed

    @staticmethod
    def _format_high_quality_interaction(data: Dict[str, Any]) -> discord.Embed:
        """Format high quality interaction notification."""
        embed = discord.Embed(
            title="⭐ High Quality Interaction",
            description="The agent produced an exceptionally high-quality response.",
            color=DiscordFormatter.COLOR_SUCCESS,
            timestamp=datetime.utcnow()
        )

        if "score" in data:
            embed.add_field(
                name="Quality Score",
                value=f"{DiscordFormatter._get_quality_emoji(data['score'])} {data['score']:.2f}",
                inline=True
            )

        if "query" in data:
            embed.add_field(
                name="Query",
                value=DiscordFormatter._truncate_text(data["query"], 1024),
                inline=False
            )

        embed.set_footer(text="Exceptional performance")

        return embed

    @staticmethod
    def _format_generic_status(event_type: str, data: Dict[str, Any]) -> discord.Embed:
        """Format generic status update."""
        embed = discord.Embed(
            title=f"📢 Status: {event_type.replace('_', ' ').title()}",
            description=str(data.get("message", "Status update received")),
            color=DiscordFormatter.COLOR_INFO,
            timestamp=datetime.utcnow()
        )

        # Add up to 10 data fields
        field_count = 0
        for key, value in data.items():
            if key != "message" and field_count < 10:
                embed.add_field(
                    name=key.replace("_", " ").title(),
                    value=DiscordFormatter._truncate_text(str(value), 1024),
                    inline=True
                )
                field_count += 1

        return embed

    @staticmethod
    def format_error_message(error: str, user_friendly: bool = True) -> discord.Embed:
        """Format error message for Discord.

        Args:
            error: Error message
            user_friendly: Whether to show user-friendly message

        Returns:
            Discord embed with error message
        """
        embed = discord.Embed(
            title="❌ Error",
            description=(
                "I encountered an error processing your request. Please try again."
                if user_friendly
                else DiscordFormatter._truncate_text(error, DiscordFormatter.MAX_EMBED_DESCRIPTION)
            ),
            color=DiscordFormatter.COLOR_ERROR,
            timestamp=datetime.utcnow()
        )

        if not user_friendly:
            embed.set_footer(text="Error details")

        return embed

    @staticmethod
    def format_rate_limit_message(cooldown_seconds: float) -> discord.Embed:
        """Format rate limit notification.

        Args:
            cooldown_seconds: Remaining cooldown time

        Returns:
            Discord embed with rate limit message
        """
        embed = discord.Embed(
            title="⏳ Rate Limit",
            description=f"Please wait {cooldown_seconds:.1f} seconds before sending another message.",
            color=DiscordFormatter.COLOR_WARNING,
            timestamp=datetime.utcnow()
        )

        embed.set_footer(text="Rate limiting active")

        return embed

    @staticmethod
    def _split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
        """Split long message into multiple parts.

        Args:
            text: Text to split
            max_length: Maximum length per message

        Returns:
            List of message parts
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                parts.append(remaining)
                break

            # Try to split at a paragraph break
            split_pos = remaining.rfind("\n\n", 0, max_length)

            # If no paragraph break, try to split at a sentence
            if split_pos == -1:
                split_pos = remaining.rfind(". ", 0, max_length)
                if split_pos != -1:
                    split_pos += 1  # Include the period

            # If no sentence break, try to split at a word
            if split_pos == -1:
                split_pos = remaining.rfind(" ", 0, max_length)

            # If no word break, just hard split
            if split_pos == -1:
                split_pos = max_length - 3  # Leave room for "..."

            parts.append(remaining[:split_pos] + "...")
            remaining = "..." + remaining[split_pos:].lstrip()

        logger.debug(f"Split long message into {len(parts)} parts")
        return parts

    @staticmethod
    def _truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add if truncated

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def _get_quality_emoji(score: float) -> str:
        """Get emoji representing quality score.

        Args:
            score: Quality score (0.0 to 1.0)

        Returns:
            Emoji string
        """
        if score >= 0.9:
            return "⭐"
        elif score >= 0.8:
            return "🌟"
        elif score >= 0.7:
            return "✨"
        elif score >= 0.6:
            return "👍"
        else:
            return "👌"
