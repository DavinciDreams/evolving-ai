"""Human authentication routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from evolving_agent.utils import nostr_auth


router = APIRouter(prefix="/auth/nostr", tags=["Authentication"])
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class OptionsRequest(BaseModel):
    pubkey: str = Field(min_length=64, max_length=64)


class VerifyRequest(BaseModel):
    challenge: str = Field(min_length=43, max_length=43)
    event: dict


@router.get("/session")
def session_status(request: Request):
    """Report feature availability and the current opaque browser session."""
    if not nostr_auth.enabled():
        return JSONResponse({"enabled": False, "signed_in": False}, headers=_NO_STORE)
    try:
        claims = nostr_auth.verify_session(request)
    except nostr_auth.NostrSessionUnavailable as exc:
        raise HTTPException(503, "Nostr session store is unavailable") from exc
    return JSONResponse(
        {
            "enabled": True,
            "signed_in": claims is not None,
            "pubkey": claims["nostr_pubkey"] if claims else None,
        },
        headers=_NO_STORE,
    )


@router.post("/options")
def sign_in_options(body: OptionsRequest, request: Request):
    cfg = nostr_auth.auth_config()
    origin = nostr_auth.require_json_origin(request, cfg)
    nostr_auth.check_rate_limit(request)
    if body.pubkey not in cfg.allowed_pubkeys:
        raise HTTPException(403, "This Nostr account is not authorized for Katbot")
    try:
        challenge = nostr_auth.create_challenge(body.pubkey, origin)
    except nostr_auth.NostrSessionUnavailable as exc:
        raise HTTPException(503, "Nostr session store is unavailable") from exc
    return JSONResponse(
        {"challenge": challenge, "verify_url": cfg.verify_url}, headers=_NO_STORE
    )


@router.post("/verify")
def sign_in_verify(body: VerifyRequest, request: Request):
    cfg = nostr_auth.auth_config()
    origin = nostr_auth.require_json_origin(request, cfg)
    nostr_auth.check_rate_limit(request)
    if not nostr_auth.valid_token(body.challenge):
        raise HTTPException(400, "Invalid Nostr sign-in challenge")
    pubkey = nostr_auth.verify_event(body.event, body.challenge, cfg)
    try:
        session = nostr_auth.consume_challenge(body.challenge, pubkey, origin)
    except nostr_auth.NostrSessionUnavailable as exc:
        raise HTTPException(503, "Nostr session store is unavailable") from exc
    response = JSONResponse(
        {"signed_in": True, "pubkey": pubkey}, headers=_NO_STORE
    )
    response.set_cookie(
        nostr_auth.SESSION_COOKIE,
        session,
        max_age=nostr_auth.SESSION_SECONDS,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


@router.post("/logout")
def sign_out(request: Request):
    cfg = nostr_auth.auth_config()
    nostr_auth.require_json_origin(request, cfg)
    try:
        nostr_auth.delete_session(request.cookies.get(nostr_auth.SESSION_COOKIE, ""))
    except nostr_auth.NostrSessionUnavailable as exc:
        raise HTTPException(503, "Nostr session store is unavailable") from exc
    response = JSONResponse({"signed_out": True}, headers=_NO_STORE)
    response.delete_cookie(
        nostr_auth.SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response
