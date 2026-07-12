FROM python:3.14-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

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
