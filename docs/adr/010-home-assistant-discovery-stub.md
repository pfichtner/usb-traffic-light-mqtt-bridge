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

Entities to expose once implemented:

- One `light` or `switch` entity per color topic (`{prefix}/red|yellow|green`).
- `select` entities for static patterns (`{prefix}/pattern`).
- `select` entities for each built-in animation (`{prefix}/pattern/anim/<name>`),
  mapping `speed_ms`, `repeats`, and `colors` to UI controls (ADR 013).
- `select` entities for each traffic light animation
  (`{prefix}/pattern/tl/<country>/<name>`), mapping `speed_factor` and
  `hold_final` to UI controls (ADR 014). The animation catalog (and any
  future country additions) is data-driven via `TL_TIMINGS`, so a future
  implementation should enumerate the catalog rather than hard-code entity
  names, ensuring new countries appear without discovery-code changes.

## Alternatives considered

- **Direct implementation**: Too early, requirements are still unclear
- **No preparation at all**: A later implementation would be harder

## Consequences

- A clear interface for HA Discovery
- No dependencies on Home Assistant
- Easy later implementation