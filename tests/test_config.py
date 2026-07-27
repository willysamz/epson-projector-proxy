from app.config import Settings


def test_defaults():
    s = Settings()
    assert s.projector_host == "192.168.1.100"
    assert s.projector_port == 3629
    assert s.poll_interval == 15.0
    assert s.mqtt_topic_prefix == "epson"
    assert s.ha_device_id == "epson_projector"


def test_env_override(monkeypatch):
    monkeypatch.setenv("PROJECTOR_HOST", "10.0.0.5")
    monkeypatch.setenv("POLL_INTERVAL", "30")
    s = Settings()
    assert s.projector_host == "10.0.0.5"
    assert s.poll_interval == 30.0
