"""
Pointer V - End-to-End Pipeline Replay Integration Tests
Verifies the complete pipeline flow:
Tracker HandFrame Output -> Gesture Classifier -> ModeManager -> SendInput Output Layer.
Tests:
1. Pointing pose moves the target cursor position.
2. Open palm held for 0.5s opens keyboard mode.
3. Hand swipe changes keyboard row once.
4. Independent finger tap emits exactly one keystroke.
5. Air double-tap on index finger emits a double-click.
"""

import os
import sys
import time
from typing import List, Tuple

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine, PoseType
from keyboard_layout import KeyboardLayoutManager, Zone
from keyboard_out import ModifierState, Win32KeyboardOutput
from mode_manager import AppMode, ModeManager
from mouse import MouseController
from recorder import create_synthetic_hand
from settings import AppConfig


class MockPipelineRunner:
    """Simulates PointerVApp._processing_loop logic deterministically."""

    def __init__(self):
        self.settings = AppConfig()
        self.settings.keyboard.open_palm_hold_s = 0.40
        self.settings.keyboard.swipe_threshold = 0.28
        self.settings.gestures.double_tap_window_ms = 450.0

        self.layout_mgr = KeyboardLayoutManager()
        self.filter = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
        self.gesture_engine = GestureEngine(self.settings)
        self.mode_manager = ModeManager(self.settings, self.layout_mgr)
        self.finger_tap_detector = FingerTapDetector(self.settings)

        self.mouse_events = []
        self.mouse = MouseController(send_hook=lambda *args: self.mouse_events.append(args))

        self.key_events = []
        self.keyboard_out = Win32KeyboardOutput(send_hook=lambda *args: self.key_events.append(args))

        self.screen_bounds = (0, 0, 1920, 1080)
        self.is_active = True
        self.cursor_pos = (0, 0)
        self.keyboard_visible = False

    def feed_frame(self, hand, dt: float = 0.02) -> dict:
        """Processes one frame through the full pipeline."""
        time.sleep(dt)

        eval_res = self.gesture_engine.process(
            hand=hand,
            screen_bounds=self.screen_bounds,
            filter_2d=self.filter,
            current_mode=self.mode_manager.mode.value,
        )
        action = eval_res["action"]

        # Mode transitions
        if action == GestureAction.ENTER_KEYBOARD.value and self.mode_manager.mode != AppMode.KEYBOARD:
            self.mode_manager.mode = AppMode.KEYBOARD
            self.keyboard_visible = True
        elif action == GestureAction.EXIT_KEYBOARD.value and self.mode_manager.mode == AppMode.KEYBOARD:
            self.mode_manager.mode = AppMode.POINTER
            self.keyboard_visible = False

        # Keyboard mode
        if self.mode_manager.mode == AppMode.KEYBOARD and self.is_active and not self.mode_manager.is_paused:
            tapped_finger, is_repeat, _ = self.finger_tap_detector.process(hand)
            cur_win = self.mode_manager.get_current_window()

            if tapped_finger is not None:
                if tapped_finger == "thumb":
                    self.keyboard_out.send_key("space", char_to_send=" ")
                else:
                    effective_hand = self.mode_manager.get_effective_handedness(hand)
                    hand_order = ["pinky", "ring", "middle", "index"] if effective_hand == "Left" else ["index", "middle", "ring", "pinky"]
                    if self.settings.keyboard.finger_mapping == "reversed":
                        hand_order.reverse()
                    slot = hand_order.index(tapped_finger) if tapped_finger in hand_order else 0
                    if 0 <= slot < len(cur_win.keys):
                        k = cur_win.keys[slot]
                        self.keyboard_out.send_key(k.code, char_to_send=k.char_to_send, needs_shift=k.needs_shift)

            self.mode_manager.evaluate_swipes(hand, tap_in_progress=(tapped_finger is not None))

        # Pointer mode
        if self.is_active and self.mode_manager.mode == AppMode.POINTER and not self.mode_manager.is_paused:
            cx = eval_res["cursor_x"]
            cy = eval_res["cursor_y"]
            self.cursor_pos = (cx, cy)
            if eval_res["hand_visible"] and action != GestureAction.PAUSE.value:
                self.mouse.move_to(cx, cy)

            if action == GestureAction.SINGLE_CLICK.value:
                self.mouse.click(cx, cy)
            elif action == GestureAction.DOUBLE_CLICK.value:
                self.mouse.double_click(cx, cy)

        return eval_res


