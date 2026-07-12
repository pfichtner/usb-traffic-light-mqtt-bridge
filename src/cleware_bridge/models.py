"""Data models for the Cleware MQTT Bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum


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
