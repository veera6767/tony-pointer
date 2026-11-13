"""
Pointer V - Synthetic Landmark Scenario Generator for Deterministic Soak & Freeze Testing
Feeds synthetic HandFrame objects at 30/60 FPS into vision pipeline:
- pointing_circle: Index finger tracing smooth circle across active region
- pointing_still: Stationary index finger
- open_palm_hold: Cycles open palm (keyboard engage) and fist (keyboard exit)
- index_taps: Rapid curl-and-release air taps
- swipes: Hand translating across directional swipe thresholds
- mixed: Sequential execution of all scenarios in an automated loop
"""

import math
import time
from typing import Optional

from tracker import HandFrame
from recorder import create_synthetic_hand


class SyntheticScenarioGenerator:
    """Produces synthetic HandFrame objects based on elapsed time and scenario name."""

    def __init__(self, scenario: str = "mixed"):
        self.scenario = scenario
        self.start_time = time.perf_counter()

    def get_hand_frame(self) -> Optional[HandFrame]:
        now = time.perf_counter()
        elapsed = now - self.start_time

        if self.scenario == "pointing_still":
            return create_synthetic_hand(
                wrist_xy=(0.5, 0.7),
                index_curl_angle=170.0,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )

        elif self.scenario == "pointing_circle":
            t = elapsed * 2.0 * math.pi / 3.0  # Full circle every 3 seconds
            cx = 0.5 + 0.20 * math.cos(t)
            cy = 0.5 + 0.15 * math.sin(t)
            return create_synthetic_hand(
                wrist_xy=(cx, cy + 0.2),
                index_curl_angle=170.0,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )

        elif self.scenario == "open_palm_hold":
            # 1.2s open palm, then 1.8s closed fist
            cycle = elapsed % 3.0
            if cycle < 1.2:
                # Open palm: all 5 fingers straight and spread
                return create_synthetic_hand(
                    wrist_xy=(0.5, 0.6),
                    index_curl_angle=175.0,
                    middle_curl_angle=175.0,
                    ring_curl_angle=175.0,
                    pinky_curl_angle=175.0,
                    thumb_curl=0.0
                )
            else:
                # Closed fist
                return create_synthetic_hand(
                    wrist_xy=(0.5, 0.6),
                    index_curl_angle=60.0,
                    middle_curl_angle=60.0,
                    ring_curl_angle=60.0,
                    pinky_curl_angle=60.0,
                    thumb_curl=1.0
                )

        elif self.scenario == "index_taps":
            # Cycles flex and release every 0.4s
            phase = (elapsed % 0.40) / 0.40
            # Dip down to 100 deg and rebound to 165 deg
            angle = 100.0 + 65.0 * (math.sin(phase * 2.0 * math.pi) * 0.5 + 0.5)
            return create_synthetic_hand(
                wrist_xy=(0.5, 0.6),
                index_curl_angle=angle,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )

        elif self.scenario == "swipes":
            # Moves wrist horizontally and vertically
            cycle = (elapsed % 4.0)
            if cycle < 1.0:
                wx = 0.3 + 0.4 * (cycle / 1.0)  # Left to right
                wy = 0.6
            elif cycle < 2.0:
                wx = 0.7 - 0.4 * ((cycle - 1.0) / 1.0)  # Right to left
                wy = 0.6
            elif cycle < 3.0:
                wx = 0.5
                wy = 0.4 + 0.4 * ((cycle - 2.0) / 1.0)  # Up to down
            else:
                wx = 0.5
                wy = 0.8 - 0.4 * ((cycle - 3.0) / 1.0)  # Down to up
            return create_synthetic_hand(
                wrist_xy=(wx, wy),
                index_curl_angle=170.0,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )

        elif self.scenario == "mixed":
            # 5s pointing_circle -> 3s open_palm_hold -> 3s index_taps -> 3s swipes (14s total cycle)
            mod = elapsed % 14.0
            if mod < 5.0:
                t = mod * 2.0 * math.pi / 2.5
                cx = 0.5 + 0.20 * math.cos(t)
                cy = 0.5 + 0.15 * math.sin(t)
                return create_synthetic_hand(
                    wrist_xy=(cx, cy + 0.2),
                    index_curl_angle=170.0,
                    middle_curl_angle=70.0,
                    ring_curl_angle=70.0,
                    pinky_curl_angle=70.0,
                    thumb_curl=1.0
                )
            elif mod < 8.0:
                sub = mod - 5.0
                if sub < 1.2:
                    return create_synthetic_hand(
                        wrist_xy=(0.5, 0.6),
                        index_curl_angle=175.0,
                        middle_curl_angle=175.0,
                        ring_curl_angle=175.0,
                        pinky_curl_angle=175.0,
                        thumb_curl=0.0
                    )
                else:
                    return create_synthetic_hand(
                        wrist_xy=(0.5, 0.6),
                        index_curl_angle=60.0,
                        middle_curl_angle=60.0,
                        ring_curl_angle=60.0,
                        pinky_curl_angle=60.0,
                        thumb_curl=1.0
                    )
            elif mod < 11.0:
                sub = mod - 8.0
                phase = (sub % 0.40) / 0.40
                angle = 100.0 + 65.0 * (math.sin(phase * 2.0 * math.pi) * 0.5 + 0.5)
                return create_synthetic_hand(
                    wrist_xy=(0.5, 0.6),
                    index_curl_angle=angle,
                    middle_curl_angle=70.0,
                    ring_curl_angle=70.0,
                    pinky_curl_angle=70.0,
                    thumb_curl=1.0
                )
            else:
                sub = mod - 11.0
                wx = 0.3 + 0.4 * (sub / 3.0)
                return create_synthetic_hand(
                    wrist_xy=(wx, 0.6),
                    index_curl_angle=170.0,
                    middle_curl_angle=70.0,
                    ring_curl_angle=70.0,
                    pinky_curl_angle=70.0,
                    thumb_curl=1.0
                )

        return None
