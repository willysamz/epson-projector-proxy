"""Declarative property registry — the single source of truth for discovery,
polling, and command routing. One Prop row per controllable/observable value."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.codecs import BoolCodec, Codec, EnumCodec, NumberCodec, VolumeCodec


class EntityType(str, Enum):
    SWITCH = "switch"
    SELECT = "select"
    NUMBER = "number"
    SENSOR = "sensor"


class Category(str, Enum):
    PRIMARY = "primary"
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class Prop:
    name: str
    friendly: str
    cmd: str
    entity: EntityType
    codec: Codec
    category: Category = Category.PRIMARY
    power_gated: bool = True
    settable: bool = True
    unit: str | None = None
    icon: str | None = None


# --- code maps (seeded; finalized in Task 5 against the live projector/library) ---
SOURCE_MAP = {"30": "HDMI1", "A0": "HDMI2", "10": "PC", "20": "PC2"}
LAMP_POWER_MAP = {"00": "High", "01": "ECO"}  # 1080 rejects "02" Medium (LUMINANCE 02 -> ERR)
IRIS_MAP = {"00": "Off", "01": "Normal", "02": "High"}
# CMODE codes verified against the live HC1080: it only ACCEPTS + holds these three
# for standard HDMI signals. "Natural" (07) and "Game" (0D) from the generic Epson
# library ERR / auto-revert (Epson gates color modes by input signal), so they are not
# offered. Names follow the amosyuen/ha-epson-projector-link const map.
CMODE_MAP = {"06": "Dynamic", "0C": "Bright Cinema", "15": "Cinema"}
# ASPECT and OVSCAN are intentionally NOT modeled in v1: neither is defined in the
# authoritative library, ASPECT returns an ambiguous two-token value ("00 30") with an
# unverified set format, and their option maps could not be confirmed without disruptively
# cycling the (in-use) projector. Deferred to a follow-up once the projector is free.


PROPS: list[Prop] = [
    Prop(
        "power",
        "Power",
        "PWR",
        EntityType.SWITCH,
        BoolCodec(on_raw="ON", off_raw="OFF"),
        category=Category.PRIMARY,
        power_gated=False,
        icon="mdi:projector",
    ),
    Prop(
        "source", "Source", "SOURCE", EntityType.SELECT, EnumCodec(SOURCE_MAP), icon="mdi:hdmi-port"
    ),
    Prop(
        "picture_mode",
        "Picture Mode",
        "CMODE",
        EntityType.SELECT,
        EnumCodec(CMODE_MAP),
        icon="mdi:palette",
    ),
    Prop(
        "lamp_power",
        "Lamp Power",
        "LUMINANCE",
        EntityType.SELECT,
        EnumCodec(LAMP_POWER_MAP),
        icon="mdi:lightning-bolt",
    ),
    Prop(
        "auto_iris",
        "Auto Iris",
        "IRIS",
        EntityType.SELECT,
        EnumCodec(IRIS_MAP),
        icon="mdi:camera-iris",
    ),
    Prop(
        "brightness",
        "Brightness",
        "BRIGHT",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        icon="mdi:brightness-6",
    ),
    Prop(
        "mute",
        "A/V Mute",
        "MUTE",
        EntityType.SWITCH,
        BoolCodec(on_raw="ON", off_raw="OFF"),
        icon="mdi:eye-off",
    ),
    Prop(
        "volume",
        "Volume",
        "VOL",
        EntityType.NUMBER,
        VolumeCodec(step_raw=23, max_level=11),
        icon="mdi:volume-high",
    ),
    # --- set-once picture/geometry (Configuration drawer) ---
    Prop(
        "contrast",
        "Contrast",
        "CONTRAST",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "saturation",
        "Color Saturation",
        "DENSITY",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "tint", "Tint", "TINT", EntityType.NUMBER, NumberCodec(0, 255, 1), category=Category.CONFIG
    ),
    Prop(
        "sharpness",
        "Sharpness",
        "SHARP",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "color_temp",
        "Color Temperature",
        "CTEMP",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "h_flip",
        "Horizontal Flip",
        "HREVERSE",
        EntityType.SWITCH,
        BoolCodec(on_raw="ON", off_raw="OFF"),
        category=Category.CONFIG,
    ),
    Prop(
        "v_flip",
        "Vertical Flip",
        "VREVERSE",
        EntityType.SWITCH,
        BoolCodec(on_raw="ON", off_raw="OFF"),
        category=Category.CONFIG,
    ),
    Prop(
        "zoom",
        "Digital Zoom",
        "ZOOM",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "v_keystone",
        "Vertical Keystone",
        "VKEYSTONE",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    Prop(
        "h_keystone",
        "Horizontal Keystone",
        "HKEYSTONE",
        EntityType.NUMBER,
        NumberCodec(0, 255, 1),
        category=Category.CONFIG,
    ),
    # --- read-only diagnostics (not power-gated where the projector answers in standby) ---
    Prop(
        "lamp_hours",
        "Lamp Hours",
        "LAMP",
        EntityType.SENSOR,
        NumberCodec(0, 100000, 1),
        category=Category.DIAGNOSTIC,
        power_gated=False,
        settable=False,
        unit="h",
        icon="mdi:timer-outline",
    ),
    Prop(
        "signal",
        "Signal",
        "SIGNAL",
        EntityType.SENSOR,
        EnumCodec({"00": "No signal", "01": "Signal present"}),
        category=Category.DIAGNOSTIC,
        settable=False,
        icon="mdi:import",
    ),
    Prop(
        "serial",
        "Serial Number",
        "SNO",
        EntityType.SENSOR,
        EnumCodec({}),
        category=Category.DIAGNOSTIC,
        power_gated=False,
        settable=False,
        icon="mdi:identifier",
    ),
]

_BY_NAME = {p.name: p for p in PROPS}


def by_name(name: str) -> Prop | None:
    return _BY_NAME.get(name)


def by_cmd(cmd: str) -> Prop | None:
    for p in PROPS:
        if p.cmd == cmd:
            return p
    return None


def settable_props() -> list[Prop]:
    return [p for p in PROPS if p.settable]


def readable_props() -> list[Prop]:
    return list(PROPS)
