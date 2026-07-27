from app.codecs import EnumCodec
from app.registry import PROPS, Category, EntityType, by_name, settable_props


def test_names_unique():
    names = [p.name for p in PROPS]
    assert len(names) == len(set(names))


def test_core_props_present():
    for n in (
        "power",
        "source",
        "picture_mode",
        "lamp_power",
        "brightness",
        "mute",
        "volume",
        "lamp_hours",
    ):
        assert by_name(n) is not None, n


def test_power_not_gated_others_gated():
    assert by_name("power").power_gated is False
    assert by_name("lamp_hours").power_gated is False  # readable in standby
    assert by_name("contrast").power_gated is True


def test_categories():
    assert by_name("power").category == Category.PRIMARY
    assert by_name("contrast").category == Category.CONFIG
    assert by_name("lamp_hours").category == Category.DIAGNOSTIC


def test_sensors_not_settable():
    for n in ("lamp_hours", "signal", "serial"):
        assert by_name(n).settable is False


def test_source_select_options():
    p = by_name("source")
    assert p.entity == EntityType.SELECT
    assert isinstance(p.codec, EnumCodec)
    assert "HDMI1" in p.codec.options


def test_settable_props_excludes_sensors():
    assert all(p.settable for p in settable_props())
    assert "lamp_hours" not in [p.name for p in settable_props()]


def test_picture_mode_options_filled():
    p = by_name("picture_mode")
    assert isinstance(p.codec, EnumCodec)
    # CMODE map finalized in Task 5 — the projector's current mode 0C must decode.
    assert "0C" in p.codec.raw_to_name
    assert p.codec.to_ha("0C") == "Bright Cinema"
    assert set(p.codec.options) == {"Dynamic", "Natural", "Bright Cinema", "Cinema"}


def test_aspect_and_overscan_not_modeled_in_v1():
    # Deferred (Task 5): not in the authoritative library, unverified option maps.
    assert by_name("aspect") is None
    assert by_name("overscan") is None
