"""Background poll loop: read the projector, publish deltas + power-gating to MQTT."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from app.discovery import discovery_payload
from app.projector_client import ProjectorUnreachable
from app.registry import readable_props

if TYPE_CHECKING:
    from app.config import Settings
    from app.mqtt_client import MqttClient
    from app.projector_client import EpsonClient

log = structlog.get_logger()


class Poller:
    def __init__(self, client: EpsonClient, mqtt: MqttClient, settings: Settings) -> None:
        self.client = client
        self.mqtt = mqtt
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._immediate = asyncio.Event()
        self._discovery_published = False
        self._last: dict[str, Any] = {}

    @property
    def _prefix(self) -> str:
        return self.settings.mqtt_topic_prefix

    def trigger_immediate_poll(self) -> None:
        self._immediate.set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except TimeoutError:
                self._task.cancel()

    async def _run(self) -> None:
        await asyncio.sleep(2)
        while not self._stop.is_set():
            try:
                await self.poll_once()
            except Exception:  # noqa: BLE001
                log.exception("poll.error")
            self._immediate.clear()
            done, pending = await asyncio.wait(
                {
                    asyncio.create_task(self._stop.wait()),
                    asyncio.create_task(self._immediate.wait()),
                },
                timeout=self.settings.poll_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    async def _publish(self, topic: str, payload: Any) -> None:
        await self.mqtt.publish(topic, payload, retain=True)

    async def _publish_delta(self, topic: str, payload: Any) -> None:
        if self._last.get(topic) != payload:
            self._last[topic] = payload
            await self._publish(topic, payload)

    async def _publish_discovery(self) -> None:
        for prop in readable_props():
            topic, payload = discovery_payload(
                prop,
                discovery_prefix=self.settings.ha_discovery_prefix,
                topic_prefix=self._prefix,
                device_id=self.settings.ha_device_id,
                device_name=self.settings.ha_device_name,
            )
            await self._publish(topic, payload)
        self._discovery_published = True

    async def poll_once(self) -> None:
        prefix = self._prefix
        try:
            pwr = await self.client.query("PWR")
        except ProjectorUnreachable:
            await self._publish(f"{prefix}/available", "offline")
            return

        await self._publish(f"{prefix}/available", "online")
        if self.settings.ha_discovery_enabled and not self._discovery_published:
            await self._publish_discovery()

        on = pwr == "01"
        await self._publish_delta(f"{prefix}/power/state", "on" if on else "off")
        await self._publish(f"{prefix}/power_available", "online" if on else "offline")

        # lamp hours / serial read even in standby
        for prop in readable_props():
            if prop.name == "power":
                continue
            if prop.power_gated and not on:
                continue
            try:
                raw = await self.client.query(prop.cmd)
            except ProjectorUnreachable:
                await self._publish(f"{prefix}/available", "offline")
                return
            if raw is None:
                continue
            value = prop.codec.to_ha(raw)
            await self._publish_delta(f"{prefix}/{prop.name}/state", value)
