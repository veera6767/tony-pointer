"""
Pointer V - Mode & Keyboard Navigation State Machine
Orchestrates transitions between POINTER, KEYBOARD, and PAINT modes.
Tracks keyboard sub-states (MAIN vs SYMBOLS zone, row index, 4-key window index),
detects normalized whole-hand swipes for row/window sliding door navigation,
manages dominant hand calibration (Left/Right/Auto), and remembers per-zone window positions.
"""

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
    State machine for Pointer V operation modes and keyboard sub-states.
    """

    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        self.settings = settings
        self.layout_manager = layout_manager

        # Current Operating Mode
        self.mode = AppMode.POINTER
        self.is_paused = False

        # Keyboard Sub-State
        self.active_zone = Zone.MAIN
        self.row_idx = 3         # Default to Home Row (Row 4: A S D F G H J K L ; ' Enter)
        self.window_idx = 0      # Default to [A S D F]

        # Memory of window positions per zone per row
        self.zone_window_memory: Dict[Zone, Dict[int, int]] = {
            Zone.MAIN: {r: 0 for r in range(6)},
            Zone.SYMBOLS: {r: 0 for r in range(6)},
        }

        # Mode Transition Timers
        self.open_palm_start: Optional[float] = None
        self.open_palm_progress: float = 0.0

        self.fist_start: Optional[float] = None
        self.fist_progress: float = 0.0

        # Whole-Hand Swipe Tracker ("Sliding Door" Gesture)
        self.neutral_hand_center: Optional[Tuple[float, float]] = None
        self.last_swipe_time: float = 0.0
        self.hand_returned_to_neutral: bool = True
        self.bounce_active: bool = False
        self.swipe_progress: float = 0.0
        self.swipe_direction: str = ""
        self.keyboard_entry_time: float = 0.0

    def get_current_window(self) -> KeyboardWindow:
        return self.layout_manager.get_window(self.active_zone, self.row_idx, self.window_idx)

    def toggle_pause(self, force_state: Optional[bool] = None) -> bool:
        """Toggles tracking pause (output suppressed, preview stays alive)."""
        if force_state is not None:
            self.is_paused = force_state
        else:
            self.is_paused = not self.is_paused
        return self.is_paused

    def toggle_keyboard_mode(self, force_state: Optional[bool] = None) -> bool:
        """Toggles between POINTER and KEYBOARD mode."""
        if force_state is not None:
            self.mode = AppMode.KEYBOARD if force_state else AppMode.POINTER
        else:
            self.mode = AppMode.KEYBOARD if self.mode != AppMode.KEYBOARD else AppMode.POINTER

        if self.mode == AppMode.KEYBOARD:
            self.keyboard_entry_time = time.perf_counter()

        self.neutral_hand_center = None
        self.swipe_progress = 0.0
        self.swipe_direction = ""
        self.open_palm_start = None
        self.open_palm_progress = 0.0
        self.fist_start = None
        self.fist_progress = 0.0
        return self.mode == AppMode.KEYBOARD

    def toggle_zone(self):
        """Shortcut (Ctrl+Alt+S) toggles between MAIN and SYMBOLS zones, remembering window."""
        new_zone = Zone.SYMBOLS if self.active_zone == Zone.MAIN else Zone.MAIN
        self._switch_zone(new_zone, restore_memory=True)

    def _switch_zone(self, new_zone: Zone, restore_memory: bool = True):
        # Save current window index for current zone and row
        self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx

        # Switch zone
        self.active_zone = new_zone

        # Restore window index in new zone
        if restore_memory:
            saved_idx = self.zone_window_memory[new_zone].get(self.row_idx, 0)
            max_idx = self.layout_manager.get_max_window_idx(new_zone, self.row_idx)
            self.window_idx = max(0, min(max_idx, saved_idx))

    def get_effective_handedness(self, hand: Optional[HandFrame]) -> str:
        """Resolves whether Left or Right hand rules apply."""
        dominant = getattr(self.settings.gestures, "dominant_hand", "auto").lower()
        if dominant in ("right", "left"):
            return dominant.capitalize()
        if hand and hand.handedness:
            return hand.handedness
        return "Right"

    def evaluate_mode_transitions(
        self,
        hand: Optional[HandFrame],
        is_pointing: bool,
        is_fist: bool,
        is_open_palm: bool
    ) -> Tuple[AppMode, float]:
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
            if is_open_palm:
                if self.open_palm_start is None:
                    self.open_palm_start = now
                    self.open_palm_progress = 0.0

                elapsed = now - self.open_palm_start
                hold_target = self.settings.keyboard.open_palm_hold_s
                self.open_palm_progress = min(1.0, elapsed / hold_target)

                if elapsed >= hold_target:
                    self.mode = AppMode.KEYBOARD
                    self.keyboard_entry_time = now
                    self.neutral_hand_center = None
                    self.swipe_progress = 0.0
                    self.swipe_direction = ""
                    self.open_palm_start = None
                    self.open_palm_progress = 0.0
                    return self.mode, 1.0

                return self.mode, self.open_palm_progress
            else:
                self.open_palm_start = None
                self.open_palm_progress = 0.0

        elif self.mode == AppMode.KEYBOARD:
            # Phase D fix: Mode hysteresis - do NOT exit keyboard mode on brief pointing gestures
            # during typing. Require deliberate fist hold to close keyboard.
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

    def evaluate_swipes(
        self,
        hand: Optional[HandFrame],
        tap_in_progress: bool = False,
        any_finger_curling: bool = False
    ) -> Optional[str]:
        """
        Detects deliberate whole-hand swipes:
        - Exactly ONE jump per swipe (cooldown ~300ms plus neutral-return)
        - "UP": Jumps one row up
        - "DOWN": Jumps one row down
        - "LEFT": Hops window left / crosses into MAIN from SYMBOLS
        - "RIGHT": Hops window right / crosses into SYMBOLS from MAIN
        Works reliably for either hand. Suppressed if any finger tap or curl is active.
        """
        if hand is None or self.mode != AppMode.KEYBOARD or tap_in_progress or any_finger_curling:
            self.neutral_hand_center = None
            self.swipe_progress = 0.0
            self.swipe_direction = ""
            return None

        now = time.perf_counter()
        cooldown = self.settings.keyboard.swipe_cooldown_ms / 1000.0

        # Phase D fix: Compute true palm centroid from wrist (0) and 4 MCP knuckles (5, 9, 13, 17)
        # to ensure swipes reflect whole-hand translation, eliminating palm tilt artifacts.
        p0 = hand.get(0)
        p5 = hand.get(5)
        p9 = hand.get(9)
        p13 = hand.get(13)
        p17 = hand.get(17)
        cx = (p0.x + p5.x + p9.x + p13.x + p17.x) / 5.0
        cy = (p0.y + p5.y + p9.y + p13.y + p17.y) / 5.0

        hand_size = max(0.04, (hand.distance_3d(0, 9) + hand.distance_3d(5, 17)) / 2.0)

        if self.neutral_hand_center is None:
            self.neutral_hand_center = (cx, cy)
            self.hand_returned_to_neutral = True
            self.swipe_progress = 0.0
            self.swipe_direction = ""
            return None

        dx = (cx - self.neutral_hand_center[0]) / hand_size
        dy = (cy - self.neutral_hand_center[1]) / hand_size
        dist = math.hypot(dx, dy)
        swipe_threshold = self.settings.keyboard.swipe_threshold

        # Update live swipe progress and direction for HUD feedback
        if dist > 0.05:
            self.swipe_progress = min(1.0, dist / max(0.01, swipe_threshold))
            if abs(dy) > abs(dx):
                self.swipe_direction = "UP" if dy < 0 else "DOWN"
            else:
                self.swipe_direction = "RIGHT" if dx > 0 else "LEFT"
        else:
            self.swipe_progress = 0.0
            self.swipe_direction = ""

        # Neutral return detection (< 0.22 hand size or after timeout)
        if dist < 0.22:
            self.hand_returned_to_neutral = True
            self.neutral_hand_center = (cx, cy)
            self.bounce_active = False
            self.swipe_progress = 0.0
            self.swipe_direction = ""
            return None
        elif self.last_swipe_time > 0 and (now - self.last_swipe_time) > 0.85:
            # Drift recovery if hand stays in a new resting position
            self.hand_returned_to_neutral = True
            self.neutral_hand_center = (cx, cy)
            self.bounce_active = False
            self.swipe_progress = 0.0
            self.swipe_direction = ""
            return None

        if not self.hand_returned_to_neutral or (now - self.last_swipe_time < cooldown):
            return None

        swipe_threshold = self.settings.keyboard.swipe_threshold

        # Vertical Swipes (Up / Down Rows)
        if abs(dy) > abs(dx) and abs(dy) >= swipe_threshold:
            if dy < 0:
                self.row_idx = max(0, self.row_idx - 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "UP"
            else:
                self.row_idx = min(5, self.row_idx + 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "DOWN"

        # Horizontal Swipes (Left / Right Windows & Zone Crossing)
        # Right always crosses into Symbols; Left always crosses into Main
        if abs(dx) > abs(dy) and abs(dx) >= swipe_threshold:
            if dx > 0:
                # Swipe RIGHT
                max_w = self.layout_manager.get_max_window_idx(self.active_zone, self.row_idx)
                if self.window_idx < max_w:
                    self.window_idx += 1
                    self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx
                    self._record_swipe(now)
                    return "RIGHT"
                elif self.active_zone == Zone.MAIN and self.settings.keyboard.symbols_panel_enabled:
                    # Cross into SYMBOLS panel at window 0
                    self._switch_zone(Zone.SYMBOLS, restore_memory=False)
                    self.window_idx = 0
                    self.zone_window_memory[Zone.SYMBOLS][self.row_idx] = 0
                    self._record_swipe(now)
                    return "CROSS_INTO_SYMBOLS"
                else:
                    self.bounce_active = True
                    self._record_swipe(now)
                    return "BOUNCE"
            else:
                # Swipe LEFT
                if self.window_idx > 0:
                    self.window_idx -= 1
                    self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx
                    self._record_swipe(now)
                    return "LEFT"
                elif self.active_zone == Zone.SYMBOLS:
                    # Cross back into MAIN keyboard at LAST window of row
                    self._switch_zone(Zone.MAIN, restore_memory=False)
                    self.window_idx = self.layout_manager.get_max_window_idx(Zone.MAIN, self.row_idx)
                    self.zone_window_memory[Zone.MAIN][self.row_idx] = self.window_idx
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
        self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx
