"""System endpoints: /health/detailed, /health/recovery, /system/*."""

from datetime import datetime

import evolving_agent.utils.app_state as state
from fastapi import APIRouter, Depends, HTTPException

from evolving_agent.utils.deps import verify_api_key

from evolving_agent.utils.config import config
from evolving_agent.utils.error_recovery import error_recovery_manager
from evolving_agent.utils.llm_interface import llm_manager
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/health/detailed", tags=["System"])
async def health_check_detailed():
    """
    Comprehensive health check endpoint with recovery status.

    Returns overall system health and component status.
    """
    try:
        # Get recovery status
        recovery_status = error_recovery_manager.get_recovery_status()

        # Get agent health if available
        agent_health = {}
        if state.agent:
            agent_health = await state.agent.check_system_health()

        # Get LLM provider health
        llm_health = {}
        try:
            llm_health = llm_manager.get_provider_health_status()
        except Exception as e:
            llm_health = {"error": str(e)}

        # Get GitHub integration health
        github_health = {}
        if state.github_modifier:
            try:
                github_health = state.github_modifier.github_integration.get_status()
            except Exception as e:
                github_health = {"error": str(e)}

        # Get Discord integration health
        discord_health = {}
        if state.discord_integration:
            try:
                discord_status = await state.discord_integration.get_status() if hasattr(state.discord_integration, 'get_status') else {}
                discord_health = {
                    "enabled": config.discord_enabled,
                    "connected": discord_status.get("connected", False),
                }
            except Exception as e:
                discord_health = {"error": str(e)}

        # Determine overall health
        degraded_mode = recovery_status.get("degraded_mode", False)

        if degraded_mode:
            overall_status = "degraded"
        elif agent_health.get("overall") != "healthy":
            overall_status = agent_health.get("overall", "unknown")
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "degraded_mode": degraded_mode,
            "components": {
                "agent": agent_health,
                "llm_providers": llm_health,
                "github": github_health,
                "discord": discord_health,
                "error_recovery": {
                    "circuit_breakers": recovery_status.get("circuit_breakers", {}),
                    "active_checkpoints": recovery_status.get("active_checkpoints", 0),
                    "recovery_history_count": recovery_status.get("recovery_history_count", 0),
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/health/recovery", tags=["System"])
async def recovery_status():
    """
    Get detailed error recovery status.

    Returns information about circuit breakers, error patterns, and recovery history.
    """
    try:
        recovery_status = error_recovery_manager.get_recovery_status()
        recovery_history = error_recovery_manager.get_recovery_history(limit=10)
        health_checks = await error_recovery_manager.perform_health_checks()

        return {
            "recovery_status": recovery_status,
            "health_checks": health_checks,
            "recent_recoveries": recovery_history,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.post("/system/trigger-recovery", tags=["System"], dependencies=[Depends(verify_api_key)])
async def trigger_recovery():
    """
    Trigger recovery operations for failed components.

    This endpoint can be used to manually trigger recovery attempts.
    """
    try:
        # Process pending GitHub operations if any
        if state.github_modifier and state.github_modifier.github_integration:
            try:
                results = await state.github_modifier.github_integration.process_pending_operations()
                return {
                    "message": "Recovery triggered",
                    "github_operations_processed": len(results),
                    "results": results
                }
            except Exception as e:
                logger.error(f"Error processing GitHub operations: {e}")
                return {
                    "message": "Recovery partially completed",
                    "error": str(e)
                }

        return {
            "message": "No pending operations to process"
        }
    except Exception as e:
        logger.error(f"Error triggering recovery: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering recovery: {str(e)}"
        )


@router.post("/system/enable-degraded-mode", tags=["System"], dependencies=[Depends(verify_api_key)])
async def enable_degraded_mode():
    """
    Manually enable degraded mode.

    This can be useful for maintenance or when issues are detected.
    """
    try:
        error_recovery_manager.set_degraded_mode(True)
        if state.agent:
            state.agent.degraded_mode = True

        return {
            "message": "Degraded mode enabled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error enabling degraded mode: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error enabling degraded mode: {str(e)}"
        )


@router.post("/system/disable-degraded-mode", tags=["System"], dependencies=[Depends(verify_api_key)])
async def disable_degraded_mode():
    """
    Manually disable degraded mode.

    This can be used to attempt to return to normal operation.
    """
    try:
        error_recovery_manager.set_degraded_mode(False)
        if state.agent:
            state.agent.degraded_mode = False

        return {
            "message": "Degraded mode disabled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error disabling degraded mode: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error disabling degraded mode: {str(e)}"
        )
