"""Private operator inbox and signed webhook intake. No dispatch endpoint."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from evolving_agent.api.routes.integration_requests import bounded_body, bounded_json
from evolving_agent.integrations.connectors import WEBHOOK_LIMIT, ConnectorService
from evolving_agent.integrations.media import IntegrationError

router = APIRouter(prefix="/connectors", tags=["Connectors"])


class Acknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    disposition: Literal["reviewed", "discarded"]


def get_connector_service(request: Request) -> ConnectorService:
    service = getattr(request.app.state, "connector_service", None)
    if service is None:
        from evolving_agent.utils.config import config

        service = ConnectorService.from_env(config)
        request.app.state.connector_service = service
    return service


@router.get("/status")
async def connector_status(request: Request):
    return get_connector_service(request).status()


@router.post("/webhooks/{connector_id}", status_code=202)
async def incoming_webhook(connector_id: str, request: Request):
    service = get_connector_service(request)
    try:
        service.require(connector_id)
        if (
            request.headers.get("content-type", "").split(";")[0].strip().lower()
            != "application/json"
        ):
            raise HTTPException(415, "Expected application/json")
        body = await bounded_body(request, WEBHOOK_LIMIT)
        return await service.receive(
            connector_id,
            body,
            request.headers.get("X-Katbot-Timestamp", ""),
            request.headers.get("X-Katbot-Signature", ""),
        )
    except IntegrationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None


@router.get("/events")
async def list_events(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    status: Literal["pending", "reviewed", "discarded", "all"] = "pending",
):
    try:
        return {
            "events": await get_connector_service(request).list_events(limit, status)
        }
    except IntegrationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None


@router.post("/events/{connector_id}/{event_id}/acknowledge")
async def acknowledge_event(connector_id: str, event_id: str, request: Request):
    try:
        service = get_connector_service(request)
        service.require(connector_id)
        payload = await bounded_json(request, Acknowledgement, 1024)
        return await service.acknowledge(connector_id, event_id, payload.disposition)
    except IntegrationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
