from __future__ import annotations

import json
import logging
import os
import threading
import uuid

import paho.mqtt.client as mqtt

from .config import BridgeConfig
from .models import (
    ANIM_TOPIC_PREFIX,
    ANIMATIONS,
    PATTERN_TOPIC_SUFFIX,
    TL_TIMINGS,
    TL_TOPIC_PREFIX,
    TOPIC_COLOR_MAP,
    AnimParams,
    Color,
    LEDState,
    animation_frames,
    parse_anim_params,
    parse_pattern,
)
from .traffic_light import TrafficLight

logger = logging.getLogger(__name__)


def _payload_has_key(payload: str, key: str) -> bool:
    """Return True if the JSON object in *payload* contains *key*.

    Returns False on empty, non-JSON, or non-object payloads so callers can
    distinguish "user did not specify the key" from an explicit value.
    """
    text = payload.strip()
    if not text:
        return False
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and key in data


class MQTTBridge:
    def __init__(self, config: BridgeConfig, light: TrafficLight) -> None:
        self._config = config
        self._light = light
        self._active_leds: set[Color] = set()

        # Guards all hardware access (set_led) and _active_leds mutations so the
        # animation worker thread and the MQTT callback thread never interleave
        # a partial frame with a direct command (ADR 013).
        self._hw_lock: threading.Lock = threading.Lock()
        self._anim_thread: threading.Thread | None = None
        self._anim_stop: threading.Event | None = None
        # The "base" device state captured before the *current* animation chain
        # began. A finite animation restores this on natural completion. When a
        # new animation interrupts a running one, the interrupting animation
        # adopts this same base instead of snapshotting the mid-animation frame
        # it overwrote, so a chain of animations always restores the state that
        # existed before the first animation started (ADR 013).
        self._anim_base_state: frozenset[Color] = frozenset()

        client_id = os.environ.get("MQTT_CLIENT_ID", "")
        if not client_id:
            client_id = f"cleware-bridge-{uuid.uuid4().hex[:12]}"

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id,
            clean_session=True,
        )
        self._subscribe_topics: list[str] = []
        self._build_subscribe_topics()

    def _build_subscribe_topics(self) -> None:
        prefix = self._config.mqtt_topic_prefix.rstrip("/")
        self._subscribe_topics = [f"{prefix}/#"]

    def start(self) -> None:
        cfg = self._config

        if cfg.mqtt_username:
            self._client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)

        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        logger.info("Connecting to MQTT broker %s:%d", cfg.mqtt_host, cfg.mqtt_port)
        try:
            self._client.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
        except Exception as exc:
            logger.error("Initial MQTT connection failed: %s", exc)

        self._client.loop_forever()

    def stop(self) -> None:
        logger.info("Stopping MQTT bridge...")
        self._cancel_animation()
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            logger.error("MQTT connection failed: %s", reason_code)
            return
        logger.info("MQTT connected")
        topic = self._subscribe_topics[0]
        client.subscribe(topic, qos=1)
        logger.info("Subscribed to %s", topic)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
        *args: object,
    ) -> None:
        if reason_code.is_failure:
            logger.warning("MQTT disconnected: %s", reason_code)
        else:
            logger.info("MQTT disconnected gracefully")

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        prefix = self._config.mqtt_topic_prefix.rstrip("/")

        if not topic.startswith(prefix):
            return

        suffix = topic[len(prefix) :].strip("/")
        payload_str = msg.payload.decode("utf-8", errors="replace")

        if suffix == PATTERN_TOPIC_SUFFIX:
            self._apply_pattern(payload_str)
            return

        if suffix.startswith(ANIM_TOPIC_PREFIX):
            anim_name = suffix[len(ANIM_TOPIC_PREFIX) :]
            self._start_animation(anim_name, payload_str)
            return

        if suffix.startswith(TL_TOPIC_PREFIX):
            tl_suffix = suffix[len(TL_TOPIC_PREFIX) :]
            self._start_tl_animation(tl_suffix, payload_str)
            return

        if suffix not in TOPIC_COLOR_MAP:
            return

        color = TOPIC_COLOR_MAP[suffix]

        logger.info("Received command on %s: payload=%s", topic, payload_str)

        brightness = self._parse_brightness(payload_str)
        if brightness is None:
            return

        # Any valid command cancels a running animation before applying (ADR 013).
        self._cancel_animation()
        try:
            with self._hw_lock:
                if brightness == 1:
                    self._light.set_led(color, LEDState.ON)
                    self._active_leds.add(color)
                    logger.info("LED %s ON (active: %s)", color.to_name(), self._active_leds)
                else:
                    self._light.set_led(color, LEDState.OFF)
                    self._active_leds.discard(color)
                    logger.info("LED %s OFF (active: %s)", color.to_name(), self._active_leds)
        except Exception as exc:
            logger.error("Failed to set LED %s: %s", color.to_name(), exc)

    def _apply_pattern(self, payload_str: str) -> None:
        """Apply a whole-device pattern, setting all LEDs atomically.

        LEDs in the parsed pattern are turned ON; every other LED is turned OFF.
        On an invalid pattern, a warning is logged and the device state is
        left unchanged. Any running animation is cancelled first (ADR 013).
        """
        logger.info("Received pattern command: payload=%s", payload_str)
        pattern = parse_pattern(payload_str)
        if pattern is None:
            logger.warning("Invalid pattern payload: %r", payload_str)
            return

        # Any valid command cancels a running animation before applying (ADR 013).
        self._cancel_animation()
        try:
            with self._hw_lock:
                self._render_frame(pattern)
            logger.info(
                "Pattern applied: %s (active: %s)",
                payload_str.strip(),
                self._active_leds,
            )
        except Exception as exc:
            logger.error("Failed to apply pattern %r: %s", payload_str, exc)

    def _render_frame(self, frame: frozenset[Color]) -> None:
        """Drive every LED to match ``frame`` and refresh tracked state.

        Must be called while holding :attr:`_hw_lock`. On a hardware error
        mid-frame, the LEDs already changed keep their new state and
        :attr:`_active_leds` is *not* updated, mirroring the per-color error
        handling: a failed frame never claims a known state.
        """
        for color in Color:
            target = LEDState.ON if color in frame else LEDState.OFF
            self._light.set_led(color, target)
        self._active_leds = set(frame)

    def _start_animation(self, name: str, payload: str) -> None:
        """Dispatch an animation command (ADR 013).

        Unknown animation names and invalid payloads are rejected with a
        warning and leave the device — and any running animation — untouched.
        A valid command cancels the running animation first, then starts the
        new one on a dedicated worker thread.
        """
        if name not in ANIMATIONS:
            logger.warning("Unknown animation: %r", name)
            return
        params = parse_anim_params(name, payload)
        if params is None:
            logger.warning("Invalid animation payload for %r: %r", name, payload)
            return
        self._launch_animation(name, params)

    def _start_tl_animation(self, tl_suffix: str, payload: str) -> None:
        """Dispatch a traffic light animation command (ADR 014).

        ``tl_suffix`` is the part after ``pattern/tl/``, of the form
        ``<country>/<animation>``.  Unknown countries or animation names are
        rejected with a warning; otherwise the JSON payload is parsed (with
        traffic-light-specific defaults applied) and the animation is
        launched via :meth:`_launch_animation`.
        """
        parts = tl_suffix.split("/", 1)
        if len(parts) != 2 or not all(parts):
            logger.warning("Invalid traffic light topic suffix: %r", tl_suffix)
            return
        country, anim_name = parts[0], parts[1]
        if country not in TL_TIMINGS or anim_name not in TL_TIMINGS[country]:
            logger.warning("Unknown traffic light animation: %r/%r", country, anim_name)
            return

        holds_final = _payload_has_key(payload, "hold_final")
        specifies_repeats = _payload_has_key(payload, "repeats")
        params = parse_anim_params(anim_name, payload)
        if params is None:
            logger.warning(
                "Invalid payload for traffic light %r/%r: %r",
                country,
                anim_name,
                payload,
            )
            return

        timings = TL_TIMINGS[country][anim_name]

        # Traffic light animations have fixed colors and per-phase durations;
        # speed_ms and colors from params are meaningless here.  Apply the
        # animation-specific defaults for hold_final and repeats when not
        # explicitly set in the payload (ADR 014).
        hold_final = params.hold_final if holds_final else timings.default_hold_final
        repeats = params.repeats if specifies_repeats else timings.default_repeats
        params = AnimParams(
            hold_final=hold_final,
            speed_factor=params.speed_factor,
            repeats=repeats,
        )
        self._launch_animation(anim_name, params)

    def _launch_animation(self, name: str, params: AnimParams) -> None:
        """Validate-independent launch: cancel running anim and start worker.

        Shared by :meth:`_start_animation` (ADR 013) and
        :meth:`_start_tl_animation` (ADR 014).  ``name`` and ``params`` must
        already be validated by the caller.
        """
        # If we are interrupting a running animation, the new animation must
        # restore the *same* base state the interrupted one would have — i.e.
        # the device state before the animation chain began — rather than the
        # mid-animation frame we are about to overwrite. Snapshotting the live
        # LEDs would otherwise capture the previous animation's transient
        # frame as the restore target (bug). A non-animated device simply
        # snapshots its current LED state (ADR 013).
        interrupting = self._anim_thread is not None and self._anim_thread.is_alive()
        if interrupting:
            previous_state = self._anim_base_state
        else:
            with self._hw_lock:
                previous_state = frozenset(self._active_leds)
        self._cancel_animation()
        self._anim_base_state = previous_state
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._run_animation,
            args=(name, params, previous_state, stop_event),
            daemon=True,
            name=f"anim-{name}",
        )
        self._anim_stop = stop_event
        self._anim_thread = thread
        thread.start()
        logger.info("Animation started: %s (params: %s)", name, params)

    def _cancel_animation(self) -> None:
        """Cancel the running animation, if any, and join its worker thread.

        Safe to call when no animation is running. Does not acquire
        :attr:`_hw_lock` so the worker can finish any in-flight frame, then
        observe the stop event and exit.
        """
        thread = self._anim_thread
        if thread is not None and thread.is_alive():
            if self._anim_stop is not None:
                self._anim_stop.set()
            thread.join(timeout=2.0)
        self._anim_thread = None
        self._anim_stop = None

    def _run_animation(
        self,
        name: str,
        params: AnimParams,
        previous_state: frozenset[Color],
        stop: threading.Event,
    ) -> None:
        """Run an animation on a worker thread until cancelled or complete.

        Each step renders a frame under :attr:`_hw_lock`, then sleeps for the
        frame's own duration (in ms) via ``stop.wait`` so a cancellation wakes
        the worker immediately.  A hardware error mid-frame aborts the
        animation.

        On natural completion of a finite animation (``repeats > 0``
        reaching its count) the worker restores ``previous_state`` — the
        device state captured before the animation started — so a finite
        animation acts as a transient overlay.  If ``params.hold_final`` is
        True, the last rendered frame's LED state is kept instead of
        restoring ``previous_state`` (ADR 014).

        If the animation is cancelled (``stop`` set by an interrupting
        command) or aborts on a hardware error, the prior state is **not**
        restored; the interrupting command owns the new state. Infinite
        animations never complete on their own.
        """
        try:
            cycles = animation_frames(name, params)
            cycle_count = 0
            last_frame: frozenset[Color] = previous_state
            while params.infinite or cycle_count < params.repeats:
                cycle = next(cycles, None)
                if cycle is None:
                    break
                for frame, duration_ms in cycle:
                    if stop.is_set():
                        return
                    with self._hw_lock:
                        try:
                            self._render_frame(frame)
                        except Exception as exc:
                            logger.error("Animation %r aborted: %s", name, exc)
                            return
                    last_frame = frame
                    if stop.wait(duration_ms / 1000.0):
                        return
                cycle_count += 1
            # Natural completion.  Re-check ``stop`` under the lock so an
            # interrupting command that set it while we waited above wins,
            # and we never clobber a state a newer command has applied.
            with self._hw_lock:
                if stop.is_set():
                    return
                if params.hold_final:
                    # Keep the last rendered frame; no hardware change needed
                    # since the LEDs already show it. Just ensure tracked
                    # state is in sync (it already is via _render_frame).
                    logger.info(
                        "Animation %r completed; holding final state: %s",
                        name,
                        {c.to_name() for c in last_frame},
                    )
                    return
                try:
                    self._render_frame(previous_state)
                    logger.info(
                        "Animation %r completed; restored previous state: %s",
                        name,
                        {c.to_name() for c in previous_state},
                    )
                except Exception as exc:
                    logger.error("Animation %r completed but restore failed: %s", name, exc)
        except Exception as exc:
            logger.error("Animation %r crashed: %s", name, exc)

    def _parse_brightness(self, payload: str) -> int | None:
        normalized = payload.strip().lower()
        if normalized in ("on", "1"):
            return 1
        if normalized in ("off", "0"):
            return 0
        try:
            value = int(payload)
        except (ValueError, TypeError):
            logger.warning("Invalid brightness payload: %r", payload)
            return None
        if value < 0 or value > 1:
            logger.warning("Brightness value out of range: %d", value)
            return None
        return value
