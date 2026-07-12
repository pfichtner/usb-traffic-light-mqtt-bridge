"""Tests for config module."""

import pytest

from cleware_bridge.config import BridgeConfig


class TestBridgeConfig:
    def test_defaults(self) -> None:
        config = BridgeConfig()
        assert config.mqtt_host == "localhost"
        assert config.mqtt_port == 1883
        assert config.mqtt_username == ""
        assert config.mqtt_password == ""
        assert config.mqtt_topic_prefix == "cleware/ampel/"
        assert config.log_level == "INFO"
        assert config.device_id == "default"

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in [
            "MQTT_HOST",
            "MQTT_PORT",
            "MQTT_USERNAME",
            "MQTT_PASSWORD",
            "MQTT_TOPIC_PREFIX",
            "LOG_LEVEL",
            "DEVICE_ID",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = BridgeConfig.from_env()
        assert config.mqtt_host == "localhost"
        assert config.mqtt_port == 1883

    def test_from_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MQTT_HOST", "192.168.1.100")
        monkeypatch.setenv("MQTT_PORT", "8883")
        monkeypatch.setenv("MQTT_USERNAME", "user")
        monkeypatch.setenv("MQTT_PASSWORD", "pass")
        monkeypatch.setenv("MQTT_TOPIC_PREFIX", "my/ampel/")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DEVICE_ID", "ampel-1")

        config = BridgeConfig.from_env()
        assert config.mqtt_host == "192.168.1.100"
        assert config.mqtt_port == 8883
        assert config.mqtt_username == "user"
        assert config.mqtt_password == "pass"
        assert config.mqtt_topic_prefix == "my/ampel/"
        assert config.log_level == "DEBUG"
        assert config.device_id == "ampel-1"

    def test_topic_prefix_slash_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MQTT_TOPIC_PREFIX", "my/ampel")
        config = BridgeConfig.from_env()
        assert config.mqtt_topic_prefix == "my/ampel/"

    def test_invalid_port_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MQTT_PORT", "not_a_number")
        config = BridgeConfig.from_env()
        assert config.mqtt_port == 1883

    def test_frozen(self) -> None:
        config = BridgeConfig()
        with pytest.raises(AttributeError):
            config.mqtt_host = "new_host"  # type: ignore[misc]
