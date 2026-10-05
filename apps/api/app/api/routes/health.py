"""Liveness and database readiness endpoints."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.db.runtime import DatabaseRuntime, database_status

router = APIRouter(prefix="/health")


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, Literal["ok", "unconfigured", "unavailable"]]


@router.get("/live", response_model=LiveResponse, summary="Check whether the API process is live")
def live() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", response_model=ReadyResponse, summary="Check runtime database readiness")
def ready(request: Request, response: Response) -> ReadyResponse:
    runtime: DatabaseRuntime | None = getattr(request.app.state, "database_runtime", None)
    checks = database_status(runtime)
    is_ready = all(value == "ok" for value in checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="ok" if is_ready else "unavailable", checks=checks)
