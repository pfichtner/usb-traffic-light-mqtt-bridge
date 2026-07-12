"""Tests for cleware USB module."""

import time
from unittest.mock import MagicMock, patch

import pytest
import usb.core

import cleware_bridge.cleware as cleware_mod
from cleware_bridge.models import Color, LEDState


class TestClewareTrafficLightInit:
    def test_device_found(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is True

    def test_device_not_found(self) -> None:
        with patch.object(cleware_mod.usb.core, "find", return_value=None):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is False

    def test_switch_product_found(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_SWITCH

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            assert light.is_connected() is True


class TestClewareTrafficLightCommands:
    @pytest.fixture()
    def mock_light(self) -> cleware_mod.ClewareTrafficLight:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
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
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(usb.core.USBError):
                light.set_color(Color.RED)
            assert light.is_connected() is False

    def test_set_led_usb_error(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            with pytest.raises(usb.core.USBError):
                light.set_led(Color.RED, LEDState.ON)
            assert light.is_connected() is False

    def test_all_off_usb_error(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False
        mock_dev.write.side_effect = usb.core.USBError("USB error")

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            # all_off catches USBError per-color in the loop, doesn't raise
            light.all_off()
            assert light.is_connected() is False


class TestClewareKernelDriver:
    def test_detach_kernel_driver(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = True

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            light.set_color(Color.RED)
            mock_dev.detach_kernel_driver.assert_called()
            # Reattach only happens on close()
            mock_dev.attach_kernel_driver.assert_not_called()
            light.close()
            mock_dev.attach_kernel_driver.assert_called()

    def test_reattach_error_ignored(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = True
        mock_dev.attach_kernel_driver.side_effect = usb.core.USBError("fail")

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
            light = cleware_mod.ClewareTrafficLight()
            light.set_color(Color.RED)
            # Should not raise during close()
            light.close()


class TestClewareClose:
    def test_close(self) -> None:
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
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
        mock_dev = MagicMock()
        mock_dev.idProduct = cleware_mod.ClewareTrafficLight.PRODUCT_ORIGINAL
        mock_dev.is_kernel_driver_active.return_value = False
        mock_dev.write.side_effect = usb.core.USBError("fail")

        with patch.object(cleware_mod.usb.core, "find", return_value=mock_dev):
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
