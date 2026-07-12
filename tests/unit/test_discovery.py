"""Tests for discovery module."""

from cleware_bridge.config import BridgeConfig
from cleware_bridge.discovery import HomeAssistantDiscovery
from cleware_bridge.traffic_light import MockTrafficLight


class TestHomeAssistantDiscovery:
    def test_publish_config_does_not_raise(self) -> None:
        discovery = HomeAssistantDiscovery()
        light = MockTrafficLight()
        config = BridgeConfig()
        # Should not raise
        discovery.publish_config(light, config)

    def test_remove_config_does_not_raise(self) -> None:
        discovery = HomeAssistantDiscovery()
        config = BridgeConfig()
        # Should not raise
        discovery.remove_config(config)
