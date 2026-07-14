# ADR 013: Animated Patterns

## Status

Accepted

## Context

ADR 012 introduced the `{prefix}/pattern` topic for atomic, whole-device
LED control and reserved the `{prefix}/pattern/anim/<name>` namespace for
future animated patterns. This ADR defines that namespace.

Static patterns (ADR 012) express a single, unchanging LED state. Many
real-world use cases are dynamic: a traffic light should blink while a
build is running, chase through colors as a startup self-test, or bounce
to attract attention. Today this requires a client-side loop of repeated
`PUBLISH` calls, which:

- Burdens the broker with high message volume.
- Competes with other clients for latency and ordering.
- Breaks when the publishing client disconnects (e.g., a browser tab
  closing stops the blinking).

A server-side animation that lives inside the bridge keeps running
independently of the publisher and lets a single MQTT message drive a
long-running visual sequence.

ADR 012 explicitly listed the missing pieces: a scheduler, cancellation
semantics on new commands, and additional tests. This ADR addresses each.

## Decision

### Topic structure

```
{prefix}/pattern/anim/<name>   e.g. cleware/ampel/pattern/anim/blink
```

`<name>` selects one of a **fixed, built-in set** of animation types
(see below). Unknown names are ignored with a warning, matching the
"last command wins, invalid commands no-op" behavior of ADR 012.

### Fixed animation catalog

| Name | Behavior |
|---|---|
| `blink` | Toggle the listed colors on/off together at each interval. |
| `chase` | One color on at a time, cycling forward in `colors` order, then repeating. |
| `bounce` | One color on at a time, cycling forward then backward (Knight-Rider style). |

All three operate on discrete ON/OFF states only — the hardware has no
PWM support (see ADR 004). `fade` and `pulse` are out of scope for the
same reason.

### Payload format

The payload is a **JSON object** with the following fields. Every field
is optional; an empty payload uses the defaults.

| Field | Type | Default | Range | Description |
|---|---|---|---|---|
| `speed_ms` | integer | `500` | `>= 100` | Milliseconds between animation steps. Values below `100` are clamped to `100` and a warning is logged. |
| `repeats` | integer | `0` | `>= 0` | Number of complete cycles. `0` means infinite — the animation runs until cancelled by another command. |
| `colors` | array of strings | all colors | subset of `["red","yellow","green"]` | Ordered list of color names to animate. Order matters for `chase` and `bounce`. Duplicates are collapsed. |

Examples:

```bash
# Blink all LEDs, infinite, 500ms (all defaults)
mosquitto_pub -t "cleware/ampel/pattern/anim/blink" -m ""

# Chase through red and green only, fast, 10 cycles
mosquitto_pub -t "cleware/ampel/pattern/anim/chase" \
  -m '{"speed_ms":250,"repeats":10,"colors":["red","green"]}'

# Bounce all LEDs, slow, infinite
mosquitto_pub -t "cleware/ampel/pattern/anim/bounce" \
  -m '{"speed_ms":1000}'
```

### Why JSON here (reopening ADR 008's decision)

ADR 008 rejected a JSON command topic for the per-color topics, and ADR
012 kept a small-string grammar (`red+green`) for this reason. A single
LED needs only one value; a static pattern needs only a set. Neither
requires structured data.

Animations are different: they combine an interval (`speed_ms`), a
repeat count (`repeats`), and an **ordered** color list (`colors`).
Encoding three structured fields — including an ordered array and a
numeric range — in a positional or key=value string would reinvent JSON
ad hoc, poorly. The options weighed:

- **key=value**: `speed_ms=250,repeats=10,colors=red,green` — loses the
  distinction between `colors=["red","green"]` (ordered, two elements)
  and a lone scalar. Array parsing becomes a special case.
- **positional**: `250 10 red green` — fragile, no self-documenting
  fields, impossible to omit middle fields.
- **JSON**: structured, widely understood, supported by every MQTT
  client library and HA. A 40-byte payload is negligible.

JSON is therefore adopted **for the `pattern/anim/*` topics only**. The
per-color topics (ADR 008) and the static pattern topic (ADR 012) keep
their existing integer and string grammars. This is a scoped exception,
not a general reversal of ADR 008.

### Semantics

- **Starting**: A publish to a valid `{prefix}/pattern/anim/<name>`
  topic starts that animation. The first step runs immediately.
