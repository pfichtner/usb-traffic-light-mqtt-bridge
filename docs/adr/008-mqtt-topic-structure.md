# ADR 008: MQTT Topic Structure with Per-Color Topics

## Status

Accepted

> **Note**: The topic structure remains valid. The subscription strategy was changed in ADR 011 from three individual subscriptions to a single wildcard subscription (`{prefix}/#`).

## Context

The bridge must receive MQTT messages and translate them into traffic-light commands. There are two main approaches:

1. A single command topic with a JSON payload
2. Separate topics per color with an integer brightness value

## Decision

Use per-color topics with an integer brightness payload. Each LED is controlled individually; multiple LEDs can be active at the same time.

## Topic structure

```
cleware/ampel/red     → 0 (off) or 1 (on)
cleware/ampel/yellow  → 0 (off) or 1 (on)
cleware/ampel/green   → 0 (off) or 1 (on)
```

## Behavior

Each LED is controlled independently. Switching one LED has no effect on the others:

```bash
# Turn red on
mosquitto_pub -t "cleware/ampel/red" -m "1"

# Turn green on — red stays on!
mosquitto_pub -t "cleware/ampel/green" -m "1"

# Turn red off — green stays on
mosquitto_pub -t "cleware/ampel/red" -m "0"
```

The bridge tracks the internal state of all LEDs and only sends the respective change to the hardware.

## Rationale

- **Independent LED control**: Multiple LEDs can be active at the same time
- **Simplicity**: An integer payload is simpler than JSON
- **Home Assistant compatible**: Per-color topics are HA-friendly
- **Clarity**: Topics are self-explanatory

## Alternatives considered

- **JSON payload**: More overhead, more complex to parse
- **Single command topic**: Less flexible for HA integration
- **State topic with JSON publish**: Not needed, since no external state tracking is required

## Consequences

- Easy integration with Home Assistant
- Clear separation of color channels
- Brightness value is ignored (hardware supports only on/off)
- No state topic required