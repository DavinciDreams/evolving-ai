"""Core Discord integration for self-improving AI agent."""

import asyncio
import io
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import discord
from loguru import logger
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
        self.max_message_length = min(
            max(int(config.discord_max_message_length), 1),
            DiscordFormatter.MAX_MESSAGE_LENGTH,
        )
        self.attachment_threshold = max(
            int(config.discord_attachment_threshold),
            DiscordFormatter.MAX_EMBED_DESCRIPTION + 1,
        )
        self.max_attachment_bytes = max(int(config.discord_max_attachment_bytes), 1)

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
            logger.info("Discord bot connected")
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
                logger.error("Discord message handling failed")
                try:
                    error_embed = self.formatter.format_error_message(
                        "Discord operation failed", user_friendly=True
                    )
                    await message.channel.send(embed=error_embed)
                except Exception as send_error:
                    logger.error("Discord error notice delivery failed")

        @self.client.event
        async def on_error(event: str, *args, **kwargs):
            """Called when an error occurs."""
            logger.error("Discord event handling failed")

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
            logger.error("Discord initialization failed")
            return False

    async def start(self):
        """Start the Discord bot."""
        try:
            self.is_running = True
            logger.info("Starting Discord bot...")
            await self.client.start(self.bot_token)
        except Exception as e:
            logger.error("Discord connection failed")
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
            logger.error("Discord shutdown failed")

    async def handle_message(self, message: discord.Message):
        """Handle incoming Discord message.

        Args:
            message: Discord message object
        """
        user_id = message.author.id
        query = message.content

        # Remove bot mention from query if present
        bot_user = self.client.user
        if bot_user and bot_user.mentioned_in(message):
            query = query.replace(f"<@{bot_user.id}>", "").strip()
            query = query.replace(f"<@!{bot_user.id}>", "").strip()

        query = query.strip()
        if not query:
            return

        logger.info("Discord message received")

        # Check rate limit
        if self.rate_limiter.is_user_rate_limited(user_id):
            cooldown = self.rate_limiter.get_remaining_cooldown(user_id)
            logger.warning("Discord message rate limited")

            rate_limit_embed = self.formatter.format_rate_limit_message(cooldown)
            await message.channel.send(embed=rate_limit_embed)
            return

        # Record request
        self.rate_limiter.add_request(user_id)

        # Retired commands must never enter the model or a publication adapter.
        if query.split(maxsplit=1)[0].lower() in {"!feature", "!request"}:
            await self.handle_feature_request(message)
            return

        # Show typing indicator if enabled
        async with message.channel.typing() if self.show_typing else self._noop_context():
            try:
                # Prepare context hints from Discord
                context_hints = [
                    f"discord_user:{message.author.name}",
                    f"discord_user_id:{user_id}",
                    f"discord_channel:{message.channel.name}",
                ]
                conversation_id = self._get_conversation_id(message)

                # Process query with agent
                start_time = datetime.utcnow()
                response = await self.agent.run(
                    query,
                    context_hints=context_hints,
                    conversation_id=conversation_id,
                    wait_for_storage=True,
                )
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

                logger.info(f"Discord response sent (processing time: {processing_time:.2f}s)")

            except Exception as e:
                logger.error("Discord message processing failed")
                error_embed = self.formatter.format_error_message(
                    "Discord operation failed", user_friendly=True
                )
                await message.channel.send(embed=error_embed)

    def _get_conversation_id(self, message: discord.Message) -> str:
        """Build a stable conversation key for Discord channel context."""
        guild_id = getattr(getattr(message, "guild", None), "id", "dm")
        channel_id = getattr(message.channel, "id", "unknown")
        return f"discord:{guild_id}:{channel_id}"

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
        response_bytes = response.encode("utf-8")
        if (
            len(response) >= self.attachment_threshold
            and len(response_bytes) <= self.max_attachment_bytes
        ):
            try:
                await self._send_attachment_with_retry(
                    channel,
                    response_bytes,
                    "The complete response is attached because it exceeds Discord's message limits.",
                )
                return
            except Exception as exc:
                logger.warning(
                    f"Discord attachment delivery failed; falling back to chunks: {type(exc).__name__}"
                )

        messages = self.formatter.format_agent_response(
            response=response,
            query_id=query_id,
            evaluation_score=evaluation_score,
            processing_time=processing_time,
            use_embed=self.use_embeds,
            max_message_length=self.max_message_length,
        )

        sent_count = 0
        try:
            for msg in messages:
                if isinstance(msg, discord.Embed):
                    await self._send_with_retry(channel, embed=msg)
                else:
                    await self._send_with_retry(channel, content=msg)
                sent_count += 1
        except Exception as exc:
            logger.error(
                f"Discord chunk delivery stopped after {sent_count}/{len(messages)} parts: "
                f"{type(exc).__name__}"
            )
            if len(response_bytes) <= self.max_attachment_bytes:
                try:
                    await self._send_attachment_with_retry(
                        channel,
                        response_bytes,
                        f"Chunk delivery stopped after {sent_count}/{len(messages)} parts; "
                        "the complete response is attached.",
                    )
                    return
                except Exception as attachment_exc:
                    raise RuntimeError(
                        f"Discord delivery incomplete: {sent_count}/{len(messages)} parts "
                        "sent and attachment fallback failed"
                    ) from attachment_exc
            raise RuntimeError(
                f"Discord delivery failed after {sent_count}/{len(messages)} parts and "
                "the response exceeds the configured attachment limit"
            ) from exc

    async def _send_attachment_with_retry(
        self,
        channel: discord.TextChannel,
        response_bytes: bytes,
        notice: str,
    ) -> discord.Message:
        """Upload a fresh file object on each attempt so retries remain valid."""
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            buffer = io.BytesIO(response_bytes)
            attachment = discord.File(buffer, filename="katbot-response.txt")
            try:
                return await channel.send(content=notice, file=attachment)
            except discord.HTTPException as exc:
                last_error = exc
                logger.warning(
                    f"Discord attachment attempt {attempt}/3 failed: {type(exc).__name__}"
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt - 1))
            finally:
                attachment.close()
        raise RuntimeError("Discord attachment failed after 3 attempts") from last_error

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
            logger.info("Posting Discord status update")

            # Get status channel
            channel = self.client.get_channel(self.status_channel_id)
            if not channel:
                logger.error("Discord status channel unavailable")
                return

            # Format status update
            embed = self.formatter.format_status_update(event_type, data)

            # Send status update
            await self._send_with_retry(channel, embed=embed)

            logger.info("Discord status update posted")

        except Exception as e:
            logger.error("Discord status update failed")

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
            logger.error("Discord startup notice failed")

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
            logger.error("Discord shutdown notice failed")

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
            logger.warning("Discord message delivery failed; retrying")
            raise

    def _noop_context(self):
        """No-op async context manager."""
        class NoopContext:
            async def __aenter__(self):
                pass

            async def __aexit__(self, *args):
                pass

        return NoopContext()

    async def _convert_feature_to_technical_spec(
        self, feature_request: str, user_name: str
    ) -> Dict[str, str]:
        """Retired: Discord commands do not authorize unbounded model work."""
        raise RuntimeError("Legacy Discord feature conversion is retired")

    async def _create_github_issue(
        self, title: str, description: str, labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retired: Discord messages cannot grant repository publication authority."""
        return {"error": "retired", "details": "Direct Discord issue publication is retired"}

    async def handle_feature_request(self, message: discord.Message):
        """Acknowledge retirement without parsing, storing, or converting payloads."""
        logger.info("Retired Discord feature command received")
        embed = discord.Embed(
            title="Feature submission retired",
            description=(
                "The !feature and !request commands no longer generate specifications "
                "or publish GitHub issues. No request was submitted or saved. "
                "Use a separately authorized repository workflow; measured strategy "
                "evaluation is available in the private steward dashboard."
            ),
            color=DiscordFormatter.COLOR_WARNING,
        )
        try:
            async with asyncio.timeout(10):
                await message.channel.send(embed=embed)
        except TimeoutError:
            logger.warning("Discord retirement notice delivery timed out")

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