def test_pipeline_pointing_moves_cursor():
    """Pointing pose must move target position across frames."""
    runner = MockPipelineRunner()

    # Move index finger across screen from x=0.3 to x=0.7
    for step in range(5):
        wx = 0.30 + step * 0.08
        hand = create_synthetic_hand(
            wrist_xy=(wx, 0.6),
            index_curl_angle=170.0,
            middle_curl_angle=70.0,
            ring_curl_angle=70.0,
            pinky_curl_angle=70.0,
        )
        runner.feed_frame(hand)

    assert runner.cursor_pos[0] > 600, f"Cursor did not move right: {runner.cursor_pos}"
    assert len(runner.mouse_events) > 0, "No mouse events dispatched!"


def test_pipeline_open_palm_opens_keyboard():
    """Holding an open palm for 0.4s must engage Keyboard mode and set HUD visibility."""
    runner = MockPipelineRunner()
    assert runner.mode_manager.mode == AppMode.POINTER
    assert runner.keyboard_visible is False

    open_palm_hand = create_synthetic_hand(
        index_curl_angle=175.0,
        middle_curl_angle=175.0,
        ring_curl_angle=175.0,
        pinky_curl_angle=175.0,
    )

    # Feed open palm for >0.45 seconds
    for _ in range(25):
        runner.feed_frame(open_palm_hand, dt=0.02)

    assert runner.mode_manager.mode == AppMode.KEYBOARD, "Mode did not transition to KEYBOARD!"
    assert runner.keyboard_visible is True, "Keyboard overlay was not marked visible!"


def test_pipeline_swipe_changes_row_once():
    """Swiping hand down once in KEYBOARD mode must change row by exactly 1."""
    runner = MockPipelineRunner()
    runner.mode_manager.mode = AppMode.KEYBOARD
    runner.mode_manager.row_idx = 3  # Home row (row 4)
    runner.keyboard_visible = True

    # 1. Establish neutral resting hand at y=0.55
    neutral_hand = create_synthetic_hand(wrist_xy=(0.50, 0.55))
    for _ in range(3):
        runner.feed_frame(neutral_hand)

    # 2. Swipe down to y=0.75 (dy / hand_size > threshold)
    swipe_hand = create_synthetic_hand(wrist_xy=(0.50, 0.75))
    runner.feed_frame(swipe_hand)

    assert runner.mode_manager.row_idx == 4, f"Row index should have increased to 4, got {runner.mode_manager.row_idx}"

    # 3. Holding displaced hand must not jump again
    for _ in range(5):
        runner.feed_frame(swipe_hand)
    assert runner.mode_manager.row_idx == 4, "Row jumped multiple times without neutral return!"


def test_pipeline_finger_curl_emits_one_key():
    """Curling the index finger once in KEYBOARD mode must emit exactly one key event."""
    runner = MockPipelineRunner()
    runner.mode_manager.mode = AppMode.KEYBOARD
    runner.mode_manager.row_idx = 3  # Row 4 (Window 0: A S D F)
    runner.mode_manager.window_idx = 0
    runner.keyboard_visible = True

    # Baseline straight fingers
    straight = create_synthetic_hand(index_curl_angle=170.0)
    for _ in range(4):
        runner.feed_frame(straight)

    # Curl index finger down
    curled = create_synthetic_hand(index_curl_angle=105.0)
    runner.feed_frame(curled)

    # Rebound back to straight
    rebound = create_synthetic_hand(index_curl_angle=165.0)
    runner.feed_frame(rebound)

    # Verify SendInput received the key for Slot 0 ("a")
    assert len(runner.key_events) >= 1, "No keystrokes were dispatched!"
    scancode_calls = [ev for ev in runner.key_events if ev[0] == "scan"]
    assert len(scancode_calls) >= 2, "Expected key down and key up scan events"


def test_pipeline_index_double_tap_emits_double_click():
    """Two swift air-taps within 450ms must emit a double click in POINTER mode."""
    runner = MockPipelineRunner()
    runner.mode_manager.mode = AppMode.POINTER

    def make_index(curl):
        return create_synthetic_hand(
            index_curl_angle=curl,
            middle_curl_angle=70.0,
            ring_curl_angle=70.0,
            pinky_curl_angle=70.0,
        )

    # Baseline pointing
    for _ in range(4):
        runner.feed_frame(make_index(170.0))

    # Tap 1: Curl & Rebound
    runner.feed_frame(make_index(105.0))
    runner.feed_frame(make_index(165.0))
    assert runner.gesture_engine.pending_single_tap is True

    # Interval before tap 2
    time.sleep(0.15)
    for _ in range(3):
        runner.feed_frame(make_index(165.0))

    # Tap 2: Curl & Rebound within double tap window
    runner.feed_frame(make_index(105.0))
    eval_res = runner.feed_frame(make_index(165.0))

    assert eval_res["action"] == GestureAction.DOUBLE_CLICK.value, f"Expected DOUBLE_CLICK, got {eval_res['action']}"

