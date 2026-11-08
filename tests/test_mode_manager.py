"""
Unit tests for ModeManager swipe state machine, neutral-return hysteresis,
zone crossing, per-zone window memory, and dominant hand support.
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from keyboard_layout import KeyboardLayoutManager, Zone
from mode_manager import AppMode, ModeManager
from recorder import create_synthetic_hand
from settings import AppConfig


def test_swipe_state_machine_one_jump_per_swipe():
    """Swiping once must trigger exactly one jump, not repeat continuously until returning to neutral."""
    cfg = AppConfig()
    cfg.keyboard.swipe_threshold = 0.30
    cfg.keyboard.swipe_cooldown_ms = 300.0

    layout_mgr = KeyboardLayoutManager()
    mgr = ModeManager(cfg, layout_mgr)
    mgr.mode = AppMode.KEYBOARD
    mgr.row_idx = 3 # Row 4
    mgr.window_idx = 0

    # 1. Establish neutral center (wrist at 0.5, 0.7)
    hand_neutral = create_synthetic_hand(wrist_xy=(0.5, 0.7))
    res1 = mgr.evaluate_swipes(hand_neutral, tap_in_progress=False)
    assert res1 is None # Establishing neutral

    # 2. Swipe DOWN (move hand down to y=0.85, dy ~ 0.15 / hand_size > 0.30)
    hand_down = create_synthetic_hand(wrist_xy=(0.5, 0.85))
    res2 = mgr.evaluate_swipes(hand_down, tap_in_progress=False)
    assert res2 == "DOWN"
    assert mgr.row_idx == 4 # One jump down

    # 3. Holding hand in the same position without neutral return MUST NOT trigger another jump!
    time.sleep(0.05)
    res3 = mgr.evaluate_swipes(hand_down, tap_in_progress=False)
    assert res3 is None, "Swipe re-triggered before returning to neutral!"

    # Even after cooldown expires, holding hand displaced must not trigger jump
    time.sleep(0.35)
    res4 = mgr.evaluate_swipes(hand_down, tap_in_progress=False)
    assert res4 is None, "Swipe re-triggered without neutral return!"

    # 4. Return to neutral (< 0.22 hand size)
    res5 = mgr.evaluate_swipes(hand_neutral, tap_in_progress=False)
    assert res5 is None
    assert mgr.hand_returned_to_neutral is True

    # 5. Now a second deliberate swipe UP can trigger
    hand_up = create_synthetic_hand(wrist_xy=(0.5, 0.55))
    res6 = mgr.evaluate_swipes(hand_up, tap_in_progress=False)
    assert res6 == "UP"
    assert mgr.row_idx == 3


def test_zone_crossing_and_window_memory():
    """Crossing into Symbols from last window of Main, and returning remembers each zone's state."""
    cfg = AppConfig()
    cfg.keyboard.symbols_panel_enabled = True
    cfg.keyboard.swipe_threshold = 0.30

    layout_mgr = KeyboardLayoutManager()
    mgr = ModeManager(cfg, layout_mgr)
    mgr.mode = AppMode.KEYBOARD
    mgr.row_idx = 3
    mgr.active_zone = Zone.MAIN

    # Move to the last window of Row 3
    max_w = layout_mgr.get_max_window_idx(Zone.MAIN, 3)
    mgr.window_idx = max_w

    # Establish neutral
    hand_neutral = create_synthetic_hand(wrist_xy=(0.5, 0.7))
    mgr.evaluate_swipes(hand_neutral, tap_in_progress=False)

    # Swipe RIGHT from last window of MAIN -> CROSS_INTO_SYMBOLS
    hand_right = create_synthetic_hand(wrist_xy=(0.65, 0.7))
    action = mgr.evaluate_swipes(hand_right, tap_in_progress=False)
    assert action == "CROSS_INTO_SYMBOLS"
    assert mgr.active_zone == Zone.SYMBOLS
    assert mgr.window_idx == 0

    # Return to neutral
    mgr.evaluate_swipes(hand_neutral, tap_in_progress=False)
    time.sleep(0.35)

    # Swipe LEFT from first window of SYMBOLS -> CROSS_INTO_MAIN
    hand_left = create_synthetic_hand(wrist_xy=(0.35, 0.7))
    action2 = mgr.evaluate_swipes(hand_left, tap_in_progress=False)
    assert action2 == "CROSS_INTO_MAIN"
    assert mgr.active_zone == Zone.MAIN
    assert mgr.window_idx == max_w

    # Test Ctrl+Alt+S toggle_zone memory
    mgr.window_idx = 1
    mgr.toggle_zone() # Switch to Symbols
    assert mgr.active_zone == Zone.SYMBOLS

    mgr.window_idx = 0
    mgr.toggle_zone() # Switch back to Main
    assert mgr.active_zone == Zone.MAIN
    assert mgr.window_idx == 1, "Main zone did not remember its window index!"


