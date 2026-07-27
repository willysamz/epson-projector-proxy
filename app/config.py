"""Application settings via pydantic-settings. Env vars are UPPER_SNAKE of each field."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="", env_nested_delimiter="__", case_sensitive=False
    )

    # Projector transport (ESC/VP.net over TCP)
    projector_host: str = "192.168.1.100"
    projector_port: int = 3629
    projector_timeout: float = 5.0
    poll_interval: float = 15.0

    # MQTT broker
    mqtt_host: str = "mqtt"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "epson-projector-proxy"
    mqtt_topic_prefix: str = "epson"
    mqtt_keepalive: int = 60
    mqtt_qos: int = 0

    # Home Assistant MQTT discovery
    ha_discovery_enabled: bool = True
    ha_discovery_prefix: str = "homeassistant"
    ha_device_name: str = "Epson HC1080 Projector"
    ha_device_id: str = "epson_projector"

    # Server
    server_host: str = "0.0.0.0"  # noqa: S104
    server_port: int = 8080

    # Logging
    log_level: str = "INFO"
    log_json: bool = True


settings = Settings()
