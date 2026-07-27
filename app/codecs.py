"""Bidirectional codecs mapping raw ESC/VP21 tokens <-> Home Assistant values."""

from __future__ import annotations

from dataclasses import dataclass, field


class Codec:
    def to_ha(self, raw: str) -> str | int:
        raise NotImplementedError

    def to_raw(self, value: object) -> str:
        raise NotImplementedError


@dataclass
class EnumCodec(Codec):
    raw_to_name: dict[str, str]
    _name_to_raw: dict[str, str] = field(init=False, repr=False)
    _upper_to_name: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._name_to_raw = {v: k for k, v in self.raw_to_name.items()}
        self._upper_to_name = {k.upper(): v for k, v in self.raw_to_name.items()}

    @property
    def options(self) -> list[str]:
        return list(self.raw_to_name.values())

    def to_ha(self, raw: str) -> str:
        return self._upper_to_name.get(raw.upper(), raw)

    def to_raw(self, value: object) -> str:
        return self._name_to_raw.get(str(value), str(value))


@dataclass
class BoolCodec(Codec):
    on_raw: str = "ON"
    off_raw: str = "OFF"

    def to_ha(self, raw: str) -> str:
        return "on" if raw.strip().upper() == self.on_raw.upper() else "off"

    def to_raw(self, value: object) -> str:
        return self.on_raw if str(value) == "on" else self.off_raw


@dataclass
class NumberCodec(Codec):
    min: int = 0
    max: int = 255
    step: int = 1

    def to_ha(self, raw: str) -> int:
        return int(raw)

    def to_raw(self, value: object) -> str:
        return str(int(float(str(value))))


@dataclass
class VolumeCodec(Codec):
    step_raw: int = 23
    max_level: int = 11

    def to_ha(self, raw: str) -> int:
        return min(round(int(raw) / self.step_raw), self.max_level)

    def to_raw(self, value: object) -> str:
        raise NotImplementedError("volume is set by stepping INC/DEC, not absolute")
