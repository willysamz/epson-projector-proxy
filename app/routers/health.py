from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.dependencies import get_projector_client, get_startup_time

router = APIRouter()


@router.get("/healthz/live")
async def live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/healthz/ready")
async def ready() -> JSONResponse:
    client = get_projector_client()
    connected = bool(client and getattr(client, "connected", False))
    uptime = (datetime.now(UTC) - get_startup_time()).total_seconds()
    return JSONResponse(
        {"status": "ok", "projector_connected": connected, "uptime_seconds": uptime}
    )
