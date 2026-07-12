"""End-to-end integration tests running the full Docker Compose stack."""

from __future__ import annotations

import subprocess
import time

import paho.mqtt.client as mqtt
import pytest

from tests.integration.conftest import DockerComposeStack

pytestmark = pytest.mark.integration


def _wait_for_log(container: str, needle: str, timeout: float = 30.0) -> str:
    """Wait until a container log contains the given string."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        result = subprocess.run(
            ["docker", "logs", container],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        if needle in output:
            return output
        time.sleep(1)
    msg = f"Container {container} log did not contain {needle!r} after {timeout}s"
    raise TimeoutError(msg)


def _publish_command(
    command_topic: str,
    command_payload: str,
    host: str = "localhost",
    port: int = 11883,
) -> None:
    """Publish a command to the MQTT broker."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
    client.connect(host, port)
    client.loop_start()
    time.sleep(0.2)
    client.publish(command_topic, command_payload)
    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()


class TestDockerComposeStack:
    """Tests that spin up the full Docker Compose stack and verify it works."""

    def test_connect_and_stay_connected(self, docker_compose_stack: DockerComposeStack) -> None:
        """Verify the bridge connects to MQTT and stays connected for 15s."""
        container = docker_compose_stack.start()
        _wait_for_log(container, "MQTT connected", timeout=30)
        assert "Subscribed to test/ampel/#" in _wait_for_log(
            container, "Subscribed to test/ampel/#"
        )

        time.sleep(15)

        logs = docker_compose_stack.logs(container)
        assert "disconnected unexpectedly" not in logs, (
            f"Bridge disconnected during 15s window. Logs:\n{logs}"
        )

    @pytest.mark.parametrize(
        ("color", "payload"),
        [
            ("red", "1"),
            ("green", "1"),
            ("yellow", "1"),
        ],
    )
    def test_color_on(
        self,
        docker_compose_stack: DockerComposeStack,
        color: str,
        payload: str,
    ) -> None:
        """Publish a color command and verify the mock light responds via logs."""
        container = docker_compose_stack.start()
        _wait_for_log(container, "MQTT connected", timeout=30)

        _publish_command(f"test/ampel/{color}", payload)

        logs = docker_compose_stack.logs(container)
        assert f"LED {color} ON" in logs

    def test_off_command(self, docker_compose_stack: DockerComposeStack) -> None:
        """Sending 0 turns the light off."""
        container = docker_compose_stack.start()
        _wait_for_log(container, "MQTT connected", timeout=30)

        _publish_command("test/ampel/green", "1")
        _publish_command("test/ampel/green", "0")

        logs = docker_compose_stack.logs(container)
        assert "LED green OFF" in logs

    def test_multiple_leds_independent(self, docker_compose_stack: DockerComposeStack) -> None:
        """Sending red=1 then green=1 should keep both on."""
        container = docker_compose_stack.start()
        _wait_for_log(container, "MQTT connected", timeout=30)

        _publish_command("test/ampel/red", "1")
        _publish_command("test/ampel/green", "1")

        logs = docker_compose_stack.logs(container)
        assert "LED red ON" in logs
        assert "LED green ON" in logs

    def test_invalid_payload(self, docker_compose_stack: DockerComposeStack) -> None:
        """Invalid payload does not change state."""
        container = docker_compose_stack.start()
        _wait_for_log(container, "MQTT connected", timeout=30)

        _publish_command("test/ampel/green", "invalid")

        logs = docker_compose_stack.logs(container)
        assert "Invalid brightness payload" in logs
