# ADR 014: Traffic Light Animations

## Status

Accepted

## Context

ADR 013 introduced a fixed catalog of generic, user-customizable animations
(`blink`, `chase`, `bounce`) that run on the bridge with a uniform `speed_ms`
interval.  These are useful as abstract attention signals, but they do not
model **real traffic light behavior**.  A common use case for a USB traffic
light is to simulate the actual phase transitions of a country's traffic
light system — for example, a German `red → red+yellow → green` transition
with regulation-based per-phase durations.

The generic animations (ADR 013) cannot express this because:

- **Variable per-phase timing.**  Real traffic lights use different durations
  per phase (e.g. 5 s red, 1 s red+yellow, 3 s green).  ADR 013's uniform
  `speed_ms` cannot encode this.
- **Fixed colors and sequences.**  The transition sequence is determined by
  traffic regulations, not by user taste.  Allowing a user to reorder or
  recolor the phases would produce nonsensical results.
- **Context-dependent completion.**  A traffic light transition typically ends
  in a "settled" state (green on, or red on) that the user wants to keep, in
  contrast to ADR 013's default where a finite animation restores the prior
  state.

Supporting more than one country (Germany now, Austria, Switzerland, etc.
later) requires a structure that keys timing data by country without
duplicating the dispatch, parsing, and runner logic.

## Decision

### Topic structure

```
{prefix}/pattern/tl/<country>/<animation>
e.g. cleware/ampel/pattern/tl/german/red-to-green
```

`<country>` selects a country catalog. `<animation>` selects an animation from
that country's catalog.  Unknown countries or animation names are ignored with
a warning, matching the "invalid commands no-op" policy of ADR 012/013.

The `pattern/tl/` namespace sits alongside `pattern/anim/` (ADR 013), below
the existing `{prefix}/#` wildcard subscription (ADR 011). No new
subscription is needed.

Note the urgency namespace is `pattern/tl/` not other parts of the topic tree,
so traffic light animations are **not** dispatched through `pattern/anim/`.

### Country and animation catalogs

```
COUNTRIES = {"german"}
GERMAN_TL_ANIMATIONS = {"blink-yellow", "red-to-green", "green-to-red"}
TL_TIMINGS = {"german": {...}}
```

Each country entry in `TL_TIMINGS` maps animation name → `TrafficLightTimings`
(see Data Model below).  Adding another country requires only extending
`COUNTRIES` and adding a `{country}_TIMINGS` dict with `TrafficLightTimings`
entries — no code changes elsewhere.

### Animation catalog (German)

| Animation | Phases (LEDs / duration) | Default `hold_final` | Default `repeats` |
|---|---|---|---|
| `blink-yellow` | yellow 500 ms → (all off) 500 ms — 1 Hz | `false` | `0` (infinite) |
| `red-to-green` | red 5 s → red+yellow 1 s → green 3 s | `true` | `1` (one cycle) |
| `green-to-red` | green 3 s → yellow 3 s → red 5 s | `true` | `1` (one cycle) |

Durations follow typical German **StVO** (Straßenverkehrs-Ordnung) traffic
light installations.  These are representative values suitable for a physical
display; precise field installations vary by intersection.

### Payload format

The payload reuses ADR 013's JSON object format.  For traffic light
animations, the recognized fields are:

| Field | Type | Default | Range / Constraint | Description |
|---|---|---|---|---|
| `speed_factor` | number | `1.0` | `0.1`–`10.0` | Divides all phase durations.  `2.0` = twice as fast (5 s → 2.5 s), `0.5` = half speed. Below `MIN_SPEED_MS` is clamped. |
| `repeats` | integer | (animation-specific) | `>= 0` | Number of complete cycles. `0` = infinite. Overrides the animation's `default_repeats` when explicitly set. |
| `hold_final` | boolean | (animation-specific) | — | Keep the last LED state after a finite animation completes. Overrides the animation's `default_hold_final` when explicitly set. |

`speed_ms` and `colors` from ADR 013 are accepted but ignored by traffic
light animations; the phase durations and LEDs are fixed by the country's
timing data.  Unknown fields are ignored for forward compatibility, as in
ADR 013.

### `hold_final` semantics

