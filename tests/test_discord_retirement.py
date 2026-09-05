"""Discord command boundaries with fake messages; never connect a bot or model."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from loguru import logger

from evolving_agent.integrations.discord_integration import DiscordIntegration


@pytest.fixture
def integration(monkeypatch):
    config = SimpleNamespace(
        discord_channel_ids=["123"],
        discord_status_channel_id=None,
        discord_mention_required=False,
        discord_embed_responses=True,
        discord_typing_indicator=False,
        discord_status_updates_enabled=False,
        discord_rate_limit_messages=10,
        discord_cooldown_seconds=0,
        discord_max_message_length=2000,
        discord_attachment_threshold=12000,
        discord_max_attachment_bytes=7_500_000,
    )
    agent = SimpleNamespace(run=AsyncMock(return_value="Safe response"))
    result = DiscordIntegration("synthetic-bot-token", agent, config)
    result.send_response = AsyncMock()
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        Mock(side_effect=AssertionError("retired command attempted HTTP")),
    )
    return result


def message(content):
    return SimpleNamespace(
        content=content,
        author=SimpleNamespace(id=42, name="private-author", bot=False),
        channel=SimpleNamespace(id=123, name="private-channel", send=AsyncMock()),
        guild=SimpleNamespace(id=987),
    )


@pytest.mark.parametrize(
    "command",
    [
        "!feature private-message",
        "!request private-message",
        "!feature",
        "!request",
        "!FEATURE private-message",
        "!REQUEST\tprivate-message",
        "  !feature private-message  ",
    ],
)
async def test_retired_commands_never_reach_model_or_publisher(integration, command):
    integration._convert_feature_to_technical_spec = AsyncMock(
        side_effect=AssertionError("converter executed")
    )
    integration._create_github_issue = AsyncMock(
        side_effect=AssertionError("publisher executed")
    )
    incoming = message(command)
    await integration.handle_message(incoming)
    integration.agent.run.assert_not_awaited()
    integration._convert_feature_to_technical_spec.assert_not_awaited()
    integration._create_github_issue.assert_not_awaited()
    httpx.AsyncClient.assert_not_called()
    incoming.channel.send.assert_awaited_once()
    notice = incoming.channel.send.call_args.kwargs["embed"]
    assert "retired" in notice.title.lower()
    assert "No request was submitted or saved" in notice.description
    assert "private-message" not in notice.description


async def test_retired_helpers_are_inert_even_if_called_directly(integration):
    with pytest.raises(RuntimeError, match="retired"):
        await integration._convert_feature_to_technical_spec(
            "private-request", "private-author"
        )
    result = await integration._create_github_issue(
        "private-title", "private-description"
    )
    assert result["error"] == "retired" and "private" not in str(result)
    httpx.AsyncClient.assert_not_called()
    integration.agent.run.assert_not_awaited()


async def test_retired_commands_still_obey_rate_admission(integration):
    integration.rate_limiter.is_user_rate_limited = Mock(return_value=True)
    integration.rate_limiter.get_remaining_cooldown = Mock(return_value=3)
    incoming = message("!feature private-message")
    await integration.handle_message(incoming)
    assert "Rate Limit" in incoming.channel.send.call_args.kwargs["embed"].title
    integration.agent.run.assert_not_awaited()


async def test_normal_chat_stays_guarded_and_whitespace_does_not_run(integration):
    await integration.handle_message(message("   \t  "))
    integration.agent.run.assert_not_awaited()
    await integration.handle_message(message("normal private-message"))
    integration.agent.run.assert_awaited_once()
    assert integration.agent.run.call_args.kwargs["wait_for_storage"] is True
    assert (
        integration.agent.run.call_args.kwargs["conversation_id"] == "discord:987:123"
    )


async def test_inbound_and_failure_logs_never_include_message_identity_or_error_body(
    integration,
):
    output = []
    sink = logger.add(lambda event: output.append(str(event)), format="{message}")
    try:
        integration.agent.run.side_effect = RuntimeError("private-provider-exception")
        incoming = message("private-message")
        await integration.handle_message(incoming)
        await integration.handle_message(message("!feature private-request"))
        await integration.client.on_error("private-event", "private-event-args")
    finally:
        logger.remove(sink)
    logs = "".join(output)
    for secret in (
        "private-message",
        "private-author",
        "private-channel",
        "private-provider-exception",
        "private-request",
        "private-event",
    ):
        assert secret not in logs
        assert secret not in str(incoming.channel.send.call_args)
