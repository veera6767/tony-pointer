"""
Replay-based unit tests for GestureEngine & FingerTapDetector using synthetic
landmark sequences (testing air double-tap, per-finger tap lockout, and pause gesture).
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine, PoseType
from recorder import create_synthetic_hand
from settings import AppConfig


def test_air_double_tap_detection():
    """Simulates two rapid flex-and-rebound motions of the index finger within 500ms."""
    cfg = AppConfig()
    cfg.gestures.double_tap_window_ms = 500.0
    cfg.gestures.tap_cooldown_ms = 150.0

    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    def make_pointing(index_angle):
        return create_synthetic_hand(
            index_curl_angle=index_angle,
            middle_curl_angle=80.0,
            ring_curl_angle=80.0,
            pinky_curl_angle=80.0
        )

    # Frame 1-3: Straight index (angle ~170 deg)
    for _ in range(4):
        h = make_pointing(170.0)
        res = engine.process(h, screen_bounds, filter_2d, "POINTER")
        time.sleep(0.02)

    # Tap 1 curl down to 100 deg
    h_curl = make_pointing(100.0)
    engine.process(h_curl, screen_bounds, filter_2d, "POINTER")
    time.sleep(0.03)

    # Tap 1 rebound to 160 deg
    h_rebound = make_pointing(160.0)
    res_tap1 = engine.process(h_rebound, screen_bounds, filter_2d, "POINTER")
    assert engine.pending_single_tap is True

    time.sleep(0.18)

    # Tap 2 curl down to 100 deg
    engine.process(h_curl, screen_bounds, filter_2d, "POINTER")
    time.sleep(0.03)

    # Tap 2 rebound to 160 deg within double tap window
    res_tap2 = engine.process(h_rebound, screen_bounds, filter_2d, "POINTER")
    assert res_tap2["action"] == GestureAction.DOUBLE_CLICK.value


def test_finger_tap_detector_neighbor_lockout():
    """When one finger taps, adjacent fingers flexed simultaneously are locked out."""
    cfg = AppConfig()
    cfg.keyboard.tap_cooldown_ms = 200.0
    cfg.keyboard.neighbor_lockout_ms = 180.0

    detector = FingerTapDetector(cfg)

    # Initial straight hand
    h_straight = create_synthetic_hand()
    for _ in range(4):
        detector.process(h_straight)
        time.sleep(0.02)

    # Index finger curl down and rebound
    h_curl = create_synthetic_hand(index_curl_angle=110.0)
    detector.process(h_curl)
    time.sleep(0.03)

    h_rebound = create_synthetic_hand(index_curl_angle=160.0)
    event1, _, _ = detector.process(h_rebound)
    assert event1 == "index"

    # Immediately on next frame, middle finger attempts tap due to coupling
    h_mid_curl = create_synthetic_hand(middle_curl_angle=110.0)
    detector.process(h_mid_curl)
    time.sleep(0.01)

    h_mid_rebound = create_synthetic_hand(middle_curl_angle=160.0)
    event2, _, _ = detector.process(h_mid_rebound)
    # Must be locked out by neighbor lockout!
    assert event2 is None, "Neighbor finger triggered without respecting lockout!"


def test_pause_fist_gesture_in_pointer_mode():
    """Holding a closed fist for 1.5s in POINTER mode triggers PAUSE_TOGGLE."""
    cfg = AppConfig()
    cfg.gestures.fist_pause_hold_s = 0.20 # Short test target

    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    # All fingers curled (Fist pose)
    h_fist = create_synthetic_hand(
        index_curl_angle=80.0, middle_curl_angle=80.0,
        ring_curl_angle=80.0, pinky_curl_angle=80.0
    )

    res1 = engine.process(h_fist, screen_bounds, filter_2d, "POINTER")
    assert res1["pose"] == PoseType.FIST.value
    assert res1["action"] == GestureAction.PAUSE.value

    # Wait for target hold duration
    time.sleep(0.25)

    res2 = engine.process(h_fist, screen_bounds, filter_2d, "POINTER")
    assert res2["action"] == GestureAction.PAUSE_TOGGLE.value
