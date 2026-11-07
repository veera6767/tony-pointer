"""
Tony Pointer - Mode & Keyboard Navigation State Machine
Orchestrates transitions between POINTER, KEYBOARD, and PAINT modes.
Tracks keyboard sub-states (MAIN vs SYMBOLS zone, row index, 4-key window index),
detects normalized whole-hand swipes for row/window sliding door navigation,
and manages open-palm / fist mode entry and exit.
"""

import collections
import enum
import math
import time
from typing import Dict, Optional, Tuple

from keyboard_layout import KeyboardLayoutManager, KeyboardWindow, Zone
from tracker import HandFrame


class AppMode(enum.Enum):
    POINTER = "POINTER"
    KEYBOARD = "KEYBOARD"
    PAINT = "PAINT"


class ModeManager:
    """
    State machine for Tony Pointer operation modes and keyboard sub-states.
    """

    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        self.settings = settings
        self.layout_manager = layout_manager

        # Current Operating Mode
        self.mode = AppMode.POINTER

        # Keyboard Sub-State
        self.active_zone = Zone.MAIN
        self.row_idx = 3         # Default to Home Row (Row 4: A S D F G H J K L ; ' Enter)
        self.window_idx = 0      # Default to [A S D F]

        # Memory of window positions per zone
        self.zone_window_memory: Dict[Zone, Dict[int, int]] = {
            Zone.MAIN: {r: 0 for r in range(6)},
            Zone.SYMBOLS: {r: 0 for r in range(6)},
        }

        # Mode Transition Timers (Hysteresis)
        self.open_palm_start: Optional[float] = None
        self.open_palm_progress: float = 0.0

        self.fist_start: Optional[float] = None
        self.fist_progress: float = 0.0

        # Whole-Hand Swipe Tracker ("Sliding Door" Gesture)
        # Tracks neutral hand position and displacement velocity
        self.neutral_hand_center: Optional[Tuple[float, float]] = None
        self.last_swipe_time: float = 0.0
        self.hand_returned_to_neutral: bool = True
        self.bounce_active: bool = False

    def get_current_window(self) -> KeyboardWindow:
        return self.layout_manager.get_window(self.active_zone, self.row_idx, self.window_idx)

    def toggle_keyboard_mode(self, force_state: Optional[bool] = None) -> bool:
        """Toggles between POINTER and KEYBOARD mode."""
        if force_state is not None:
            self.mode = AppMode.KEYBOARD if force_state else AppMode.POINTER
        else:
            self.mode = AppMode.KEYBOARD if self.mode != AppMode.KEYBOARD else AppMode.POINTER

        self.neutral_hand_center = None
        self.open_palm_start = None
        self.open_palm_progress = 0.0
        self.fist_start = None
        self.fist_progress = 0.0
        return self.mode == AppMode.KEYBOARD

    def toggle_zone(self):
        """Shortcut (Ctrl+Alt+S) toggles between MAIN and SYMBOLS zones."""
        new_zone = Zone.SYMBOLS if self.active_zone == Zone.MAIN else Zone.MAIN
        self._switch_zone(new_zone)

    def _switch_zone(self, new_zone: Zone):
        # Save current window index for current zone and row
        self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx

        # Switch zone
        self.active_zone = new_zone

        # Restore window index in new zone (clamped to valid bounds)
        saved_idx = self.zone_window_memory[new_zone].get(self.row_idx, 0)
        max_idx = self.layout_manager.get_max_window_idx(new_zone, self.row_idx)
        self.window_idx = max(0, min(max_idx, saved_idx))

    def evaluate_mode_transitions(self, hand: Optional[HandFrame], is_pointing: bool, is_fist: bool, is_open_palm: bool) -> Tuple[AppMode, float]:
        """
        Monitors pose holds to transition between POINTER and KEYBOARD modes:
        - Holding OPEN PALM ~0.5s opens KEYBOARD mode.
        - Holding FIST ~0.5s or switching to POINTING closes KEYBOARD mode.
        """
        now = time.perf_counter()

        if hand is None:
            self.open_palm_start = None
            self.open_palm_progress = 0.0
            self.fist_start = None
            self.fist_progress = 0.0
            return self.mode, 0.0

        if self.mode == AppMode.POINTER:
            # Check Open Palm to ENGAGE Keyboard Mode
            if is_open_palm:
                if self.open_palm_start is None:
                    self.open_palm_start = now
                    self.open_palm_progress = 0.0

                elapsed = now - self.open_palm_start
                hold_target = self.settings.keyboard.open_palm_hold_s
                self.open_palm_progress = min(1.0, elapsed / hold_target)

                if elapsed >= hold_target:
                    self.mode = AppMode.KEYBOARD
                    self.neutral_hand_center = None
                    self.open_palm_start = None
                    self.open_palm_progress = 0.0
                    return self.mode, 1.0

                return self.mode, self.open_palm_progress
            else:
                self.open_palm_start = None
                self.open_palm_progress = 0.0

        elif self.mode == AppMode.KEYBOARD:
            # Check Fist or Pointing pose to DISENGAGE Keyboard Mode
            if is_pointing:
                # Instant return to pointing cursor
                self.mode = AppMode.POINTER
                return self.mode, 0.0

            if is_fist:
                if self.fist_start is None:
                    self.fist_start = now
                    self.fist_progress = 0.0

                elapsed = now - self.fist_start
                hold_target = self.settings.keyboard.fist_close_hold_s
                self.fist_progress = min(1.0, elapsed / hold_target)

                if elapsed >= hold_target:
                    self.mode = AppMode.POINTER
                    self.fist_start = None
                    self.fist_progress = 0.0
                    return self.mode, 1.0

                return self.mode, self.fist_progress
            else:
                self.fist_start = None
                self.fist_progress = 0.0

        return self.mode, 0.0

    def evaluate_swipes(self, hand: Optional[HandFrame], tap_in_progress: bool) -> Optional[str]:
        """
        Detects deliberate whole-hand swipes:
        - "UP": Jumps one row up
        - "DOWN": Jumps one row down
        - "LEFT": Hops window left / crosses into MAIN from SYMBOLS
        - "RIGHT": Hops window right / crosses into SYMBOLS from MAIN
        """
        if hand is None or self.mode != AppMode.KEYBOARD or tap_in_progress:
            self.neutral_hand_center = None
            return None

        now = time.perf_counter()
        cooldown = self.settings.keyboard.swipe_cooldown_ms / 1000.0

        # Hand center: average of wrist (0) and MCPs (5, 9, 13, 17)
        wrist = hand.get(0)
        mcp9 = hand.get(9)
        cx = (wrist.x + mcp9.x) / 2.0
        cy = (wrist.y + mcp9.y) / 2.0

        # Normalize displacement by hand size
        hand_size = max(0.04, hand.distance_3d(0, 9))

        if self.neutral_hand_center is None:
            self.neutral_hand_center = (cx, cy)
            self.hand_returned_to_neutral = True
            return None

        dx = (cx - self.neutral_hand_center[0]) / hand_size
        dy = (cy - self.neutral_hand_center[1]) / hand_size
        dist = math.hypot(dx, dy)

        # Check return to neutral hysteresis (< 0.25 hand size)
        if dist < 0.22:
            self.hand_returned_to_neutral = True
            # Update neutral anchor slowly
            self.neutral_hand_center = (
                self.neutral_hand_center[0] * 0.9 + cx * 0.1,
                self.neutral_hand_center[1] * 0.9 + cy * 0.1,
            )
            self.bounce_active = False

        if not self.hand_returned_to_neutral or (now - self.last_swipe_time < cooldown):
            return None

        swipe_threshold = self.settings.keyboard.swipe_threshold

        # Vertical Swipes (Up / Down Rows)
        if abs(dy) > abs(dx) and abs(dy) >= swipe_threshold:
            if dy < 0:
                # Swipe UP -> Row decreases (Row 6 -> 5 -> 4 -> 3 -> 2 -> 1)
                self.row_idx = max(0, self.row_idx - 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "UP"
            else:
                # Swipe DOWN -> Row increases (Row 1 -> 2 -> 3 -> 4 -> 5 -> 6)
                self.row_idx = min(5, self.row_idx + 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "DOWN"

        # Horizontal Swipes (Left / Right Windows & Zone Crossing)
        if abs(dx) > abs(dy) and abs(dx) >= swipe_threshold:
            if dx > 0:
                # Swipe RIGHT
                max_w = self.layout_manager.get_max_window_idx(self.active_zone, self.row_idx)
                if self.window_idx < max_w:
                    # Hop to next window in current zone
                    self.window_idx += 1
                    self._record_swipe(now)
                    return "RIGHT"
                elif self.active_zone == Zone.MAIN and self.settings.keyboard.symbols_panel_enabled:
                    # Cross into SYMBOLS panel on first window of same row!
                    self._switch_zone(Zone.SYMBOLS)
                    self.window_idx = 0
                    self._record_swipe(now)
                    return "CROSS_INTO_SYMBOLS"
                else:
                    # Last window of SYMBOLS -> Bounce feedback
                    self.bounce_active = True
                    self._record_swipe(now)
                    return "BOUNCE"
            else:
                # Swipe LEFT
                if self.window_idx > 0:
                    self.window_idx -= 1
                    self._record_swipe(now)
                    return "LEFT"
                elif self.active_zone == Zone.SYMBOLS:
                    # Cross back into MAIN keyboard on LAST window of same row!
                    self._switch_zone(Zone.MAIN)
                    self.window_idx = self.layout_manager.get_max_window_idx(Zone.MAIN, self.row_idx)
                    self._record_swipe(now)
                    return "CROSS_INTO_MAIN"
                else:
                    self.bounce_active = True
                    self._record_swipe(now)
                    return "BOUNCE"

        return None

    def _record_swipe(self, timestamp: float):
        self.last_swipe_time = timestamp
        self.hand_returned_to_neutral = False

    def _clamp_window_to_current_row(self):
        max_idx = self.layout_manager.get_max_window_idx(self.active_zone, self.row_idx)
        self.window_idx = max(0, min(max_idx, self.window_idx))
