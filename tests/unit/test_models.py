"""Tests for models module."""

from datetime import datetime

import pytest

from cleware_bridge.models import (
    NAMED_PATTERNS,
    PATTERN_TOPIC_SUFFIX,
    Color,
    LEDState,
    TrafficLightState,
    parse_pattern,
)


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


class TestParsePattern:
    def test_all_off_named(self) -> None:
        assert parse_pattern("all_off") == frozenset()

    def test_all_on_named(self) -> None:
        assert parse_pattern("all_on") == frozenset(Color)

    def test_named_case_insensitive(self) -> None:
        assert parse_pattern("ALL_OFF") == frozenset()
        assert parse_pattern("All_On") == frozenset(Color)

    def test_named_with_whitespace(self) -> None:
        assert parse_pattern("  all_off  ") == frozenset()

    def test_single_color(self) -> None:
        assert parse_pattern("red") == frozenset({Color.RED})

    def test_two_colors(self) -> None:
        assert parse_pattern("red+green") == frozenset({Color.RED, Color.GREEN})

    def test_three_colors(self) -> None:
        assert parse_pattern("red+yellow+green") == frozenset(Color)

    def test_plus_with_spaces(self) -> None:
        assert parse_pattern("red + green") == frozenset({Color.RED, Color.GREEN})

    def test_case_insensitive_colors(self) -> None:
        assert parse_pattern("RED+GREEN") == frozenset({Color.RED, Color.GREEN})

    def test_duplicate_colors_collapse(self) -> None:
        assert parse_pattern("red+red") == frozenset({Color.RED})

    def test_unknown_color_returns_none(self) -> None:
        assert parse_pattern("red+blue") is None

    def test_unknown_named_returns_none(self) -> None:
        assert parse_pattern("foo") is None

    def test_empty_returns_none(self) -> None:
        assert parse_pattern("") is None
        assert parse_pattern("   ") is None

    def test_leading_plus_returns_none(self) -> None:
        assert parse_pattern("+red") is None

    def test_trailing_plus_returns_none(self) -> None:
        assert parse_pattern("red+") is None

    def test_double_plus_returns_none(self) -> None:
        assert parse_pattern("red++green") is None

    def test_bare_plus_returns_none(self) -> None:
        assert parse_pattern("+") is None

    def test_named_patterns_constant(self) -> None:
        assert NAMED_PATTERNS["all_off"] == frozenset()
        assert NAMED_PATTERNS["all_on"] == frozenset(Color)
        assert len(NAMED_PATTERNS) == 2

    def test_pattern_topic_suffix_constant(self) -> None:
        assert PATTERN_TOPIC_SUFFIX == "pattern"

    def test_returns_frozenset(self) -> None:
        result = parse_pattern("red")
        assert isinstance(result, frozenset)


class TestParsePatternColorMembership:
    def test_yellow_in_result(self) -> None:
        assert parse_pattern("yellow") == frozenset({Color.YELLOW})

    def test_yellow_and_green(self) -> None:
        assert parse_pattern("yellow+green") == frozenset({Color.YELLOW, Color.GREEN})
