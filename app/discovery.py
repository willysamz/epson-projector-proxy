"""Build Home Assistant MQTT discovery payloads from registry Props.

Topic convention: {discovery_prefix}/{component}/{object_id}/config (retained).
Every payload embeds the same device block so all entities group under one HA
device card. availability_mode='all' with two or three availability topics
implements power-gating."""

from __future__ import annotations

from typing import Any

from app.registry import Category, EntityType, Prop

DEVICE_MANUFACTURER = "Epson"
DEVICE_MODEL = "Home Cinema 1080"

_AVAIL = {"payload_available": "online", "payload_not_available": "offline"}


def device_block(device_id: str, device_name: str) -> dict[str, Any]:
    return {
        "identifiers": [device_id],
        "name": device_name,
        "manufacturer": DEVICE_MANUFACTURER,
        "model": DEVICE_MODEL,
    }


def topics(prefix: str, prop_name: str) -> dict[str, str]:
    return {"state": f"{prefix}/{prop_name}/state", "command": f"{prefix}/{prop_name}/set"}


def availability_list(prefix: str, power_gated: bool) -> list[dict[str, str]]:
    items = [
        {"topic": f"{prefix}/bridge/available", **_AVAIL},
        {"topic": f"{prefix}/available", **_AVAIL},
    ]
    if power_gated:
        items.append({"topic": f"{prefix}/power_available", **_AVAIL})
    return items


def _entity_category(prop: Prop) -> str | None:
    if prop.category == Category.CONFIG:
        return "config"
    if prop.category == Category.DIAGNOSTIC:
        return "diagnostic"
    return None


def discovery_payload(
    prop: Prop,
    *,
    discovery_prefix: str,
    topic_prefix: str,
    device_id: str,
    device_name: str,
) -> tuple[str, dict[str, Any]]:
    object_id = f"{device_id}_{prop.name}"
    t = topics(topic_prefix, prop.name)
    payload: dict[str, Any] = {
        "name": prop.friendly,
        "unique_id": object_id,
        "object_id": object_id,
        "state_topic": t["state"],
        "availability": availability_list(topic_prefix, prop.power_gated),
        "availability_mode": "all",
        "device": device_block(device_id, device_name),
    }
    if prop.icon:
        payload["icon"] = prop.icon
    cat = _entity_category(prop)
    if cat:
        payload["entity_category"] = cat
    if prop.settable:
        payload["command_topic"] = t["command"]

    if prop.entity == EntityType.SWITCH:
        payload["payload_on"] = "on"
        payload["payload_off"] = "off"
    elif prop.entity == EntityType.SELECT:
        payload["options"] = prop.codec.options  # type: ignore[attr-defined]
    elif prop.entity == EntityType.NUMBER:
        payload["min"] = getattr(prop.codec, "min", 0)
        payload["max"] = getattr(prop.codec, "max", getattr(prop.codec, "max_level", 255))
        payload["step"] = getattr(prop.codec, "step", 1)
        payload["mode"] = "slider"
    elif prop.entity == EntityType.SENSOR:
        if prop.unit:
            payload["unit_of_measurement"] = prop.unit

    component = prop.entity.value
    config_topic = f"{discovery_prefix}/{component}/{object_id}/config"
    return config_topic, payload
