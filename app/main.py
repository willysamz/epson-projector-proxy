from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI

from app import __version__
from app.commands import CommandHandler
from app.config import settings
from app.dependencies import set_projector_client, set_startup_time
from app.mqtt_client import MqttClient
from app.poller import Poller
from app.projector_client import EpsonClient
from app.routers import health

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()  # type: ignore[list-item]
        if settings.log_json
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        _LEVELS.get(settings.log_level.upper(), logging.INFO)
    ),
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()


def _parse_set_topic(topic: str, prefix: str) -> str | None:
    m = re.fullmatch(rf"{re.escape(prefix)}/([a-z0-9_]+)/set", topic)
    return m.group(1) if m else None


async def _command_subscriber(
    mqtt: MqttClient, handler: CommandHandler, poller: Poller, prefix: str
) -> None:
    try:
        await mqtt.subscribe(f"{prefix}/+/set")
        async for message in mqtt.messages:
            prop = _parse_set_topic(str(message.topic), prefix)
            if prop is None:
                continue
            payload = (
                message.payload.decode()
                if isinstance(message.payload, bytes)
                else str(message.payload)
            )
            try:
                ok = await handler.handle(prop, payload)
                if ok:
                    # Optimistic: reflect the change immediately so HA doesn't snap
                    # back to the old value; the triggered poll reconciles the truth.
                    await mqtt.publish(f"{prefix}/{prop}/state", payload, retain=True)
                    poller.trigger_immediate_poll()
            except Exception:  # noqa: BLE001
                log.exception("command.error", topic=str(message.topic))
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("command_subscriber.stopped")
        raise


async def _start_mqtt(client: EpsonClient) -> tuple | None:
    """Open MQTT session, start poller + command subscriber. Returns teardown handles
    or None if MQTT is not reachable (service still serves health)."""
    prefix = settings.mqtt_topic_prefix
    mqtt = MqttClient(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        client_id=settings.mqtt_client_id,
        keepalive=settings.mqtt_keepalive,
        qos=settings.mqtt_qos,
        availability_topic=f"{prefix}/bridge/available",
    )
    ctx = mqtt.session()
    await ctx.__aenter__()
    try:
        poller = Poller(client, mqtt, settings)
        await poller.start()
        handler = CommandHandler(client)
        cmd_task = asyncio.create_task(_command_subscriber(mqtt, handler, poller, prefix))
    except Exception:  # noqa: BLE001
        await ctx.__aexit__(None, None, None)
        raise
    return ctx, poller, cmd_task


async def _shutdown(handles: tuple | None, client: EpsonClient) -> None:
    """Best-effort teardown: each step is independent so a failure in one
    never prevents closing the projector socket."""
    if handles is not None:
        ctx, poller, cmd_task = handles
        cmd_task.cancel()
        try:
            await cmd_task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            log.exception("command_subscriber.shutdown_error")
        try:
            await poller.stop()
        except Exception:  # noqa: BLE001
            log.exception("poller.stop_failed")
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            log.exception("mqtt.close_failed")
    try:
        await client.close()
    except Exception:  # noqa: BLE001
        log.exception("client.close_failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    set_startup_time(datetime.now(UTC))
    client = EpsonClient(
        settings.projector_host, settings.projector_port, settings.projector_timeout
    )
    set_projector_client(client)
    handles = None
    try:
        handles = await _start_mqtt(client)
    except Exception:  # noqa: BLE001
        log.exception("mqtt.start_failed")
    yield
    await _shutdown(handles, client)


app = FastAPI(title="Epson Projector Proxy", version=__version__, lifespan=lifespan)
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root() -> dict:
    return {"name": "Epson Projector Proxy", "version": __version__}