def test_left_and_right_handedness_resolution():
    """ModeManager correctly identifies effective handedness for Auto, Left, and Right settings."""
    cfg = AppConfig()
    layout_mgr = KeyboardLayoutManager()
    mgr = ModeManager(cfg, layout_mgr)

    hand_right = create_synthetic_hand(is_left_hand=False)
    hand_left = create_synthetic_hand(is_left_hand=True)

    # Auto mode: follows HandFrame
    cfg.gestures.dominant_hand = "auto"
    assert mgr.get_effective_handedness(hand_right) == "Right"
    assert mgr.get_effective_handedness(hand_left) == "Left"

    # Forced Left mode
    cfg.gestures.dominant_hand = "left"
    assert mgr.get_effective_handedness(hand_right) == "Left"

    # Forced Right mode
    cfg.gestures.dominant_hand = "right"
    assert mgr.get_effective_handedness(hand_left) == "Right"


def test_left_hand_swipes_and_zone_crossing():
    """Left hand must follow the exact same intuitive navigation: swipe right enters Symbols, swipe left enters Main."""
    cfg = AppConfig()
    cfg.gestures.dominant_hand = "left"
    cfg.keyboard.symbols_panel_enabled = True
    cfg.keyboard.swipe_threshold = 0.30

    layout_mgr = KeyboardLayoutManager()
    mgr = ModeManager(cfg, layout_mgr)
    mgr.mode = AppMode.KEYBOARD
    mgr.row_idx = 3
    mgr.active_zone = Zone.MAIN
    max_w = layout_mgr.get_max_window_idx(Zone.MAIN, 3)
    mgr.window_idx = max_w

    # Left hand in neutral
    left_neutral = create_synthetic_hand(wrist_xy=(0.5, 0.7), is_left_hand=True)
    mgr.evaluate_swipes(left_neutral, tap_in_progress=False)

    # Swipe RIGHT with left hand across boundary into Symbols
    left_swipe_right = create_synthetic_hand(wrist_xy=(0.65, 0.7), is_left_hand=True)
    action = mgr.evaluate_swipes(left_swipe_right, tap_in_progress=False)
    assert action == "CROSS_INTO_SYMBOLS"
    assert mgr.active_zone == Zone.SYMBOLS
    assert mgr.window_idx == 0

    # Neutral return
    mgr.evaluate_swipes(left_neutral, tap_in_progress=False)
    time.sleep(0.35)

    # Swipe LEFT with left hand back into Main
    left_swipe_left = create_synthetic_hand(wrist_xy=(0.35, 0.7), is_left_hand=True)
    action2 = mgr.evaluate_swipes(left_swipe_left, tap_in_progress=False)
    assert action2 == "CROSS_INTO_MAIN"
    assert mgr.active_zone == Zone.MAIN
    assert mgr.window_idx == max_w


def test_finger_visual_order_left_vs_right_hand():
    """Visual mapping: Right hand index is slot 0, Left hand index is slot 3 (aligned with visual screen position)."""
    hand_right = create_synthetic_hand(is_left_hand=False)
    hand_left = create_synthetic_hand(is_left_hand=True)

    finger_names = ["index", "middle", "ring", "pinky"]
    tip_indices = [8, 12, 16, 20]

    # Right hand: sorted by x gives [index, middle, ring, pinky]
    r_pairs = [(finger_names[i], hand_right.get(tip_indices[i]).x) for i in range(4)]
    r_pairs.sort(key=lambda p: p[1])
    r_sorted = [p[0] for p in r_pairs]
    assert r_sorted.index("index") == 0
    assert r_sorted.index("pinky") == 3

    # Left hand: sorted by x gives [pinky, ring, middle, index]
    l_pairs = [(finger_names[i], hand_left.get(tip_indices[i]).x) for i in range(4)]
    l_pairs.sort(key=lambda p: p[1])
    l_sorted = [p[0] for p in l_pairs]
    assert l_sorted.index("pinky") == 0
    assert l_sorted.index("index") == 3


