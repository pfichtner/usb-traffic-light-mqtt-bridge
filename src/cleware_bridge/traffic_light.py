"""Hardware abstraction layer for traffic light control."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .models import Color, LEDState

logger = logging.getLogger(__name__)


class TrafficLight(ABC):
    """Abstract base class for traffic light hardware."""

    @abstractmethod
    def set_led(self, color: Color, state: LEDState) -> None:
        """Set a single LED on or off without affecting other LEDs."""

    @abstractmethod
    def set_color(self, color: Color) -> None:
        """Set the traffic light to the specified color.

        Turns off all other LEDs and lights the specified one.
        """

    @abstractmethod
    def all_off(self) -> None:
        """Turn off all LEDs."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the hardware device is reachable."""

    @abstractmethod
    def close(self) -> None:
        """Release resources and close device handles."""


class MockTrafficLight(TrafficLight):
    """In-memory mock implementation for testing."""

    def __init__(self) -> None:
        self._active: set[Color] = set()
        self._connected: bool = True

    @property
    def active_colors(self) -> set[Color]:
        """Return the set of currently active colors."""
        return self._active.copy()

    def set_led(self, color: Color, state: LEDState) -> None:
        """Set a single LED on or off without affecting others."""
        if not self._connected:
            msg = "Mock traffic light is not connected"
            raise ConnectionError(msg)
        if state == LEDState.ON:
            self._active.add(color)
            logger.info("Mock LED %s ON (active: %s)", color.to_name(), self._active)
        else:
            self._active.discard(color)
            logger.info("Mock LED %s OFF (active: %s)", color.to_name(), self._active)

    def set_color(self, color: Color) -> None:
        """Set only this color, turning off all others."""
        if not self._connected:
            msg = "Mock traffic light is not connected"
            raise ConnectionError(msg)
        prev = self._active.copy()
        self._active = {color}
        logger.info(
            "Mock traffic light set_color %s (was: %s)",
            color.to_name(),
            prev if prev else "none",
        )

    def all_off(self) -> None:
        """Turn off all LEDs."""
        if not self._connected:
            msg = "Mock traffic light is not connected"
            raise ConnectionError(msg)
        self._active.clear()
        logger.info("Mock traffic light all off")

    def is_connected(self) -> bool:
        """Return mock connection status."""
        return self._connected

    def close(self) -> None:
        """Release mock resources."""
        self._connected = False
        self._active.clear()

    def set_disconnected(self) -> None:
        """Simulate hardware disconnection for testing."""
        self._connected = False

    def set_connected(self) -> None:
        """Simulate hardware reconnection for testing."""
        self._connected = True
