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

    # Max ESC/VP.net messages to skip while resyncing past unsolicited events
    # (the projector pushes e.g. IMEVENT on an input/signal change) before giving up.
    _MAX_SKIP = 8
    _IO_ERRORS = (TimeoutError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError)

    async def _read_msg(self) -> str:
        assert self._reader is not None
        data = await asyncio.wait_for(self._reader.readuntil(b":"), self.timeout)
        return data.decode(errors="replace").strip().rstrip(":").strip()

    async def query(self, cmd: str) -> str | None:
        """Send CMD? and return its value, or None on ERR.

        Skips unsolicited messages (e.g. IMEVENT pushed on an input change) and
        any stale reply whose key doesn't match the command, so an input-change
        event can't desync the request/response stream."""
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None
            try:
                self._writer.write(f"{cmd}?".encode() + b"\r")
                await self._writer.drain()
                for _ in range(self._MAX_SKIP):
                    resp = await self._read_msg()
                    if not resp:
                        continue
                    if "=" in resp:
                        key, val = resp.split("=", 1)
                        if key.strip().upper() == cmd.upper():
                            return val.strip()
                        log.debug("projector.skip", got=key.strip(), want=cmd)
                        continue
                    if resp.upper().endswith("ERR"):
                        return None
                    log.debug("projector.skip", got=resp, want=cmd)
            except self._IO_ERRORS as e:
                await self._reset()
                raise ProjectorUnreachable(f"io failed on {cmd}?: {e}") from e
            await self._reset()
            raise ProjectorUnreachable(
                f"desync: no reply matched {cmd}? within {self._MAX_SKIP} messages"
            )

    async def set(self, cmd: str, arg: str) -> bool:
        """Send CMD ARG and return True on ack (bare ':'), False on ERR.

        Skips unsolicited event messages that may precede the ack."""
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None
            try:
                self._writer.write(f"{cmd} {arg}".encode() + b"\r")
                await self._writer.drain()
                for _ in range(self._MAX_SKIP):
                    resp = await self._read_msg()
                    if resp == "":
                        return True
                    if resp.upper().endswith("ERR"):
                        return False
                    log.debug("projector.skip_set", got=resp, cmd=cmd)
            except self._IO_ERRORS as e:
                await self._reset()
                raise ProjectorUnreachable(f"io failed on set {cmd}: {e}") from e
            await self._reset()
            raise ProjectorUnreachable(
                f"desync: no ack for set {cmd} within {self._MAX_SKIP} messages"
            )

    async def close(self) -> None:
        async with self._lock:
            await self._reset()
