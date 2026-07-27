import pytest

from app.config import Settings
from app.poller import Poller


class RecordingMqtt:
    def __init__(self):
        self.published = []  # (topic, payload, retain)

    async def publish(self, topic, payload, retain=False):
        self.published.append((topic, payload, retain))

    def last(self, topic):
        vals = [p for (t, p, _) in self.published if t == topic]
        return vals[-1] if vals else None


class FakeClient:
    def __init__(self, state, unreachable=False):
        self.state = state
        self.unreachable = unreachable

    async def query(self, cmd):
        from app.projector_client import ProjectorUnreachable

        if self.unreachable:
            raise ProjectorUnreachable("down")
        return self.state.get(cmd)


@pytest.mark.asyncio
async def test_poll_publishes_power_and_states_when_on():
    state = {
        "PWR": "01",
        "SOURCE": "30",
        "CMODE": "07",
        "BRIGHT": "126",
        "LAMP": "5850",
        "VOL": "23",
        "MUTE": "OFF",
    }
    mqtt = RecordingMqtt()
    p = Poller(FakeClient(state), mqtt, Settings())
    await p.poll_once()
    assert mqtt.last("epson/available") == "online"
    assert mqtt.last("epson/power/state") == "on"
    assert mqtt.last("epson/power_available") == "online"
    assert mqtt.last("epson/source/state") == "HDMI1"
    assert mqtt.last("epson/brightness/state") == 126
    assert mqtt.last("epson/volume/state") == 1  # 23 // 23 -> level 1


@pytest.mark.asyncio
async def test_poll_gates_picture_props_when_off():
    state = {"PWR": "00"}
    mqtt = RecordingMqtt()
    p = Poller(FakeClient(state), mqtt, Settings())
    await p.poll_once()
    assert mqtt.last("epson/power/state") == "off"
    assert mqtt.last("epson/power_available") == "offline"
    # picture props are not queried/published while off
    assert mqtt.last("epson/contrast/state") is None


@pytest.mark.asyncio
async def test_poll_unreachable_marks_offline():
    mqtt = RecordingMqtt()
    p = Poller(FakeClient({}, unreachable=True), mqtt, Settings())
    await p.poll_once()
    assert mqtt.last("epson/available") == "offline"


@pytest.mark.asyncio
async def test_discovery_published_once():
    state = {"PWR": "01", "SOURCE": "30"}
    mqtt = RecordingMqtt()
    p = Poller(FakeClient(state), mqtt, Settings())
    await p.poll_once()
    await p.poll_once()
    cfgs = [t for (t, _, _) in mqtt.published if t.endswith("/config")]
    # each entity's config published exactly once across two cycles
    assert len(cfgs) == len(set(cfgs))