- **Cancellation**: Any incoming command — a per-color message (ADR
  008), a static pattern (ADR 012), or a new anim message — cancels the
  running animation **before** the new command is processed. There is
  no explicit stop topic; the "any command cancels" rule is sufficient.
- **Completion**: When `repeats > 0` and the count is reached, the
  animation stops and the device is **restored to the state it had just
  before the animation started**. The internal `_active_leds` set is set
  to that saved snapshot, so a finite animation acts as a transient
  overlay: once it is over, the traffic light returns to what it was
  showing. The bridge records the base state in `_anim_base_state`; when
  no animation is running this is a snapshot of `_active_leds` taken
  under `_hw_lock` at dispatch time, before the first frame renders.
- **Cancellation vs. completion**: A cancelled (interrupted) animation
  **never** restores the prior state — the interrupting command owns the
  new state. Only natural completion of a finite animation restores.
  The worker re-checks the stop event under `_hw_lock` before restoring,
  so an interrupt that arrives at the moment of completion still wins
  and the restore is skipped.
- **Interrupted animation chains**: When a new animation interrupts a
  running one, the interrupting animation must restore the **same base
  state** the interrupted animation would have — i.e. the device state
  that existed before the *first* animation in the chain began — rather
  than the mid-animation frame it is overwriting. The dispatcher
  therefore snapshots the live LEDs only when no animation is running;
  when interrupting, it reuses the running animation's `_anim_base_state`
  as its own restore target. Without this, a finite animation that
  interrupts another would restore the interrupted animation's transient
  frame instead of the original device state (bug fix: the base state
  must be carried across an interrupted chain so consecutive animations
  act as a single transient overlay over the pre-chain state).
- **Infinite animations**: `repeats = 0` (and the default) run until
  cancelled by another command. They never complete on their own and
  therefore never restore.
- **Fire-and-forget**: The bridge does **not** publish animation status
  to any state topic. Clients that need to know whether an animation is
  running must track the commands they have sent. Adding a state topic
  remains possible later without changing this ADR (see Alternatives).
- **Retained messages**: `pattern/anim/*` topics are **not** retained.
  Animations are transient commands, not device state. A late-joining
  subscriber should not cause a stale animation to restart. Senders
  must not set the retained flag on anim messages.

### Concurrency model

The bridge runs a single-threaded MQTT loop (`loop_forever()`), but an
animation needs a **background timing thread**. To keep hardware access
safe:

- A `threading.Lock` (`_hw_lock`) guards every `set_led` call and every
  mutation of `_active_leds`. Both the MQTT callback path and the
  animation worker acquire this lock.
- The animation runs on a dedicated worker thread, one at a time.
  Starting a new animation while one is running first signals the
  running thread to stop (via a `threading.Event`), joins it, then
  starts the new worker.
- `_on_message` acquires `_hw_lock` before dispatching to the per-color
  or static-pattern path, so an in-flight animation step cannot
  interleave with a direct command.

This guarantees that hardware commands are serialized and that
cancellation is race-free.

### Safety limits

- **Minimum interval**: `speed_ms` below `100` is clamped to `100` to
  prevent USB thrashing, with a warning logged.
- **Hardware error mid-animation**: If `set_led` raises during a step,
  the animation aborts immediately, the error is logged, and the device
  is left in whatever state the failed step reached — mirroring the
  ADR 012 pattern-apply error handling. The worker thread exits.
- **Bridge shutdown**: `stop()` cancels the running animation and joins
  the worker thread before disconnecting the client.

## Implementation

