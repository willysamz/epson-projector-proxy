from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.projector_client import EpsonClient

_client: EpsonClient | None = None
_startup: datetime | None = None


def set_projector_client(c: EpsonClient) -> None:
    global _client
    _client = c


def get_projector_client() -> EpsonClient | None:
    return _client


def set_startup_time(t: datetime) -> None:
    global _startup
    _startup = t


def get_startup_time() -> datetime:
    return _startup or datetime.now(UTC)
