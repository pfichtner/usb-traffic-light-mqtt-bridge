"""Tests for models module."""

import logging
from datetime import datetime

import pytest

from cleware_bridge.models import (
    ANIM_TOPIC_PREFIX,
    ANIMATIONS,
    COUNTRIES,
    DEFAULT_COLORS,
    DEFAULT_REPEATS,
    DEFAULT_SPEED_FACTOR,
    DEFAULT_SPEED_MS,
    GERMAN_TL_ANIMATIONS,
    MAX_SPEED_FACTOR,
    MIN_SPEED_FACTOR,
    MIN_SPEED_MS,
    NAMED_PATTERNS,
    PATTERN_TOPIC_SUFFIX,
    TL_TIMINGS,
    TL_TOPIC_PREFIX,
    AnimParams,
    Color,
    LEDState,
    TrafficLightPhase,
    TrafficLightState,
    animation_frames,
    parse_anim_params,
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


class TestAnimConstants:
    def test_animations_catalog(self) -> None:
        assert frozenset({"blink", "chase", "bounce"}) == ANIMATIONS

    def test_anim_topic_prefix(self) -> None:
        assert ANIM_TOPIC_PREFIX == "pattern/anim/"

    def test_default_speed_ms(self) -> None:
        assert DEFAULT_SPEED_MS == 500

    def test_min_speed_ms(self) -> None:
        assert MIN_SPEED_MS == 100

    def test_default_repeats_infinite(self) -> None:
        assert DEFAULT_REPEATS == 0

    def test_default_colors_order(self) -> None:
        assert DEFAULT_COLORS == (Color.RED, Color.YELLOW, Color.GREEN)


class TestAnimParamsDefaults:
    def test_defaults(self) -> None:
        params = AnimParams()
        assert params.speed_ms == DEFAULT_SPEED_MS
        assert params.repeats == DEFAULT_REPEATS
        assert params.colors == DEFAULT_COLORS
        assert params.infinite is True


class TestParseAnimParams:
    def test_empty_payload_returns_defaults(self) -> None:
        params = parse_anim_params("blink", "")
        assert params == AnimParams()

    def test_blank_payload_returns_defaults(self) -> None:
        assert parse_anim_params("blink", "   \n") == AnimParams()

    def test_custom_speed_ms(self) -> None:
        params = parse_anim_params("blink", '{"speed_ms":250}')
        assert params.speed_ms == 250
        assert params.repeats == DEFAULT_REPEATS
        assert params.colors == DEFAULT_COLORS

    def test_speed_ms_below_minimum_clamps(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            params = parse_anim_params("blink", '{"speed_ms":10}')
        assert params is not None
        assert params.speed_ms == MIN_SPEED_MS
        assert any("below minimum" in r.message for r in caplog.records)

    def test_speed_ms_at_minimum(self) -> None:
        params = parse_anim_params("blink", '{"speed_ms":100}')
        assert params is not None
        assert params.speed_ms == 100

    def test_speed_ms_bool_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_ms":true}') is None

    def test_speed_ms_float_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_ms":1.5}') is None

    def test_speed_ms_string_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_ms":"250"}') is None

    def test_repeats_custom(self) -> None:
        params = parse_anim_params("blink", '{"repeats":10}')
        assert params is not None
        assert params.repeats == 10
        assert params.infinite is False

    def test_repeats_zero_is_infinite(self) -> None:
        params = parse_anim_params("blink", '{"repeats":0}')
        assert params is not None
        assert params.repeats == 0
        assert params.infinite is True

    def test_repeats_negative_rejected(self) -> None:
        assert parse_anim_params("blink", '{"repeats":-1}') is None

    def test_repeats_bool_rejected(self) -> None:
        assert parse_anim_params("blink", '{"repeats":true}') is None

    def test_repeats_float_rejected(self) -> None:
        assert parse_anim_params("blink", '{"repeats":1.5}') is None

    def test_colors_custom_preserves_order(self) -> None:
        params = parse_anim_params("chase", '{"colors":["green","red"]}')
        assert params is not None
        assert params.colors == (Color.GREEN, Color.RED)

    def test_colors_duplicates_collapsed(self) -> None:
        params = parse_anim_params("blink", '{"colors":["red","red","green"]}')
        assert params is not None
        assert params.colors == (Color.RED, Color.GREEN)

    def test_colors_empty_list_rejected(self) -> None:
        assert parse_anim_params("blink", '{"colors":[]}') is None

    def test_colors_unknown_name_rejected(self) -> None:
        assert parse_anim_params("blink", '{"colors":["blue"]}') is None

    def test_colors_non_string_element_rejected(self) -> None:
        assert parse_anim_params("blink", '{"colors":["red",1]}') is None

    def test_colors_not_a_list_rejected(self) -> None:
        assert parse_anim_params("blink", '{"colors":"red"}') is None

    def test_combined_fields(self) -> None:
        params = parse_anim_params(
            "chase", '{"speed_ms":250,"repeats":10,"colors":["red","green"]}'
        )
        assert params == AnimParams(250, 10, (Color.RED, Color.GREEN))

    def test_non_object_json_rejected(self) -> None:
        assert parse_anim_params("blink", "[1,2,3]") is None

    def test_invalid_json_rejected(self) -> None:
        assert parse_anim_params("blink", "{bad") is None

    def test_unknown_field_ignored(self) -> None:
        params = parse_anim_params("blink", '{"speed_ms":250,"future":"x"}')
        assert params is not None
        assert params.speed_ms == 250

    def test_returns_animparams(self) -> None:
        params = parse_anim_params("blink", "{}")
        assert isinstance(params, AnimParams)


class TestAnimationFrames:
    def _params(self, colors: tuple[Color, ...] = DEFAULT_COLORS) -> AnimParams:
        return AnimParams(colors=colors)

    def test_blink_default_cycle(self) -> None:
        cycle = next(animation_frames("blink", self._params()))
        assert cycle == [
            (frozenset(DEFAULT_COLORS), DEFAULT_SPEED_MS),
            (frozenset(), DEFAULT_SPEED_MS),
        ]

    def test_blink_custom_colors(self) -> None:
        cycle = next(animation_frames("blink", self._params((Color.RED, Color.GREEN))))
        assert cycle == [
            (frozenset({Color.RED, Color.GREEN}), DEFAULT_SPEED_MS),
            (frozenset(), DEFAULT_SPEED_MS),
        ]

    def test_chase_default_cycle(self) -> None:
        cycle = next(animation_frames("chase", self._params()))
        assert cycle == [
            (frozenset({Color.RED}), DEFAULT_SPEED_MS),
            (frozenset({Color.YELLOW}), DEFAULT_SPEED_MS),
            (frozenset({Color.GREEN}), DEFAULT_SPEED_MS),
        ]

    def test_chase_custom_colors(self) -> None:
        cycle = next(animation_frames("chase", self._params((Color.RED, Color.GREEN))))
        assert cycle == [
            (frozenset({Color.RED}), DEFAULT_SPEED_MS),
            (frozenset({Color.GREEN}), DEFAULT_SPEED_MS),
        ]

    def test_bounce_default_cycle(self) -> None:
        cycle = next(animation_frames("bounce", self._params()))
        assert cycle == [
            (frozenset({Color.RED}), DEFAULT_SPEED_MS),
            (frozenset({Color.YELLOW}), DEFAULT_SPEED_MS),
            (frozenset({Color.GREEN}), DEFAULT_SPEED_MS),
            (frozenset({Color.YELLOW}), DEFAULT_SPEED_MS),
        ]

    def test_bounce_two_colors_degenerates(self) -> None:
        cycle = next(animation_frames("bounce", self._params((Color.RED, Color.GREEN))))
        assert cycle == [
            (frozenset({Color.RED}), DEFAULT_SPEED_MS),
            (frozenset({Color.GREEN}), DEFAULT_SPEED_MS),
        ]

    def test_bounce_single_color(self) -> None:
        cycle = next(animation_frames("bounce", self._params((Color.RED,))))
        assert cycle == [(frozenset({Color.RED}), DEFAULT_SPEED_MS)]

    def test_generator_yields_multiple_cycles(self) -> None:
        gen = animation_frames("chase", self._params((Color.RED,)))
        first = next(gen)
        second = next(gen)
        assert first == [(frozenset({Color.RED}), DEFAULT_SPEED_MS)]
        assert second == [(frozenset({Color.RED}), DEFAULT_SPEED_MS)]

    def test_custom_speed_ms_used_as_duration(self) -> None:
        params = AnimParams(colors=DEFAULT_COLORS, speed_ms=250)
        cycle = next(animation_frames("chase", params))
        assert cycle == [
            (frozenset({Color.RED}), 250),
            (frozenset({Color.YELLOW}), 250),
            (frozenset({Color.GREEN}), 250),
        ]

    def test_unknown_animation_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown animation"):
            next(animation_frames("hazard", self._params()))


class TestTrafficLightConstants:
    def test_tl_topic_prefix(self) -> None:
        assert TL_TOPIC_PREFIX == "pattern/tl/"

    def test_countries_contains_german(self) -> None:
        assert "german" in COUNTRIES

    def test_german_tl_animations_catalog(self) -> None:
        assert frozenset({"blink-yellow", "red-to-green", "green-to-red"}) == GERMAN_TL_ANIMATIONS

    def test_default_speed_factor(self) -> None:
        assert DEFAULT_SPEED_FACTOR == 1.0

    def test_speed_factor_ranges(self) -> None:
        assert MIN_SPEED_FACTOR == 0.1
        assert MAX_SPEED_FACTOR == 10.0

    def test_tl_timings_has_german(self) -> None:
        assert "german" in TL_TIMINGS
        assert set(TL_TIMINGS["german"].keys()) == GERMAN_TL_ANIMATIONS


class TestGermanTrafficLightTimings:
    def test_blink_yellow_phases(self) -> None:
        timings = TL_TIMINGS["german"]["blink-yellow"]
        assert timings.name == "blink-yellow"
        assert timings.default_hold_final is False
        assert timings.default_repeats == 0
        assert timings.phases == (
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=500),
            TrafficLightPhase(leds=frozenset(), duration_ms=500),
        )

    def test_red_to_green_phases(self) -> None:
        timings = TL_TIMINGS["german"]["red-to-green"]
        assert timings.name == "red-to-green"
        assert timings.default_hold_final is True
        assert timings.default_repeats == 1
        assert timings.phases == (
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.RED, Color.YELLOW}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=3000),
        )

    def test_green_to_red_phases(self) -> None:
        timings = TL_TIMINGS["german"]["green-to-red"]
        assert timings.name == "green-to-red"
        assert timings.default_hold_final is True
        assert timings.default_repeats == 1
        assert timings.phases == (
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=3000),
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=5000),
        )


