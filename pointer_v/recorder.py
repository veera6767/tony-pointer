"""
Pointer V - Landmark Stream Recorder & Replay Engine
Records raw 3D landmark coordinates (21 points per frame with timestamps, zero image data)
and replays them through the gesture engine without requiring a webcam.
Provides synthetic generator utilities for unit testing and offline development.
"""

import json
import math
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from tracker import HandFrame, LandmarkPoint


class LandmarkRecorder:
    """Records raw HandFrame sequences in memory and exports to JSON."""

    def __init__(self):
        self.is_recording = False
        self.frames: List[Dict] = []
        self.start_time: float = 0.0

    def start(self):
        self.frames = []
        self.start_time = time.perf_counter()
        self.is_recording = True

    def record_frame(self, hand: Optional[HandFrame]):
        if not self.is_recording:
            return

        now = time.perf_counter()
        elapsed_ms = int((now - self.start_time) * 1000)

        if hand is None:
            self.frames.append({
                "time_ms": elapsed_ms,
                "present": False,
                "landmarks": [],
                "handedness": "Right"
            })
            return

        points = [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in hand.landmarks]
        self.frames.append({
            "time_ms": elapsed_ms,
            "present": True,
            "landmarks": points,
            "handedness": hand.handedness
        })

    def stop(self) -> int:
        self.is_recording = False
        return len(self.frames)

    def save_to_file(self, filepath: str) -> bool:
        try:
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "2.0.0",
                    "frame_count": len(self.frames),
                    "frames": self.frames,
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"[Recorder] Error saving replay file: {e}")
            return False


class LandmarkReplayer:
    """Loads recorded landmark JSON files and feeds them back as HandFrame streams."""

    def __init__(self, filepath: Optional[str] = None):
        self.frames: List[Dict] = []
        if filepath:
            self.load_from_file(filepath)

    def load_from_file(self, filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.frames = data.get("frames", [])
            return True
        except Exception as e:
            print(f"[Replayer] Error loading replay file: {e}")
            return False

    def get_frames(self) -> List[Optional[HandFrame]]:
        result = []
        for item in self.frames:
            if not item.get("present", False):
                result.append(None)
                continue

            pts = item.get("landmarks", [])
            lm_objs = [LandmarkPoint(p[0], p[1], p[2]) for p in pts]
            hf = HandFrame(
                landmarks=lm_objs,
                timestamp_ms=item.get("time_ms", 0),
                handedness=item.get("handedness", "Right"),
            )
            result.append(hf)
        return result


def create_synthetic_hand(
    wrist_xy: Tuple[float, float] = (0.5, 0.7),
    index_curl_angle: float = 170.0,
    middle_curl_angle: float = 170.0,
    ring_curl_angle: float = 170.0,
    pinky_curl_angle: float = 170.0,
    thumb_curl: float = 0.0,
    is_left_hand: bool = False,
    timestamp_ms: int = 0
) -> HandFrame:
    """Generates a mathematically plausible 21-point HandFrame for testing."""
    wx, wy = wrist_xy
    hand_sign = -1.0 if is_left_hand else 1.0

    landmarks = [LandmarkPoint(wx, wy, 0.0)] # 0: Wrist

    # Thumb: 1, 2, 3, 4
    landmarks.append(LandmarkPoint(wx - 0.04 * hand_sign, wy - 0.03, 0.0))
    landmarks.append(LandmarkPoint(wx - 0.07 * hand_sign, wy - 0.06, 0.0))
    landmarks.append(LandmarkPoint(wx - 0.09 * hand_sign, wy - 0.09, 0.0))
    # Tip 4
    landmarks.append(LandmarkPoint(wx - (0.10 - thumb_curl * 0.04) * hand_sign, wy - (0.12 - thumb_curl * 0.05), 0.0))

    # Helper to calculate joint coordinates given extension angle
    # 180 deg = straight up, 90 deg = bent forward
    def _make_finger(mcp_x, mcp_y, curl_angle):
        pts = [LandmarkPoint(mcp_x, mcp_y, 0.0)] # MCP
        # PIP
        pip_y = mcp_y - 0.07
        pts.append(LandmarkPoint(mcp_x, pip_y, 0.0))
        # DIP
        rad = math.radians(180.0 - curl_angle)
        dip_x = mcp_x + math.sin(rad) * 0.05
        dip_y = pip_y - math.cos(rad) * 0.05
        pts.append(LandmarkPoint(dip_x, dip_y, 0.0))
        # TIP
        tip_x = dip_x + math.sin(rad * 1.5) * 0.04
        tip_y = dip_y - math.cos(rad * 1.5) * 0.04
        pts.append(LandmarkPoint(tip_x, tip_y, 0.0))
        return pts

    # Index: 5, 6, 7, 8
    landmarks.extend(_make_finger(wx - 0.03 * hand_sign, wy - 0.12, index_curl_angle))
    # Middle: 9, 10, 11, 12
    landmarks.extend(_make_finger(wx, wy - 0.13, middle_curl_angle))
    # Ring: 13, 14, 15, 16
    landmarks.extend(_make_finger(wx + 0.03 * hand_sign, wy - 0.12, ring_curl_angle))
    # Pinky: 17, 18, 19, 20
    landmarks.extend(_make_finger(wx + 0.06 * hand_sign, wy - 0.10, pinky_curl_angle))

    return HandFrame(
        landmarks=landmarks,
        timestamp_ms=timestamp_ms,
        handedness="Left" if is_left_hand else "Right"
    )
