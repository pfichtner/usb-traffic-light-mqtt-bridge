# ADR 012: Pattern Convenience Topic

## Status

Accepted

## Context

ADR 008 defines per-color topics (`{prefix}/red`, `{prefix}/yellow`,
`{prefix}/green`), each controlled independently with an integer payload.
Switching several LEDs at once therefore requires multiple `PUBLISH` packets:

```bash
mosquitto_pub -t "cleware/ampel/red"   -m "1"
mosquitto_pub -t "cleware/ampel/green" -m "1"
mosquitto_pub -t "cleware/ampel/yellow" -m "0"
```

For dashboards, scripts, and automations that frequently set the whole
traffic light at once, this is tedious and non-atomic — an observer can see
intermediate states between the publishes.

ADR 008 explicitly rejected a *single command topic with a JSON payload*.
This ADR introduces a convenience topic that addresses the same use case
without adopting an arbitrary JSON schema or weakening the per-color topics.

## Decision

Add an additive, optional convenience topic:

```
{prefix}/pattern   e.g. cleware/ampel/pattern
```

The payload is a **pattern string** (not an integer). It is parsed by the new
`parse_pattern()` helper in `models.py`:

| Payload | Result |
|---|---|
| `all_off` | All LEDs OFF |
| `all_on` | All LEDs ON |
| `red`, `yellow`, `green` | Only that LED ON, all others OFF |
| `red+green`, `red+yellow+green`, … | The listed LEDs ON, all others OFF |

Parsing rules:

- Case-insensitive, surrounding whitespace trimmed.
- Colors in a `+`-joined list are resolved via the existing `Color.from_name`.
- Unknown names or colors, empty payloads, and malformed combinations
  (e.g. `red+`, `+red`, `red++green`) return `None` and the bridge logs a
  warning and leaves the device state unchanged.

Semantics:

- Applying a pattern sets the **whole** traffic light atomically: every LED
  in the parsed set is turned ON; every other LED is turned OFF. This is the
  convenience win — one publish replaces N.
- Per-color topics (ADR 008) remain unchanged and work alongside the pattern
  topic. A subsequent `cleware/ampel/red 0` overrides the pattern for the red
  LED; a subsequent pattern publish overrides the per-color state for all
  LEDs.
- The bridge's internal `_active_leds` set is rebuilt from the pattern after
  a successful apply, so state stays consistent with both code paths.

## Reserved namespace

The `pattern` suffix is reserved for pattern-related subtopics. The wildcard
subscription from ADR 011 (`{prefix}/#`) already receives them.

The following namespace is **reserved for future animated patterns** but not
implemented in this ADR:

```
{prefix}pattern/anim/<name>
```

Messages to such subtopics are received by the bridge and ignored today
(the suffix `pattern/anim/<name>` neither matches `TOPIC_COLOR_MAP` nor
equals `pattern` and is therefore filtered out by `_on_message`). Animated
patterns require a scheduler, cancellation semantics on new commands, and
additional tests, and will be covered by a separate ADR.

## Implementation

```python
# models.py
NAMED_PATTERNS: dict[str, frozenset[Color]] = {
    "all_off": frozenset(),
    "all_on": frozenset(Color),
}

def parse_pattern(payload: str) -> frozenset[Color] | None:
    normalized = payload.strip().lower()
    if not normalized:
        return None
    if normalized in NAMED_PATTERNS:
        return NAMED_PATTERNS[normalized]
    parts = [p.strip() for p in normalized.split("+")]
    if not all(parts):
        return None
    colors: set[Color] = set()
    for part in parts:
        try:
            colors.add(Color.from_name(part))
        except ValueError:
            return None
    return frozenset(colors)
```

```python
# mqtt_client.py — inside _on_message, after computing the suffix
if suffix == PATTERN_TOPIC_SUFFIX:
    self._apply_pattern(payload_str)
    return
# ... existing per-color path unchanged
```

`_apply_pattern` iterates over every `Color`, calls `set_led(... ON/OFF)`
accordingly, and reassigns `self._active_leds = set(pattern)`. Hardware
errors during the loop are logged and abort the apply, mirroring the existing
per-color error handling.

## Rationale

- **Convenience**: One publish replaces N when setting the whole light.
- **Atomicity**: The bridge applies the full set in a tight loop so external
  observers see a single transition.
- **Additive**: ADR 008 per-color topics and the existing HA integration are
  untouched; the pattern topic is purely opt-in.
- **No JSON schema**: Avoids reopening the JSON-payload decision from ADR 008.
  The grammar is a tiny, easy-to-type string.
- **Forward-compatible**: Reserved `pattern/anim/*` namespace means animated
  patterns can be added later without restructuring the topic tree.

## Alternatives considered

- **Single JSON command topic** (`{prefix}set` with `{"red":1,"yellow":0,...}`):
  Rejected again — see ADR 008. The pattern topic covers the multi-LED use
  case with a far smaller and HA-friendly surface.
- **Additive-only semantics** (pattern turns LEDs ON, never OFF): Less
  predictable — `red+green` would leave yellow in whatever state it was in.
  Atomic semantics match the "set the light to X" intent of the feature.
- **A growing registry of named patterns** (`stop`, `go`, `caution`, …):
  Deferred. The `+`-joined form already expresses any combination; named
  shortcuts can be added to `NAMED_PATTERNS` later without a schema change.
- **Animated patterns in this ADR**: Out of scope. Requires timers,
  cancellation, and additional tests; tracked via the reserved
  `pattern/anim/*` namespace.

## Consequences

- ADR 008 per-color topics remain valid and unchanged.
- ADR 011 wildcard subscription requires no changes — `pattern` is below the
  existing `{prefix}/#` filter.
- `models.py` gains `parse_pattern`, `NAMED_PATTERNS`, and
  `PATTERN_TOPIC_SUFFIX`; `mqtt_client.py` gains a `_apply_pattern` branch.
- The `pattern` and `pattern/anim/*` suffixes are now reserved and must not
  be reused as color names.
- New unit tests cover pattern parsing and dispatch, including invalid
  payloads, the per-color/pattern interaction, and the reserved-namespace
  filtering.
- Animated patterns are deferred and will require a separate ADR.