class TestAnimationFramesTrafficLight:
    def _params(self, speed_factor: float = 1.0) -> AnimParams:
        return AnimParams(speed_factor=speed_factor, country="german")

    def test_blink_yellow_cycle(self) -> None:
        cycle = next(animation_frames("blink-yellow", self._params()))
        assert cycle == [
            (frozenset({Color.YELLOW}), 500),
            (frozenset(), 500),
        ]

    def test_red_to_green_cycle(self) -> None:
        cycle = next(animation_frames("red-to-green", self._params()))
        assert cycle == [
            (frozenset({Color.RED}), 1000),
            (frozenset({Color.RED, Color.YELLOW}), 1000),
            (frozenset({Color.GREEN}), 3000),
        ]

    def test_green_to_red_cycle(self) -> None:
        cycle = next(animation_frames("green-to-red", self._params()))
        assert cycle == [
            (frozenset({Color.GREEN}), 1000),
            (frozenset({Color.YELLOW}), 3000),
            (frozenset({Color.RED}), 5000),
        ]

    def test_speed_factor_2_halves_durations(self) -> None:
        cycle = next(animation_frames("red-to-green", self._params(2.0)))
        assert cycle == [
            (frozenset({Color.RED}), 500),
            (frozenset({Color.RED, Color.YELLOW}), 500),
            (frozenset({Color.GREEN}), 1500),
        ]

    def test_speed_factor_05_doubles_durations(self) -> None:
        cycle = next(animation_frames("blink-yellow", self._params(0.5)))
        assert cycle == [
            (frozenset({Color.YELLOW}), 1000),
            (frozenset(), 1000),
        ]

    def test_speed_factor_large_clamps_to_min(self) -> None:
        cycle = next(animation_frames("blink-yellow", self._params(100.0)))
        assert cycle == [
            (frozenset({Color.YELLOW}), MIN_SPEED_MS),
            (frozenset(), MIN_SPEED_MS),
        ]

    def test_generator_yields_multiple_cycles(self) -> None:
        gen = animation_frames("blink-yellow", self._params())
        first = next(gen)
        second = next(gen)
        assert first == second

    def test_unknown_tl_animation_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown animation"):
            next(animation_frames("made-up-tl", self._params()))


