"""Tests for models module."""

from datetime import datetime

import pytest

from cleware_bridge.models import Color, LEDState, TrafficLightState


class TestColor:
    def test_from_name_red(self) -> None:
        assert Color.from_name("red") == Color.RED

    def test_from_name_green(self) -> None:
        assert Color.from_name("green") == Color.GREEN

    def test_from_name_yellow(self) -> None:
        assert Color.from_name("yellow") == Color.YELLOW

    def test_from_name_case_insensitive(self) -> None:
        assert Color.from_name("RED") == Color.RED
        assert Color.from_name("Green") == Color.GREEN

    def test_from_name_with_whitespace(self) -> None:
        assert Color.from_name("  red  ") == Color.RED

    def test_from_name_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unknown color"):
            Color.from_name("purple")

    def test_from_name_empty(self) -> None:
        with pytest.raises(ValueError, match="Unknown color"):
            Color.from_name("")

    def test_to_name(self) -> None:
        assert Color.RED.to_name() == "red"
        assert Color.YELLOW.to_name() == "yellow"
        assert Color.GREEN.to_name() == "green"

    def test_enum_values(self) -> None:
        assert Color.RED == 0x10
        assert Color.YELLOW == 0x11
        assert Color.GREEN == 0x12

    def test_all_colors(self) -> None:
        assert list(Color) == [Color.RED, Color.YELLOW, Color.GREEN]


class TestLEDState:
    def test_off(self) -> None:
        assert LEDState.OFF == 0

    def test_on(self) -> None:
        assert LEDState.ON == 1


class TestTrafficLightState:
    def test_default_state(self) -> None:
        state = TrafficLightState()
        assert state.active_colors == set()
        assert state.connected is False
        assert isinstance(state.timestamp, datetime)

    def test_with_active_colors(self) -> None:
        state = TrafficLightState(active_colors={Color.RED, Color.GREEN}, connected=True)
        assert Color.RED in state.active_colors
        assert Color.GREEN in state.active_colors
        assert Color.YELLOW not in state.active_colors
        assert state.connected is True

    def test_active_colors_is_same_reference(self) -> None:
        original: set[Color] = {Color.RED}
        state = TrafficLightState(active_colors=original)
        assert state.active_colors is original
