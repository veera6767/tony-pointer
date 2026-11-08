"""
Pointer V - Gesture Recognition Engine
Identifies air double-taps, single clicks, two-finger right click, two-finger scroll,
pause fist-hold (1.5s countdown), brush lock dwell/pinch, and auto-pause timeouts
with high spatial precision, dominant hand awareness, and anti-jitter lookback buffer.
"""

import collections
import enum
import math
import time
from typing import Callable, Deque, Dict, Optional, Tuple

from filters import PositionHistoryBuffer, apply_acceleration
from tracker import HandFrame


class PoseType(enum.Enum):
    UNKNOWN = "UNKNOWN"
    OPEN_PALM = "OPEN_PALM"          # Rest pose: engages keyboard mode or pauses cursor
    POINTING = "POINTING"            # Cursor active: index extended, others curled
    TWO_FINGER = "TWO_FINGER"        # Index + Middle extended: scroll or right-click
    PINCH = "PINCH"                  # Index tip touches Thumb tip: brush lock
    FIST = "FIST"                    # All fingers curled: pause in POINTER or exit in KEYBOARD


class GestureAction(enum.Enum):
    NONE = "NONE"
    MOVE = "MOVE"
    SINGLE_CLICK = "SINGLE_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    SCROLL = "SCROLL"
    BRUSH_LOCK_TOGGLE = "BRUSH_LOCK_TOGGLE"
    BRUSH_UNLOCK = "BRUSH_UNLOCK"
    PAUSE = "PAUSE"
    PAUSE_TOGGLE = "PAUSE_TOGGLE"
    AUTO_PAUSE = "AUTO_PAUSE"
    ENTER_KEYBOARD = "ENTER_KEYBOARD"
    EXIT_KEYBOARD = "EXIT_KEYBOARD"


