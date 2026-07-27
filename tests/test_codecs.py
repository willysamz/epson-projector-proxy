import pytest

from app.codecs import BoolCodec, EnumCodec, NumberCodec, VolumeCodec


def test_enum_roundtrip():
    c = EnumCodec({"30": "HDMI1", "A0": "HDMI2", "10": "PC"})
    assert c.to_ha("30") == "HDMI1"
    assert c.to_ha("a0") == "HDMI2"  # case-insensitive raw
    assert c.to_raw("HDMI2") == "A0"
    assert c.options == ["HDMI1", "HDMI2", "PC"]


def test_enum_unknown_passthrough():
    c = EnumCodec({"00": "High"})
    assert c.to_ha("FF") == "FF"  # unknown raw -> raw
    assert c.to_raw("Nope") == "Nope"  # unknown name -> unchanged


def test_bool():
    c = BoolCodec()
    assert c.to_ha("ON") == "on"
    assert c.to_ha("off") == "off"
    assert c.to_raw("on") == "ON"
    assert c.to_raw("off") == "OFF"


def test_number():
    c = NumberCodec(min=0, max=255, step=1)
    assert c.to_ha("126") == 126
    assert c.to_raw(200) == "200"
    assert (c.min, c.max, c.step) == (0, 255, 1)


def test_volume_level():
    c = VolumeCodec(step_raw=23, max_level=11)
    assert c.to_ha("0") == 0
    assert c.to_ha("23") == 1
    assert c.to_ha("232") == 10
    assert c.to_ha("255") == 11  # clamped to max_level
    with pytest.raises(NotImplementedError):
        c.to_raw(5)
