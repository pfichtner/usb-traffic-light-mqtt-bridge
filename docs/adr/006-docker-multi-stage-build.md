# ADR 006: Multi-Stage Docker Build with a Non-Root User

## Status

Accepted

## Context

The Docker container should:

- Run securely (non-root)
- Optionally pass through USB devices
- Be small
- Be suitable for production

## Decision

Use a multi-stage build with:

1. A builder stage for dependencies
2. A runtime stage with a non-root user
3. libusb for USB access

## Dockerfile

```dockerfile
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y libusb-1.0-0

FROM base AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

FROM base
RUN groupadd -r bridge && useradd -r -g bridge -d /home/bridge bridge
WORKDIR /home/bridge
COPY --from=builder /install /usr/local
USER bridge
ENTRYPOINT ["python", "-m", "cleware_bridge"]
```

## Rationale

- **Security**: A non-root user reduces the attack surface
- **Small size**: The multi-stage build removes build dependencies
- **USB access**: libusb is available, USB devices can be passed through
- **Maintainability**: Clear separation of build and runtime

## USB passthrough in Docker

```yaml
services:
  bridge:
    devices:
      - /dev/bus/usb:/dev/bus/usb
```

## Alternatives considered

- **Single-stage**: Larger image, bigger attack surface
- **Root user**: Security risk
- **alpine**: USB issues due to musl libc

## Consequences

- Secure deployment
- USB access works with device passthrough
- Image size ~150 MB