class GestureEngine:
    """
    Mathematical and temporal state machine for gesture recognition.
    Processes HandFrame landmarks at 30-60 FPS.
    """

    def __init__(self, settings):
        self.settings = settings
        self.history_buffer = PositionHistoryBuffer(max_duration_s=0.6)

        # Pose and action states
        self.current_pose = PoseType.UNKNOWN
        self.active_action = GestureAction.NONE
        self.brush_locked = False

        # Air-tap detection variables
        self.index_angle_history: Deque[Tuple[float, float]] = collections.deque(maxlen=15)
        self.last_tap_time: float = 0.0
        self.pending_single_tap: bool = False
        self.tap_frozen_pos: Optional[Tuple[int, int]] = None

        # Two-finger hold (Right Click)
        self.two_finger_start_time: Optional[float] = None
        self.two_finger_right_clicked: bool = False
        self.last_two_finger_y: Optional[float] = None

        # Dwell Brush Lock
        self.dwell_start_time: Optional[float] = None
        self.dwell_anchor_pos: Optional[Tuple[float, float]] = None
        self.dwell_progress: float = 0.0

        # Open Palm Hold for Keyboard Mode entry
        self.open_palm_start_time: Optional[float] = None
        self.open_palm_progress: float = 0.0

        # Fist Hold for Keyboard Mode exit or Pause gesture in POINTER mode
        self.fist_start_time: Optional[float] = None
        self.fist_progress: float = 0.0
        self.fist_pause_start_time: Optional[float] = None
        self.fist_pause_progress: float = 0.0

        # Pinch Brush Lock
        self.last_pinch_time: float = 0.0
        self.is_pinching: bool = False

        # Hand presence and safety watchdog
        self.last_hand_time: float = 0.0
        self.auto_paused_emitted: bool = False

    def classify_pose(self, hand: HandFrame) -> PoseType:
        """
        Determines the current hand posture based on joint extension angles
        and relative fingertip-to-wrist Euclidean distances.
        Works identically for right or left hands.
        """
        # Landmark indices:
        # Wrist: 0
        # Thumb: 1, 2, 3, 4
        # Index: 5(MCP), 6(PIP), 7(DIP), 8(TIP)
        # Middle: 9, 10, 11, 12
        # Ring: 13, 14, 15, 16
        # Pinky: 17, 18, 19, 20

        dist_wrist_index_tip = hand.distance_3d(0, 8)
        dist_wrist_index_pip = hand.distance_3d(0, 6)
        index_extended = dist_wrist_index_tip > dist_wrist_index_pip * 1.10 or hand.angle_deg(5, 6, 8) > 135.0

        dist_wrist_middle_tip = hand.distance_3d(0, 12)
        dist_wrist_middle_pip = hand.distance_3d(0, 10)
        middle_extended = dist_wrist_middle_tip > dist_wrist_middle_pip * 1.10 or hand.angle_deg(9, 10, 12) > 135.0

        dist_wrist_ring_tip = hand.distance_3d(0, 16)
        dist_wrist_ring_pip = hand.distance_3d(0, 14)
        ring_extended = dist_wrist_ring_tip > dist_wrist_ring_pip * 1.05 or hand.angle_deg(13, 14, 16) > 130.0

        dist_wrist_pinky_tip = hand.distance_3d(0, 20)
        dist_wrist_pinky_pip = hand.distance_3d(0, 18)
        pinky_extended = dist_wrist_pinky_tip > dist_wrist_pinky_pip * 1.05 or hand.angle_deg(17, 18, 20) > 130.0

        # Check Pinch: distance between thumb tip (4) and index tip (8)
        pinch_dist = hand.distance_3d(4, 8)
        if pinch_dist < self.settings.gestures.pinch_threshold:
            return PoseType.PINCH

        # Open Palm: all four main fingers extended
        if index_extended and middle_extended and ring_extended and pinky_extended:
            return PoseType.OPEN_PALM

        # Two-Finger: Index and Middle extended, Ring and Pinky curled
        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return PoseType.TWO_FINGER

        # Pointing: Index extended, Middle, Ring, Pinky curled
        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return PoseType.POINTING

        # Fist: all curled
        if not index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return PoseType.FIST

        return PoseType.UNKNOWN

    def update_dwell_lock(self, norm_x: float, norm_y: float, now: float) -> Tuple[bool, float]:
        """
        Dwell Brush Lock: holding the index finger stationary for ~0.6s
        fills a radial progress ring and locks the mouse button.
        """
        if self.dwell_anchor_pos is None or self.dwell_start_time is None:
            self.dwell_anchor_pos = (norm_x, norm_y)
            self.dwell_start_time = now
            self.dwell_progress = 0.0
            return False, 0.0

        dx = norm_x - self.dwell_anchor_pos[0]
        dy = norm_y - self.dwell_anchor_pos[1]
        drift = math.hypot(dx, dy)
        allowed_drift = 0.02

        if drift > allowed_drift:
            self.dwell_anchor_pos = (norm_x, norm_y)
            self.dwell_start_time = now
            self.dwell_progress = 0.0
            return False, 0.0

        elapsed = now - self.dwell_start_time
        target = self.settings.gestures.dwell_lock_time_s
        self.dwell_progress = min(1.0, elapsed / target)

        if elapsed >= target:
            self.dwell_start_time = None
            self.dwell_anchor_pos = None
            self.dwell_progress = 0.0
            return True, 1.0

        return False, self.dwell_progress

    def detect_air_tap(self, hand: HandFrame, now: float) -> bool:
        """
        Detects an "air tap" motion:
        A swift curl-and-release flexure of the index finger (PIP/DIP angle).
        Angular velocity dips sharply and rebounds within 120-250ms.
        """
        if len(self.index_angle_history) < 5:
            return False

        angles = [a for t, a in self.index_angle_history if now - t <= 0.30]
        if len(angles) < 4:
            return False

        min_angle = min(angles)
        max_angle = max(angles)
        angle_delta = max_angle - min_angle
        current_angle = angles[-1]
        rebounded = current_angle > (min_angle + 16.0) and current_angle > 135.0

        cooldown_s = self.settings.gestures.tap_cooldown_ms / 1000.0
        if angle_delta >= 18.0 and rebounded and (now - self.last_tap_time > cooldown_s):
            self.last_tap_time = now
            return True

        return False

    def process(
        self,
        hand: Optional[HandFrame],
        screen_bounds: Tuple[int, int, int, int],
        filter_2d,
        current_mode: str = "POINTER"
    ) -> Dict:
        """
        Main frame evaluation routine.
        Returns state dictionary with target cursor coordinates, actions, and overlay HUD hints.
        """
        now = time.perf_counter()
        vx, vy, vw, vh = screen_bounds

        result = {
            "pose": PoseType.UNKNOWN.value,
            "action": GestureAction.NONE.value,
            "cursor_x": 0,
            "cursor_y": 0,
            "dwell_progress": self.dwell_progress,
            "open_palm_progress": self.open_palm_progress,
            "fist_progress": self.fist_progress,
            "fist_pause_progress": self.fist_pause_progress,
            "brush_locked": self.brush_locked,
            "hand_visible": False,
            "status_text": "SEARCHING FOR HAND",
        }

        # 1. Safety Check: Hand Lost
        if hand is None:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            self.open_palm_start_time = None
            self.open_palm_progress = 0.0
            self.fist_start_time = None
            self.fist_progress = 0.0
            self.fist_pause_start_time = None
            self.fist_pause_progress = 0.0
            self.two_finger_start_time = None

            if self.last_hand_time > 0:
                elapsed_lost = now - self.last_hand_time
                if elapsed_lost > (self.settings.gestures.hand_timeout_ms / 1000.0):
                    result["action"] = GestureAction.PAUSE.value
                    result["status_text"] = "TRACKING LOST"

                # Auto-release brush lock if hand lost for > 1.0s
                if self.brush_locked and elapsed_lost > self.settings.gestures.safety_release_timeout_s:
                    self.brush_locked = False
                    result["action"] = GestureAction.BRUSH_UNLOCK.value
                    result["brush_locked"] = False
                    result["status_text"] = "SAFETY AUTO-RELEASE"

                # Auto-pause watchdog after N seconds (default 10s)
                auto_pause_timeout = getattr(self.settings.gestures, "auto_pause_timeout_s", 10.0)
                if elapsed_lost >= auto_pause_timeout and not self.auto_paused_emitted:
                    self.auto_paused_emitted = True
                    result["action"] = GestureAction.AUTO_PAUSE.value
                    result["status_text"] = f"AUTO-PAUSED ({int(auto_pause_timeout)}s NO HAND)"

            return result

        # Hand detected!
        self.last_hand_time = now
        self.auto_paused_emitted = False
        result["hand_visible"] = True

        pose = self.classify_pose(hand)
        self.current_pose = pose
        result["pose"] = pose.value

        # Record index PIP joint angle on every frame for air-tap flexion trajectory analysis
        flex_angle = hand.angle_deg(5, 6, 8)
        self.index_angle_history.append((now, flex_angle))

        # In KEYBOARD mode, check for Fist close hold or return to pointing
        if current_mode == "KEYBOARD":
            result["action"] = GestureAction.PAUSE.value
            self.fist_pause_start_time = None
            self.fist_pause_progress = 0.0

            if pose == PoseType.POINTING:
                result["action"] = GestureAction.EXIT_KEYBOARD.value
                result["status_text"] = "EXIT KEYBOARD (POINTING)"
                return result

            if pose == PoseType.FIST:
                if self.fist_start_time is None:
                    self.fist_start_time = now
                    self.fist_progress = 0.0
                elapsed = now - self.fist_start_time
                target = self.settings.keyboard.fist_close_hold_s
                self.fist_progress = min(1.0, elapsed / target)
                result["fist_progress"] = self.fist_progress
                if elapsed >= target:
                    self.fist_start_time = None
                    self.fist_progress = 0.0
                    result["action"] = GestureAction.EXIT_KEYBOARD.value
                    result["status_text"] = "EXIT KEYBOARD (FIST)"
                else:
                    result["status_text"] = f"HOLD FIST TO CLOSE ({int(self.fist_progress * 100)}%)"
                return result
            else:
                self.fist_start_time = None
                self.fist_progress = 0.0
                result["status_text"] = "AIR KEYBOARD ACTIVE"
                return result

        # 2. Extract Index Fingertip (Landmark 8) for cursor positioning
        index_tip = hand.get(8)
        norm_x = index_tip.x
        norm_y = index_tip.y

        # Map Active Region to Target Screen
        ar = self.settings.active_region
        clamped_x = max(ar.x_min, min(ar.x_max, norm_x))
        clamped_y = max(ar.y_min, min(ar.y_max, norm_y))

        span_x = max(0.01, ar.x_max - ar.x_min)
        span_y = max(0.01, ar.y_max - ar.y_min)
        remapped_x = (clamped_x - ar.x_min) / span_x
        remapped_y = (clamped_y - ar.y_min) / span_y

        raw_screen_x = vx + int(remapped_x * vw)
        raw_screen_y = vy + int(remapped_y * vh)

        # One Euro Filter
        filt_x, filt_y = filter_2d.filter(raw_screen_x, raw_screen_y, now)
        screen_x = int(round(filt_x))
        screen_y = int(round(filt_y))

        self.history_buffer.append(screen_x, screen_y, now)
        result["cursor_x"] = screen_x
        result["cursor_y"] = screen_y

        # 3. Handle Closed Fist in POINTER Mode: 1.5s hold to Pause
        if pose == PoseType.FIST:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            self.two_finger_start_time = None
            self.open_palm_start_time = None

            if self.fist_pause_start_time is None:
                self.fist_pause_start_time = now
                self.fist_pause_progress = 0.0

            elapsed = now - self.fist_pause_start_time
            target = getattr(self.settings.gestures, "fist_pause_hold_s", 1.50)
            self.fist_pause_progress = min(1.0, elapsed / target)
            result["fist_pause_progress"] = self.fist_pause_progress

            if elapsed >= target:
                self.fist_pause_start_time = None
                self.fist_pause_progress = 0.0
                result["action"] = GestureAction.PAUSE_TOGGLE.value
                result["status_text"] = "PAUSED (FIST GESTURE)"
                return result

            result["action"] = GestureAction.PAUSE.value
            result["status_text"] = f"HOLD FIST TO PAUSE ({int(self.fist_pause_progress * 100)}%)"
            return result
        else:
            self.fist_pause_start_time = None
            self.fist_pause_progress = 0.0

        # 4. Handle Open Palm: Keyboard Entry
        if pose == PoseType.OPEN_PALM:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            self.two_finger_start_time = None

            if self.brush_locked:
                self.brush_locked = False
                result["action"] = GestureAction.BRUSH_UNLOCK.value
                result["brush_locked"] = False
                result["status_text"] = "BRUSH RELEASED"
                return result

            if self.open_palm_start_time is None:
                self.open_palm_start_time = now
                self.open_palm_progress = 0.0

            elapsed = now - self.open_palm_start_time
            target = self.settings.keyboard.open_palm_hold_s
            self.open_palm_progress = min(1.0, elapsed / target)
            result["open_palm_progress"] = self.open_palm_progress

            if elapsed >= target:
                self.open_palm_start_time = None
                self.open_palm_progress = 0.0
                result["action"] = GestureAction.ENTER_KEYBOARD.value
                result["status_text"] = "AIR KEYBOARD ENGAGED"
                return result

            result["action"] = GestureAction.PAUSE.value
            result["status_text"] = f"HOLD OPEN PALM: KEYBOARD ({int(self.open_palm_progress * 100)}%)"
            return result
        else:
            self.open_palm_start_time = None
            self.open_palm_progress = 0.0

        # 5. Handle Pinch (Brush Lock Toggle)
        if pose == PoseType.PINCH:
            if not self.is_pinching and (now - self.last_pinch_time > 0.4):
                self.is_pinching = True
                self.last_pinch_time = now
                self.brush_locked = not self.brush_locked
                result["action"] = (
                    GestureAction.BRUSH_LOCK_TOGGLE.value
                    if self.brush_locked
                    else GestureAction.BRUSH_UNLOCK.value
                )
                result["brush_locked"] = self.brush_locked
                result["status_text"] = "BRUSH LOCKED" if self.brush_locked else "BRUSH RELEASED"
                return result
        else:
            self.is_pinching = False

        # 6. Handle Two-Finger Gestures (Scroll & Right Click)
        if pose == PoseType.TWO_FINGER:
            self.dwell_start_time = None
            self.dwell_progress = 0.0

            if self.two_finger_start_time is None:
                self.two_finger_start_time = now
                self.two_finger_right_clicked = False
                self.last_two_finger_y = (hand.get(8).y + hand.get(12).y) / 2.0
                result["status_text"] = "TWO-FINGER GESTURE"
                return result

            elapsed_two_finger = now - self.two_finger_start_time
            current_two_finger_y = (hand.get(8).y + hand.get(12).y) / 2.0

            delta_y = current_two_finger_y - (self.last_two_finger_y or current_two_finger_y)
            self.last_two_finger_y = current_two_finger_y

            if abs(delta_y) > 0.008:
                scroll_amount = -int(delta_y * 100 * self.settings.gestures.scroll_sensitivity)
                result["action"] = GestureAction.SCROLL.value
                result["scroll_delta"] = scroll_amount
                result["status_text"] = f"SCROLLING ({scroll_amount:+d})"
                return result

            if (
                elapsed_two_finger >= self.settings.gestures.right_click_hold_s
                and not self.two_finger_right_clicked
            ):
                self.two_finger_right_clicked = True
                result["action"] = GestureAction.RIGHT_CLICK.value
                result["status_text"] = "RIGHT CLICK"
                return result

            result["status_text"] = "HOLD FOR RIGHT CLICK"
            return result
        else:
            self.two_finger_start_time = None

        # 7. Pointing Pose: Air Tap Clicks & Dwell Brush Lock
        if pose == PoseType.POINTING:
            if not self.brush_locked:
                locked, progress = self.update_dwell_lock(norm_x, norm_y, now)
                result["dwell_progress"] = progress
                if locked:
                    self.brush_locked = True
                    result["action"] = GestureAction.BRUSH_LOCK_TOGGLE.value
                    result["brush_locked"] = True
                    result["status_text"] = "BRUSH LOCKED (DWELL)"
                    return result

            tap_detected = self.detect_air_tap(hand, now)
            if tap_detected:
                stable_pos = self.history_buffer.get_position_at_lookback(150.0)
                if stable_pos:
                    result["cursor_x"] = int(stable_pos[0])
                    result["cursor_y"] = int(stable_pos[1])

                double_tap_window_s = self.settings.gestures.double_tap_window_ms / 1000.0

                if self.pending_single_tap and (now - self.last_tap_time <= double_tap_window_s):
                    self.pending_single_tap = False
                    result["action"] = GestureAction.DOUBLE_CLICK.value
                    result["status_text"] = "DOUBLE CLICK (AIR TAP)"
                    return result
                else:
                    self.pending_single_tap = True
                    self.tap_frozen_pos = (result["cursor_x"], result["cursor_y"])

            double_tap_window_s = self.settings.gestures.double_tap_window_ms / 1000.0
            if (
                self.pending_single_tap
                and (now - self.last_tap_time > double_tap_window_s)
                and self.settings.gestures.single_click_enabled
            ):
                self.pending_single_tap = False
                result["action"] = GestureAction.SINGLE_CLICK.value
                if self.tap_frozen_pos:
                    result["cursor_x"] = self.tap_frozen_pos[0]
                    result["cursor_y"] = self.tap_frozen_pos[1]
                result["status_text"] = "SINGLE CLICK"
                return result

            result["action"] = GestureAction.MOVE.value
            result["status_text"] = "BRUSH PAINTING" if self.brush_locked else "POINTING"
            return result

        return result
