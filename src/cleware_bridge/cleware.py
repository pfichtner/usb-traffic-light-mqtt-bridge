"""Cleware USB traffic light implementation using pyusb."""

from __future__ import annotations

import contextlib
import logging
import time

import usb.core
import usb.util

from .models import Color, LEDState
from .traffic_light import TrafficLight

logger = logging.getLogger(__name__)


class ClewareTrafficLight(TrafficLight):
    """Control a Cleware USB traffic light via pyusb."""

    VENDOR_ID = 0x0D50
    PRODUCT_ORIGINAL = 0x0008
    PRODUCT_SWITCH = 0x0030
    CTRL_ENDPOINT = 0x02
    INTERFACE = 0

    def __init__(self, device_id: str = "default") -> None:
        self._device_id = device_id
        self._device: usb.core.Device | None = None
        self._reattach = False
        self._connected = False
        self._last_attempt = 0.0
        self._find_device()

    def _find_device(self) -> None:
        """Search for a connected Cleware USB device."""
        for product_id in (self.PRODUCT_ORIGINAL, self.PRODUCT_SWITCH):
            dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=product_id)
            if dev is not None:
                self._device = dev
                self._connected = True
                logger.info(
                    "Cleware device found: vendor=0x%04X product=0x%04X",
                    self.VENDOR_ID,
                    product_id,
                )
                self._ensure_detached()
                return
        self._device = None
        self._connected = False
        logger.warning("Cleware device not found (device_id=%s)", self._device_id)

    def _ensure_detached(self) -> None:
        """Detach kernel driver if active."""
        if self._device is None:
            return
        try:
            if self._device.is_kernel_driver_active(self.INTERFACE):
                self._device.detach_kernel_driver(self.INTERFACE)
                self._reattach = True
        except usb.core.USBError:
            pass

    def _reattach_kernel_driver(self) -> None:
        """Reattach kernel driver if it was detached."""
        if self._device is None or not self._reattach:
            return
        try:
            usb.util.dispose_resources(self._device)
            self._device.attach_kernel_driver(self.INTERFACE)
            self._reattach = False
        except (usb.core.USBError, NotImplementedError):
            pass

    def set_led(self, color: Color, state: LEDState) -> None:
        """Set a single LED on or off without affecting other LEDs."""
        if not self._connected or self._device is None:
            self._try_reconnect()
            if not self._connected:
                msg = f"Cleware device not available for LED {color.to_name()}"
                raise ConnectionError(msg)

        self._send_command(color, state)
        logger.info("LED %s %s", color.to_name(), "ON" if state == LEDState.ON else "OFF")

    def set_color(self, color: Color) -> None:
        """Set the traffic light to the specified color.

        Turns off all other LEDs and lights the specified one.
        """
        if not self._connected or self._device is None:
            self._try_reconnect()
            if not self._connected:
                msg = f"Cleware device not available for color {color.to_name()}"
                raise ConnectionError(msg)

        self._send_command(color, LEDState.ON)

        for other_color in Color:
            if other_color != color:
                try:
                    self._send_command(other_color, LEDState.OFF)
                except Exception as exc:
                    logger.warning("Failed to turn off %s: %s", other_color.to_name(), exc)

        logger.info("Traffic light set_color %s", color.to_name())

    def _send_command(self, color: Color, state: LEDState) -> None:
        """Send a raw USB command to the device."""
        assert self._device is not None

        try:
            product_id = self._device.idProduct

            if product_id == self.PRODUCT_ORIGINAL:
                payload = bytes([0x00, int(color), int(state)])
            elif product_id == self.PRODUCT_SWITCH:
                payload = self._build_switch_payload(color, state)
            else:
                msg = f"Unknown product ID: 0x{product_id:04X}"
                raise ValueError(msg)

            self._device.write(self.CTRL_ENDPOINT, payload, timeout=1000)
        except usb.core.USBError as exc:
            self._connected = False
            logger.error("USB error during command: %s", exc)
            raise

    @staticmethod
    def _build_switch_payload(color: Color, state: LEDState) -> bytes:
        """Build the payload for V4 switch-type traffic lights."""
        color_id = int(color) % 0x10
        color_offset = color_id * 4
        direction = 0x000F
        value = (direction << color_offset) * int(state)
        mask = direction << color_offset
        return bytes([11]) + value.to_bytes(2, "big") + mask.to_bytes(2, "big")

    def _try_reconnect(self) -> None:
        """Attempt to reconnect if enough time has passed."""
        now = time.monotonic()
        if now - self._last_attempt < 5.0:
            return
        self._last_attempt = now
        logger.info("Attempting to reconnect to Cleware device...")
        self._find_device()

    def all_off(self) -> None:
        """Turn off all LEDs."""
        if not self._connected or self._device is None:
            self._try_reconnect()
            if not self._connected:
                msg = "Cleware device not available"
                raise ConnectionError(msg)

        for color in Color:
            try:
                self._send_command(color, LEDState.OFF)
            except Exception as exc:
                logger.warning("Failed to turn off %s: %s", color.to_name(), exc)

        logger.info("Traffic light all off")

    def is_connected(self) -> bool:
        """Return whether the device is reachable."""
        return self._connected

    def close(self) -> None:
        """Release USB resources."""
        if self._device is not None:
            with contextlib.suppress(Exception):
                self.all_off()
            self._reattach_kernel_driver()
            usb.util.dispose_resources(self._device)
            self._device = None
        self._connected = False
        logger.info("Cleware device closed")
