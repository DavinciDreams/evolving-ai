"""Rate limiting for Discord bot to prevent spam and abuse."""

import time
from collections import defaultdict, deque
from typing import Dict, Deque
from loguru import logger


class RateLimiter:
    """Rate limiter for Discord bot interactions.

    Implements a sliding window rate limiter to prevent users from
    overwhelming the bot with too many requests.
    """

    def __init__(self, max_messages: int = 10, window_seconds: int = 60, cooldown_seconds: int = 2):
        """Initialize rate limiter.

        Args:
            max_messages: Maximum messages allowed in the time window
            window_seconds: Time window in seconds
            cooldown_seconds: Minimum seconds between messages from same user
        """
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds

        # Track message timestamps per user (sliding window)
        self._user_messages: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=max_messages))

        # Track last message time per user (for cooldown)
        self._last_message_time: Dict[int, float] = {}

        logger.info(
            f"Rate limiter initialized: {max_messages} msgs/{window_seconds}s, "
            f"{cooldown_seconds}s cooldown"
        )

    def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limits.

        Args:
            user_id: Discord user ID

        Returns:
            True if user is allowed to send message, False if rate limited
        """
        current_time = time.time()

        # Check cooldown (minimum time between messages)
        if user_id in self._last_message_time:
            time_since_last = current_time - self._last_message_time[user_id]
            if time_since_last < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_last
                logger.debug(
                    f"User {user_id} cooldown active: {remaining:.1f}s remaining"
                )
                return False

        # Check sliding window rate limit
        user_messages = self._user_messages[user_id]

        # Remove messages outside the window
        cutoff_time = current_time - self.window_seconds
        while user_messages and user_messages[0] < cutoff_time:
            user_messages.popleft()

        # Check if user has exceeded max messages in window
        if len(user_messages) >= self.max_messages:
            oldest_message = user_messages[0]
            time_until_reset = self.window_seconds - (current_time - oldest_message)
            logger.warning(
                f"User {user_id} rate limited: {len(user_messages)}/{self.max_messages} "
                f"messages in window. Reset in {time_until_reset:.1f}s"
            )
            return False

        return True

    def add_request(self, user_id: int) -> None:
        """Record a request from a user.

        Args:
            user_id: Discord user ID
        """
        current_time = time.time()
        self._user_messages[user_id].append(current_time)
        self._last_message_time[user_id] = current_time

        logger.debug(
            f"Request recorded for user {user_id}: "
            f"{len(self._user_messages[user_id])}/{self.max_messages} in window"
        )

    def get_remaining_cooldown(self, user_id: int) -> float:
        """Get remaining cooldown time for a user.

        Args:
            user_id: Discord user ID

        Returns:
            Remaining cooldown time in seconds, 0 if no cooldown
        """
        if user_id not in self._last_message_time:
            return 0.0

        current_time = time.time()
        time_since_last = current_time - self._last_message_time[user_id]
        remaining = max(0.0, self.cooldown_seconds - time_since_last)

        return remaining

    def get_remaining_window_time(self, user_id: int) -> float:
        """Get time until rate limit window resets for user.

        Args:
            user_id: Discord user ID

        Returns:
            Seconds until oldest message expires from window, 0 if no messages
        """
        user_messages = self._user_messages[user_id]

        if not user_messages:
            return 0.0

        current_time = time.time()
        oldest_message = user_messages[0]
        remaining = self.window_seconds - (current_time - oldest_message)

        return max(0.0, remaining)

    def reset_user_limit(self, user_id: int) -> None:
        """Reset rate limit for a specific user.

        Args:
            user_id: Discord user ID
        """
        if user_id in self._user_messages:
            self._user_messages[user_id].clear()
        if user_id in self._last_message_time:
            del self._last_message_time[user_id]

        logger.info(f"Rate limit reset for user {user_id}")

    def get_user_message_count(self, user_id: int) -> int:
        """Get current message count for user in window.

        Args:
            user_id: Discord user ID

        Returns:
            Number of messages in current window
        """
        current_time = time.time()
        user_messages = self._user_messages[user_id]

        # Clean up old messages
        cutoff_time = current_time - self.window_seconds
        while user_messages and user_messages[0] < cutoff_time:
            user_messages.popleft()

        return len(user_messages)

    def is_user_rate_limited(self, user_id: int) -> bool:
        """Check if user is currently rate limited.

        Args:
            user_id: Discord user ID

        Returns:
            True if user is rate limited, False otherwise
        """
        return not self.check_rate_limit(user_id)

    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with rate limiter stats
        """
        return {
            "max_messages": self.max_messages,
            "window_seconds": self.window_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "active_users": len(self._user_messages),
            "total_tracked_users": len(self._last_message_time),
        }
