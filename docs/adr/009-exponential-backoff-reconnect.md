# ADR 009: Exponential Backoff for MQTT Reconnection

## Status

Accepted

## Context

The MQTT broker may be temporarily unavailable. The bridge should:

- Automatically try to re-establish the connection
- Not overload the broker
- Be robust against temporary outages

## Decision

Use exponential backoff via paho-mqtt's `reconnect_delay_set()`.

## Implementation

```python
client.reconnect_delay_set(min_delay=1, max_delay=60)
client.loop_forever()  # Automatic reconnection
```

## Behavior

- Initial delay: 1 second
- Maximum delay: 60 seconds
- Multiplier: Exponential (1s, 2s, 4s, 8s, ... up to 60s)
- Automatic reset on a successful connection

## Rationale

- **Protects the broker**: No overload during long outages
- **Fast recovery**: Quick reconnect after short outages
- **Standard solution**: paho-mqtt provides this directly
- **No custom implementation needed**

## Alternatives considered

- **Fixed retry interval**: Overloads the broker during long outages
- **Manual reconnect**: More error-prone
- **No reconnect**: Leads to permanent connection loss

## Consequences

- Robust behavior during temporary outages
- No manual configuration required
- The broker is not overloaded