class TestParseAnimParamsHoldFinal:
    def test_hold_final_default_false(self) -> None:
        params = parse_anim_params("blink", "")
        assert params.hold_final is False

    def test_hold_final_true(self) -> None:
        params = parse_anim_params("blink", '{"hold_final":true}')
        assert params.hold_final is True

    def test_hold_final_false_explicit(self) -> None:
        params = parse_anim_params("blink", '{"hold_final":false}')
        assert params.hold_final is False

    def test_hold_final_non_bool_rejected(self) -> None:
        assert parse_anim_params("blink", '{"hold_final":1}') is None
        assert parse_anim_params("blink", '{"hold_final":"true"}') is None
        assert parse_anim_params("blink", '{"hold_final":null}') is None

    def test_hold_final_unknown_field_ignored(self) -> None:
        params = parse_anim_params("blink", '{"hold_final":true,"unrelated":1}')
        assert params is not None
        assert params.hold_final is True


class TestParseAnimParamsSpeedFactor:
    def test_speed_factor_default(self) -> None:
        params = parse_anim_params("blink", "")
        assert params.speed_factor == DEFAULT_SPEED_FACTOR

    def test_speed_factor_float(self) -> None:
        params = parse_anim_params("blink", '{"speed_factor":2.0}')
        assert params.speed_factor == 2.0

    def test_speed_factor_int_accepted(self) -> None:
        params = parse_anim_params("blink", '{"speed_factor":2}')
        assert params is not None
        assert params.speed_factor == 2.0

    def test_speed_factor_zero_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":0}') is None

    def test_speed_factor_negative_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":-1}') is None

    def test_speed_factor_too_large_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":100}') is None

    def test_speed_factor_below_min_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":0.05}') is None

    def test_speed_factor_bool_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":true}') is None

    def test_speed_factor_string_rejected(self) -> None:
        assert parse_anim_params("blink", '{"speed_factor":"2"}') is None

    def test_speed_factor_boundary_min(self) -> None:
        params = parse_anim_params("blink", '{"speed_factor":0.1}')
        assert params is not None
        assert params.speed_factor == 0.1

    def test_speed_factor_boundary_max(self) -> None:
        params = parse_anim_params("blink", '{"speed_factor":10}')
        assert params is not None
        assert params.speed_factor == 10.0