By default, finite traffic light animations follow ADR 013's "transient
overlay" rule: on natural completion the device is restored to the state it
had before the animation started.  With `hold_final: true`, the **last LED
turned on in the sequence** (e.g. green for `red-to-green`, red for
`green-to-red`) stays on after the animation completes, so the traffic light
remains in the post-transition state.  This is the default for
`red-to-green` and `green-to-red` because the dominant real-world use case
is to land the light in a meaningful steady state (green or red).

`blink-yellow` defaults to `hold_final: false` because it is by nature
infinite (`repeats = 0`) and never "completes"; an infinite animation never
holds a final state.

`hold_final` affects **only natural completion**.  A cancelled (interrupted)
animation never holds or restores — the interrupting command owns the new
state (ADR 013 cancellation rule applies unchanged).

### Animation-specific defaults

Each `TrafficLightTimings` carries `default_hold_final` and
`default_repeats`.  These are applied when the corresponding payload field is
**not present** in the user's JSON. If the user explicitly sets
`hold_final: false` on `red-to-green`, the hold is overridden and the prior
state is restored on completion.  This lets users opt out of the hold without
needing a separate payload field per animation.

The bridge tracks payload key presence via a helper (`_payload_has_key`) that
peeks at the raw JSON before parsing, so "user did not specify" is distinct
from "user explicitly set to default value".

### Frame format change

Frames now carry a duration.  Each frame is a tuple
`{frozenset[Color], int}` of LEDs and duration_ms rather than a bare
`frozenset[Color]`.  For generic animations (ADR 013) every frame shares
`params.speed_ms`; for traffic light animations each frame carries its
own scaled duration.  This unifies the runner: `_run_animation` sleeps for
`duration_ms / 1000.0` per frame regardless of animation type.

### Sceneexample (end-to-end traffic light cycle)

A client can orchestrate a full traffic light cycle by publishing three
traffic light animations in sequence:

```bash
# 1. From red, transition to green (hold green)
mosquitto_pub -t "cleware/ampel/pattern/tl/german/red-to-green" -m ""
# ... animation runs ~9 s, light settles on green ...

# 2. From green, transition to red (hold red)
mosquitto_pub -t "cleware/ampel/pattern/tl/german/green-to-red" -m ""
# ... animation runs ~11 s, light settles on red ...
```

No per-step client involvement is needed; each publish drives a multi-second
sequence server-side.

## Data model

```python
@dataclass(frozen=True)
class TrafficLightPhase:
    leds: frozenset[Color]
    duration_ms: int

@dataclass(frozen=True)
class TrafficLightTimings:
    name: str
    phases: tuple[TrafficLightPhase, ...]
    default_hold_final: bool
    default_repeats: int

TL_TIMINGS: dict[str, dict[str, TrafficLightTimings]]
```

A `_scale_timings(timings, speed_factor)` helper multiplies each phase's
duration by `1 / speed_factor`, clamped to `MIN_SPEED_MS`. The
`animation_frames(name, params)` generator yields `(leds, duration_ms)`
tuples from the scaled timings for traffic light animation names, and
`(leds, params.speed_ms)` for generic animations.

## Cancellation and threading

Traffic light animations reuse ADR 013's threading model unchanged: a single
worker thread, `_hw_lock` guarding all hardware access, and the "any command
cancels" rule.  `_launch_animation` is the shared mechanism; both
`_start_animation` (ADR 013) and `_start_tl_animation` (this ADR) validate
their inputs then delegate to it.  Interrupted-animation chain handling
(carrying `_anim_base_state` across chained animations) is unchanged.

## Examples

```bash
# Blink yellow at 1 Hz (German caution signal), infinite
mosquitto_pub -t "cleware/ampel/pattern/tl/german/blink-yellow" -m ""

# Red-to-green transition (default hold_final=true keeps green)
mosquitto_pub -t "cleware/ampel/pattern/tl/german/red-to-green" -m ""

# Green-to-red transition at 2× speed (keeps red)
mosquitto_pub -t "cleware/ampel/pattern/tl/german/green-to-red" \
  -m '{"speed_factor":2.0}'

# Red-to-green but restore prior state instead of holding green
mosquitto_pub -t "cleware/ampel/pattern/tl/german/red-to-green" \
  -m '{"hold_final":false}'
```

## Rationale