```python
# models.py
ANIM_TOPIC_PREFIX: str = "pattern/anim/"

# Fixed built-in animation names.
ANIMATIONS: frozenset[str] = frozenset({"blink", "chase", "bounce"})

# Default animation parameters.
DEFAULT_SPEED_MS: int = 500
MIN_SPEED_MS: int = 100
DEFAULT_REPEATS: int = 0  # 0 = infinite
DEFAULT_COLORS: tuple[Color, ...] = (Color.RED, Color.YELLOW, Color.GREEN)


@dataclass(frozen=True)
class AnimParams:
    """Validated parameters for an animation."""

    speed_ms: int = DEFAULT_SPEED_MS
    repeats: int = DEFAULT_REPEATS
    colors: tuple[Color, ...] = DEFAULT_COLORS

    @property
    def infinite(self) -> bool:
        return self.repeats == 0


def parse_anim_params(
    animation: str, payload: str
) -> AnimParams | None:
    """Parse a JSON payload into AnimParams for the given animation.

    Returns None on invalid JSON, unknown fields, or out-of-range values,
    matching the non-fatal policy of ADR 012.
    """
    colors = payload.strip()
    if not colors:
        return AnimParams()
    try:
        data = json.loads(colors)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if "speed_ms" in data:
        value = data["speed_ms"]
        if not isinstance(value, int) or value < MIN_SPEED_MS:
            if isinstance(value, int) and value < MIN_SPEED_MS:
                logger.warning(  # noqa: G004
                    "speed_ms %d below minimum %d, clamping", value, MIN_SPEED_MS
                )
                value = MIN_SPEED_MS
            else:
                return None
        # ... assemble AnimParams with clamped/value-checked fields
    # ... repeats and colors validation analogous
    return AnimParams(speed_ms=value, ...)
```

```python
# mqtt_client.py — inside _on_message, before the per-color path
if suffix.startswith(ANIM_TOPIC_PREFIX):
    anim_name = suffix[len(ANIM_TOPIC_PREFIX):]
    self._start_animation(anim_name, payload_str)
    return
```

```python
# mqtt_client.py — animation worker
def _start_animation(self, name: str, payload: str) -> None:
    if name not in ANIMATIONS:
        logger.warning("Unknown animation: %r", name)
        return
    params = parse_anim_params(name, payload)
    if params is None:
        logger.warning("Invalid animation payload for %r: %r", name, payload)
        return
    self._cancel_animation()
    with self._hw_lock:
        previous_state = frozenset(self._active_leds)
    self._anim_stop = threading.Event()
    self._anim_thread = threading.Thread(
        target=self._run_animation,
        args=(name, params, previous_state, self._anim_stop),
        daemon=True,
    )
    self._anim_thread.start()

def _cancel_animation(self) -> None:
    if self._anim_stop is not None:
        self._anim_stop.set()
    if self._anim_thread is not None and self._anim_thread.is_alive():
        self._anim_thread.join(timeout=2.0)
    self._anim_stop = None
    self._anim_thread = None

def _run_animation(
    self, name: str, params: AnimParams,
    previous_state: frozenset[Color], stop: threading.Event,
) -> None:
    cycle = 0
    while params.infinite or cycle < params.repeats:
        for step in self._animation_steps(name, params):
            if stop.is_set():
                return  # cancelled — do not restore
            with self._hw_lock:
                try:
                    self._render_step(step)
                except Exception as exc:
                    logger.error("Animation %r aborted: %s", name, exc)
                    return
            if stop.wait(params.speed_ms):
                return  # cancelled — do not restore
        cycle += 1
    # Natural completion of a finite animation: restore the snapshot.
    with self._hw_lock:
        if not stop.is_set():
            self._render_step(previous_state)
```

`_animation_steps` is an iterator yielding `frozenset[Color]` frames per
the animation type. `_render_step` sets LEDs to match a frame and updates
`_active_leds` under `_hw_lock`.

The per-color and static-pattern paths in `_on_message` acquire
`_hw_lock` and call `_cancel_animation()` before applying their
command, so cancellation always precedes the new state.

## Rationale

- **Server-side persistence**: An animation sent once keeps running
  even if the publishing client disconnects or restarts.
- **Broker relief**: One message drives thousands of state transitions
  instead of thousands of messages.
- **Fixed built-in set**: A small, predictable catalog is easy to
  document, test, and expose to Home Assistant. User-extensibility can
  come later (see Alternatives) without restructuring topics.
- **JSON is scoped**: Only `pattern/anim/*` uses JSON; the per-color
  and static pattern topics keep their existing grammars. ADR 008's
  core decision (simple integer per-LED topics) is untouched.
- **Implicit cancellation**: "Any command cancels" is the least
  surprising rule — it reuses the "last command wins" semantics already
  established by ADR 012 and avoids a separate stop topic that clients
  must remember to call.
- **Fire-and-forget simplicity**: Omitting a state topic keeps the
  bridge's publish path empty (matching ADR 012's design) and avoids
  generating a high-volume stream of status messages from the
  animation loop. State can be derived on the client side from the
  command history.
- **Infinite by default**: The dominant use case for a traffic light is
  "blink until something changes." Making `repeats=0` the default means
  the simple `mosquitto_pub -m ""` invocation starts an infinite
  blink, which is almost always what the user wants.

