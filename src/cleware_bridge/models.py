"""Data models for the Cleware MQTT Bridge."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum

logger = logging.getLogger(__name__)


class Color(IntEnum):
    """Traffic light colors matching Cleware USB hardware protocol."""

    RED = 0x10
    YELLOW = 0x11
    GREEN = 0x12

    @classmethod
    def from_name(cls, name: str) -> Color:
        """Parse a color name string to Color enum.

        Raises:
            ValueError: If the name does not match any color.
        """
        mapping = {
            "red": cls.RED,
            "yellow": cls.YELLOW,
            "green": cls.GREEN,
        }
        key = name.strip().lower()
        if key not in mapping:
            msg = f"Unknown color: {name!r}. Valid colors: {list(mapping.keys())}"
            raise ValueError(msg)
        return mapping[key]

    def to_name(self) -> str:
        """Return the lowercase name of the color."""
        return self.name.lower()


class LEDState(IntEnum):
    """LED on/off state."""

    OFF = 0
    ON = 1


# Mapping from topic suffix to Color
TOPIC_COLOR_MAP: dict[str, Color] = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "green": Color.GREEN,
}

# Reserved topic suffix for pattern commands.
PATTERN_TOPIC_SUFFIX: str = "pattern"

# Named whole-device patterns. Each entry maps a pattern name to the set of
# LEDs that should be ON after applying the pattern; every other LED is turned
# OFF. Names are matched case-insensitively and after trimming whitespace.
NAMED_PATTERNS: dict[str, frozenset[Color]] = {
    "all_off": frozenset(),
    "all_on": frozenset(Color),
}


def parse_pattern(payload: str) -> frozenset[Color] | None:
    """Parse a pattern payload to a set of colors.

    Accepted forms (case-insensitive, surrounding whitespace stripped):

    - A named pattern from :data:`NAMED_PATTERNS` (e.g. ``all_off``, ``all_on``)
    - A ``+``-joined combination of color names, e.g. ``red+green`` or
      ``red + yellow + green``. Colors are resolved via :meth:`Color.from_name`.

    Returns:
        A :class:`frozenset` of :class:`Color` members, or ``None`` if the
        payload is empty or contains an unknown name or color.
    """
    normalized = payload.strip().lower()
    if not normalized:
        return None

    if normalized in NAMED_PATTERNS:
        return NAMED_PATTERNS[normalized]

    parts = [part.strip() for part in normalized.split("+")]
    # Reject empty parts (e.g. "red+", "+red", "red++green") and the trivial
    # "+"/empty combination.
    if not all(parts) or any(part == "" for part in parts):
        return None

    colors: set[Color] = set()
    for part in parts:
        try:
            colors.add(Color.from_name(part))
        except ValueError:
            return None
    return frozenset(colors)


@dataclass
class TrafficLightState:
    """Represents the current state of the traffic light."""

    active_colors: set[Color] = field(default_factory=set)
    connected: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Animated patterns (ADR 013)
# ---------------------------------------------------------------------------

# Reserved topic prefix for animated pattern commands. The full topic suffix
# received by the bridge is `{prefix}/pattern/anim/<name>` (see ADR 012), so the
# sub-suffix after the device prefix is `pattern/anim/<name>`.
ANIM_TOPIC_PREFIX: str = "pattern/anim/"

# Fixed, built-in animation names. The catalog is intentionally small and
# closed; new built-ins can be added here without a schema change (ADR 013).
ANIMATIONS: frozenset[str] = frozenset({"blink", "chase", "bounce"})

# Default animation parameters.
DEFAULT_SPEED_MS: int = 500
MIN_SPEED_MS: int = 100
DEFAULT_REPEATS: int = 0  # 0 means infinite — run until cancelled.
DEFAULT_COLORS: tuple[Color, ...] = (Color.RED, Color.YELLOW, Color.GREEN)

# ---------------------------------------------------------------------------
# Traffic light animations (ADR 014)
# ---------------------------------------------------------------------------

# Topic prefix for country-specific traffic light animations.
# Full topic: `{prefix}/pattern/tl/<country>/<animation>`
TL_TOPIC_PREFIX: str = "pattern/tl/"

# Supported country codes.  New countries can be added by extending this set
# and providing timing data in TL_TIMINGS (see ADR 014).
COUNTRIES: frozenset[str] = frozenset({"german", "usa", "uk"})

# Animation names for German traffic lights (StVO-regulated timings).
GERMAN_TL_ANIMATIONS: frozenset[str] = frozenset({"blink-yellow", "red-to-green", "green-to-red"})

# Animation names for USA traffic lights (no red+yellow before green).
USA_TL_ANIMATIONS: frozenset[str] = frozenset({"blink-yellow", "red-to-green", "green-to-red"})

# Animation names for UK traffic lights (red+amber before green, amber flash).
UK_TL_ANIMATIONS: frozenset[str] = frozenset({"blink-yellow", "red-to-green", "green-to-red"})

# Default speed multiplier for traffic light animations.  1.0 uses the
# regulation timings as-is; 2.0 doubles the speed (halves all durations).
DEFAULT_SPEED_FACTOR: float = 1.0
MIN_SPEED_FACTOR: float = 0.1
MAX_SPEED_FACTOR: float = 10.0


@dataclass(frozen=True)
class AnimParams:
    """Validated parameters for an animation command (ADR 013, ADR 014).

    Every field has a default, so an empty payload selects sensible defaults.
    ``speed_ms`` is always ``>= MIN_SPEED_MS`` after parsing. ``colors`` is an
    ordered tuple with duplicates removed; order matters for ``chase`` and
    ``bounce``.

    ``hold_final`` controls whether the last LED state persists after a
    finite animation completes naturally (ADR 014).  ``speed_factor``
    scales traffic light animation timings (ADR 014).
    """

    speed_ms: int = DEFAULT_SPEED_MS
    repeats: int = DEFAULT_REPEATS
    colors: tuple[Color, ...] = DEFAULT_COLORS
    hold_final: bool = False
    speed_factor: float = DEFAULT_SPEED_FACTOR
    country: str | None = None

    @property
    def infinite(self) -> bool:
        """True when the animation runs until cancelled."""
        return self.repeats == 0


def parse_anim_params(animation: str, payload: str) -> AnimParams | None:
    """Parse a JSON payload into :class:`AnimParams`.

    Accepts an optional JSON object with the fields ``speed_ms`` (int ``>= 100``),
    ``repeats`` (int ``>= 0``, where ``0`` means infinite), ``colors``
    (ordered list of color names), ``hold_final`` (bool), and ``speed_factor``
    (float, ``0.1`` to ``10.0``).  Every field is optional; an empty/blank
    payload returns the defaults.  Unknown object fields are ignored for
    forward compatibility.

    ``animation`` is accepted as the dispatched animation name so future
    per-animation defaults can be applied; it is currently unused.

    Returns:
        ``AnimParams`` on success, or ``None`` on invalid JSON, a non-object
        JSON value, or any out-of-range or wrongly-typed field. The caller is
        responsible for logging the rejection (ADR 012/013 non-fatal policy).
    """
    _ = animation  # reserved for per-animation defaults
    text = payload.strip()
    if not text:
        return AnimParams()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    speed_ms = DEFAULT_SPEED_MS
    if "speed_ms" in data:
        value = data["speed_ms"]
        # bool is a subtype of int; reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < MIN_SPEED_MS:
            logger.warning("speed_ms %d below minimum %d, clamping", value, MIN_SPEED_MS)
            value = MIN_SPEED_MS
        speed_ms = value

    repeats = DEFAULT_REPEATS
    if "repeats" in data:
        value = data["repeats"]
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < 0:
            return None
        repeats = value

    colors = DEFAULT_COLORS
    if "colors" in data:
        raw_colors = data["colors"]
        if not isinstance(raw_colors, list) or len(raw_colors) == 0:
            return None
        ordered: list[Color] = []
        seen: set[Color] = set()
        for item in raw_colors:
            if not isinstance(item, str):
                return None
            try:
                color = Color.from_name(item)
            except ValueError:
                return None
            if color not in seen:
                seen.add(color)
                ordered.append(color)
        colors = tuple(ordered)

    hold_final = False
    if "hold_final" in data:
        value = data["hold_final"]
        if not isinstance(value, bool):
            return None
        hold_final = value

    speed_factor = DEFAULT_SPEED_FACTOR
    if "speed_factor" in data:
        value = data["speed_factor"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if value < MIN_SPEED_FACTOR or value > MAX_SPEED_FACTOR:
            return None
        speed_factor = float(value)

    return AnimParams(
        speed_ms=speed_ms,
        repeats=repeats,
        colors=colors,
        hold_final=hold_final,
        speed_factor=speed_factor,
    )


def animation_frames(name: str, params: AnimParams) -> Iterator[list[tuple[frozenset[Color], int]]]:
    """Yield animation *cycles* for the named animation.

    Each cycle is an ordered list of frames, and each frame is a tuple of
    ``(leds, duration_ms)`` where *leds* is a :class:`frozenset` of the LEDs
    that should be ON during that step and *duration_ms* is the number of
    milliseconds to display the frame.  For standard animations (blink, chase,
    bounce) all frames share ``params.speed_ms``; traffic light animations use
    regulation-based per-phase durations scaled by ``params.speed_factor``.

    The generator yields full cycles indefinitely; the caller is responsible
    for counting cycles and stopping after ``params.repeats`` and/or
    responding to cancellation.

    Raises:
        ValueError: If ``name`` is not a known animation. Callers that have
            already validated the name will never see this.
    """
    if name in GERMAN_TL_ANIMATIONS or name in USA_TL_ANIMATIONS or name in UK_TL_ANIMATIONS:
        cycle = _traffic_light_cycle(name, params.country, params)
    elif name == "blink":
        on_frame = frozenset(params.colors)
        off_frame: frozenset[Color] = frozenset()
        cycle = [(on_frame, params.speed_ms), (off_frame, params.speed_ms)]
    elif name == "chase":
        cycle = [(frozenset((color,)), params.speed_ms) for color in params.colors]
    elif name == "bounce":
        forward = list(params.colors)
        # Reverse run excluding the first and last element so the turnaround
        # does not repeat an endpoint: [r, y, g] -> back [y] -> cycle
        # [r, y, g, y]. Degenerates to the forward run for <= 2 colors.
        back = forward[-2:0:-1]
        cycle = [(frozenset((color,)), params.speed_ms) for color in forward + back]
    else:
        raise ValueError(f"Unknown animation: {name!r}")

    while True:
        yield cycle


# ---------------------------------------------------------------------------
# Traffic light timing data (ADR 014)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrafficLightPhase:
    """A single phase in a traffic light animation sequence."""

    leds: frozenset[Color]
    duration_ms: int


@dataclass(frozen=True)
class TrafficLightTimings:
    """Complete timing specification for a country-specific traffic light animation."""

    name: str
    phases: tuple[TrafficLightPhase, ...]
    default_hold_final: bool
    default_repeats: int


# German traffic light timings (StVO — Straßenverkehrs-Ordnung).
# Durations are based on typical German traffic light installations.
_GERMAN_TIMINGS: dict[str, TrafficLightTimings] = {
    "blink-yellow": TrafficLightTimings(
        name="blink-yellow",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=500),
            TrafficLightPhase(leds=frozenset(), duration_ms=500),
        ),
        default_hold_final=False,
        default_repeats=0,
    ),
    "red-to-green": TrafficLightTimings(
        name="red-to-green",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.RED, Color.YELLOW}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=3000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
    "green-to-red": TrafficLightTimings(
        name="green-to-red",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=3000),
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=5000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
}

# USA traffic light timings (MUTCD — Manual on Uniform Traffic Control Devices).
# Key difference: no red+yellow phase before green.
_USA_TIMINGS: dict[str, TrafficLightTimings] = {
    "blink-yellow": TrafficLightTimings(
        name="blink-yellow",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=500),
            TrafficLightPhase(leds=frozenset(), duration_ms=500),
        ),
        default_hold_final=False,
        default_repeats=0,
    ),
    "red-to-green": TrafficLightTimings(
        name="red-to-green",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=3000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
    "green-to-red": TrafficLightTimings(
        name="green-to-red",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=4000),
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=1000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
}

# UK traffic light timings (Traffic Signs Regulations and General Directions).
# Key difference: red+amber before green, amber-only flash phase at some intersections.
_UK_TIMINGS: dict[str, TrafficLightTimings] = {
    "blink-yellow": TrafficLightTimings(
        name="blink-yellow",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=500),
            TrafficLightPhase(leds=frozenset(), duration_ms=500),
        ),
        default_hold_final=False,
        default_repeats=0,
    ),
    "red-to-green": TrafficLightTimings(
        name="red-to-green",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.RED, Color.YELLOW}), duration_ms=500),
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=3000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
    "green-to-red": TrafficLightTimings(
        name="green-to-red",
        phases=(
            TrafficLightPhase(leds=frozenset({Color.GREEN}), duration_ms=1000),
            TrafficLightPhase(leds=frozenset({Color.YELLOW}), duration_ms=3000),
            TrafficLightPhase(leds=frozenset({Color.RED}), duration_ms=5000),
        ),
        default_hold_final=True,
        default_repeats=1,
    ),
}

# Country code -> animation name -> timings.
TL_TIMINGS: dict[str, dict[str, TrafficLightTimings]] = {
    "german": _GERMAN_TIMINGS,
    "usa": _USA_TIMINGS,
    "uk": _UK_TIMINGS,
}


def _scale_timings(
    timings: TrafficLightTimings, speed_factor: float
) -> list[tuple[frozenset[Color], int]]:
    """Scale a traffic light timing sequence by *speed_factor*.

    Each phase duration is divided by *speed_factor* and clamped to
    :data:`MIN_SPEED_MS` so the hardware is never thrashed.
    """
    scaled: list[tuple[frozenset[Color], int]] = []
    for phase in timings.phases:
        duration = max(MIN_SPEED_MS, int(phase.duration_ms / speed_factor))
        scaled.append((phase.leds, duration))
    return scaled


def _traffic_light_cycle(
    name: str, country: str | None, params: AnimParams
) -> list[tuple[frozenset[Color], int]]:
    """Build a single-cycle frame list for a traffic light animation."""
    # Country and animation validation are done by the caller (MQTT dispatch).
    # Look up timings directly from the specified country.
    if country is None:
        raise ValueError(f"Traffic light animation {name!r} requires a country")
    if country not in TL_TIMINGS:
        raise ValueError(f"Unknown country: {country!r}")
    if name not in TL_TIMINGS[country]:
        raise ValueError(f"Unknown traffic light animation: {name!r} for country {country!r}")
    return _scale_timings(TL_TIMINGS[country][name], params.speed_factor)
