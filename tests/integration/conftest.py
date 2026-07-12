"""Integration test fixtures using real Mosquitto broker."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from cleware_bridge.config import BridgeConfig
    from cleware_bridge.traffic_light import MockTrafficLight

logger = logging.getLogger(__name__)


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    """Wait until a port is accepting connections."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.5)
    msg = f"Port {host}:{port} not available after {timeout}s"
    raise TimeoutError(msg)


class MosquittoBroker:
    """Manages a Mosquitto Docker container for integration tests."""

    def __init__(self, host: str = "localhost", port: int = 11883) -> None:
        self.host = host
        self.port = port
        self.container_id: str | None = None

    def start(self) -> None:
        """Start Mosquitto container."""
        subprocess.run(
            ["docker", "rm", "-f", "mosquitto-test"],
            capture_output=True,
            check=False,
        )

        # mosquitto 2.x rejects "/dev/null" as a config file, so generate a
        # minimal config inside the container (avoiding host bind mounts,
        # which don't work when the Docker daemon runs on a host that does
        # not share this filesystem).
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "mosquitto-test",
                "-p",
                f"{self.port}:1883",
                "eclipse-mosquitto:2",
                "sh",
                "-c",
                "printf 'allow_anonymous true\\nlistener 1883\\n' "
                "> /tmp/mosquitto.conf && exec mosquitto -c /tmp/mosquitto.conf -v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.container_id = result.stdout.strip()
        _wait_for_port(self.host, self.port)

    def stop(self) -> None:
        """Stop and remove Mosquitto container."""
        subprocess.run(
            ["docker", "rm", "-f", "mosquitto-test"],
            capture_output=True,
            check=False,
        )
        self.container_id = None


class DockerComposeStack:
    """Manages a full docker compose stack for end-to-end container tests."""

    def __init__(self, compose_file: str, project_name: str = "cleware-test") -> None:
        self.compose_file = compose_file
        self.project_name = project_name
        self._compose_args = [
            "docker",
            "compose",
            "-f",
            compose_file,
            "-p",
            project_name,
        ]

    def start(self, service: str = "bridge") -> str:
        """Start the stack and return bridge container name."""
        subprocess.run(
            [*self._compose_args, "up", "-d", "--build", service],
            capture_output=True,
            text=True,
            check=True,
        )
        container = f"{self.project_name}-{service}-1"
        return container

    def stop(self) -> None:
        """Stop and remove the stack."""
        subprocess.run(
            [*self._compose_args, "down", "--volumes", "--remove-orphans"],
            capture_output=True,
            text=True,
            check=False,
        )

    def logs(self, container: str) -> str:
        """Get logs from a container."""
        result = subprocess.run(
            ["docker", "logs", container],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout + result.stderr


@pytest.fixture(scope="module")
def mosquitto() -> MosquittoBroker:  # type: ignore[misc]
    """Module-scoped Mosquitto broker fixture."""
    broker = MosquittoBroker()
    broker.start()
    yield broker
    broker.stop()


@pytest.fixture()
def bridge_config(mosquitto: MosquittoBroker) -> BridgeConfig:  # type: ignore[misc]
    """Create a BridgeConfig pointing to the test broker."""
    from cleware_bridge.config import BridgeConfig

    return BridgeConfig(
        mqtt_host=mosquitto.host,
        mqtt_port=mosquitto.port,
        mqtt_topic_prefix="test/ampel/",
        log_level="DEBUG",
        device_id="test",
    )


@pytest.fixture()
def mock_light() -> MockTrafficLight:  # type: ignore[misc]
    """Create a fresh MockTrafficLight."""
    from cleware_bridge.traffic_light import MockTrafficLight

    return MockTrafficLight()


@pytest.fixture(scope="module")
def docker_compose_stack() -> DockerComposeStack:
    """Module-scoped docker compose stack for end-to-end tests."""
    compose_file = os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.test.yml")
    stack = DockerComposeStack(compose_file)
    yield stack
    stack.stop()
