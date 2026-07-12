# USB Traffic Light MQTT Bridge

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

Each LED is controlled independently. Switching one LED has no effect on the others.

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
