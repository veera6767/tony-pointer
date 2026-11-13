"""
Pointer V - Independent Per-Finger Air Tap & Hold-Repeat Detector
Tracks 5 distinct fingers (Index, Middle, Ring, Pinky, and Thumb).
Detects swift curl-and-release flexions with anatomical calibration
(ring and pinky have adjusted thresholds) and supports hold-to-repeat,
plus an inter-finger neighbor lockout to prevent false cross-fires.
"""

import collections
import time
from typing import Dict, Optional, Tuple

from tracker import HandFrame


class FingerTapDetector:
    """
    Analyzes per-finger joint angle and tip-to-palm displacement trajectories
    to identify rapid, independent finger air-taps.
    """

    def __init__(self, settings):
        self.settings = settings

        # Finger definitions: (name, tip_idx, dip_idx, pip_idx, mcp_idx)
        self.fingers = [
            ("index", 8, 7, 6, 5),
            ("middle", 12, 11, 10, 9),
            ("ring", 16, 15, 14, 13),
            ("pinky", 20, 19, 18, 17),
        ]

        # Historical trajectories: finger_name -> deque of (timestamp, angle, norm_dist)
        self.history: Dict[str, collections.deque] = {
            f[0]: collections.deque(maxlen=15) for f in self.fingers
        }
        self.thumb_history: collections.deque = collections.deque(maxlen=15)

        # Timers and state
        self.last_tap_time: Dict[str, float] = {f[0]: 0.0 for f in self.fingers}
        self.last_tap_time["thumb"] = 0.0

        # Global neighbor lockout across all fingers
        self.last_any_tap_time: float = 0.0

        self.curl_hold_start: Dict[str, Optional[float]] = {f[0]: None for f in self.fingers}
        self.curl_hold_start["thumb"] = None

        self.last_repeat_time: Dict[str, float] = {f[0]: 0.0 for f in self.fingers}
        self.last_repeat_time["thumb"] = 0.0

        # Debug curl values for UI sliders and calibration
        self.current_curls: Dict[str, float] = {
            "thumb": 0.0, "index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0
        }

    def compute_curls(self, hand: Optional[HandFrame]) -> Dict[str, float]:
        """Calculates normalized curl metrics (0.0 = straight, 1.0 = fully curled) for all 5 fingers."""
        if hand is None:
            return dict(self.current_curls)
        for f_name, tip_idx, dip_idx, pip_idx, mcp_idx in self.fingers:
            pip_angle = hand.angle_deg(mcp_idx, pip_idx, tip_idx)
            curl_metric = max(0.0, min(1.0, (170.0 - pip_angle) / 70.0))
            self.current_curls[f_name] = curl_metric
        thumb_angle = hand.angle_deg(1, 2, 4)
        thumb_curl = max(0.0, min(1.0, (160.0 - thumb_angle) / 55.0))
        self.current_curls["thumb"] = thumb_curl
        return dict(self.current_curls)

    def process(self, hand: Optional[HandFrame]) -> Tuple[Optional[str], bool, Dict[str, float]]:
        """
        Evaluates frame for finger taps or hold-repeats.
        Returns:
            (tapped_finger_name, is_repeat, current_curls_dict)
            where tapped_finger_name is "index", "middle", "ring", "pinky", "thumb", or None.
        """
        if hand is None:
            self._reset_holds()
            return None, False, self.current_curls

        now = time.perf_counter()

        # Measure hand scale for distance normalization (wrist 0 to middle MCP 9)
        hand_scale = max(0.04, hand.distance_3d(0, 9))

        # 1. Evaluate 4 main typing fingers (Index, Middle, Ring, Pinky)
        detected_event = None
        is_repeat = False

        neighbor_lockout = getattr(self.settings.keyboard, "neighbor_lockout_ms", 160.0) / 1000.0

        for f_name, tip, dip, pip, mcp in self.fingers:
            # Measure PIP joint angle (180 deg = straight, < 120 deg = curled)
            pip_angle = hand.angle_deg(mcp, pip, tip)

            # Measure fingertip to wrist distance normalized by hand size
            norm_tip_dist = hand.distance_3d(0, tip) / hand_scale

            # Record curl value for live debug bar (0.0 = completely straight, 1.0 = fully curled)
            curl_metric = max(0.0, min(1.0, (170.0 - pip_angle) / 70.0))
            self.current_curls[f_name] = curl_metric

            # Append to history
            hist = self.history[f_name]
            hist.append((now, pip_angle, norm_tip_dist))

            if len(hist) < 4:
                continue

            # Per-finger sensitivity threshold (Ring and Pinky are weaker anatomically)
            sens_factor = getattr(self.settings.keyboard, f"{f_name}_sensitivity", 1.0)
            base_threshold = 20.0 / max(0.4, sens_factor)

            # Check recent trajectory within last 250ms
            recent = [entry for entry in hist if (now - entry[0]) <= 0.25]
            if len(recent) < 3:
                continue

            angles = [r[1] for r in recent]
            min_ang = min(angles)
            max_ang = max(angles)
            curr_ang = angles[-1]

            # A tap is a rapid curl (dip in angle) followed by rebound towards straight (>130 deg)
            rebounded = (curr_ang > min_ang + 14.0) and (curr_ang > 130.0)
            angle_delta = max_ang - min_ang

            cooldown = self.settings.keyboard.tap_cooldown_ms / 1000.0

            # Tap Trigger (enforcing neighbor lockout so adjacent fingers never double-trigger)
            if (
                angle_delta >= base_threshold
                and rebounded
                and (now - self.last_tap_time[f_name] > cooldown)
                and (now - self.last_any_tap_time > neighbor_lockout)
                and detected_event is None
            ):
                self.last_tap_time[f_name] = now
                self.last_any_tap_time = now
                detected_event = f_name
                is_repeat = False
                self.curl_hold_start[f_name] = None
                continue

            # Hold-to-Repeat Trigger (e.g. holding Backspace or Arrows)
            is_curled = curr_ang < 120.0
            if is_curled:
                hold_start = self.curl_hold_start[f_name]
                if hold_start is None:
                    self.curl_hold_start[f_name] = now
                else:
                    hold_duration = now - hold_start
                    repeat_delay = self.settings.keyboard.key_repeat_delay_s
                    repeat_interval = self.settings.keyboard.key_repeat_interval_s

                    if hold_duration >= repeat_delay and (now - self.last_repeat_time[f_name] > repeat_interval):
                        self.last_repeat_time[f_name] = now
                        detected_event = f_name
                        is_repeat = True
            else:
                self.curl_hold_start[f_name] = None

        # 2. Evaluate Thumb (Space key trigger)
        if self.settings.keyboard.thumb_is_space:
            thumb_angle = hand.angle_deg(1, 2, 4)
            thumb_dist = hand.distance_3d(0, 4) / hand_scale
            thumb_curl = max(0.0, min(1.0, (160.0 - thumb_angle) / 55.0))
            self.current_curls["thumb"] = thumb_curl

            self.thumb_history.append((now, thumb_angle, thumb_dist))
            if len(self.thumb_history) >= 4 and detected_event is None:
                recent_thumb = [e for e in self.thumb_history if (now - e[0]) <= 0.25]
                if len(recent_thumb) >= 3:
                    t_angles = [e[1] for e in recent_thumb]
                    t_min = min(t_angles)
                    t_max = max(t_angles)
                    t_curr = t_angles[-1]
                    t_rebound = (t_curr > t_min + 12.0) and (t_curr > 125.0)

                    cooldown = self.settings.keyboard.tap_cooldown_ms / 1000.0
                    if (
                        (t_max - t_min >= 18.0)
                        and t_rebound
                        and (now - self.last_tap_time["thumb"] > cooldown)
                        and (now - self.last_any_tap_time > neighbor_lockout)
                    ):
                        self.last_tap_time["thumb"] = now
                        self.last_any_tap_time = now
                        detected_event = "thumb"
                        is_repeat = False

        return detected_event, is_repeat, self.current_curls

    def _reset_holds(self):
        for f in self.curl_hold_start:
            self.curl_hold_start[f] = None