- **Server-side persistence.** Like ADR 013's generic animations, traffic
  light animations keep running independently of the publishing client — a
  multi-second transition continues even if the client disconnects.
- **Fixed timings per country.** Real traffic light behavior is not
  user-configurable; the timings are regulatory.  Encoding them as data
  (not as a user-supplied parameter) avoids producing nonsense transitions
  (e.g. "green → red with no yellow").
- **Speed factor vs. speed_ms.** A speed multiplier is more intuitive than
  "milliseconds per step" for scaling a multi-phase sequence with
  heterogeneous durations.  Multiplying or dividing timed data is the
  natural operation; replacing specific durations with a single interval
  would discard the regulation-derived relative timings.
- **`hold_final` as a first-class option.** Real traffic lights settle into
  a steady state (green, red).  Holding the final state by default for
  transitions matches the dominant use case ("drive the light to green and
  leave it there"); the explicit `hold_final: false` lets advanced users
  treat a transition as a transient overlay that restores the prior state.
- **Per-animation defaults (`default_repeats`, `default_hold_final`) in
  timing data.** Centralizes animation-specific behavior near the timing
  data so adding a new country's animations does not require touching
  dispatch code.
- **Frame-format two-tuple.** Embedding the duration in the frame keeps the
  runner simple (one `stop.wait(duration_ms / 1000.0)` call) and uniform
  across generic and traffic light animations.  No external per-frame
  timing file or config is needed.

## Alternatives considered

- **Generic `speed_ms` over all frames.** Rejected.  It cannot encode
  variable per-phase durations, which are essential to real traffic light
  behavior; all phases would share one identical interval, which is
  unrealistic.
- **External `/config` timings file referenced by country name.**
  Rejected.  Over-engineered for a compact set of regulatory timings; the
  in-source `TL_TIMINGS` dict is simpler to maintain and test, and adding
  a country requires only new data, not config-file plumbing.
- **Topic `<prefix>/pattern/anim/tl-german-<name>`.** Rejected.  Bundles
  country into the animation name and mixes traffic lights into the
  generic `pattern/anim/` namespace, making it unclear which fields apply
  and harder to extend.
- **Separate stop or state topic.** Rejected for the same reasons as ADR
  013; the "any command cancels" rule and fire-and-forget model remain.
- **`fade`/`pulse` transitions.** Out of scope, as in ADR 013: the hardware
  exposes ON/OFF only and software PWM is unreliable over USB.
- **User-overridable per-phase durations.** Rejected.  Phases are
  regulation-derived; user overrides would allow nonsensical sequences.
  `speed_factor` provides the useful axis (overall speed) without
  breaking the relative timing structure.

## Consequences

- The `{prefix}/pattern/tl/<country>/<animation>` namespace is now defined.
  The existing wildcard subscription `{prefix}/#` covers it with no change.
- `AnimParams` gains `hold_final` (bool) and `speed_factor` (float).
  Generic animations accept these fields (ignored / unused) so the payload
  parser remains unified; traffic light animations use them.
- `animation_frames` now yields `{(leds, duration_ms)}` cycle lists for all
  animations; `_run_animation` reads the per-frame duration.  Tests for
  ADR 013 animations are updated to expect tuples.
- `models.py` gains `TrafficLightPhase`, `TrafficLightTimings`,
  `TL_TIMINGS`, `_scale_timings`, and the German timing data; new constants
  `TL_TOPIC_PREFIX`, `COUNTRIES`, `GERMAN_TL_ANIMATIONS`, `DEFAULT_SPEED_FACTOR`,
  `MIN_SPEED_FACTOR`, `MAX_SPEED_FACTOR`.
- `mqtt_client.py` gains `_start_tl_animation` (which delegates to the shared
  `_launch_animation`), and uses `_payload_has_key` to detect explicit
  `hold_final` / `repeats` and apply animation-specific defaults otherwise.
- Adding another country (e.g. Austria) requires only: add the code to
  `COUNTRIES`, define an `{COUNTRY}_TIMINGS` dict with `TrafficLightTimings`
  entries, and add it to `TL_TIMINGS`. The dispatch, parsing, and runner
  code require no changes.
- Home Assistant discovery (ADR 010) can expose each traffic light animation
  as a `select` entity; the JSON payload maps to a UI control with a speed
  slider and a "hold final state" toggle.