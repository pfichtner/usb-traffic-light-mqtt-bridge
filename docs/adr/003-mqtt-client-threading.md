# ADR 003: paho-mqtt v2 with a Thread-Based Event Loop

## Status

Accepted

## Context

The bridge must receive and process MQTT messages. There are two main approaches:

1. Thread-based using `loop_start()` / `loop_forever()`
2. Asyncio-based with `loop()` integration

## Decision

Use paho-mqtt v2 with a thread-based event loop (`loop_forever()`).

## Rationale

- **Simplicity**: `loop_forever()` handles reconnection automatically
- **Robustness**: The thread-based approach is proven and well tested
- **Exponential backoff**: paho-mqtt supports `reconnect_delay_set(min_delay=1, max_delay=60)` directly
- **Lower complexity**: No asyncio event loop needed

## Technical details

```python
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
client.reconnect_delay_set(min_delay=1, max_delay=60)
client.loop_forever()  # Blocks, handles reconnection automatically
```

## Alternatives considered

- **asyncio**: Higher complexity when integrating with paho-mqtt, no significant advantages for this application
- **Manual event loop**: More error-prone, more code

## Consequences

- Simpler implementation
- Automatic reconnection with backoff
- Thread safety must be taken into account