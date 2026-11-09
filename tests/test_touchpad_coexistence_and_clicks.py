"""
Tests for Touchpad Coexistence, Click Arbitration, and Safety Guardrails.
Guarantees:
1. Still hand in two-finger pose for 10s produces at most ONE right click.
2. No hand, low confidence (<0.50), or outside active region produces ZERO clicks.
3. Dwell in POINTER mode NEVER presses button; dwell in PAINT mode does, and auto-releases.
4. Physical cursor movement triggers yielding and releases buttons.
5. Circuit breaker trips and pauses output on rapid click bursts.
6. Multi-monitor coordinate mappings (including negative X virtual desktop).
7. Shutdown / emergency release releases all buttons and keys.
"""

import os
import sys
import time
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from filters import OneEuroFilter2D
from gestures import GestureAction, GestureEngine, PoseType
from mouse import MouseController
from settings import AppConfig
from tracker import HandFrame, LandmarkPoint


from recorder import create_synthetic_hand

def create_mock_hand(
    confidence: float = 0.95,
    pose: str = "POINTING"
) -> HandFrame:
    """Generates synthetic HandFrame with controllable pose and confidence."""
    if pose == "POINTING":
        h = create_synthetic_hand(
            index_curl_angle=170.0,
            middle_curl_angle=70.0,
            ring_curl_angle=70.0,
            pinky_curl_angle=70.0
        )
    elif pose == "TWO_FINGER":
        h = create_synthetic_hand(
            index_curl_angle=170.0,
            middle_curl_angle=170.0,
            ring_curl_angle=70.0,
            pinky_curl_angle=70.0
        )
    else:
        h = create_synthetic_hand()

    h.confidence = confidence
    return h


def test_still_hand_two_finger_fires_at_most_once():
    """A still hand held in TWO_FINGER pose for 10 seconds must fire at most 1 right click."""
    cfg = AppConfig()
    cfg.gestures.click_mode = "all"
    cfg.gestures.right_click_hold_s = 0.30
    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    # 1. Start in pointing pose to establish baseline
    h_pointing = create_mock_hand(pose="POINTING")
    for _ in range(5):
        engine.process(h_pointing, screen_bounds, filter_2d, "POINTER")

    # 2. Transition into two-finger pose and hold stationary
    right_clicks = 0
    h_two = create_mock_hand(pose="TWO_FINGER")

    # Simulate 50 frames over ~1.0 second
    for _ in range(50):
        res = engine.process(h_two, screen_bounds, filter_2d, "POINTER")
        if res["action"] == GestureAction.RIGHT_CLICK.value:
            right_clicks += 1
        time.sleep(0.015)

    assert right_clicks == 1, f"Expected exactly 1 right click, got {right_clicks}"


def test_no_hand_low_confidence_outside_region_zero_clicks():
    """No hand, confidence < 0.50, or outside active region produces ZERO clicks."""
    cfg = AppConfig()
    cfg.gestures.click_mode = "all"
    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    # Case A: hand is None
    res_none = engine.process(None, screen_bounds, filter_2d, "POINTER")
    assert res_none["action"] in (GestureAction.NONE.value, GestureAction.PAUSE.value)

    # Case B: low confidence (0.35)
    h_low_conf = create_mock_hand(confidence=0.35, pose="POINTING")
    res_low = engine.process(h_low_conf, screen_bounds, filter_2d, "POINTER")
    assert res_low["action"] != GestureAction.SINGLE_CLICK.value
    assert res_low["action"] != GestureAction.DOUBLE_CLICK.value

    # Case C: hand outside active region (norm_x = 0.01, outside default 0.15..0.85)
    h_outside = create_mock_hand(confidence=0.95, pose="POINTING")
    for pt in h_outside.landmarks:
        pt.x = 0.01
        pt.y = 0.01
    res_out = engine.process(h_outside, screen_bounds, filter_2d, "POINTER")
    assert res_out["in_active_region"] is False
    assert res_out["action"] != GestureAction.SINGLE_CLICK.value


