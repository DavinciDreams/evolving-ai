"""Bound raw bodies before parsing; validation failures never echo input."""

import asyncio
import json

from fastapi import HTTPException, Request
from pydantic import ValidationError


def json_request_schema(model) -> dict:
    """Keep OpenAPI useful while parsing manually to bound and redact failures."""
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": model.model_json_schema()}},
        }
    }


async def bounded_body(request: Request, limit: int) -> bytes:
    if request.headers.get("content-encoding", "identity") != "identity":
        raise HTTPException(415, "Compressed request bodies are not accepted")
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) < 0 or int(length) > limit:
                raise HTTPException(413, "Request body exceeds limit")
        except ValueError:
            raise HTTPException(400, "Invalid content length") from None
    result = bytearray()
    try:
        async with asyncio.timeout(15):
            async for chunk in request.stream():
                if len(result) + len(chunk) > limit:
                    raise HTTPException(413, "Request body exceeds limit")
                result.extend(chunk)
    except TimeoutError:
        raise HTTPException(408, "Request body timed out") from None
    return bytes(result)


async def bounded_json(request: Request, model, limit: int):
    if (
        request.headers.get("content-type", "").split(";")[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(415, "Expected application/json")
    body = await bounded_body(request, limit)
    try:
        return model.model_validate_json(body)
    except (ValidationError, ValueError, RecursionError, json.JSONDecodeError):
        # Pydantic's default error includes input, potentially megabytes of media/secrets.
        raise HTTPException(
            422, "Invalid request fields or field limits exceeded"
        ) from None
