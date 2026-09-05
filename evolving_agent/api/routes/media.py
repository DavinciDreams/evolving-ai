"""Private media endpoints; output is never automatically attached to memory."""

from fastapi import APIRouter, HTTPException, Request, Response

from evolving_agent.api.routes.integration_requests import (
    bounded_json,
    json_request_schema,
)
from evolving_agent.integrations.media import (
    AUDIO_LIMIT,
    IMAGE_LIMIT,
    IntegrationError,
    MediaService,
    SpeechRequest,
    TranscriptionRequest,
    VisionRequest,
)

router = APIRouter(prefix="/media", tags=["Media"])


def get_media_service(request: Request) -> MediaService:
    service = getattr(request.app.state, "media_service", None)
    if service is None:
        from evolving_agent.utils.config import config

        service = MediaService.from_env(config)
        request.app.state.media_service = service
    return service


@router.get("/status")
async def media_status(request: Request):
    return get_media_service(request).status()


async def _execute(request: Request, capability: str, schema, limit: int):
    service = get_media_service(request)
    try:
        service.require(capability)
        payload = await bounded_json(request, schema, limit)
        method = "transcribe" if capability == "transcription" else capability
        return await getattr(service, method)(payload)
    except IntegrationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None


@router.post("/vision", openapi_extra=json_request_schema(VisionRequest))
async def vision(request: Request):
    return await _execute(
        request, "vision", VisionRequest, 4 * ((IMAGE_LIMIT + 2) // 3) + 32_768
    )


@router.post("/transcribe", openapi_extra=json_request_schema(TranscriptionRequest))
async def transcribe(request: Request):
    return await _execute(
        request,
        "transcription",
        TranscriptionRequest,
        4 * ((AUDIO_LIMIT + 2) // 3) + 4096,
    )


@router.post("/speech", openapi_extra=json_request_schema(SpeechRequest))
async def speech(request: Request):
    data = await _execute(request, "speech", SpeechRequest, 32_768)
    return Response(
        data,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Audio-Generated": "ai",
            "Content-Disposition": 'inline; filename="katbot-speech.mp3"',
        },
    )