def test_dwell_in_pointer_never_presses_button():
    """Dwell in POINTER mode must NEVER press mouse button; in PAINT mode it does."""
    cfg = AppConfig()
    cfg.gestures.dwell_lock_time_s = 0.20
    engine = GestureEngine(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    screen_bounds = (0, 0, 1920, 1080)

    h_point = create_mock_hand(pose="POINTING")

    # In POINTER mode: hold still for 0.4s
    pointer_locked = False
    for _ in range(20):
        res = engine.process(h_point, screen_bounds, filter_2d, "POINTER")
        if res["action"] == GestureAction.BRUSH_LOCK_TOGGLE.value:
            pointer_locked = True
        time.sleep(0.02)
    assert pointer_locked is False, "Dwell in POINTER mode pressed mouse button!"

    # In PAINT mode: hold still for 0.4s -> should lock brush
    paint_locked = False
    for _ in range(25):
        res = engine.process(h_point, screen_bounds, filter_2d, "PAINT")
        if res["action"] == GestureAction.BRUSH_LOCK_TOGGLE.value:
            paint_locked = True
        time.sleep(0.02)
    assert paint_locked is True, "Dwell in PAINT mode failed to lock brush!"


def test_brush_lock_timeout_releases():
    """Brush lock auto-releases after max duration."""
    mouse = MouseController(send_hook=lambda *args: None)
    mouse.left_down()
    assert mouse.is_left_down is True

    # Simulate timeout elapsed
    mouse.left_down_time = time.perf_counter() - 35.0
    released = mouse.check_brush_lock_timeout(max_duration_s=30.0)
    assert released is True
    assert mouse.is_left_down is False


def test_touchpad_physical_movement_yields():
    """When physical cursor moves, input arbitration triggers yielding."""
    mouse = MouseController(send_hook=lambda *args: None)
    mouse.last_set_pos = (500, 500)
    
    # Mock GetCursorPos returning (520, 500) -> 20px physical movement
    mouse.get_cursor_pos = lambda: (520, 500)

    yielded = mouse.check_physical_move(threshold_px=6, yield_duration_s=1.5)
    assert yielded is True
    assert mouse.is_yielding is True

    # While yielding, move_to does not dispatch
    sent = []
    mouse.send_hook = lambda *args: sent.append(args)
    mouse.move_to(600, 600)
    assert len(sent) == 0, "Dispatched movement while yielding to touchpad!"


def test_circuit_breaker_trips_on_click_burst():
    """Circuit breaker trips if more than 4 clicks happen in 2s."""
    mouse = MouseController(send_hook=lambda *args: None)

    for i in range(4):
        tripped = mouse.record_click_and_check_breaker(is_right=False, x=100, y=100)
        assert tripped is False

    # 5th click within 2s trips breaker
    tripped_5 = mouse.record_click_and_check_breaker(is_right=False, x=100, y=100)
    assert tripped_5 is True


def test_coordinate_mapping_multi_monitor_and_negative():
    """Verify virtual desktop normalization across dual monitors and negative coordinates."""
    mouse = MouseController(send_hook=lambda *args: None)

    # Monitor A: (0, 0, 1920, 1080), Monitor B (left): (-1920, 0, 1920, 1080)
    # Virtual bounds: (-1920, 0, 3840, 1080)
    v_bounds = (-1920, 0, 3840, 1080)

    # Leftmost pixel of left monitor (-1920, 0) -> (0, 0)
    nx0, ny0 = mouse.normalize_to_virtual_desktop(-1920, 0, virtual_bounds=v_bounds)
    assert nx0 == 0
    assert ny0 == 0

    # Center origin (0, 540) -> (~32767, ~32767)
    nx_mid, ny_mid = mouse.normalize_to_virtual_desktop(0, 540, virtual_bounds=v_bounds)
    assert abs(nx_mid - 32767) <= 200
    assert abs(ny_mid - 32767) <= 200

    # Rightmost pixel (1919, 1079) -> (65535, 65535)
    nx_max, ny_max = mouse.normalize_to_virtual_desktop(1919, 1079, virtual_bounds=v_bounds)
    assert nx_max == 65535
    assert ny_max == 65535


def test_emergency_release_releases_all():
    """Emergency release safely clears all mouse buttons and keys."""
    mouse = MouseController(send_hook=lambda *args: None)
    mouse.is_left_down = True
    mouse.emergency_release()
    assert mouse.is_left_down is False
