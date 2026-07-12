# ADR 001: Python as the Implementation Language

## Status

Accepted

## Context

The USB traffic light MQTT bridge is intended to run as a production-ready service on Linux servers. The language must:

- Offer good MQTT library support
- Enable USB hardware access
- Be easy to test
- Be suitable for Docker

## Decision

Use Python 3.11+ as the implementation language.

## Rationale

- **paho-mqtt**: MQTT library with excellent Python support (v2 with asyncio support)
- **pyusb**: USB hardware access via libusb, well tested
- **pytest**: Industry standard for Python tests with coverage support
- **ruff/mypy**: Modern linting and type-checking tools
- **Docker**: Official Python images, well maintained

## Alternatives considered

- **Go**: Higher performance, but higher entry cost for USB access (no established library)
- **Rust**: Higher performance, but higher complexity for this use case
- **Node.js**: No good USB support

## Consequences

- A Python runtime is required (~100 MB Docker image)
- Good testability through mocking
- Easy to extend