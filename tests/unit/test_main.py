"""Tests for main module."""

import signal
from unittest.mock import MagicMock, patch

import pytest

from cleware_bridge.main import _create_traffic_light, _setup_logging
from cleware_bridge.traffic_light import MockTrafficLight


class TestSetupLogging:
    def test_setup_logging_info(self) -> None:
        _setup_logging("INFO")

    def test_setup_logging_debug(self) -> None:
        _setup_logging("DEBUG")

    def test_setup_logging_invalid_level(self) -> None:
        _setup_logging("INVALID")


class TestCreateTrafficLight:
    def test_mock_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIGHT_BACKEND", "mock")
        light = _create_traffic_light(MagicMock())
        assert isinstance(light, MockTrafficLight)

    def test_cleware_backend_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIGHT_BACKEND", "cleware")
        mock_dev = MagicMock()
        mock_dev.idProduct = 0x0008
        with patch("cleware_bridge.cleware.usb.core.find", return_value=mock_dev):
            light = _create_traffic_light(MagicMock())
            from cleware_bridge.cleware import ClewareTrafficLight

            assert isinstance(light, ClewareTrafficLight)

    def test_auto_backend_no_device_exits_abnormally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LIGHT_BACKEND", raising=False)
        with patch("cleware_bridge.cleware.usb.core.find", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                _create_traffic_light(MagicMock())
            assert exc_info.value.code == 1

    def test_auto_backend_exception_exits_abnormally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LIGHT_BACKEND", raising=False)
        with patch(
            "cleware_bridge.cleware.usb.core.find",
            side_effect=Exception("USB error"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                _create_traffic_light(MagicMock())
            assert exc_info.value.code == 1


class TestMainFunction:
    def test_main_exits_abnormally_when_no_device_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LIGHT_BACKEND", raising=False)
        monkeypatch.setenv("MQTT_HOST", "localhost")
        monkeypatch.setenv("MQTT_PORT", "11883")

        with (
            patch("cleware_bridge.cleware.usb.core.find", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from cleware_bridge import main as main_mod

            main_mod.main()

        assert exc_info.value.code == 1

    def test_main_shuts_down_on_sigterm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIGHT_BACKEND", "mock")
        monkeypatch.setenv("MQTT_HOST", "localhost")
        monkeypatch.setenv("MQTT_PORT", "11883")

        with (
            patch("cleware_bridge.main.MQTTBridge") as mock_bridge_cls,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_bridge = MagicMock()
            mock_bridge_cls.return_value = mock_bridge

            from cleware_bridge import main as main_mod

            original_signal = signal.signal

            def fake_signal(signum: int, handler: object) -> None:
                if signum == signal.SIGTERM:
                    handler(signum, None)
                original_signal(signum, handler)

            with patch.object(signal, "signal", side_effect=fake_signal):
                main_mod.main()

        assert exc_info.value.code == 0

    def test_main_keyboard_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIGHT_BACKEND", "mock")
        monkeypatch.setenv("MQTT_HOST", "localhost")
        monkeypatch.setenv("MQTT_PORT", "11883")

        with patch("cleware_bridge.main.MQTTBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_bridge.start.side_effect = KeyboardInterrupt()
            mock_bridge_cls.return_value = mock_bridge

            from cleware_bridge import main as main_mod

            main_mod.main()

            mock_bridge.stop.assert_called_once()

    def test_main_finally_block_executes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIGHT_BACKEND", "mock")
        monkeypatch.setenv("MQTT_HOST", "localhost")
        monkeypatch.setenv("MQTT_PORT", "11883")

        with patch("cleware_bridge.main.MQTTBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_light = MagicMock()
            mock_bridge_cls.return_value = mock_bridge

            from cleware_bridge import main as main_mod

            with patch("cleware_bridge.main._create_traffic_light", return_value=mock_light):
                main_mod.main()

            mock_bridge.stop.assert_called_once()
            mock_light.close.assert_called_once()
