import json

import pytest

from app.mqtt_client import MqttClient


def test_encode_payload_dict():
    c = MqttClient(host="mqtt")
    assert c._encode({"a": 1}) == json.dumps({"a": 1}).encode()
    assert c._encode("on") == b"on"
    assert c._encode(b"x") == b"x"


@pytest.mark.asyncio
async def test_publish_outside_session_raises():
    c = MqttClient(host="mqtt")
    with pytest.raises(RuntimeError):
        await c.publish("t", "x")
