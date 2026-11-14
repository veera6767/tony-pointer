"""
Tests for air double-click and single-click timing, lookback freeze position,
and circuit breaker integration.
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from filters import OneEuroFilter2D
from gestures import GestureAction, GestureEngine
from mouse import MouseController
from recorder import create_synthetic_hand
from settings import AppConfig


def _simulate_tap(engine, screen_bounds, filter_2d, mode="POINTER"):
    """Helper to simulate an index finger tap: straight -> curl -> rebound."""
    h_straight = create_synthetic_hand(index_curl_angle=170.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    h_curl = create_synthetic_hand(index_curl_angle=105.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    h_rebound = create_synthetic_hand(index_curl_angle=162.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)

    # Rebound frame triggers tap detection
    engine.process(h_curl, screen_bounds, filter_2d, mode)
    time.sleep(0.02)
    return engine.process(h_rebound, screen_bounds, filter_2d, mode)


@pytest.mark.parametrize("inter_tap_gap_s", [0.20, 0.28, 0.40])
def test_double_click_at_various_gaps(inter_tap_gap_s):
    """
    Verifies that natural double taps at 200ms, 280ms, and 400ms
    are all recognized and emit DOUBLE_CLICK without getting blocked by cooldowns.
    """
    cfg = AppConfig()
    cfg.gestures.double_tap_window_ms = 500.0
    cfg.gestures.tap_cooldown_ms = 180.0

    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    # Establish baseline straight frames
    h_straight = create_synthetic_hand(index_curl_angle=170.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    for _ in range(5):
        engine.process(h_straight, screen_bounds, filter_2d, "POINTER")
        time.sleep(0.015)

    # Tap 1
    res1 = _simulate_tap(engine, screen_bounds, filter_2d)
    assert engine.pending_single_tap is True, "Tap 1 failed to enter pending double-tap window"

    # Inter-tap gap: stream resting frames at ~30 FPS
    gap_steps = max(1, int(inter_tap_gap_s / 0.033))
    dt_step = inter_tap_gap_s / gap_steps
    for _ in range(gap_steps):
        time.sleep(dt_step)
        engine.process(h_straight, screen_bounds, filter_2d, "POINTER")

    # Tap 2
    res2 = _simulate_tap(engine, screen_bounds, filter_2d)
    assert res2["action"] == GestureAction.DOUBLE_CLICK.value, (
        f"Tap 2 with gap {inter_tap_gap_s}s did not emit DOUBLE_CLICK (got {res2['action']})"
    )
    assert engine.pending_single_tap is False


def test_single_click_fires_when_window_expires():
    """
    Verifies that when only one tap is performed, SINGLE_CLICK is emitted
    after the double-tap window expires.
    """
    cfg = AppConfig()
    cfg.gestures.double_tap_window_ms = 250.0  # short window for testing

    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    h_straight = create_synthetic_hand(index_curl_angle=170.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    for _ in range(5):
        engine.process(h_straight, screen_bounds, filter_2d, "POINTER")
        time.sleep(0.015)

    # Perform Tap 1
    _simulate_tap(engine, screen_bounds, filter_2d)
    assert engine.pending_single_tap is True

    # Wait past window expiry
    time.sleep(0.30)

    # Next frame should emit the timed-out SINGLE_CLICK
    res = engine.process(h_straight, screen_bounds, filter_2d, "POINTER")
    assert res["action"] == GestureAction.SINGLE_CLICK.value
    assert engine.pending_single_tap is False


def test_cursor_freeze_lookback_stability():
    """
    Verifies that the frozen click position uses pre-tap position from 150ms lookback,
    avoiding the displacement caused by the finger curling motion.
    """
    cfg = AppConfig()
    cfg.gestures.cursor_freeze_lookback_ms = 150.0
    cfg.gestures.cursor_freeze_after_tap_ms = 400.0

    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    # Feed resting hand position at (0.5, 0.5)
    h_rest = create_synthetic_hand(wrist_xy=(0.5, 0.5), index_curl_angle=170.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    for _ in range(12):
        engine.process(h_rest, screen_bounds, filter_2d, "POINTER")
        time.sleep(0.02)  # ~240ms of history at rest position

    # During curl, hand moves slightly to (0.55, 0.55) due to muscle tendon tension
    h_displaced_curl = create_synthetic_hand(wrist_xy=(0.55, 0.55), index_curl_angle=105.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    engine.process(h_displaced_curl, screen_bounds, filter_2d, "POINTER")
    time.sleep(0.02)

    h_displaced_rebound = create_synthetic_hand(wrist_xy=(0.55, 0.55), index_curl_angle=162.0, middle_curl_angle=80.0, ring_curl_angle=80.0, pinky_curl_angle=80.0)
    res_tap = engine.process(h_displaced_rebound, screen_bounds, filter_2d, "POINTER")

    # The frozen cursor position should be close to resting (0.5, 0.5) mapped to screen (~960), NOT displaced
    assert engine.tap_frozen_pos is not None
    frozen_x, frozen_y = engine.tap_frozen_pos
    # Expected resting center x is 960 (0.5 * 1920)
    assert abs(frozen_x - 960) < 40, f"Frozen position {frozen_x} did not use resting lookback position"


def test_mouse_double_click_circuit_breaker_single_action():
    """
    Verifies that mouse.double_click counts as 1 circuit breaker action,
    not 2 separate clicks, preventing tripping the breaker on normal double-clicks.
    """
    mouse = MouseController(safe_sink=True)

    # Perform 4 double clicks (which dispatch 8 Win32 down/up events)
    for _ in range(4):
        success = mouse.double_click(x=500, y=500)
        assert success is True
        time.sleep(0.05)

    # 4 double clicks recorded as exactly 4 actions in click_history
    assert len(mouse.click_history) == 4, f"Expected 4 actions, got {len(mouse.click_history)}"

    # The 5th double click within 2s exceeds the limit of 4 and trips the breaker
    tripped = mouse.double_click(x=500, y=500)
    assert tripped is False, "5th click within 2s should trip breaker and return False"
