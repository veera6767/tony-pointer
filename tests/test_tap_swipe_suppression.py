"""
Unit tests for mutual suppression between finger taps and whole-hand swipes,
and keyboard mode entry grace period hysteresis.
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from finger_taps import FingerTapDetector
from keyboard_layout import KeyboardLayoutManager
from mode_manager import AppMode, ModeManager
from recorder import create_synthetic_hand
from settings import AppConfig


def test_tap_rejected_during_fast_palm_movement():
    """Finger taps must be rejected when palm translation velocity is high (e.g. mid-swipe)."""
    cfg = AppConfig()
    detector = FingerTapDetector(cfg)

    # Establish baseline hand at (0.5, 0.5)
    h_rest = create_synthetic_hand(wrist_xy=(0.5, 0.5))
    detector.process(h_rest)
    time.sleep(0.02)

    # Simulate fast palm movement (moving from x=0.5 to x=0.8 within 0.05s)
    # Hand moves fast while index curls and rebounds
    h_moving_curl = create_synthetic_hand(wrist_xy=(0.65, 0.5), index_curl_angle=105.0)
    detector.process(h_moving_curl)
    time.sleep(0.03)

    h_moving_rebound = create_synthetic_hand(wrist_xy=(0.80, 0.5), index_curl_angle=162.0)
    event, _, _ = detector.process(h_moving_rebound)

    # Must be suppressed because palm speed was high
    assert event is None, "Finger tap triggered during high-speed palm translation!"


def test_swipe_rejected_during_fast_finger_curl():
    """Swipes must be rejected while any typing finger is curling fast."""
    cfg = AppConfig()
    cfg.keyboard.swipe_threshold = 0.30
    layout_mgr = KeyboardLayoutManager()
    mgr = ModeManager(cfg, layout_mgr)
    mgr.mode = AppMode.KEYBOARD

    detector = FingerTapDetector(cfg)

    # Establish neutral center
    h_neutral = create_synthetic_hand(wrist_xy=(0.5, 0.7))
    mgr.evaluate_swipes(h_neutral)
    detector.process(h_neutral)
    time.sleep(0.02)

    # Finger curls fast (angle drops from 170 to 105)
    h_curling = create_synthetic_hand(wrist_xy=(0.65, 0.7), index_curl_angle=105.0)
    detector.process(h_curling)

    # Check if detector sees rapid curling
    is_curling = detector.is_curling_fast(threshold_delta=14.0)
    assert is_curling is True, "Fast finger curl was not detected by is_curling_fast"

    # Evaluate swipe with any_finger_curling=True
    swipe_action = mgr.evaluate_swipes(h_curling, any_finger_curling=is_curling)
    assert swipe_action is None, "Swipe was not suppressed during rapid finger curl!"


def test_keyboard_mode_entry_stabilization_grace_period():
    """When switching to KEYBOARD mode, taps are ignored for the first 300ms to allow hand stabilization."""
    cfg = AppConfig()
    detector = FingerTapDetector(cfg)

    # Prime history buffer with straight resting frames
    h_straight = create_synthetic_hand(index_curl_angle=170.0)
    for _ in range(4):
        detector.process(h_straight)
        time.sleep(0.015)

    # Hand enters keyboard mode at now
    t_entry = time.perf_counter()

    # Immediate curl and rebound 100ms after entry
    time.sleep(0.05)
    h_curl = create_synthetic_hand(index_curl_angle=105.0)
    detector.process(h_curl, keyboard_entry_time=t_entry)
    time.sleep(0.03)

    h_rebound = create_synthetic_hand(index_curl_angle=162.0)
    event, _, _ = detector.process(h_rebound, keyboard_entry_time=t_entry)

    # Within 300ms, event must be suppressed
    assert event is None, "Tap was detected during the 300ms keyboard entry grace period!"

    # Wait past 300ms grace period with resting frames streamed at ~30 FPS
    for _ in range(8):
        time.sleep(0.033)
        detector.process(h_straight, keyboard_entry_time=t_entry)
    assert (time.perf_counter() - t_entry) >= 0.30

    # Now a fresh tap should be accepted
    detector.process(h_curl, keyboard_entry_time=t_entry)
    time.sleep(0.03)
    event2, _, _ = detector.process(h_rebound, keyboard_entry_time=t_entry)
    assert event2 == "index", "Tap was rejected after the 300ms grace period expired!"
