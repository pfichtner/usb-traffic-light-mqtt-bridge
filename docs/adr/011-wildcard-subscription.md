# ADR 011: Wildcard Subscription Instead of Individual Per-Color Subscriptions

## Status

Accepted

## Context

Until now the bridge subscribed to three separate topics (`{prefix}/red`, `{prefix}/green`, `{prefix}/yellow`) on the MQTT broker (see ADR 008). All three topics share the same root prefix and differ only in the last segment (the color).

Three separate `subscribe` calls mean:

- Three SUBSCRIBE packets on connection setup
- Three separate subscription entries in the broker
- On reconnect, the three subscriptions must be registered again

## Decision

Instead of three individual subscriptions, subscribe to a single wildcard topic:

```
{prefix}/#
```

So the bridge now subscribes only to `cleware/ampel/#` (or the configured prefix) instead of the three concrete topics.

## Implementation

```python
# Before:
self._subscribe_topics = [
    f"{prefix}/red",
    f"{prefix}/green",
    f"{prefix}/yellow",
]

# After:
self._subscribe_topics = [f"{prefix}/#"]
```

In `_on_connect` only a single `client.subscribe()` call is made.

Message processing in `_on_message` remains unchanged: it strips the prefix, checks the suffix against `TOPIC_COLOR_MAP`, and ignores unknown suffixes (e.g. `cleware/ampel/blue`). Unknown subtopics are therefore filtered out automatically.

## Rationale

- **Less broker load**: One SUBSCRIBE packet instead of three
- **Simpler code**: No loop, no hard-coded color set in the subscription logic
- **Automatic extensibility**: New colors below the prefix are covered by the wildcard automatically (as long as they are added to `TOPIC_COLOR_MAP`)
- **Structure preserved**: The published topics remain unchanged (`{prefix}/red`, `{prefix}/green`, `{prefix}/yellow`); only the subscription strategy changes. ADR 008 remains valid for the topic structure.

## Alternatives considered

- **Keep three separate subscriptions**: More overhead, no advantages for this flat hierarchy
- **Shared subscriptions (`$share/...`)**: Only relevant with multiple bridge instances; not required at the moment
- **Single command topic with a JSON payload**: Already rejected in ADR 008

## Consequences

- The bridge receives messages of all subtopics below `{prefix}/` (e.g. also `{prefix}/status`), but ignores unknown suffixes
- `TOPIC_COLOR_MAP` remains the central control for valid color topics
- ADR 008 (topic structure) remains valid; only the subscription strategy is amended here
- For many new colors, only the `Color` enum and `TOPIC_COLOR_MAP` need to be extended, not the subscription logic