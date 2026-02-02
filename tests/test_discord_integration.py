"""Tests for Discord integration."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from evolving_agent.integrations.discord_rate_limiter import RateLimiter
from evolving_agent.integrations.discord_formatter import DiscordFormatter
import discord


class TestRateLimiter:
    """Tests for rate limiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct parameters."""
        limiter = RateLimiter(max_messages=10, window_seconds=60, cooldown_seconds=2)

        assert limiter.max_messages == 10
        assert limiter.window_seconds == 60
        assert limiter.cooldown_seconds == 2

    def test_rate_limiter_allows_first_message(self):
        """Test that rate limiter allows first message from user."""
        limiter = RateLimiter(max_messages=10, window_seconds=60, cooldown_seconds=2)
        user_id = 12345

        assert limiter.check_rate_limit(user_id) is True

    def test_rate_limiter_enforces_cooldown(self):
        """Test that rate limiter enforces cooldown between messages."""
        limiter = RateLimiter(max_messages=10, window_seconds=60, cooldown_seconds=2)
        user_id = 12345

        # First message should be allowed
        assert limiter.check_rate_limit(user_id) is True
        limiter.add_request(user_id)

        # Immediate second message should be blocked
        assert limiter.check_rate_limit(user_id) is False

    def test_rate_limiter_enforces_message_limit(self):
        """Test that rate limiter enforces max messages in window."""
        limiter = RateLimiter(max_messages=3, window_seconds=60, cooldown_seconds=0)
        user_id = 12345

        # First 3 messages should be allowed
        for i in range(3):
            assert limiter.check_rate_limit(user_id) is True
            limiter.add_request(user_id)

        # 4th message should be blocked
        assert limiter.check_rate_limit(user_id) is False

    def test_rate_limiter_reset_user(self):
        """Test that rate limiter can reset user limits."""
        limiter = RateLimiter(max_messages=1, window_seconds=60, cooldown_seconds=2)
        user_id = 12345

        # First message
        limiter.add_request(user_id)
        assert limiter.check_rate_limit(user_id) is False

        # Reset and try again
        limiter.reset_user_limit(user_id)
        assert limiter.check_rate_limit(user_id) is True

    def test_rate_limiter_get_stats(self):
        """Test that rate limiter returns correct stats."""
        limiter = RateLimiter(max_messages=10, window_seconds=60, cooldown_seconds=2)

        stats = limiter.get_stats()

        assert stats["max_messages"] == 10
        assert stats["window_seconds"] == 60
        assert stats["cooldown_seconds"] == 2
        assert stats["active_users"] == 0


class TestDiscordFormatter:
    """Tests for Discord message formatter."""

    def test_truncate_text(self):
        """Test text truncation."""
        text = "A" * 100
        truncated = DiscordFormatter._truncate_text(text, 50)

        assert len(truncated) == 50
        assert truncated.endswith("...")

    def test_truncate_text_no_truncation_needed(self):
        """Test that short text is not truncated."""
        text = "Short text"
        truncated = DiscordFormatter._truncate_text(text, 50)

        assert truncated == text

    def test_split_long_message(self):
        """Test splitting long messages."""
        text = "A" * 3000
        parts = DiscordFormatter._split_long_message(text, max_length=2000)

        assert len(parts) == 2
        assert all(len(part) <= 2000 for part in parts)

    def test_split_short_message(self):
        """Test that short messages are not split."""
        text = "Short message"
        parts = DiscordFormatter._split_long_message(text, max_length=2000)

        assert len(parts) == 1
        assert parts[0] == text

    def test_format_agent_response_embed(self):
        """Test formatting agent response as embed."""
        response = "This is a test response from the agent."
        messages = DiscordFormatter.format_agent_response(
            response=response,
            query_id="test-123",
            evaluation_score=0.85,
            processing_time=1.5,
            use_embed=True
        )

        assert len(messages) == 1
        assert isinstance(messages[0], discord.Embed)
        assert messages[0].description == response

    def test_format_agent_response_plain(self):
        """Test formatting agent response as plain text."""
        response = "This is a test response from the agent."
        messages = DiscordFormatter.format_agent_response(
            response=response,
            use_embed=False
        )

        assert len(messages) == 1
        assert messages[0] == response

    def test_format_error_message(self):
        """Test formatting error message."""
        error = "Test error message"
        embed = DiscordFormatter.format_error_message(error, user_friendly=True)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "❌ Error"
        assert embed.color == DiscordFormatter.COLOR_ERROR

    def test_format_rate_limit_message(self):
        """Test formatting rate limit message."""
        cooldown = 5.5
        embed = DiscordFormatter.format_rate_limit_message(cooldown)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "⏳ Rate Limit"
        assert "5.5 seconds" in embed.description

    def test_format_self_improvement_status(self):
        """Test formatting self-improvement status."""
        data = {
            "improvements": ["Improved function X", "Optimized algorithm Y"],
            "files_modified": 3,
            "pr_url": "https://github.com/test/repo/pull/123"
        }

        embed = DiscordFormatter._format_self_improvement_status(data)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "🔧 Self-Improvement Cycle Complete"
        assert embed.color == DiscordFormatter.COLOR_SUCCESS

    def test_format_knowledge_update_status(self):
        """Test formatting knowledge update status."""
        data = {
            "category": "Programming",
            "entries_added": 5,
            "summary": "New knowledge about Python best practices"
        }

        embed = DiscordFormatter._format_knowledge_update_status(data)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "📚 Knowledge Base Updated"
        assert embed.color == DiscordFormatter.COLOR_INFO

    def test_get_quality_emoji(self):
        """Test quality emoji selection."""
        assert DiscordFormatter._get_quality_emoji(0.95) == "⭐"
        assert DiscordFormatter._get_quality_emoji(0.85) == "🌟"
        assert DiscordFormatter._get_quality_emoji(0.75) == "✨"
        assert DiscordFormatter._get_quality_emoji(0.65) == "👍"
        assert DiscordFormatter._get_quality_emoji(0.50) == "👌"


@pytest.mark.asyncio
class TestDiscordIntegration:
    """Tests for Discord integration."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = Mock()
        agent.run = AsyncMock(return_value="Test response from agent")
        agent.register_status_callback = Mock()
        return agent

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock()
        config.discord_channel_ids = ["123456789"]
        config.discord_status_channel_id = "987654321"
        config.discord_mention_required = False
        config.discord_embed_responses = True
        config.discord_typing_indicator = True
        config.discord_status_updates_enabled = True
        config.discord_rate_limit_messages = 10
        config.discord_cooldown_seconds = 2
        return config

    async def test_discord_integration_initialization(self, mock_agent, mock_config):
        """Test Discord integration initializes correctly."""
        from evolving_agent.integrations.discord_integration import DiscordIntegration

        integration = DiscordIntegration(
            bot_token="test_token",
            agent=mock_agent,
            config=mock_config
        )

        assert integration.bot_token == "test_token"
        assert integration.agent == mock_agent
        assert integration.config == mock_config
        assert len(integration.allowed_channel_ids) == 1

    async def test_discord_integration_initialize(self, mock_agent, mock_config):
        """Test Discord integration initialize method."""
        from evolving_agent.integrations.discord_integration import DiscordIntegration

        integration = DiscordIntegration(
            bot_token="test_token",
            agent=mock_agent,
            config=mock_config
        )

        # Mock the agent having the callback method
        mock_agent.register_status_callback = Mock()

        result = await integration.initialize()

        assert result is True
        mock_agent.register_status_callback.assert_called_once()

    async def test_send_response(self, mock_agent, mock_config):
        """Test sending response to Discord."""
        from evolving_agent.integrations.discord_integration import DiscordIntegration

        integration = DiscordIntegration(
            bot_token="test_token",
            agent=mock_agent,
            config=mock_config
        )

        # Mock channel
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock()

        # Send response
        await integration.send_response(
            channel=mock_channel,
            response="Test response",
            evaluation_score=0.85,
            processing_time=1.5
        )

        # Verify channel.send was called
        assert mock_channel.send.called

    async def test_get_stats(self, mock_agent, mock_config):
        """Test getting integration stats."""
        from evolving_agent.integrations.discord_integration import DiscordIntegration

        integration = DiscordIntegration(
            bot_token="test_token",
            agent=mock_agent,
            config=mock_config
        )

        stats = integration.get_stats()

        assert "initialized" in stats
        assert "is_running" in stats
        assert "allowed_channels" in stats
        assert "rate_limiter" in stats
