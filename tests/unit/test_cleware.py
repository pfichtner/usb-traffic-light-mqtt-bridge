"""Tests for cleware USB module."""

import time
from unittest.mock import MagicMock, patch

import pytest
import usb.core

import cleware_bridge.cleware as cleware_mod
from cleware_bridge.models import Color, LEDState


def _make_mock_device(
    *,
    product_id: int = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL,
    serial: str | None = None,
    bus: int = 1,
    port_numbers: tuple[int, ...] = (1,),
    kernel_driver_active: bool = False,
) -> MagicMock:
    """Build a MagicMock that looks enough like a pyusb Device for our tests."""
    mock_dev = MagicMock()
    mock_dev.idProduct = product_id
    mock_dev.serial_number = serial
    mock_dev.bus = bus
    mock_dev.port_numbers = port_numbers
    mock_dev.is_kernel_driver_active.return_value = kernel_driver_active
    return mock_dev


class TestClewareTrafficLightInit:
    def test_device_found(self) -> None:
        mock_dev = _make_mock_device()

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is True

    def test_device_not_found(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is False

    def test_switch_product_found(self) -> None:
        mock_dev = _make_mock_device(
            product_id=cleware_mod.ClewareTrafficLight.PRODUCT_SWITCH,
        )

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is True


class TestClewareTrafficLightCommands:
    @pytest.fixture()
    def mock_light(self) -> cleware_mod.ClewareTrafficLight:
        mock_dev = _make_mock_device(kernel_driver_active=False)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
        return light

    def test_set_led_on_sends_payload(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light.set_led(Color.RED, LEDState.ON)
        mock_light._device.write.assert_called_once()

    def test_set_led_off_sends_payload(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light.set_led(Color.RED, LEDState.OFF)
        mock_light._device.write.assert_called_once()

    def test_set_led_does_not_affect_others(
        self, mock_light: cleware_mod.ClewareTrafficLight
    ) -> None:
        mock_light.set_led(Color.RED, LEDState.ON)
        assert mock_light._device.write.call_count == 1
        mock_light.set_led(Color.GREEN, LEDState.ON)
        assert mock_light._device.write.call_count == 2

    def test_set_color_sends_payload(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light.set_color(Color.RED)
        mock_light._device.write.assert_called()

    def test_set_color_turns_off_others(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light.set_color(Color.GREEN)
        assert mock_light._device.write.call_count == 3

    def test_all_off(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light.all_off()
        assert mock_light._device.write.call_count == 3

    def test_set_color_when_not_connected(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(ConnectionError):
                light.set_color(Color.RED)

    def test_set_led_when_not_connected(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(ConnectionError):
                light.set_led(Color.RED, LEDState.ON)

    def test_set_color_reconnect_throttled(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            light._last_attempt = time.monotonic()
            with pytest.raises(ConnectionError):
                light.set_color(Color.RED)

    def test_all_off_when_not_connected(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(ConnectionError):
                light.all_off()

    def test_switch_product_payload(self, mock_light: cleware_mod.ClewareTrafficLight) -> None:
        mock_light._device.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_SWITCH
        mock_light.set_color(Color.RED)
        mock_light._device.write.assert_called()


class TestClewareTrafficLightUSBErrors:
    def test_usb_error_sets_disconnected(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(usb.core.USBError):
                light.set_color(Color.RED)
            assert light.is_connected() is False

    def test_set_led_usb_error(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(usb.core.USBError):
                light.set_led(Color.RED, LEDState.ON)
            assert light.is_connected() is False

    def test_all_off_usb_error(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            # all_off catches USBError per-color in the loop, doesn't raise
            light.all_off()
            assert light.is_connected() is False


class TestClewareKernelDriver:
    def test_detach_kernel_driver(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=True)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light.set_color(Color.RED)
            mock_dev.detach_kernel_driver.assert_called()
            # Reattach only happens on close()
            mock_dev.attach_kernel_driver.assert_not_called()
            light.close()
            mock_dev.attach_kernel_driver.assert_called()

    def test_reattach_error_ignored(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=True)
        mock_dev.attach_kernel_driver.side_effect = usb.core.USBError("fail")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light.set_color(Color.RED)
            # Should not raise during close()
            light.close()


class TestClewareClose:
    def test_close(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light.close()
            assert light.is_connected() is False
            assert light._device is None

    def test_close_no_device(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            light.close()
            assert light.is_connected() is False

    def test_close_all_off_error_ignored(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)
        mock_dev.write.side_effect = usb.core.USBError("fail")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light.close()
            assert light.is_connected() is False


class TestClewareBuildSwitchPayload:
    def test_red_on(self) -> None:
        payload = cleware_mod.ClewareTrafficLight._build_switch_payload(Color.RED, LEDState.ON)
        assert len(payload) == 5
        assert payload[0] == 11

    def test_green_off(self) -> None:
        payload = cleware_mod.ClewareTrafficLight._build_switch_payload(Color.GREEN, LEDState.OFF)
        assert len(payload) == 5
        assert payload[0] == 11

    def test_yellow_on(self) -> None:
        payload = cleware_mod.ClewareTrafficLight._build_switch_payload(Color.YELLOW, LEDState.ON)
        assert len(payload) == 5
        assert payload[0] == 11


class TestClewareReconnectThrottle:
    def test_try_reconnect_throttle_respects_timing(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light._connected = False
            light._last_attempt = time.monotonic()
            light._try_reconnect()
            assert mock_dev.write.call_count == 0

    def test_try_reconnect_after_timeout(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light._connected = False
            light._last_attempt = time.monotonic() - 6.0
            light._try_reconnect()
            assert light._last_attempt > time.monotonic() - 1.0


class TestClewareSetColorPartialFailure:
    def test_set_color_logs_warning_on_turn_off_failure(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)
        call_count = [0]

        def write_side_effect(endpoint, payload, timeout=1000):
            call_count[0] += 1
            if call_count[0] > 1:
                raise usb.core.USBError("USB error")

        mock_dev.write.side_effect = write_side_effect

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light.set_color(Color.RED)
            assert mock_dev.write.call_count >= 2


class TestClewareUnknownProductId:
    def test_send_command_unknown_product_id(self) -> None:
        mock_dev = _make_mock_device(kernel_driver_active=False)

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            light._connected = True
            light._device.idProduct = 0x9999
            with pytest.raises(ValueError, match="Unknown product ID"):
                light.set_led(Color.RED, LEDState.ON)


class TestClewareMultipleDevices:
    """Tests for the multi-device identification logic added for MQTTA-1."""

    def test_default_with_single_device_selects_it(self) -> None:
        mock_dev = _make_mock_device(serial="ABC123")

        with patch.object(cleware_mod.usb.core, "find", return_value=[mock_dev]):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is True
            assert light._device is mock_dev

    def test_default_with_multiple_devices_raises_clear_error(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
            pytest.raises(ValueError, match="Multiple Cleware traffic lights detected"),
        ):
            cleware_mod.ClewareTrafficLight()

    def test_select_first_device_by_serial(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
        ):
            light = cleware_mod.ClewareTrafficLight(device_id="ABC123")
            assert light.is_connected() is True
            assert light._device is dev1

    def test_select_second_device_by_serial(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
        ):
            light = cleware_mod.ClewareTrafficLight(device_id="DEF456")
            assert light.is_connected() is True
            assert light._device is dev2

    def test_select_device_by_port_path_when_serials_duplicated(self) -> None:
        dev1 = _make_mock_device(serial="SAME", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="SAME", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
        ):
            light = cleware_mod.ClewareTrafficLight(device_id="1:2")
            assert light.is_connected() is True
            assert light._device is dev2

    def test_commands_sent_only_to_selected_device(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
        ):
            light = cleware_mod.ClewareTrafficLight(device_id="DEF456")
            light.set_led(Color.RED, LEDState.ON)
            dev2.write.assert_called_once()
            dev1.write.assert_not_called()

    def test_unselected_devices_disposed(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources") as dispose,
        ):
            cleware_mod.ClewareTrafficLight(device_id="DEF456")
            dispose.assert_called_once_with(dev1)

    def test_configured_device_not_found(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
            pytest.raises(ValueError, match=r"Configured device .* not found"),
        ):
            cleware_mod.ClewareTrafficLight(device_id="MISSING")

    def test_duplicate_serial_by_serial_id_raises_ambiguous_error(self) -> None:
        dev1 = _make_mock_device(serial="SAME", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="SAME", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
            pytest.raises(ValueError, match="matches multiple devices"),
        ):
            cleware_mod.ClewareTrafficLight(device_id="SAME")

    def test_port_path_detected_when_serial_unavailable(self) -> None:
        dev1 = _make_mock_device(serial=None, bus=1, port_numbers=(3,))

        with patch.object(cleware_mod.usb.core, "find", return_value=[dev1]):
            light = cleware_mod.ClewareTrafficLight(device_id="1:3")
            assert light.is_connected() is True
            assert light._device is dev1

    def test_deterministic_across_reconnects(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))

        with patch.object(cleware_mod.usb.core, "find", return_value=[dev1]):
            light = cleware_mod.ClewareTrafficLight(device_id="ABC123")
            light._connected = False
            light._last_attempt = time.monotonic() - 6.0
            light._try_reconnect()
            assert light._device is dev1
            assert light.is_connected() is True

    def test_two_different_identifiers_default_fails(self) -> None:
        dev1 = _make_mock_device(serial="SERIAL1", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial=None, bus=2, port_numbers=(3,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
            pytest.raises(ValueError, match="Multiple Cleware traffic lights detected"),
        ):
            cleware_mod.ClewareTrafficLight()

    def test_device_id_port_path_with_unique_serials_still_works(self) -> None:
        dev1 = _make_mock_device(serial="ABC123", bus=1, port_numbers=(1,))
        dev2 = _make_mock_device(serial="DEF456", bus=1, port_numbers=(2,))

        with (
            patch.object(cleware_mod.usb.core, "find", return_value=[dev1, dev2]),
            patch.object(cleware_mod.usb.util, "dispose_resources"),
        ):
            light = cleware_mod.ClewareTrafficLight(device_id="1:2")
            assert light.is_connected() is True
            assert light._device is dev2
