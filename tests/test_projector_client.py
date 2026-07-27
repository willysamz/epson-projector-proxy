import pytest

from app.projector_client import EpsonClient, ProjectorUnreachable


@pytest.mark.asyncio
async def test_query_returns_value(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("PWR") == "01"
    assert await c.query("SOURCE") == "30"
    await c.close()


@pytest.mark.asyncio
async def test_query_err_returns_none(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("GAMMA") is None  # unknown cmd -> ERR -> None
    await c.close()


@pytest.mark.asyncio
async def test_set_ok_and_reflected(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.set("SOURCE", "A0") is True
    assert await c.query("SOURCE") == "A0"
    await c.close()


@pytest.mark.asyncio
async def test_set_err_returns_false(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.set("GAMMA", "00") is False
    await c.close()


@pytest.mark.asyncio
async def test_volume_stepping(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("VOL") == "0"
    await c.set("VOL", "INC")
    assert await c.query("VOL") == "23"
    await c.close()


@pytest.mark.asyncio
async def test_reconnect_after_transport_error(fake_projector):
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("PWR") == "01"
    fake_projector.fail_next = True
    with pytest.raises(ProjectorUnreachable):
        await c.query("PWR")
    # next call transparently reconnects
    assert await c.query("PWR") == "01"
    await c.close()


@pytest.mark.asyncio
async def test_unreachable_host_raises():
    c = EpsonClient("127.0.0.1", 1, timeout=1)  # nothing listening
    with pytest.raises(ProjectorUnreachable):
        await c.query("PWR")
    await c.close()


@pytest.mark.asyncio
async def test_handshake_rejection_closes_socket(fake_projector):
    import asyncio as _a

    fake_projector.reject_handshake = True
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    with pytest.raises(ProjectorUnreachable):
        await c.query("PWR")
    await _a.sleep(0.05)
    assert fake_projector.open_conns == 0  # no leaked connection
    assert c.connected is False
    await c.close()


@pytest.mark.asyncio
async def test_query_skips_unsolicited_event(fake_projector):
    # The projector pushes an unsolicited IMEVENT (as on an input change) before
    # the next reply; the client must resync and still return PWR's real value.
    fake_projector.inject_event = 1
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("PWR") == "01"
    await c.close()


@pytest.mark.asyncio
async def test_poll_sequence_stays_in_sync_after_event(fake_projector):
    # An IMEVENT must not shift every following reply by one (the bug that made
    # VOL? return MUTE's "OFF" -> int() crash). Each query stays matched to its cmd.
    fake_projector.inject_event = 1
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.query("SOURCE") == "30"
    assert await c.query("MUTE") == "OFF"
    assert await c.query("VOL") == "0"
    assert await c.query("CONTRAST") == "126"
    await c.close()


@pytest.mark.asyncio
async def test_set_skips_unsolicited_event(fake_projector):
    fake_projector.inject_event = 1
    c = EpsonClient(fake_projector.host, fake_projector.port, timeout=2)
    assert await c.set("SOURCE", "A0") is True
    assert await c.query("SOURCE") == "A0"
    await c.close()
