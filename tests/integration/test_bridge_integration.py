"""Integration tests for the Cleware MQTT Bridge."""

from __future__ import annotations

import threading
import time

import paho.mqtt.client as mqtt
import pytest

from cleware_bridge.config import BridgeConfig
from cleware_bridge.models import Color, LEDState
from cleware_bridge.mqtt_client import MQTTBridge
from cleware_bridge.traffic_light import MockTrafficLight

pytestmark = pytest.mark.integration


class TestBridgeIntegration:
    """Integration tests with a real Mosquitto broker."""

    def _start_bridge(self, config: BridgeConfig, light: MockTrafficLight) -> MQTTBridge:
        """Start the bridge in a background thread."""
        bridge = MQTTBridge(config, light)
        thread = threading.Thread(target=bridge.start, daemon=True)
        thread.start()
        time.sleep(1.0)  # Wait for connection
        return bridge

    def _publish_command(
        self,
        host: str,
        port: int,
        topic: str,
        payload: str,
    ) -> None:
        """Publish a command to the MQTT broker."""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
        client.connect(host, port)
        client.loop_start()
        time.sleep(0.2)
        client.publish(topic, payload)
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()

    def test_green_on(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/green", "1")
            assert Color.GREEN in light.active_colors
        finally:
            bridge.stop()

    def test_red_on(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/red", "1")
            assert Color.RED in light.active_colors
        finally:
            bridge.stop()

    def test_yellow_on(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/yellow", "1")
            assert Color.YELLOW in light.active_colors
        finally:
            bridge.stop()

    def test_multiple_leds_independent(
        self, mosquitto: object, bridge_config: BridgeConfig
    ) -> None:
        """Turn on red, then green. Both should stay on."""
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/red", "1")
            assert Color.RED in light.active_colors

            self._publish_command(broker.host, broker.port, "test/ampel/green", "1")
            assert Color.RED in light.active_colors
            assert Color.GREEN in light.active_colors
        finally:
            bridge.stop()

    def test_turn_off_one_led(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        """Turn on red and green, then turn off red. Green should stay on."""
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/red", "1")
            self._publish_command(broker.host, broker.port, "test/ampel/green", "1")
            assert light.active_colors == {Color.RED, Color.GREEN}

            self._publish_command(broker.host, broker.port, "test/ampel/red", "0")
            assert Color.RED not in light.active_colors
            assert Color.GREEN in light.active_colors
        finally:
            bridge.stop()

    def test_brightness_zero_off(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        light.set_led(Color.GREEN, LEDState.ON)
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/green", "0")
            assert Color.GREEN not in light.active_colors
        finally:
            bridge.stop()

    def test_invalid_payload_no_state_change(
        self, mosquitto: object, bridge_config: BridgeConfig
    ) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/green", "invalid_data")
            assert light.active_colors == set()
        finally:
            bridge.stop()

    def test_on_string_turns_on(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/green", "on")
            assert Color.GREEN in light.active_colors
        finally:
            bridge.stop()

    def test_off_string_turns_off(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/red", "off")
            assert Color.RED not in light.active_colors
        finally:
            bridge.stop()

    def test_rejects_value_over_1(self, mosquitto: object, bridge_config: BridgeConfig) -> None:
        from tests.integration.conftest import MosquittoBroker

        broker: MosquittoBroker = mosquitto  # type: ignore[assignment]
        light = MockTrafficLight()
        bridge = self._start_bridge(bridge_config, light)

        try:
            self._publish_command(broker.host, broker.port, "test/ampel/green", "255")
            assert light.active_colors == set()
        finally:
            bridge.stop()
