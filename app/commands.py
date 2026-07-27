"""Route an MQTT <prop>/set payload to the projector via the registry codec."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.codecs import VolumeCodec
from app.registry import by_name

if TYPE_CHECKING:
    from app.projector_client import EpsonClient

log = structlog.get_logger()


class CommandHandler:
    def __init__(self, client: EpsonClient, volume_prop_name: str = "volume") -> None:
        self.client = client
        self.volume_prop_name = volume_prop_name

    async def handle(self, prop_name: str, payload: str) -> bool:
        prop = by_name(prop_name)
        if prop is None or not prop.settable:
            log.warning("command.ignored", prop=prop_name)
            return False

        if isinstance(prop.codec, VolumeCodec):
            return await self._set_volume(prop, int(float(payload)))

        raw = prop.codec.to_raw(payload)
        ok = await self.client.set(prop.cmd, raw)
        log.info("command.set", prop=prop_name, raw=raw, ok=ok)
        return ok

    async def _set_volume(self, prop, target_level: int) -> bool:
        max_level = getattr(prop.codec, "max_level", 11)
        target = max(0, min(target_level, max_level))
        current = None
        for _ in range(20):
            raw = await self.client.query(prop.cmd)
            if raw is None:
                return False
            current = prop.codec.to_ha(raw)
            if current == target:
                return True
            ok = await self.client.set(prop.cmd, "INC" if current < target else "DEC")
            if not ok:
                break
        log.warning("command.volume_cap_reached", target=target, current=current)
        return False
