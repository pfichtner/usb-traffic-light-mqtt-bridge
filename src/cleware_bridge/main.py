"""Main entry point for the Cleware MQTT Bridge."""

from __future__ import annotations

import logging
import signal
import sys

from .cleware import ClewareTrafficLight
from .config import BridgeConfig
from .mqtt_client import MQTTBridge
from .traffic_light import MockTrafficLight, TrafficLight

logger = logging.getLogger("cleware_bridge")


def _setup_logging(level: str) -> None:
    """Configure structured logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)


def _create_traffic_light(config: BridgeConfig) -> TrafficLight:
    """Create the appropriate traffic light implementation.

    Uses MockTrafficLight when LIGHT_BACKEND=mock is set,
    otherwise attempts to use real Cleware USB hardware.
    """
    import os

    backend = os.environ.get("LIGHT_BACKEND", "auto")

    if backend == "mock":
        logger.info("Using MockTrafficLight (LIGHT_BACKEND=mock)")
        return MockTrafficLight()

    if backend == "cleware":
        logger.info("Using ClewareTrafficLight (LIGHT_BACKEND=cleware)")
        return ClewareTrafficLight(device_id=config.device_id)

    # Auto-detect: try real hardware, otherwise fail loudly
    try:
        light = ClewareTrafficLight(device_id=config.device_id)
        if light.is_connected():
            return light
    except Exception as exc:
        logger.error("Could not initialize Cleware hardware: %s", exc)
        raise SystemExit(1) from exc

    logger.error("No Cleware device found. Set LIGHT_BACKEND=mock to run without hardware.")
    raise SystemExit(1)


def main() -> None:
    """Run the Cleware MQTT Bridge."""
    config = BridgeConfig.from_env()
    _setup_logging(config.log_level)

    logger.info("Starting Cleware MQTT Bridge v1.0.0")
    logger.info(
        "MQTT: %s:%d, prefix: %s",
        config.mqtt_host,
        config.mqtt_port,
        config.mqtt_topic_prefix,
    )

    light = _create_traffic_light(config)
    bridge = MQTTBridge(config, light)

    def shutdown(sig: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down...", sig)
        bridge.stop()
        light.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        bridge.stop()
        light.close()
        logger.info("Bridge stopped")
