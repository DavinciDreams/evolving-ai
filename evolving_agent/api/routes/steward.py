"""Private asynchronous controls; no request waits for an evaluation loop."""
from dataclasses import fields

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from evolving_agent.core.runtime import RuntimeBusyError
from evolving_agent.self_modification.improvement_lab import BenchmarkCase, GuidanceCandidate, GuidanceStrategy
from evolving_agent.utils.deps import get_agent, verify_api_key
from evolving_agent.utils.secret_redaction import redact_text

router = APIRouter(prefix="/steward", tags=["Steward"], dependencies=[Depends(verify_api_key)])


def control(agent):
    current = getattr(agent, "steward", None)
    if not current:
        raise HTTPException(503, "Steward control is not initialized")
    return current


def enqueue(current, kind, operation):
    try:
        return current.submit(kind, operation)
    except RuntimeBusyError:
        raise HTTPException(409, "Another operation is still running") from None


@router.get("/status")
async def status(agent=Depends(get_agent)):
    return control(agent).status()


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, agent=Depends(get_agent)):
    job = control(agent).jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired; use its durable HAM artifact ID")
    return job


@router.post("/dream", status_code=202)
async def dream(agent=Depends(get_agent)):
    current = control(agent)
    if not current.dreams.settings.enabled:
        raise HTTPException(403, "Dream consolidation is disabled")
    return enqueue(current, "dream", lambda: current.dreams.run_once(reason="operator"))


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=16000)
    expected: str = Field(min_length=1, max_length=16000)
    split: str
    critical: bool = False


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    strategy: dict
    source_memory_ids: list[str] = Field(default_factory=list, max_length=32)
    rationale: str = Field(default="", max_length=1000)
    cases: list[CaseRequest] = Field(min_length=4, max_length=24)


def lab_control(agent):
    current = control(agent)
    if not current.lab:
        raise HTTPException(403, "Measured improvement lab is disabled")
    return current


@router.post("/improvement/evaluate", status_code=202)
async def evaluate(request: EvaluationRequest, agent=Depends(get_agent)):
    current = lab_control(agent)
    try:
        if set(request.strategy) - {item.name for item in fields(GuidanceStrategy)}:
            raise ValueError("Unknown strategy fields")
        candidate = GuidanceCandidate(
            request.candidate_id, GuidanceStrategy(**request.strategy),
            tuple(request.source_memory_ids), redact_text(request.rationale)[0],
        )
        cases = tuple(BenchmarkCase(**case.model_dump()) for case in request.cases)
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid strategy or benchmark; use the documented closed schema") from None
    return enqueue(current, "improvement", lambda: current.lab.evaluate(candidate, cases, request.run_id))


class PromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)


@router.get("/improvement/runs/{run_id}")
async def improvement_report(run_id: str, agent=Depends(get_agent)):
    current = lab_control(agent)
    try:
        report = current.lab.get_report(run_id)
    except ValueError:
        raise HTTPException(422, "Invalid run identifier") from None
    if report is None:
        raise HTTPException(404, "Run expired or not found; use its durable HAM artifact ID")
    return report


@router.post("/improvement/promote", status_code=202)
async def promote(request: PromotionRequest, agent=Depends(get_agent)):
    current = lab_control(agent)
    return enqueue(current, "improvement", lambda: current.lab.promote(request.run_id, request.expected_revision))


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


@router.post("/improvement/rollback", status_code=202)
async def rollback(request: RollbackRequest, agent=Depends(get_agent)):
    current = lab_control(agent)
    return enqueue(current, "improvement", lambda: current.lab.rollback(
        request.expected_revision, redact_text(request.reason)[0]))
