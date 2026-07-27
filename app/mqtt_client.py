"""Thin aiomqtt wrapper: one long-lived client, LWT/birth on an availability
topic, retained publishes, shared by poller (publish) and command subscriber."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiomqtt
import structlog

log = structlog.get_logger()


class MqttClient:
    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        client_id: str = "epson-projector-proxy",
        keepalive: int = 60,
        qos: int = 0,
        availability_topic: str = "epson/bridge/available",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.keepalive = keepalive
        self.qos = qos
        self.availability_topic = availability_topic
        self._client: aiomqtt.Client | None = None

    def _encode(self, payload: str | bytes | dict[str, Any]) -> bytes:
        if isinstance(payload, dict):
            return json.dumps(payload).encode()
        if isinstance(payload, str):
            return payload.encode()
        return payload

    def _new_client(self) -> aiomqtt.Client:
        will = aiomqtt.Will(
            topic=self.availability_topic, payload=b"offline", qos=self.qos, retain=True
        )
        return aiomqtt.Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            identifier=self.client_id,
            keepalive=self.keepalive,
            will=will,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[MqttClient]:
        async with self._new_client() as client:
            self._client = client
            await client.publish(self.availability_topic, b"online", qos=self.qos, retain=True)
            try:
                yield self
            finally:
                try:
                    await client.publish(
                        self.availability_topic, b"offline", qos=self.qos, retain=True
                    )
                except Exception:  # noqa: BLE001
                    pass
                self._client = None

    async def publish(
        self, topic: str, payload: str | bytes | dict[str, Any], retain: bool = False
    ) -> None:
        if self._client is None:
            raise RuntimeError("publish outside session()")
        await self._client.publish(topic, self._encode(payload), qos=self.qos, retain=retain)

    async def subscribe(self, topic_filter: str) -> None:
        if self._client is None:
            raise RuntimeError("subscribe outside session()")
        await self._client.subscribe(topic_filter)

    @property
    def messages(self) -> AsyncIterator[aiomqtt.Message]:
        if self._client is None:
            raise RuntimeError("messages outside session()")
        return self._client.messages
