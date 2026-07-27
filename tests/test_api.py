from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_health_live():
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    with patch("app.main.EpsonClient", return_value=mock_client):
        # MQTT disabled path: force settings.mqtt_host unreachable is complex;
        # instead patch _start_mqtt to a no-op so lifespan is pure.
        with patch("app.main._start_mqtt", new=AsyncMock(return_value=None)):
            from app.main import app

            with TestClient(app) as client:
                r = client.get("/healthz/live")
                assert r.status_code == 200
                assert r.json()["status"] == "ok"


def test_health_ready():
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    with patch("app.main.EpsonClient", return_value=mock_client):
        with patch("app.main._start_mqtt", new=AsyncMock(return_value=None)):
            from app.main import app

            with TestClient(app) as client:
                r = client.get("/healthz/ready")
                assert r.status_code == 200
                assert "projector_connected" in r.json()


def test_command_topic_parsing():
    from app.main import _parse_set_topic

    assert _parse_set_topic("epson/source/set", "epson") == "source"
    assert _parse_set_topic("epson/brightness/set", "epson") == "brightness"
    assert _parse_set_topic("epson/source/state", "epson") is None
    assert _parse_set_topic("other/source/set", "epson") is None


@pytest.mark.asyncio
async def test_shutdown_closes_client_even_if_poller_stop_raises():
    import asyncio

    from app.main import _shutdown

    client = MagicMock()
    client.close = AsyncMock()
    poller = MagicMock()
    poller.stop = AsyncMock(side_effect=RuntimeError("boom"))
    ctx = MagicMock()
    ctx.__aexit__ = AsyncMock()
    cmd_task = asyncio.create_task(asyncio.sleep(3600))
    await _shutdown((ctx, poller, cmd_task), client)
    client.close.assert_awaited_once()  # runs despite poller.stop raising
    ctx.__aexit__.assert_awaited()


@pytest.mark.asyncio
async def test_command_subscriber_triggers_poll_on_successful_set():
    from app.main import _command_subscriber

    class Msg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    class FakeMqtt:
        async def subscribe(self, f):
            pass

        @property
        def messages(self):
            async def gen():
                yield Msg("epson/source/set", b"HDMI2")

            return gen()

    handler = MagicMock()
    handler.handle = AsyncMock(return_value=True)
    poller = MagicMock()
    await _command_subscriber(FakeMqtt(), handler, poller, "epson")
    handler.handle.assert_awaited_once_with("source", "HDMI2")
    poller.trigger_immediate_poll.assert_called_once()


@pytest.mark.asyncio
async def test_command_subscriber_no_poll_when_handle_false():
    from app.main import _command_subscriber

    class Msg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    class FakeMqtt:
        async def subscribe(self, f):
            pass

        @property
        def messages(self):
            async def gen():
                yield Msg("epson/source/set", b"HDMI2")

            return gen()

    handler = MagicMock()
    handler.handle = AsyncMock(return_value=False)
    poller = MagicMock()
    await _command_subscriber(FakeMqtt(), handler, poller, "epson")
    handler.handle.assert_awaited_once_with("source", "HDMI2")
    poller.trigger_immediate_poll.assert_not_called()
