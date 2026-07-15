# USB Traffic Light MQTT Bridge

[![Tests](https://github.com/pfichtner/usb-traffic-light-mqtt-bridge/actions/workflows/tests.yml/badge.svg)](https://github.com/pfichtner/usb-traffic-light-mqtt-bridge/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/pfichtner/usb-traffic-light-mqtt-bridge/blob/main/LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/pfichtner/usb-traffic-light-mqtt-bridge/graph/badge.svg)](https://codecov.io/gh/pfichtner/usb-traffic-light-mqtt-bridge)

```
MQTT Broker ──► usb-traffic-light-mqtt-bridge ──► USB Ampel
```

## Architecture

```
                   ┌──────────────────────┐
                   │    MQTT Broker       │
                   │  (Mosquitto etc.)    │
                   └─────────┬────────────┘
                             │
                   subscribe │
                             │
                   ┌─────────┴────────────┐
                   │ usb-traffic-light-   │
                   │ mqtt-bridge          │
                   │                      │
                   │ ┌──────────────────┐ │
                   │ │ MQTTBridge       │ │
                   │ │  (paho-mqtt)     │ │
                   │ └───────┬──────────┘ │
                   │         │            │
                   │ ┌───────▼──────────┐ │
                   │ │ TrafficLight     │ │
                   │ │  (ABC)           │ │
                   │ └───────┬──────────┘ │
                   │         │            │
                   │ ┌───────▼──────────┐ │
                   │ │ ClewareTraffic   │ │
                   │ │  Light (pyusb)   │ │
                   │ └──────────────────┘ │
                   └─────────┬────────────┘
                             │
                             │ USB HID
                             ▼
                   ┌─────────┴────────────┐
                   │  USB Ampel           │
                   └──────────────────────┘
```

## Installation

### With pip

```bash
pip install -e .
```

### With Docker

```bash
docker compose build
docker compose up -d
```

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | `` | MQTT username |
| `MQTT_PASSWORD` | `` | MQTT password |
| `MQTT_TOPIC_PREFIX` | `cleware/ampel/` | Topic prefix for commands |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `DEVICE_ID` | `default` | Device ID for multiple traffic lights |
| `LIGHT_BACKEND` | `auto` | Hardware backend: `auto`, `cleware`, `mock` |

## MQTT Topics

### Commands (Subscribe)

| Topic | Payload | Description |
|---|---|---|
| `cleware/ampel/red` | `0` or `1` | Red: 0=off, 1=on |
| `cleware/ampel/yellow` | `0` or `1` | Yellow: 0=off, 1=on |
| `cleware/ampel/green` | `0` or `1` | Green: 0=off, 1=on |
| `cleware/ampel/pattern` | pattern string | Set the whole light at once (see below) |
| `cleware/ampel/pattern/anim/<name>` | JSON object | Start an animation, e.g. `blink`, `chase`, `bounce` (see below) |
| `cleware/ampel/pattern/tl/<country>/<name>` | JSON object | Start a traffic light animation, e.g. `german/red-to-green` (see below) |

Each LED is controlled independently. Switching one LED has no effect on the others.
Any command (per-color, `pattern`, or a new animation) cancels a running animation.

#### Pattern topic

`cleware/ampel/pattern` accepts a pattern string and sets the whole traffic
light atomically — LEDs in the pattern turn on, every other LED turns off.
This replaces multiple per-color publishes with one.

| Payload | Result |
|---|---|
| `all_off` | All LEDs off |
| `all_on` | All LEDs on |
| `red` | Only red on |
| `red+green` | Red and green on, yellow off |
| `red+yellow+green` | All LEDs on (same as `all_on`) |

Names are case-insensitive. Unknown patterns are logged and ignored.

#### Animated patterns

`cleware/ampel/pattern/anim/<name>` starts a server-side animation that keeps
running on the bridge even after the publishing client disconnects. `<name>`
selects one of three built-in animations:

| Name | Behavior |
|---|---|
| `blink` | Toggle the listed colors on/off together each step |
| `chase` | One color on at a time, cycling forward through `colors` order |
| `bounce` | One color on at a time, forward then backward (Knight-Rider style) |

The payload is an optional JSON object. Every field is optional; an empty
payload uses the defaults (blink all colors, infinite, 500 ms steps).

| Field | Type | Default | Range / Constraint | Description |
|---|---|---|---|---|
| `speed_ms` | integer | `500` | `>= 100` (clamped; a lower value logs a warning) | Milliseconds between animation steps. |
| `repeats` | integer | `0` | `>= 0` | Number of complete cycles. `0` means infinite — the animation runs until cancelled by another command. |
| `colors` | array of strings | all colors `["red","yellow","green"]` | subset of the color names; duplicates are collapsed | Ordered list of color names to animate. Order matters for `chase` and `bounce`; for `blink` it only selects which LEDs toggle. |

Field validation is non-fatal and matches the "invalid commands no-op" policy:
an empty `colors` array, a non-integer `speed_ms`/`repeats`, or an unknown
color name causes the whole payload to be rejected (any running animation is
left untouched). Unknown object fields are **ignored** for forward
compatibility. A `bool` is not accepted where an integer is expected.

Any subsequent command — a per-color message, a static `pattern` publish, or a
new animation — cancels the running animation. There is no explicit stop
topic. Animations are fire-and-forget: the bridge does not publish animation
status, and `pattern/anim/*` messages must not be retained.

The first animation frame renders immediately on publish; subsequent frames
are spaced `speed_ms` apart.

When a finite animation (`repeats > 0`) finishes on its own, the device is
restored to the state it had just before the animation started — a finite
animation is a transient overlay. If the animation is cancelled by another
command instead, the prior state is **not** restored; the interrupting
command's state takes over. Infinite animations (`repeats = 0`) never finish
on their own and therefore never restore.

Unknown animation names and invalid JSON payloads are logged and ignored, and
leave any running animation untouched. If a hardware error occurs mid-step,
the animation aborts immediately, the error is logged, and the device is left
in whatever state the failed step reached.

#### Traffic light animations

`cleware/ampel/pattern/tl/<country>/<name>` starts a **country-specific**
traffic light animation that uses regulation-based timings and phases. The
country currently supported is `german` (German StVO timings). Each animation
has fixed colors and per-phase durations; the optional JSON payload lets you
scale the timing and control whether the final LED state persists after a
finite animation completes.

| Animation (`german/…`) | Behavior | Default `hold_final` | Default `repeats` |
|---|---|---|---|
| `blink-yellow` | Blink yellow at 1 Hz (500 ms on / 500 ms off) | `false` | `0` (infinite) |
| `red-to-green` | Red (5 s) → red+yellow (1 s) → green (3 s) | `true` | `1` (one cycle) |
| `green-to-red` | Green (3 s) → yellow (3 s) → red (5 s) | `true` | `1` (one cycle) |

The payload is an optional JSON object:

| Field | Type | Default | Range / Constraint | Description |
|---|---|---|---|---|
| `speed_factor` | number | `1.0` | `0.1`–`10.0` | Scales all phase durations. `2.0` = twice as fast, `0.5` = half speed. Below `MIN_SPEED_MS` is clamped. |
| `repeats` | integer | (see table above) | `>= 0` | Number of complete cycles. `0` means infinite. Overrides the animation-specific default. |
| `hold_final` | boolean | (see table above) | — | When `true`, keep the last LED state after a finite animation completes instead of restoring the prior state. Overrides the animation-specific default. |

> **`hold_final`** — by default a finite animation restores the device state
> that existed *before* the animation started (a transient overlay). With
> `hold_final: true`, the last LED turned on in the sequence (e.g. green for
> `red-to-green`, red for `green-to-red`) stays on after the animation
> completes, so the traffic light remains in the post-transition state. This
> is useful to drive a real transition end-to-end. An explicitly cancelled
> animation never holds the final state — the interrupting command owns the
> new state.

The `speed_ms` and `colors` fields from the generic animated-patterns payload
are accepted but ignored by traffic light animations; durations and colors are
fixed by the country's traffic light regulations and encoded in the animation
data.

### Examples

Turn red on:
```bash
mosquitto_pub -h localhost -t "cleware/ampel/red" -m "1"
```

Turn green on (red stays on):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/green" -m "1"
```

Turn red off (green stays on):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/red" -m "0"
```

All off:
```bash
mosquitto_pub -h localhost -t "cleware/ampel/red" -m "0"
mosquitto_pub -h localhost -t "cleware/ampel/yellow" -m "0"
mosquitto_pub -h localhost -t "cleware/ampel/green" -m "0"
```

All off (one publish via the pattern topic):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern" -m "all_off"
```

Red + green on, yellow off (one publish):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern" -m "red+green"
```

Blink all LEDs, infinite, defaults (one publish):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/anim/blink" -m ""
```

Chase red → green, fast, 10 cycles:
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/anim/chase" \
  -m '{"speed_ms":250,"repeats":10,"colors":["red","green"]}'
```

Stop the running animation (any command cancels):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern" -m "all_off"
```

Blink yellow at 1 Hz (German traffic light caution signal), infinite:
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/tl/german/blink-yellow" -m ""
```

Red-to-green transition (hold green after completion):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/tl/german/red-to-green" -m ""
```

Green-to-red transition at 2× speed (hold red after completion):
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/tl/german/green-to-red" \
  -m '{"speed_factor":2.0}'
```

Red-to-green transition but restore the prior state on completion:
```bash
mosquitto_pub -h localhost -t "cleware/ampel/pattern/tl/german/red-to-green" \
  -m '{"hold_final":false}'
```

## Hardware

This bridge targets the **Cleware USB Ampel** (USB traffic light), a USB HID
device manufactured by Cleware GmbH. The project is independent of, and not
affiliated with, Cleware GmbH. "Cleware" is a trademark of Cleware GmbH, used
here only to identify the hardware this software works with.

Supported devices:

| Device | USB Vendor ID | USB Product ID |
|---|---|---|
| Cleware USB Ampel V1–V3 (original) | `0x0D50` | `0x0008` |
| Cleware USB Ampel V4 (2023+) | `0x0D50` | `0x0030` |

The hardware abstraction (`TrafficLight` ABC) allows adding support for other
USB traffic lights independently of Cleware.

## Hardware Setup

### udev Rule (Linux)

Without a udev rule, the service needs root privileges for USB access.

```bash
# /etc/udev/rules.d/99-cleware.rules
# V4 (2023+)
SUBSYSTEM=="usb", ATTR{idVendor}=="0d50", ATTR{idProduct}=="0008", MODE="666"

# V3 and older
SUBSYSTEM=="usb", ATTR{idVendor}=="0d50", ATTR{idProduct}=="0030", MODE="666"
```

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Docker with USB

```bash
docker compose up -d
```

The `docker-compose.yml` passes through `/dev/bus/usb` automatically.

## Development

### Install dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v -m integration

# All tests with coverage
pytest --cov=cleware_bridge --cov-report=term-missing -v
```

### Linting

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```

## Troubleshooting

### USB device not found

```bash
# Check USB devices
lsusb | grep 0d50

# Enable debug logs
LOG_LEVEL=DEBUG python -m cleware_bridge
```

### MQTT connection failed

The bridge automatically reconnects with exponential backoff (1s–60s).

### Mock mode for testing

```bash
LIGHT_BACKEND=mock MQTT_HOST=localhost python -m cleware_bridge
```

## Technical Details

- **Python:** 3.11+
- **MQTT:** paho-mqtt v2 (thread-based)
- **USB:** pyusb (HID over libusb)
- **Cleware USB IDs:** Vendor `0x0D50`, Products `0x0008` / `0x0030`
- **Error handling:** Exponential backoff for MQTT, reconnect on USB errors
