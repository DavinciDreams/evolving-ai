"""Cached private telemetry; status requests never probe models or replay effects."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import evolving_agent.utils.app_state as state
from evolving_agent.utils.config import config
from evolving_agent.utils.deps import verify_api_key
from evolving_agent.utils.error_recovery import error_recovery_manager
from evolving_agent.utils.llm_interface import llm_manager
from evolving_agent.utils.logging import setup_logger

logger = setup_logger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _cached_recovery():
    raw = error_recovery_manager.get_recovery_status()
    # Arbitrary diagnostics, service names and checkpoint data may hold secrets.
    return {
        "degraded_mode": raw.get("degraded_mode") is True,
        "active_checkpoints": _count(raw.get("active_checkpoints")),
        "partial_responses": _count(raw.get("partial_responses")),
        "recovery_history_count": _count(raw.get("recovery_history_count")),
        "circuit_breaker_count": len(raw.get("circuit_breakers", {})),
    }


@router.get("/health/detailed", tags=["System"])
async def health_check_detailed():
    """Read cached facts only; not a live availability or successful-call claim."""
    try:
        recovery = _cached_recovery()
        providers = {}
        for name in ("openai", "anthropic", "openrouter", "zai"):
            cached = llm_manager.provider_status.get(name, {})
            providers[name] = {
                "last_reported_available": (
                    cached.get("available")
                    if type(cached.get("available")) is bool
                    else None
                ),
                "has_recorded_error": bool(cached.get("last_error")),
                "request_count": _count(cached.get("request_count")),
                "freshness": "not_verified_by_this_request",
            }
        agent = state.agent
        components = getattr(agent, "component_health", {}) if agent else {}
        return {
            "status": "degraded" if recovery["degraded_mode"] else "not_probed",
            "cached_only": True,
            "timestamp": datetime.now().isoformat(),
            "degraded_mode": recovery["degraded_mode"],
            "components": {
                "agent": {
                    "initialized": getattr(agent, "initialized", False) is True,
                    "last_reported": {
                        name: (
                            components.get(name)
                            if type(components.get(name)) is bool
                            else None
                        )
                        for name in ("memory", "knowledge_base", "persistent_storage")
                    },
                },
                "llm_providers": providers,
                "github": {
                    "configured": state.github_modifier is not None,
                    "status": "not_probed",
                },
                "discord": {
                    "enabled": bool(config.discord_enabled),
                    "status": "not_probed",
                },
                "error_recovery": recovery,
            },
        }
    except Exception as exc:
        logger.error("Cached health unavailable: {}", type(exc).__name__)
        raise HTTPException(503, "Cached health telemetry unavailable") from None


@router.get("/health/recovery", tags=["System"])
async def recovery_status():
    """Counts only; no probes, raw recovery logs, or implicit recovery actions."""
    try:
        return {
            "recovery_status": _cached_recovery(),
            "cached_only": True,
            "health_checks": {"performed": False},
            "recent_recoveries_included": False,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("Cached recovery unavailable: {}", type(exc).__name__)
        raise HTTPException(503, "Cached recovery telemetry unavailable") from None


@router.post(
    "/system/trigger-recovery",
    tags=["System"],
    deprecated=True,
    responses={410: {"description": "Legacy repository queue replay is retired"}},
)
async def trigger_recovery():
    """A recovery label does not authorize queued commits, branches, or PRs."""
    raise HTTPException(
        410,
        "Legacy repository queue replay is retired. Reconcile pending effects "
        "through a separately authorized repository workflow.",
    )


def _set_degraded(enabled):
    agent = state.agent
    runtime = getattr(agent, "runtime", None)
    steward = getattr(agent, "steward", None)
    if runtime and runtime.busy:
        raise HTTPException(
            409, "Runtime is occupied; mode changes do not clear its lease"
        )
    if steward and (
        steward.busy
        or steward.dreams.status()["running"]
        or (steward.lab and steward.lab.status()["busy"])
        or (steward.learning and steward.learning.status()["running"])
    ):
        raise HTTPException(
            409, "Steward is occupied; mode changes do not clear its lease"
        )
    error_recovery_manager.set_degraded_mode(enabled)
    if agent:
        agent.degraded_mode = enabled
    return {
        "degraded_mode": enabled,
        "runtime_lease_unchanged": True,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/system/enable-degraded-mode", tags=["System"])
async def enable_degraded_mode():
    return _set_degraded(True)


@router.post("/system/disable-degraded-mode", tags=["System"])
async def disable_degraded_mode():
    return _set_degraded(False)
