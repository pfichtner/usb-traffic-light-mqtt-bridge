"""Cleware USB traffic light implementation using pyusb."""

from __future__ import annotations

import contextlib
import logging
import time
from collections import Counter
from dataclasses import dataclass

import usb.core
import usb.util

from .models import Color, LEDState
from .traffic_light import TrafficLight

logger = logging.getLogger(__name__)


@dataclass
class _DeviceCandidate:
    """A discovered Cleware USB device with stable identifiers."""

    device: usb.core.Device
    serial: str | None
    port_path: str
    primary_id: str = ""

    def set_primary_id(self, serial_counts: Counter[str]) -> None:
        """Choose the most stable identifier for this device.

        Unique serial numbers are preferred. When serial numbers are missing or
        duplicated, the physical USB topology (port path) is used because it
        survives reconnects on the same port, unlike the transient device address.
        """
        if self.serial and serial_counts[self.serial] == 1:
            self.primary_id = self.serial
        else:
            self.primary_id = self.port_path


def _read_serial(device: usb.core.Device) -> str | None:
    """Read the USB serial number, returning None if unavailable."""
    try:
        serial = device.serial_number
    except usb.core.USBError:
        return None
    if serial is None:
        return None
    return str(serial)


def _port_path(device: usb.core.Device) -> str:
    """Build a stable identifier from the USB bus/port topology.

    The bus number plus the physical port path is stable across reconnects as
    long as the device stays plugged into the same port.
    """
    ports = device.port_numbers or ()
    port_str = ".".join(str(port) for port in ports)
    return f"{device.bus}:{port_str}"


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

    def _enumerate_devices(self) -> list[_DeviceCandidate]:
        """Enumerate all connected Cleware USB traffic lights."""
        candidates: list[_DeviceCandidate] = []
        found = usb.core.find(
            idVendor=self.VENDOR_ID,
            find_all=True,
        )
        if found is None:
            return candidates
        for device in found:
            if device.idProduct not in (self.PRODUCT_ORIGINAL, self.PRODUCT_SWITCH):
                continue
            candidates.append(
                _DeviceCandidate(
                    device=device,
                    serial=_read_serial(device),
                    port_path=_port_path(device),
                )
            )
        return candidates

    def _select_device(self, candidates: list[_DeviceCandidate]) -> _DeviceCandidate:
        """Select a unique device from the candidates based on DEVICE_ID."""
        if not candidates:
            if self._device_id == "default":
                msg = "No Cleware traffic light found."
                raise RuntimeError(msg)
            msg = (
                f"Configured device {self._device_id!r} not found. "
                "No Cleware traffic light detected."
            )
            raise ValueError(msg)

        serials = [candidate.serial for candidate in candidates if candidate.serial]
        serial_counts = Counter(serials)
        for candidate in candidates:
            candidate.set_primary_id(serial_counts)

        if self._device_id == "default":
            if len(candidates) == 1:
                return candidates[0]
            lines = "\n".join(
                f"  - {candidate.primary_id} (port {candidate.port_path})"
                for candidate in candidates
            )
            msg = (
                "Multiple Cleware traffic lights detected. "
                "Configure DEVICE_ID to uniquely identify one of them.\n"
                f"Detected devices:\n{lines}"
            )
            raise ValueError(msg)

        primary_map = {candidate.primary_id: candidate for candidate in candidates}
        serial_map: dict[str, list[_DeviceCandidate]] = {}
        port_map = {candidate.port_path: candidate for candidate in candidates}
        for candidate in candidates:
            if candidate.serial:
                serial_map.setdefault(candidate.serial, []).append(candidate)

        if self._device_id in primary_map:
            return primary_map[self._device_id]
        if self._device_id in serial_map:
            matches = serial_map[self._device_id]
            if len(matches) > 1:
                lines = "\n".join(f"  - {candidate.port_path}" for candidate in matches)
                msg = (
                    f"DEVICE_ID {self._device_id!r} matches multiple devices "
                    "with the same serial number. Use a port path to disambiguate:\n"
                    f"{lines}"
                )
                raise ValueError(msg)
            return matches[0]
        if self._device_id in port_map:
            return port_map[self._device_id]

        lines = "\n".join(
            f"  - {candidate.primary_id} (port {candidate.port_path})" for candidate in candidates
        )
        msg = f"Configured device {self._device_id!r} not found.\nDetected devices:\n{lines}"
        raise ValueError(msg)

    def _find_device(self) -> None:
        """Search for a connected Cleware USB device matching DEVICE_ID."""
        candidates = self._enumerate_devices()
        try:
            selected = self._select_device(candidates)
        except ValueError as exc:
            self._device = None
            self._connected = False
            logger.error("%s", exc)
            raise
        except RuntimeError as exc:
            self._device = None
            self._connected = False
            logger.warning("%s", exc)
            return

        for candidate in candidates:
            if candidate.device is not selected.device:
                usb.util.dispose_resources(candidate.device)

        self._device = selected.device
        self._connected = True
        logger.info(
            "Cleware device selected: device_id=%s, port=%s",
            selected.primary_id,
            selected.port_path,
        )
        self._ensure_detached()

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
        try:
            self._find_device()
        except ValueError as exc:
            logger.warning("Failed to reconnect to Cleware device: %s", exc)
            self._connected = False

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
