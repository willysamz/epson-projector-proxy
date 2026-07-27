from app.discovery import availability_list, discovery_payload
from app.registry import by_name

COMMON = dict(
    discovery_prefix="homeassistant",
    topic_prefix="epson",
    device_id="epson_projector",
    device_name="Epson HC1080 Projector",
)


def test_power_switch_payload():
    topic, p = discovery_payload(by_name("power"), **COMMON)
    assert topic == "homeassistant/switch/epson_projector_power/config"
    assert p["command_topic"] == "epson/power/set"
    assert p["state_topic"] == "epson/power/state"
    assert p["payload_on"] == "on" and p["payload_off"] == "off"
    assert p["device"]["identifiers"] == ["epson_projector"]
    # power is not gated -> no power_available topic
    avails = [a["topic"] for a in p["availability"]]
    assert "epson/power_available" not in avails
    assert p["availability_mode"] == "all"
    assert "entity_category" not in p


def test_source_select_payload():
    topic, p = discovery_payload(by_name("source"), **COMMON)
    assert topic == "homeassistant/select/epson_projector_source/config"
    assert "HDMI1" in p["options"]


def test_number_payload_has_range():
    _, p = discovery_payload(by_name("brightness"), **COMMON)
    assert p["min"] == 0 and p["max"] == 255 and p["step"] == 1
    assert p["mode"] == "slider"


def test_config_entity_category_and_gating():
    _, p = discovery_payload(by_name("contrast"), **COMMON)
    assert p["entity_category"] == "config"
    avails = [a["topic"] for a in p["availability"]]
    assert "epson/power_available" in avails  # gated -> greys out when off


def test_sensor_payload():
    _, p = discovery_payload(by_name("lamp_hours"), **COMMON)
    assert "command_topic" not in p  # sensors are read-only
    assert p["unit_of_measurement"] == "h"
    assert p["entity_category"] == "diagnostic"


def test_availability_list():
    base = [a["topic"] for a in availability_list("epson", power_gated=False)]
    gated = [a["topic"] for a in availability_list("epson", power_gated=True)]
    assert base == ["epson/bridge/available", "epson/available"]
    assert "epson/power_available" in gated
