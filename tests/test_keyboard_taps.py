"""
Tests for keyboard finger tap adaptive baselines and alternative thumb-pinch typing.
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from finger_taps import FingerTapDetector
from recorder import create_synthetic_hand
from settings import AppConfig


def test_adaptive_resting_baselines():
    """
    Verifies that fingers with naturally curved resting posture (e.g. 148 deg)
    adaptively update their resting baseline and trigger taps on relative curl.
    """
    cfg = AppConfig()
    detector = FingerTapDetector(cfg)

    # Initial default baseline is 165.0
    assert detector.resting_baselines["ring"] == 165.0

    # Stream relaxed hand with naturally slightly curved ring finger (~148 deg)
    h_relaxed = create_synthetic_hand(ring_curl_angle=148.0)
    for _ in range(25):
        detector.process(h_relaxed)
        time.sleep(0.01)

    # Baseline should adapt down towards 148 deg
    adapted_baseline = detector.resting_baselines["ring"]
    assert adapted_baseline < 155.0, f"Ring baseline {adapted_baseline} did not adapt to 148 deg"

    # Now curl ring finger to 110 deg and rebound to 142 deg
    h_curl = create_synthetic_hand(ring_curl_angle=110.0)
    detector.process(h_curl)
    time.sleep(0.03)

    h_rebound = create_synthetic_hand(ring_curl_angle=142.0)
    event, _, _ = detector.process(h_rebound)
    assert event == "ring", "Ring finger tap failed to trigger against adapted baseline!"


def test_thumb_pinch_typing():
    """
    Verifies alternative typing mode: pinching thumb tip with index, middle, ring, or pinky
    triggers that finger's tap event.
    """
    cfg = AppConfig()
    cfg.keyboard.thumb_pinch_typing = True
    cfg.keyboard.tap_cooldown_ms = 150.0
    cfg.keyboard.neighbor_lockout_ms = 120.0

    detector = FingerTapDetector(cfg)

    # Hand at rest: open palm with all fingertips away from thumb
    h_rest = create_synthetic_hand()
    for _ in range(5):
        detector.process(h_rest)
        time.sleep(0.015)

    # 1. Pinch Index to Thumb: move landmark 8 close to landmark 4
    # Create hand where index tip is pinched to thumb tip
    h_pinch_index = create_synthetic_hand()
    # Move index tip (landmark 8) to thumb tip position (landmark 4)
    thumb_tip = h_pinch_index.landmarks[4]
    h_pinch_index.landmarks[8] = thumb_tip

    detector.process(h_pinch_index)
    time.sleep(0.03)

    # Release pinch: restore open palm
    h_release = create_synthetic_hand()
    event, is_repeat, _ = detector.process(h_release)
    assert event == "index", f"Expected index pinch tap, got {event}"
    assert is_repeat is False

    # Wait past lockout
    time.sleep(0.20)

    # 2. Pinch Middle to Thumb
    h_pinch_mid = create_synthetic_hand()
    thumb_tip = h_pinch_mid.landmarks[4]
    h_pinch_mid.landmarks[12] = thumb_tip

    detector.process(h_pinch_mid)
    time.sleep(0.03)

    event_mid, _, _ = detector.process(h_release)
    assert event_mid == "middle", f"Expected middle pinch tap, got {event_mid}"
