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


@dataclass
class TrafficLightState:
    """Represents the current state of the traffic light."""

    active_colors: set[Color] = field(default_factory=set)
    connected: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
