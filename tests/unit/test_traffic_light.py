"""Tests for traffic_light module."""

import pytest

from cleware_bridge.models import Color, LEDState
from cleware_bridge.traffic_light import MockTrafficLight, TrafficLight


class TestTrafficLightABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            TrafficLight()  # type: ignore[abstract]


class TestMockTrafficLight:
    def test_initial_state(self) -> None:
        light = MockTrafficLight()
        assert light.active_colors == set()
        assert light.is_connected() is True

    def test_set_led_on(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        assert light.active_colors == {Color.RED}

    def test_set_led_on_multiple(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        light.set_led(Color.GREEN, LEDState.ON)
        assert light.active_colors == {Color.RED, Color.GREEN}

    def test_set_led_off(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        light.set_led(Color.RED, LEDState.OFF)
        assert light.active_colors == set()

    def test_set_led_off_nonexistent(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.OFF)
        assert light.active_colors == set()

    def test_set_color(self) -> None:
        light = MockTrafficLight()
        light.set_color(Color.RED)
        assert light.active_colors == {Color.RED}

    def test_set_color_changes(self) -> None:
        light = MockTrafficLight()
        light.set_color(Color.RED)
        light.set_color(Color.GREEN)
        assert light.active_colors == {Color.GREEN}

    def test_set_led_does_not_affect_others(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        light.set_led(Color.GREEN, LEDState.ON)
        assert light.active_colors == {Color.RED, Color.GREEN}
        light.set_led(Color.RED, LEDState.OFF)
        assert light.active_colors == {Color.GREEN}

    def test_all_off(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.RED, LEDState.ON)
        light.set_led(Color.GREEN, LEDState.ON)
        light.all_off()
        assert light.active_colors == set()

    def test_is_connected(self) -> None:
        light = MockTrafficLight()
        assert light.is_connected() is True

    def test_set_disconnected(self) -> None:
        light = MockTrafficLight()
        light.set_disconnected()
        assert light.is_connected() is False

    def test_set_led_when_disconnected(self) -> None:
        light = MockTrafficLight()
        light.set_disconnected()
        with pytest.raises(ConnectionError):
            light.set_led(Color.RED, LEDState.ON)

    def test_set_color_when_disconnected(self) -> None:
        light = MockTrafficLight()
        light.set_disconnected()
        with pytest.raises(ConnectionError):
            light.set_color(Color.RED)

    def test_all_off_when_disconnected(self) -> None:
        light = MockTrafficLight()
        light.set_disconnected()
        with pytest.raises(ConnectionError):
            light.all_off()

    def test_close(self) -> None:
        light = MockTrafficLight()
        light.set_led(Color.GREEN, LEDState.ON)
        light.close()
        assert light.is_connected() is False
        assert light.active_colors == set()

    def test_set_connected(self) -> None:
        light = MockTrafficLight()
        light.set_disconnected()
        light.set_connected()
        assert light.is_connected() is True
        light.set_led(Color.YELLOW, LEDState.ON)
        assert light.active_colors == {Color.YELLOW}

    def test_all_colors(self) -> None:
        light = MockTrafficLight()
        for color in Color:
            light.set_led(color, LEDState.ON)
        assert light.active_colors == set(Color)


class TestClewareTrafficLightMocked:
    def test_find_device_no_hardware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import cleware_bridge.cleware as cleware_mod

        monkeypatch.setattr(cleware_mod.usb.core, "find", lambda **kwargs: None)
        light = cleware_mod.ClewareTrafficLight()
        assert light.is_connected() is False

    def test_set_color_when_not_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import cleware_bridge.cleware as cleware_mod

        monkeypatch.setattr(cleware_mod.usb.core, "find", lambda **kwargs: None)
        light = cleware_mod.ClewareTrafficLight()
        with pytest.raises(ConnectionError):
            light.set_color(Color.RED)

    def test_set_led_when_not_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import cleware_bridge.cleware as cleware_mod

        monkeypatch.setattr(cleware_mod.usb.core, "find", lambda **kwargs: None)
        light = cleware_mod.ClewareTrafficLight()
        with pytest.raises(ConnectionError):
            light.set_led(Color.RED, LEDState.ON)
