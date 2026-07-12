"""Home Assistant MQTT Discovery support (stub for future implementation)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .config import BridgeConfig
from .traffic_light import TrafficLight

logger = logging.getLogger(__name__)


class DiscoveryPublisher(ABC):
    """Abstract base class for MQTT discovery publishing."""

    @abstractmethod
    def publish_config(self, light: TrafficLight, config: BridgeConfig) -> None:
        """Publish discovery configuration for the traffic light."""

    @abstractmethod
    def remove_config(self, config: BridgeConfig) -> None:
        """Remove discovery configuration."""


class HomeAssistantDiscovery(DiscoveryPublisher):
    """Home Assistant MQTT Discovery publisher.

    Placeholder for future implementation. When enabled, this will publish
    auto-discovery messages so Home Assistant can automatically detect
    the traffic light.
    """

    def publish_config(self, light: TrafficLight, config: BridgeConfig) -> None:
        """Publish HA discovery config. Not yet implemented."""
        logger.info("HA Discovery not yet implemented - skipping")

    def remove_config(self, config: BridgeConfig) -> None:
        """Remove HA discovery config. Not yet implemented."""
        logger.info("HA Discovery removal not yet implemented - skipping")
