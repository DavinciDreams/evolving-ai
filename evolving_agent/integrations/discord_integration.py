"""Core Discord integration for self-improving AI agent."""

import asyncio
import discord
from typing import Optional, Dict, Any, List, Callable
from loguru import logger
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from .discord_formatter import DiscordFormatter
from .discord_rate_limiter import RateLimiter


class DiscordIntegration:
    """Discord integration for the self-improving AI agent.

    Handles message routing between Discord and the agent, manages
    rate limiting, formats responses, and posts status updates.
    """

    def __init__(
        self,
        bot_token: str,
        agent,
        config,
        intents: Optional[discord.Intents] = None
    ):
        """Initialize Discord integration.

        Args:
            bot_token: Discord bot token
            agent: SelfImprovingAgent instance
            config: Configuration object
            intents: Optional Discord intents (default: message content intent)
        """
        self.bot_token = bot_token
        self.agent = agent
        self.config = config

        # Discord client
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.guilds = True
            intents.messages = True

        self.client = discord.Client(intents=intents)
        self.formatter = DiscordFormatter()

        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_messages=config.discord_rate_limit_messages,
            window_seconds=60,
            cooldown_seconds=config.discord_cooldown_seconds
        )

        # Configuration
        self.allowed_channel_ids = [
            int(cid) for cid in config.discord_channel_ids if cid
        ]
        self.status_channel_id = (
            int(config.discord_status_channel_id)
            if config.discord_status_channel_id
            else None
        )
        self.mention_required = config.discord_mention_required
        self.use_embeds = config.discord_embed_responses
        self.show_typing = config.discord_typing_indicator
        self.status_updates_enabled = config.discord_status_updates_enabled

        # State
        self.initialized = False
        self.is_running = False
        self._setup_event_handlers()

        logger.info(
            f"Discord integration initialized. "
            f"Channels: {len(self.allowed_channel_ids)}, "
            f"Status channel: {self.status_channel_id}, "
            f"Mention required: {self.mention_required}"
        )

    def _setup_event_handlers(self):
        """Setup Discord client event handlers."""

        @self.client.event
        async def on_ready():
            """Called when Discord bot is ready."""
            logger.info(f"Discord bot logged in as {self.client.user}")
            logger.info(f"Bot ID: {self.client.user.id}")
            logger.info(f"Connected to {len(self.client.guilds)} guilds")

            # Set bot status
            await self.client.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="for messages | Self-Improving AI"
                )
            )

            # Post startup status if configured
            if self.status_updates_enabled and self.status_channel_id:
                await self._post_startup_status()

            self.initialized = True

        @self.client.event
        async def on_message(message: discord.Message):
            """Called when a message is received."""
            try:
                # Ignore messages from bots (including self)
                if message.author.bot:
                    return

                # Check if message is in allowed channels
                if self.allowed_channel_ids and message.channel.id not in self.allowed_channel_ids:
                    return

                # Check if mention is required
                if self.mention_required and not self.client.user.mentioned_in(message):
                    return

                # Process the message
                await self.handle_message(message)

            except Exception as e:
                logger.error(f"Error in on_message: {e}", exc_info=True)
                try:
                    error_embed = self.formatter.format_error_message(
                        str(e), user_friendly=True
                    )
                    await message.channel.send(embed=error_embed)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")

        @self.client.event
        async def on_error(event: str, *args, **kwargs):
            """Called when an error occurs."""
            logger.error(f"Discord error in {event}: {args}", exc_info=True)

        @self.client.event
        async def on_disconnect():
            """Called when bot disconnects."""
            logger.warning("Discord bot disconnected")

        @self.client.event
        async def on_resumed():
            """Called when bot reconnects."""
            logger.info("Discord bot reconnected")

    async def initialize(self) -> bool:
        """Initialize the Discord integration.

        Returns:
            True if initialization successful
        """
        try:
            # Validate configuration
            if not self.bot_token:
                raise ValueError("Discord bot token not provided")

            if not self.allowed_channel_ids:
                logger.warning(
                    "No allowed channel IDs configured. "
                    "Bot will respond in all channels where it can see messages."
                )

            # Register status callback with agent
            if hasattr(self.agent, 'register_status_callback'):
                self.agent.register_status_callback(self.handle_status_update)
                logger.info("Registered status update callback with agent")
            else:
                logger.warning(
                    "Agent does not support status callbacks. "
                    "Status updates will not be posted."
                )

            logger.info("Discord integration initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Discord integration: {e}")
            return False

    async def start(self):
        """Start the Discord bot."""
        try:
            self.is_running = True
            logger.info("Starting Discord bot...")
            await self.client.start(self.bot_token)
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            self.is_running = False
            raise

    async def close(self):
        """Shutdown the Discord bot."""
        try:
            logger.info("Shutting down Discord bot...")
            self.is_running = False

            # Post shutdown status if configured
            if self.status_updates_enabled and self.status_channel_id:
                await self._post_shutdown_status()

            await self.client.close()
            logger.info("Discord bot shutdown complete")

        except Exception as e:
            logger.error(f"Error during Discord bot shutdown: {e}")

    async def handle_message(self, message: discord.Message):
        """Handle incoming Discord message.

        Args:
            message: Discord message object
        """
        user_id = message.author.id
        query = message.content

        # Remove bot mention from query if present
        if self.client.user.mentioned_in(message):
            query = query.replace(f"<@{self.client.user.id}>", "").strip()
            query = query.replace(f"<@!{self.client.user.id}>", "").strip()

        if not query:
            return

        logger.info(
            f"Received message from {message.author} "
            f"in #{message.channel.name}: {query[:100]}..."
        )

        # Check rate limit
        if self.rate_limiter.is_user_rate_limited(user_id):
            cooldown = self.rate_limiter.get_remaining_cooldown(user_id)
            logger.warning(f"User {user_id} is rate limited")

            rate_limit_embed = self.formatter.format_rate_limit_message(cooldown)
            await message.channel.send(embed=rate_limit_embed)
            return

        # Record request
        self.rate_limiter.add_request(user_id)

        # Show typing indicator if enabled
        async with message.channel.typing() if self.show_typing else self._noop_context():
            try:
                # Prepare context hints from Discord
                context_hints = [
                    f"discord_user:{message.author.name}",
                    f"discord_user_id:{user_id}",
                    f"discord_channel:{message.channel.name}",
                ]

                # Process query with agent
                start_time = datetime.utcnow()
                response = await self.agent.run(query, context_hints=context_hints)
                processing_time = (datetime.utcnow() - start_time).total_seconds()

                # Get evaluation score if available
                evaluation_score = None
                # Note: The agent's last evaluation score could be stored in agent state
                # For now, we'll leave it as None

                # Send response
                await self.send_response(
                    message.channel,
                    response,
                    query_id=None,
                    evaluation_score=evaluation_score,
                    processing_time=processing_time
                )

                logger.info(
                    f"Sent response to {message.author} "
                    f"(processing time: {processing_time:.2f}s)"
                )

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_embed = self.formatter.format_error_message(
                    str(e), user_friendly=True
                )
                await message.channel.send(embed=error_embed)

    async def send_response(
        self,
        channel: discord.TextChannel,
        response: str,
        query_id: Optional[str] = None,
        evaluation_score: Optional[float] = None,
        processing_time: Optional[float] = None
    ):
        """Send response to Discord channel.

        Args:
            channel: Discord channel to send to
            response: Response text
            query_id: Optional query identifier
            evaluation_score: Optional evaluation score
            processing_time: Optional processing time in seconds
        """
        try:
            # Format response
            messages = self.formatter.format_agent_response(
                response=response,
                query_id=query_id,
                evaluation_score=evaluation_score,
                processing_time=processing_time,
                use_embed=self.use_embeds
            )

            # Send all message parts
            for msg in messages:
                if isinstance(msg, discord.Embed):
                    await self._send_with_retry(channel, embed=msg)
                else:
                    await self._send_with_retry(channel, content=msg)

        except Exception as e:
            logger.error(f"Failed to send response: {e}", exc_info=True)
            raise

    async def handle_status_update(self, event_type: str, data: Dict[str, Any]):
        """Handle status update from agent.

        This is called by the agent when important events occur.

        Args:
            event_type: Type of status update
            data: Event data
        """
        if not self.status_updates_enabled:
            return

        if not self.status_channel_id:
            logger.warning("Status updates enabled but no status channel configured")
            return

        try:
            logger.info(f"Posting status update: {event_type}")

            # Get status channel
            channel = self.client.get_channel(self.status_channel_id)
            if not channel:
                logger.error(f"Status channel {self.status_channel_id} not found")
                return

            # Format status update
            embed = self.formatter.format_status_update(event_type, data)

            # Send status update
            await self._send_with_retry(channel, embed=embed)

            logger.info(f"Posted status update: {event_type}")

        except Exception as e:
            logger.error(f"Failed to post status update: {e}", exc_info=True)

    async def _post_startup_status(self):
        """Post startup status message."""
        try:
            channel = self.client.get_channel(self.status_channel_id)
            if channel:
                data = {
                    "message": "Self-improving AI agent is now online",
                }
                embed = self.formatter.format_status_update("agent_startup", data)
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to post startup status: {e}")

    async def _post_shutdown_status(self):
        """Post shutdown status message."""
        try:
            channel = self.client.get_channel(self.status_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🔴 Agent Offline",
                    description="The self-improving AI agent is shutting down.",
                    color=0xFF0000,
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to post shutdown status: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _send_with_retry(
        self,
        channel: discord.TextChannel,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None
    ) -> discord.Message:
        """Send message with automatic retry on failure.

        Args:
            channel: Channel to send to
            content: Optional message content
            embed: Optional embed

        Returns:
            Sent message

        Raises:
            discord.HTTPException: If sending fails after retries
        """
        try:
            return await channel.send(content=content, embed=embed)
        except discord.HTTPException as e:
            logger.warning(f"Failed to send message (retrying): {e}")
            raise

    def _noop_context(self):
        """No-op async context manager."""
        class NoopContext:
            async def __aenter__(self):
                pass

            async def __aexit__(self, *args):
                pass

        return NoopContext()

    def get_stats(self) -> Dict[str, Any]:
        """Get Discord integration statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "initialized": self.initialized,
            "is_running": self.is_running,
            "bot_user": str(self.client.user) if self.client.user else None,
            "allowed_channels": len(self.allowed_channel_ids),
            "status_channel_configured": self.status_channel_id is not None,
            "guilds_connected": len(self.client.guilds) if self.initialized else 0,
            "rate_limiter": self.rate_limiter.get_stats(),
        }
