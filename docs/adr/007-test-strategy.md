# ADR 007: Test Strategy with pytest and Mocking

## Status

Accepted

## Context

The bridge must be thoroughly tested:

- Unit tests for isolated components
- Integration tests with a real MQTT broker
- Tests must run without USB hardware
- Coverage target: at least 90%

## Decision

Use a two-tier test strategy:

1. **Unit tests**: pytest with MockTrafficLight (no hardware needed)
2. **Integration tests**: pytest with a Mosquitto Docker container

## Architecture

```
tests/
├── unit/
│   ├── test_models.py         # Data models
│   ├── test_config.py         # Configuration
│   ├── test_traffic_light.py  # Mock + ABC
│   ├── test_cleware.py        # USB with mocks
│   ├── test_mqtt_client.py    # MQTT bridge
│   ├── test_discovery.py      # HA discovery
│   └── test_main.py           # Entry point
└── integration/
    ├── conftest.py            # Mosquitto container
    └── test_bridge_integration.py
```

## Mocking strategy

- **USB devices**: `unittest.mock.patch` for `usb.core.find`
- **MQTT broker**: Real Mosquitto in Docker
- **Hardware**: MockTrafficLight implements the ABC

## Rationale

- **No hardware required**: All tests run without real USB devices
- **Fast**: Unit tests in < 1s
- **Reliable**: No hardware dependencies
- **CI-compatible**: Tests run in GitHub Actions

## Alternatives considered

- **Only integration tests**: Too slow, requires Docker
- **Hardware-in-the-loop**: Not possible in CI
- **Snapshot tests**: Not meaningful for hardware control

## Consequences

- High test coverage (96.15%)
- Fast test execution
- Easy addition of new tests