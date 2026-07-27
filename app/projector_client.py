"""Serialized TCP client for Epson ESC/VP.net (port 3629, no auth).

One persistent connection behind an asyncio.Lock; both the poller and command
handler funnel through it, so there are never competing sockets. Any transport
error resets the connection and is surfaced as ProjectorUnreachable; the next
call reconnects transparently."""

from __future__ import annotations

import asyncio

import structlog

log = structlog.get_logger()

HANDSHAKE = b"ESC/VP.net\x10\x03\x00\x00\x00\x00"


class ProjectorError(Exception):
    pass


class ProjectorUnreachable(ProjectorError):
    pass


class EpsonClient:
    def __init__(self, host: str, port: int = 3629, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass

    async def _ensure_connected(self) -> None:
        if self.connected:
            return
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
        except (TimeoutError, OSError) as e:
            await self._reset()
            raise ProjectorUnreachable(f"connect failed: {e}") from e
        try:
            writer.write(HANDSHAKE)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(16), self.timeout)
        except (TimeoutError, OSError, asyncio.IncompleteReadError) as e:
            await self._close_writer(writer)
            raise ProjectorUnreachable(f"handshake io failed: {e}") from e
        if resp[14] != 0x20:
            await self._close_writer(writer)
            raise ProjectorUnreachable(f"handshake rejected: {resp!r}")
        self._reader, self._writer = reader, writer
        log.info("projector.connected", host=self.host, port=self.port)

    async def _reset(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = None
        self._writer = None

    async def _roundtrip(self, raw: str) -> str:
        await self._ensure_connected()
        assert self._reader is not None and self._writer is not None
        try:
            self._writer.write(raw.encode() + b"\r")
            await self._writer.drain()
            data = await asyncio.wait_for(self._reader.readuntil(b":"), self.timeout)
        except (TimeoutError, OSError, asyncio.IncompleteReadError) as e:
            await self._reset()
            raise ProjectorUnreachable(f"io failed on {raw!r}: {e}") from e
        return data.decode(errors="replace").strip().rstrip(":").strip()

    async def query(self, cmd: str) -> str | None:
        async with self._lock:
            resp = await self._roundtrip(f"{cmd}?")
        if resp == "ERR" or resp.endswith("ERR"):
            return None
        if "=" in resp:
            return resp.split("=", 1)[1].strip()
        return resp or None

    async def set(self, cmd: str, arg: str) -> bool:
        async with self._lock:
            resp = await self._roundtrip(f"{cmd} {arg}")
        return "ERR" not in resp

    async def close(self) -> None:
        async with self._lock:
            await self._reset()
