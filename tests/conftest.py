import asyncio

import pytest_asyncio


class FakeProjector:
    """Minimal ESC/VP.net TCP server for tests."""

    def __init__(self):
        # raw ESC/VP21 state: cmd -> value string
        self.state = {
            "PWR": "01",
            "SOURCE": "30",
            "CMODE": "07",
            "LUMINANCE": "00",
            "IRIS": "01",
            "BRIGHT": "126",
            "MUTE": "OFF",
            "VOL": "0",
            "CONTRAST": "126",
            "LAMP": "5850",
            "SNO": "TESTSERIAL01",
        }
        self.server = None
        self.host = "127.0.0.1"
        self.port = None
        self.fail_next = False  # force one transport error
        self.reject_handshake = False  # force handshake rejection
        self.open_conns = 0  # track open connections for socket leak tests
        self.inject_event = 0  # emit N unsolicited IMEVENT messages before upcoming replies

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader, writer):
        self.open_conns += 1
        try:
            handshake = await reader.readexactly(16)
            assert handshake.startswith(b"ESC/VP.net")
            reply = bytearray(16)
            if self.reject_handshake:
                reply[14] = 0x00  # rejection
            else:
                reply[14] = 0x20  # success
            writer.write(bytes(reply))
            await writer.drain()
            if self.reject_handshake:
                # Wait for client to close; returns b'' when closed, blocks if client leaks
                try:
                    await reader.read()
                except Exception:
                    pass
                return
            while True:
                try:
                    line = await reader.readuntil(b"\r")
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break
                if self.fail_next:
                    self.fail_next = False
                    writer.close()
                    return
                text = line.decode().strip()
                if text.endswith("?"):
                    cmd = text[:-1]
                    out = f"{cmd}={self.state[cmd]}\r:".encode() if cmd in self.state else b"ERR\r:"
                else:
                    parts = text.split(None, 1)
                    cmd = parts[0]
                    arg = parts[1] if len(parts) > 1 else ""
                    if cmd in self.state:
                        if cmd == "VOL" and arg in ("INC", "DEC"):
                            v = int(self.state["VOL"])
                            v = min(255, v + 23) if arg == "INC" else max(0, v - 23)
                            self.state["VOL"] = str(v)
                        elif arg:
                            self.state[cmd] = arg
                        out = b":"
                    else:
                        out = b"ERR\r:"
                # Simulate the projector pushing an unsolicited IMEVENT (as it does on
                # an input/signal change) just before a normal reply — this desyncs a
                # naive one-read-per-command client.
                if self.inject_event > 0:
                    self.inject_event -= 1
                    writer.write(b"IMEVENT=0001 03 00000002 00000000 T1 F1\r:")
                writer.write(out)
                await writer.drain()
        finally:
            try:
                writer.close()
            except Exception:
                pass
            self.open_conns -= 1


@pytest_asyncio.fixture
async def fake_projector():
    fp = FakeProjector()
    await fp.start()
    yield fp
    await fp.stop()
