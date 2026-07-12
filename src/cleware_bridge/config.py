"""Configuration management via environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    """Immutable bridge configuration loaded from environment variables."""

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "cleware/ampel/"
    log_level: str = "INFO"
    device_id: str = "default"

    @classmethod
    def from_env(cls) -> BridgeConfig:
        """Load configuration from environment variables with defaults."""
        topic_prefix = os.environ.get("MQTT_TOPIC_PREFIX", "cleware/ampel/")
        if not topic_prefix.endswith("/"):
            topic_prefix += "/"

        port_str = os.environ.get("MQTT_PORT", "1883")
        try:
            port = int(port_str)
        except ValueError:
            port = 1883

        return cls(
            mqtt_host=os.environ.get("MQTT_HOST", "localhost"),
            mqtt_port=port,
            mqtt_username=os.environ.get("MQTT_USERNAME", ""),
            mqtt_password=os.environ.get("MQTT_PASSWORD", ""),
            mqtt_topic_prefix=topic_prefix,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            device_id=os.environ.get("DEVICE_ID", "default"),
        )
