# ADR 005: Configuration via Environment Variables

## Status

Accepted

## Context

The bridge must run in different environments (local, Docker, CI). Configuration must:

- Be suitable for Docker deployments
- Be flexible for local development
- Not require configuration files

## Decision

Configure everything via environment variables with sensible defaults.

## Variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | `` | MQTT username |
| `MQTT_PASSWORD` | `` | MQTT password |
| `MQTT_TOPIC_PREFIX` | `cleware/ampel/` | Topic prefix |
| `MQTT_TOPIC_STATE` | (auto) | State topic |
| `LOG_LEVEL` | `INFO` | Log level |
| `DEVICE_ID` | `default` | Device ID |
| `LIGHT_BACKEND` | `auto` | Hardware backend |

## Rationale

- **Docker-compatible**: `environment:` in docker-compose.yml
- **Twelve-Factor App**: Recommended approach for cloud-native applications
- **Simplicity**: No configuration files needed
- **Security**: Secrets can come from secret-management systems

## Implementation

```python
@dataclass(frozen=True)
class BridgeConfig:
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    # ...

    @classmethod
    def from_env(cls) -> BridgeConfig:
        return cls(
            mqtt_host=os.environ.get("MQTT_HOST", "localhost"),
            # ...
        )
```

## Alternatives considered

- **Configuration files**: More complexity, harder in Docker
- **Command-line arguments**: Not ideal for Docker, more overhead

## Consequences

- Simple configuration across all environments
- No file management required
- Secrets can be passed securely via environment variables