# ADR 016: Fail-Fast USB Initialization at Startup

## Status

Accepted

## Context

Originally the bridge could be started with `LIGHT_BACKEND=cleware` even when
no compatible USB device was connected. The missing hardware was only noticed
when the first MQTT command arrived, because the connection was validated
lazily inside the command path. This delayed failure made operational problems
harder to diagnose and violated the principle of failing fast.

## Decision

When the backend is set to `auto` or `cleware`, the bridge must verify that a
compatible Cleware USB device is available immediately during startup. If the
device cannot be found or the configured `DEVICE_ID` is ambiguous, the program
exits with a non-zero status code and a clear log message before the MQTT
client is started.

## Rationale

- **Fail fast**: Configuration or hardware problems surface immediately at start
  time, not after a message has been published.
- **Operational clarity**: The logs show the exact error before any MQTT state
  is managed.
- **Safety**: The bridge never starts in a state where it would silently ignore
  commands.
- **Mock independence**: `LIGHT_BACKEND=mock` is explicitly exempted because it
  is intended for development and CI without hardware.

## Consequences

- `LIGHT_BACKEND=cleware` now exits on startup if no matching device is found.
- `LIGHT_BACKEND=auto` already behaved this way; the change unifies the behavior.
- Startup tests must assert `SystemExit(1)` when no hardware is present.
- The same `_init_cleware_traffic_light` helper is used for both `auto` and
  `cleware` backends to avoid duplicated logic.

## Related

- ADR 004: Hardware Abstraction Using the ABC Pattern
- ADR 015: USB Device Identification for Multiple Cleware Traffic Lights
- Issue MQTTA-2: usb device fail fast
