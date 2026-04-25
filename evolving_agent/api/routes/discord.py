"""Discord endpoints: /discord/status."""

import evolving_agent.utils.app_state as state
from fastapi import APIRouter

from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/discord/status", tags=["Discord"])
async def get_discord_status():
    """
    Get Discord bot status and connection information.
    """
    try:
        if not state.discord_integration:
            return {
                "enabled": False,
                "connected": False,
                "message": "Discord integration not enabled"
            }

        is_ready = (
            state.discord_integration.client and
            state.discord_integration.client.user is not None
        )

        status_info = {
            "enabled": True,
            "connected": is_ready,
            "bot_name": state.discord_integration.client.user.name if is_ready else None,
            "bot_id": str(state.discord_integration.client.user.id) if is_ready else None,
            "guild_count": len(state.discord_integration.client.guilds) if is_ready else 0,
            "allowed_channels": len(state.discord_integration.allowed_channel_ids),
            "status_channel_configured": state.discord_integration.status_channel_id is not None,
            "mention_required": state.discord_integration.mention_required,
        }

        return status_info

    except Exception as e:
        logger.error(f"Error getting Discord status: {e}")
        return {
            "enabled": False,
            "connected": False,
            "error": str(e)
        }
