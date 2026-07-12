# ADR 002: pyusb as the Direct USB Library

## Status

Accepted

## Context

The bridge must communicate with the USB traffic light. There are two options:

1. Use the existing Python library `cleware-traffic-light` (PyPI) as a dependency
2. Direct implementation on top of `pyusb`

## Decision

Direct implementation on top of `pyusb` instead of relying on the external `cleware-traffic-light` library.

## Rationale

- **Full control**: A custom implementation gives full control over error handling and hardware access
- **No external dependency**: Fewer dependencies = smaller attack surface for security issues
- **Maintainability**: The external library is not actively maintained (last update 2024)
- **Flexibility**: A custom implementation can be adapted to specific requirements

## Technical details

- **USB Vendor ID**: `0x0D50`
- **Product IDs**: `0x0008` (original V1–V3), `0x0030` (V4 Switch)
- **Endpoint**: `0x02`
- **Interface**: `0`

## Alternatives considered

- **cleware-traffic-light**: External dependency, limited maintenance, less control
- **subprocess wrapper**: Too slow, difficult error handling

## Consequences

- More in-house code to maintain
- Full control over USB communication
- Better integration with custom error-handling strategies