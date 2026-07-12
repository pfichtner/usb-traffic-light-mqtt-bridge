# ADR 004: Hardware Abstraction Using the ABC Pattern

## Status

Accepted

## Context

The MQTT logic must not depend directly on Cleware-specific code. The hardware component must be exchangeable for:

- Unit tests (mock)
- Different hardware versions
- Future extensions (other traffic-light types)

## Decision

Use the Abstract Base Class (ABC) pattern with `TrafficLight` as the abstract base class.

## Architecture

```
TrafficLight (ABC)
    |
    +-- ClewareTrafficLight  (pyusb)
    |
    +-- MockTrafficLight     (tests)
```

## Interface

```python
class TrafficLight(ABC):
    @abstractmethod
    def set_color(self, color: Color) -> None: ...

    @abstractmethod
    def all_off(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def close(self) -> None: ...
```

## Rationale

- **Testability**: MockTrafficLight enables hardware tests without real devices
- **Exchangeability**: New hardware implementations can be added
- **Separation of concerns**: The MQTT logic is independent of hardware details
- **Uniform interface**: All implementations expose the same API

## Alternatives considered

- **Direct dependency**: Would make testing harder and hardware exchange difficult
- **Duck typing**: Less explicit, harder to maintain

## Consequences

- Slightly more code (ABC + implementations)
- Significantly better testability
- Clear architectural separation