## Alternatives considered

- **key=value string payload** (e.g. `speed_ms=250,repeats=10,colors=red,green`):
  Rejected. Structured fields with an ordered array and numeric ranges
  are exactly what JSON solves; a key=value dialect would be a bespoke,
  less-capable reimplementation. See "Why JSON here" above.
- **Positional string** (`250 10 red green`): Rejected. Fragile, no
  field names, impossible to omit middle fields safely.
- **Extensible animation registry** (user-defined animations via config
  file or additional topics): Deferred. A fixed built-in set is
  simpler to test and expose to HA first. New built-ins can be added to
  `ANIMATIONS` without a schema change; user-defined animations can be
  revisited after real-world usage reveals which custom patterns are
  actually needed.
- **Explicit `pattern/anim/stop` topic**: Rejected. The "any command
  cancels" rule already covers every stop use case (publish `all_off`,
  set a static pattern, or start a new animation). A dedicated stop
  topic adds surface area for no new capability. It could be added
  later as a convenience alias if clients find the implicit rule
  confusing in practice.
- **Animation state topic** (`pattern/anim/state`): Deferred (not
  rejected). Publishing animation status would let HA show "blinking…"
  and let late-joining clients detect a running animation. Omitted now
  to keep the fire-and-forget model simple and to avoid a
  high-frequency status stream. Can be added later as a non-breaking
  addition.
- **`asyncio`-based scheduler**: Rejected. Rewriting the bridge away
  from `paho-mqtt`'s `loop_forever()` to an asyncio loop would be
  invasive and touch ADR 003 (threading) and ADR 009 (reconnection). A
  dedicated worker thread plus a lock is the smallest change that
  works.
- **`threading.Timer` chain** instead of a worker thread: Rejected.
  Spawning a new `Timer` per step is higher overhead and harder to
  cancel cleanly than a single thread with an `Event`. The worker thread
  also gives a clear join point on shutdown.
- **Retained anim messages**: Rejected. Animations are transient
  commands; restart-on-reconnect semantics would surprise users (a
  stale `blink` restarting after a bridge reboot). Senders must not set
  the retained flag; the bridge ignores the retained flag and never
  republishes anim state.
- **`fade` / `pulse` animations**: Out of scope. The hardware exposes
  ON/OFF only (ADR 004). Software PWM via rapid USB toggling flickers
  due to USB latency and is not reliable. Could be revisited only if
  PWM-capable hardware is introduced.

## Consequences

- ADR 012's reserved `pattern/anim/*` namespace is now defined by this
  ADR. Messages to `{prefix}/pattern/anim/<name>` are dispatched to the
  animation worker instead of being silently ignored.
- The wildcard subscription from ADR 011 (`{prefix}/#`) requires no
  changes — `pattern/anim/*` is below the existing filter.
- `models.py` gains `ANIM_TOPIC_PREFIX`, `ANIMATIONS`, `AnimParams`,
  `parse_anim_params`, and default constants; `mqtt_client.py` gains
  `_hw_lock`, `_anim_thread`, `_anim_stop`, `_start_animation`,
  `_cancel_animation`, `_run_animation`, `_animation_steps`, and
  `_render_step`.
- The per-color (ADR 008) and static-pattern (ADR 012) paths acquire
  `_hw_lock` and call `_cancel_animation()` before applying their
  command, so any incoming message cancels a running animation.
- `TrafficLight` hardware access is now lock-guarded everywhere; ADR
  004's abstraction is unchanged but concurrency is contractually
  serialized by the bridge.
- `stop()` cancels the running animation and joins the worker thread
  before disconnecting, ensuring a clean shutdown.
- New unit and integration tests cover: each animation type's frame
  sequence (time-mocked), cancellation on per-color/pattern/anim
  commands, min-interval clamping, invalid JSON, unknown animation
  names, hardware error mid-animation, infinite animation until
  cancelled, shutdown joining the thread, and lock contention between
  the animation worker and `_on_message`.
- The `pattern/anim/*` topics are non-retained. The existing
  `pattern/anim/<name>` filtering in `_on_message` is replaced by
  active dispatch.
- Home Assistant discovery (ADR 010) can expose each animation as a
  `select` entity when implemented; the JSON payload maps cleanly to a
  buttons/dropdown UI.