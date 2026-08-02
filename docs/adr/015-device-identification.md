# ADR 015: USB Device Identification for Multiple Cleware Traffic Lights

## Status

Accepted

## Context

The bridge targets the Cleware USB traffic light. Originally it used
`usb.core.find(...)` which returns only the first matching device. The
`DEVICE_ID` configuration value was accepted but ignored, making it impossible
to run multiple identical traffic lights on the same host.

We needed a deterministic identification strategy that:

1. Actually uses `DEVICE_ID` to select a device.
2. Works when multiple identical devices are connected.
3. Survives USB reconnects and reboots.
4. Produces clear errors when the configuration is ambiguous or missing.
5. Can be tested without physical hardware.

## Decision

Enumerate all Cleware devices with `usb.core.find(idVendor=0x0D50,
find_all=True)`, then select the desired device using stable identifiers.

### Identifier hierarchy

1. **USB serial number** — used as the primary identifier when it is present
   and unique across all detected devices.
2. **USB topology (`bus:port_numbers`)** — used as the fallback identifier
   when a serial number is missing or duplicated.
3. **USB device address** — explicitly avoided as a primary identifier because
   it is transient and changes after a reconnect.

### Selection rules

- `DEVICE_ID=default` selects the only connected device. If multiple devices
  are present, the bridge raises a clear error and lists the available
  identifiers.
- `DEVICE_ID=<serial>` selects the device with that serial number. If multiple
  devices share the same serial, the bridge raises an ambiguity error and asks
  the user to specify a port path.
- `DEVICE_ID=<bus>:<port>` selects the device at the given physical USB port.
- If the configured identifier cannot be found, the bridge raises a clear
  error and lists detected devices.

### Resource cleanup

Unselected enumerated devices are released with
`usb.util.dispose_resources(...)` so the bridge does not hold unnecessary USB
handles.

## Rationale

- **Determinism**: Physical port topology is stable as long as the device stays
  plugged into the same port. Serial numbers are even more stable when unique.
- **Hardware independence**: The device address is convenient but changes on
  reconnect, so it would silently switch devices after a restart.
- **User experience**: The error messages emitted when multiple devices are
  detected serve as the discovery mechanism, removing the need for a separate
  device-listing tool.
- **Testability**: The PyUSB layer is mocked in unit tests, allowing
  comprehensive coverage of one device, multiple devices, duplicate serials,
  ambiguous configuration, and missing devices.

## Alternatives considered

- **Use only serial numbers**: Fails when Cleware devices share the same
  serial (a known issue with some units).
- **Use only USB device address**: Simple but non-deterministic after reconnect.
- **Require a separate discovery tool**: Adds friction; the error-message
  approach is self-documenting.
- **Use libusb `port_numbers` exclusively**: Stable but ignores the useful
  serial number when it is unique.

## Consequences

- `DEVICE_ID` is now meaningful and required when multiple traffic lights are
  connected.
- Backwards compatibility is preserved for single-device setups
  (`DEVICE_ID=default`).
- Error messages guide the user toward a valid configuration.
- Unit tests must enumerate mock devices instead of patching a single
  `usb.core.find(...)` call.

## Related

- ADR 002: pyusb as the Direct USB Library
- ADR 004: Hardware Abstraction Using the ABC Pattern
- Issue MQTTA-1: Support Multiple Cleware USB Traffic Lights
