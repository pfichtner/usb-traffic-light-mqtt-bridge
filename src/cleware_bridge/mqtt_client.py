from __future__ import annotations

import logging
import os
import uuid

import paho.mqtt.client as mqtt

from .config import BridgeConfig
from .models import (
    PATTERN_TOPIC_SUFFIX,
    TOPIC_COLOR_MAP,
    Color,
    LEDState,
    parse_pattern,
)
from .traffic_light import TrafficLight

logger = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self, config: BridgeConfig, light: TrafficLight) -> None:
        self._config = config
        self._light = light
        self._active_leds: set[Color] = set()

        client_id = os.environ.get("MQTT_CLIENT_ID", "")
        if not client_id:
            client_id = f"cleware-bridge-{uuid.uuid4().hex[:12]}"

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id,
            clean_session=True,
        )
        self._subscribe_topics: list[str] = []
        self._build_subscribe_topics()

    def _build_subscribe_topics(self) -> None:
        prefix = self._config.mqtt_topic_prefix.rstrip("/")
        self._subscribe_topics = [f"{prefix}/#"]

    def start(self) -> None:
        cfg = self._config

        if cfg.mqtt_username:
            self._client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)

        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        logger.info("Connecting to MQTT broker %s:%d", cfg.mqtt_host, cfg.mqtt_port)
        try:
            self._client.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
        except Exception as exc:
            logger.error("Initial MQTT connection failed: %s", exc)

        self._client.loop_forever()

    def stop(self) -> None:
        logger.info("Stopping MQTT bridge...")
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            logger.error("MQTT connection failed: %s", reason_code)
            return
        logger.info("MQTT connected")
        topic = self._subscribe_topics[0]
        client.subscribe(topic, qos=1)
        logger.info("Subscribed to %s", topic)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
        *args: object,
    ) -> None:
        if reason_code.is_failure:
            logger.warning("MQTT disconnected: %s", reason_code)
        else:
            logger.info("MQTT disconnected gracefully")

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        prefix = self._config.mqtt_topic_prefix.rstrip("/")

        if not topic.startswith(prefix):
            return

        suffix = topic[len(prefix) :].strip("/")
        payload_str = msg.payload.decode("utf-8", errors="replace")

        if suffix == PATTERN_TOPIC_SUFFIX:
            self._apply_pattern(payload_str)
            return

        if suffix not in TOPIC_COLOR_MAP:
            return

        color = TOPIC_COLOR_MAP[suffix]

        logger.info("Received command on %s: payload=%s", topic, payload_str)

        brightness = self._parse_brightness(payload_str)
        if brightness is None:
            return

        try:
            if brightness == 1:
                self._light.set_led(color, LEDState.ON)
                self._active_leds.add(color)
                logger.info("LED %s ON (active: %s)", color.to_name(), self._active_leds)
            else:
                self._light.set_led(color, LEDState.OFF)
                self._active_leds.discard(color)
                logger.info("LED %s OFF (active: %s)", color.to_name(), self._active_leds)
        except Exception as exc:
            logger.error("Failed to set LED %s: %s", color.to_name(), exc)

    def _apply_pattern(self, payload_str: str) -> None:
        """Apply a whole-device pattern, setting all LEDs atomically.

        LEDs in the parsed pattern are turned ON; every other LED is turned OFF.
        On an invalid pattern, a warning is logged and the device state is
        left unchanged.
        """
        logger.info("Received pattern command: payload=%s", payload_str)
        pattern = parse_pattern(payload_str)
        if pattern is None:
            logger.warning("Invalid pattern payload: %r", payload_str)
            return

        try:
            for color in Color:
                target = LEDState.ON if color in pattern else LEDState.OFF
                self._light.set_led(color, target)
            self._active_leds = set(pattern)
            logger.info(
                "Pattern applied: %s (active: %s)",
                payload_str.strip(),
                self._active_leds,
            )
        except Exception as exc:
            logger.error("Failed to apply pattern %r: %s", payload_str, exc)

    def _parse_brightness(self, payload: str) -> int | None:
        normalized = payload.strip().lower()
        if normalized in ("on", "1"):
            return 1
        if normalized in ("off", "0"):
            return 0
        try:
            value = int(payload)
        except (ValueError, TypeError):
            logger.warning("Invalid brightness payload: %r", payload)
            return None
        if value < 0 or value > 1:
            logger.warning("Brightness value out of range: %d", value)
            return None
        return value
