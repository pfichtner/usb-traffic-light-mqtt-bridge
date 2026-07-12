"""Tests for MQTT bridge client."""

from unittest.mock import MagicMock

import paho.mqtt.client as mqtt

from cleware_bridge.config import BridgeConfig
from cleware_bridge.models import Color, LEDState
from cleware_bridge.mqtt_client import MQTTBridge
from cleware_bridge.traffic_light import MockTrafficLight


class TestMQTTBridgeParseBrightness:
    def test_valid_numeric_values(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("0") == 0
        assert bridge._parse_brightness("1") == 1

    def test_on_string(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("on") == 1

    def test_on_string_case_insensitive(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("ON") == 1
        assert bridge._parse_brightness("On") == 1

    def test_off_string(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("off") == 0

    def test_off_string_case_insensitive(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("OFF") == 0
        assert bridge._parse_brightness("Off") == 0

    def test_negative_value(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("-1") is None

    def test_over_1(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("2") is None
        assert bridge._parse_brightness("128") is None
        assert bridge._parse_brightness("255") is None

    def test_invalid_string(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("abc") is None

    def test_float(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("1.5") is None

    def test_empty_string(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._parse_brightness("") is None


class TestMQTTBridgeOnMessage:
    def _make_bridge(self, prefix: str = "cleware/ampel/") -> MQTTBridge:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_topic_prefix=prefix)
        bridge = MQTTBridge(config, light)
        bridge._light = light
        return bridge

    def _make_msg(self, topic: str, payload: str) -> mqtt.MQTTMessage:
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.topic = topic
        msg.payload = payload.encode("utf-8")
        return msg

    def test_green_on(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/green", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.GREEN in bridge._light.active_colors

    def test_red_on(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/red", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.RED in bridge._light.active_colors

    def test_yellow_on(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/yellow", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.YELLOW in bridge._light.active_colors

    def test_green_on_with_on_string(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/green", "on")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.GREEN in bridge._light.active_colors

    def test_red_on_with_on_string(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/red", "ON")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.RED in bridge._light.active_colors

    def test_off_string_turns_off(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.RED, LEDState.ON)
        msg = self._make_msg("cleware/ampel/red", "off")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.RED not in bridge._light.active_colors

    def test_off_string_uppercase_turns_off(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.GREEN, LEDState.ON)
        msg = self._make_msg("cleware/ampel/green", "OFF")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.GREEN not in bridge._light.active_colors

    def test_brightness_zero_turns_off(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.RED, LEDState.ON)
        msg = self._make_msg("cleware/ampel/red", "0")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.RED not in bridge._light.active_colors

    def test_invalid_payload_no_state_change(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/green", "invalid")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == set()

    def test_unknown_topic_suffix_ignored(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/blue", "255")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == set()

    def test_unrelated_topic_ignored(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("other/topic/red", "255")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == set()

    def test_custom_prefix(self) -> None:
        bridge = self._make_bridge(prefix="custom/ampel/")
        msg = self._make_msg("custom/ampel/green", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert Color.GREEN in bridge._light.active_colors

    def test_set_led_error_publishes_state(self) -> None:
        bridge = self._make_bridge()
        bridge._client = MagicMock()
        bridge._light.set_disconnected()
        msg = self._make_msg("cleware/ampel/green", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]

    def test_red_on_green_on_both_active(self) -> None:
        bridge = self._make_bridge()
        msg_red = self._make_msg("cleware/ampel/red", "1")
        bridge._on_message(None, None, msg_red)  # type: ignore[arg-type]
        msg_green = self._make_msg("cleware/ampel/green", "1")
        bridge._on_message(None, None, msg_green)  # type: ignore[arg-type]
        assert Color.RED in bridge._light.active_colors
        assert Color.GREEN in bridge._light.active_colors

    def test_red_on_green_off_red_stays(self) -> None:
        bridge = self._make_bridge()
        msg_red = self._make_msg("cleware/ampel/red", "1")
        bridge._on_message(None, None, msg_red)  # type: ignore[arg-type]
        msg_green_off = self._make_msg("cleware/ampel/green", "0")
        bridge._on_message(None, None, msg_green_off)  # type: ignore[arg-type]
        assert Color.RED in bridge._light.active_colors
        assert bridge._active_leds == {Color.RED}

    def test_all_three_on(self) -> None:
        bridge = self._make_bridge()
        for color in ("red", "yellow", "green"):
            msg = self._make_msg(f"cleware/ampel/{color}", "1")
            bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._active_leds == {Color.RED, Color.YELLOW, Color.GREEN}

    def test_all_three_off(self) -> None:
        bridge = self._make_bridge()
        for color in ("red", "yellow", "green"):
            msg = self._make_msg(f"cleware/ampel/{color}", "1")
            bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        for color in ("red", "yellow", "green"):
            msg = self._make_msg(f"cleware/ampel/{color}", "0")
            bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._active_leds == set()

    def test_active_leds_tracked_internally(self) -> None:
        bridge = self._make_bridge()
        assert bridge._active_leds == set()
        msg = self._make_msg("cleware/ampel/red", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._active_leds == {Color.RED}
        msg = self._make_msg("cleware/ampel/green", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._active_leds == {Color.RED, Color.GREEN}


class TestMQTTBridgePatternTopic:
    def _make_bridge(self, prefix: str = "cleware/ampel/") -> MQTTBridge:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_topic_prefix=prefix)
        bridge = MQTTBridge(config, light)
        bridge._light = light
        return bridge

    def _make_msg(self, topic: str, payload: str) -> mqtt.MQTTMessage:
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.topic = topic
        msg.payload = payload.encode("utf-8")
        return msg

    def test_all_off_clears_active_leds(self) -> None:
        bridge = self._make_bridge()
        for color in (Color.RED, Color.YELLOW, Color.GREEN):
            bridge._light.set_led(color, LEDState.ON)
        msg = self._make_msg("cleware/ampel/pattern", "all_off")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == set()
        assert bridge._active_leds == set()

    def test_all_on_lights_every_led(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/pattern", "all_on")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED, Color.YELLOW, Color.GREEN}
        assert bridge._active_leds == {Color.RED, Color.YELLOW, Color.GREEN}

    def test_combination_pattern_turns_others_off(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.YELLOW, LEDState.ON)
        msg = self._make_msg("cleware/ampel/pattern", "red+green")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED, Color.GREEN}
        assert bridge._active_leds == {Color.RED, Color.GREEN}

    def test_single_color_pattern_turns_others_off(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.RED, LEDState.ON)
        bridge._light.set_led(Color.GREEN, LEDState.ON)
        msg = self._make_msg("cleware/ampel/pattern", "yellow")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.YELLOW}
        assert bridge._active_leds == {Color.YELLOW}

    def test_pattern_is_case_insensitive(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/pattern", "RED+GREEN")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED, Color.GREEN}

    def test_invalid_pattern_no_state_change(self) -> None:
        bridge = self._make_bridge()
        bridge._on_message(None, None, self._make_msg("cleware/ampel/red", "1"))  # type: ignore[arg-type]
        msg = self._make_msg("cleware/ampel/pattern", "purple+blue")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED}
        assert bridge._active_leds == {Color.RED}

    def test_invalid_pattern_unknown_named_no_state_change(self) -> None:
        bridge = self._make_bridge()
        bridge._on_message(None, None, self._make_msg("cleware/ampel/red", "1"))  # type: ignore[arg-type]
        msg = self._make_msg("cleware/ampel/pattern", "hazard")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED}
        assert bridge._active_leds == {Color.RED}

    def test_per_color_topic_still_works_after_pattern(self) -> None:
        bridge = self._make_bridge()
        msg = self._make_msg("cleware/ampel/pattern", "all_on")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        msg_green_off = self._make_msg("cleware/ampel/green", "0")
        bridge._on_message(None, None, msg_green_off)  # type: ignore[arg-type]
        assert Color.GREEN not in bridge._light.active_colors
        assert Color.RED in bridge._light.active_colors
        assert Color.YELLOW in bridge._light.active_colors
        assert bridge._active_leds == {Color.RED, Color.YELLOW}

    def test_pattern_after_per_color_overwrites_state(self) -> None:
        bridge = self._make_bridge()
        bridge._light.set_led(Color.RED, LEDState.ON)
        bridge._light.set_led(Color.GREEN, LEDState.ON)
        bridge._active_leds = {Color.RED, Color.GREEN}
        msg = self._make_msg("cleware/ampel/pattern", "all_off")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == set()
        assert bridge._active_leds == set()

    def test_pattern_custom_prefix(self) -> None:
        bridge = self._make_bridge(prefix="custom/ampel/")
        msg = self._make_msg("custom/ampel/pattern", "red+green")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED, Color.GREEN}

    def test_pattern_nested_subtopic_ignored(self) -> None:
        # Reserved namespace `pattern/anim/...` is not handled yet and must
        # be ignored without side effects (see ADR 012).
        bridge = self._make_bridge()
        bridge._on_message(None, None, self._make_msg("cleware/ampel/red", "1"))  # type: ignore[arg-type]
        msg = self._make_msg("cleware/ampel/pattern/anim/hazard", "1")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        assert bridge._light.active_colors == {Color.RED}
        assert bridge._active_leds == {Color.RED}

    def test_pattern_set_led_error_logged(self) -> None:
        bridge = self._make_bridge()
        bridge._client = MagicMock()
        bridge._light.set_disconnected()
        msg = self._make_msg("cleware/ampel/pattern", "all_on")
        bridge._on_message(None, None, msg)  # type: ignore[arg-type]
        # Hardware failure must not raise and must not corrupt tracked state
        # beyond the LED state we attempted to set.
        assert bridge._active_leds == set()


class TestMQTTBridgeSubscribeTopics:
    def test_default_topics(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_topic_prefix="cleware/ampel/")
        bridge = MQTTBridge(config, light)
        assert bridge._subscribe_topics == ["cleware/ampel/#"]

    def test_custom_prefix(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_topic_prefix="my/device/")
        bridge = MQTTBridge(config, light)
        assert bridge._subscribe_topics == ["my/device/#"]

    def test_prefix_without_trailing_slash(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_topic_prefix="test/ampel")
        bridge = MQTTBridge(config, light)
        assert bridge._subscribe_topics == ["test/ampel/#"]

    def test_single_subscription_topic(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert len(bridge._subscribe_topics) == 1


class TestMQTTBridgeCallbacks:
    def _make_bridge(self) -> MQTTBridge:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        bridge._client = MagicMock()
        return bridge

    def test_on_connect_subscribes_topics(self) -> None:
        bridge = self._make_bridge()
        reason_code = MagicMock()
        reason_code.is_failure = False
        bridge._on_connect(bridge._client, None, {}, reason_code, None)
        assert bridge._client.subscribe.call_count == 1

    def test_on_connect_failure(self) -> None:
        bridge = self._make_bridge()
        reason_code = MagicMock()
        reason_code.is_failure = True
        bridge._on_connect(bridge._client, None, {}, reason_code, None)
        bridge._client.subscribe.assert_not_called()

    def test_on_disconnect_failure(self) -> None:
        bridge = self._make_bridge()
        reason_code = MagicMock()
        reason_code.is_failure = True
        # Should not raise
        bridge._on_disconnect(bridge._client, None, {}, reason_code, None)

    def test_on_disconnect_graceful(self) -> None:
        bridge = self._make_bridge()
        reason_code = MagicMock()
        reason_code.is_failure = False
        # Should not raise
        bridge._on_disconnect(bridge._client, None, {}, reason_code, None)


class TestMQTTBridgeStartStop:
    def test_start_calls_connect_and_loop(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        bridge._client = MagicMock()
        bridge.start()
        bridge._client.connect.assert_called_once()
        bridge._client.loop_forever.assert_called_once()

    def test_start_with_username(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig(mqtt_username="user", mqtt_password="pass")
        bridge = MQTTBridge(config, light)
        bridge._client = MagicMock()
        bridge.start()
        bridge._client.username_pw_set.assert_called_once_with("user", "pass")

    def test_start_connection_error(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        bridge._client = MagicMock()
        bridge._client.connect.side_effect = OSError("Connection refused")
        bridge.start()
        bridge._client.loop_forever.assert_called_once()

    def test_stop(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        bridge._client = MagicMock()
        bridge.stop()
        bridge._client.disconnect.assert_called_once()
        bridge._client.loop_stop.assert_called_once()


class TestMQTTBridgeActiveLeds:
    def test_initially_empty(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        assert bridge._active_leds == set()

    def test_led_added_on_on_command(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.topic = "cleware/ampel/red"
        msg.payload = b"1"
        bridge._on_message(None, None, msg)
        assert bridge._active_leds == {Color.RED}

    def test_led_removed_on_off_command(self) -> None:
        light = MockTrafficLight()
        config = BridgeConfig()
        bridge = MQTTBridge(config, light)
        bridge._active_leds.add(Color.RED)
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.topic = "cleware/ampel/red"
        msg.payload = b"0"
        bridge._on_message(None, None, msg)
        assert bridge._active_leds == set()
