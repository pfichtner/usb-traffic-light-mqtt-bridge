# ADR 010: Home Assistant MQTT Discovery Stub

## Status

Accepted

## Context

Home Assistant can discover MQTT devices automatically via MQTT Discovery. The bridge should:

- Support HA Discovery later on
- Not be implemented yet
- Prepare the architecture for it

## Decision

Implement `DiscoveryPublisher` as a stub using an Abstract Base Class.

## Implementation

```python
class DiscoveryPublisher(ABC):
    @abstractmethod
    def publish_config(self, light: TrafficLight, config: BridgeConfig) -> None: ...

    @abstractmethod
    def remove_config(self, config: BridgeConfig) -> None: ...

class HomeAssistantDiscovery(DiscoveryPublisher):
    def publish_config(self, light, config):
        logger.info("HA Discovery not yet implemented - skipping")

    def remove_config(self, config):
        logger.info("HA Discovery removal not yet implemented - skipping")
```

## Rationale

- **Preparation**: The architecture is ready for a later implementation
- **No overhead**: The stub is minimal
- **Testability**: The interface can be mocked
- **Extensibility**: New discovery protocols can be added

## Future implementation

When HA Discovery is implemented:

1. `publish_config()` publishes the configuration to `homeassistant/light/{device_id}/config`
2. `remove_config()` removes the configuration
3. State updates are sent automatically via the existing state publication

## Alternatives considered

- **Direct implementation**: Too early, requirements are still unclear
- **No preparation at all**: A later implementation would be harder

## Consequences

- A clear interface for HA Discovery
- No dependencies on Home Assistant
- Easy later implementation