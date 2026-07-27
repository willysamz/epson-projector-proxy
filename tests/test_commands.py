import pytest

from app.commands import CommandHandler


class SpyClient:
    def __init__(self, vol="0"):
        self.sets = []  # (cmd, arg)
        self.state = {"VOL": vol}

    async def set(self, cmd, arg):
        self.sets.append((cmd, arg))
        if cmd == "VOL" and arg in ("INC", "DEC"):
            v = int(self.state["VOL"])
            v = min(255, v + 23) if arg == "INC" else max(0, v - 23)
            self.state["VOL"] = str(v)
        return True

    async def query(self, cmd):
        return self.state.get(cmd)


@pytest.mark.asyncio
async def test_enum_set_encodes():
    c = SpyClient()
    h = CommandHandler(c)
    assert await h.handle("source", "HDMI2") is True
    assert c.sets == [("SOURCE", "A0")]


@pytest.mark.asyncio
async def test_switch_set_encodes():
    c = SpyClient()
    h = CommandHandler(c)
    await h.handle("mute", "on")
    assert c.sets == [("MUTE", "ON")]


@pytest.mark.asyncio
async def test_number_set_encodes():
    c = SpyClient()
    h = CommandHandler(c)
    await h.handle("brightness", "200")
    assert c.sets == [("BRIGHT", "200")]


@pytest.mark.asyncio
async def test_volume_steps_up_to_level():
    c = SpyClient(vol="0")
    h = CommandHandler(c)
    await h.handle("volume", "3")  # target level 3 -> 3 INC steps
    assert c.sets == [("VOL", "INC"), ("VOL", "INC"), ("VOL", "INC")]


@pytest.mark.asyncio
async def test_unknown_or_readonly_ignored():
    c = SpyClient()
    h = CommandHandler(c)
    assert await h.handle("nope", "x") is False
    assert await h.handle("lamp_hours", "5") is False
    assert c.sets == []
