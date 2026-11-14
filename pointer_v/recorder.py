"""
Pointer V - Landmark Stream Recorder & Replay Engine
Records raw 3D landmark coordinates (21 points per frame with timestamps, zero image data)
and replays them through the gesture engine without requiring a webcam.
Provides synthetic generator utilities for unit testing and offline development.
"""

import datetime
import json
import math
import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from tracker import HandFrame, LandmarkPoint


def get_recordings_dir() -> Path:
    """Returns local %APPDATA%\\PointerV\\recordings directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "PointerV" / "recordings"
    else:
        p = Path.home() / ".pointerv" / "recordings"
    p.mkdir(parents=True, exist_ok=True)
    return p


GUIDED_STEPS: List[Dict] = [
    {
        "id": "idle_pointing",
        "title": "1/17: Idle Pointing (20s)",
        "prompt": "Hold your hand in normal pointing pose (index extended, other fingers curled). Hold still or move gently. Do not click.",
        "duration_s": 20.0,
    },
    {
        "id": "active_movement",
        "title": "2/17: Region Movement (20s)",
        "prompt": "Move pointer around the entire active region, testing slow smooth motion and fast transitions (20 seconds).",
        "duration_s": 20.0,
    },
    {
        "id": "single_index_tap",
        "title": "3/17: 10 Single Index Taps",
        "prompt": "Perform 10 deliberate single index finger air-taps (curl down and release), waiting about 1 second between taps.",
        "duration_s": 20.0,
    },
    {
        "id": "double_index_tap",
        "title": "4/17: 10 Double Index Taps",
        "prompt": "Perform 10 double index taps (two quick taps in natural succession, 200-350ms apart). Pause ~1s between pairs.",
        "duration_s": 20.0,
    },
    {
        "id": "thumb_index_pinch",
        "title": "5/17: 5 Single Pinches",
        "prompt": "Perform 5 single thumb-index pinches (bring thumb tip to index tip, then release).",
        "duration_s": 15.0,
    },
    {
        "id": "double_pinch",
        "title": "6/17: 5 Double Pinches",
        "prompt": "Perform 5 double pinches (pinch twice quickly, then release). Pause 1s between pairs.",
        "duration_s": 15.0,
    },
    {
        "id": "open_palm_still",
        "title": "7/17: Open Palm Still (10s)",
        "prompt": "Hold hand open with all 5 fingers comfortably extended for 10 seconds. Keep natural small movement.",
        "duration_s": 10.0,
    },
    {
        "id": "open_palm_index_tap",
        "title": "8/17: 10 Index Taps (Open Palm)",
        "prompt": "With open palm: flick your INDEX finger down towards palm and release, 10 times.",
        "duration_s": 15.0,
    },
    {
        "id": "open_palm_middle_tap",
        "title": "9/17: 10 Middle Taps (Open Palm)",
        "prompt": "With open palm: flick your MIDDLE finger down towards palm and release, 10 times.",
        "duration_s": 15.0,
    },
    {
        "id": "open_palm_ring_tap",
        "title": "10/17: 10 Ring Taps (Open Palm)",
        "prompt": "With open palm: flick your RING finger down towards palm and release, 10 times.",
        "duration_s": 15.0,
    },
    {
        "id": "open_palm_pinky_tap",
        "title": "11/17: 10 Pinky Taps (Open Palm)",
        "prompt": "With open palm: flick your PINKY finger down towards palm and release, 10 times.",
        "duration_s": 15.0,
    },
    {
        "id": "open_palm_thumb_tap",
        "title": "12/17: 10 Thumb Taps (Open Palm)",
        "prompt": "With open palm: tap your THUMB inward towards palm and release, 10 times.",
        "duration_s": 15.0,
    },
    {
        "id": "swipe_down",
        "title": "13/17: 5 Swipes DOWN",
        "prompt": "Perform 5 deliberate whole-hand swipes DOWN (move hand down ~4 inches, return to center).",
        "duration_s": 12.0,
    },
    {
        "id": "swipe_up",
        "title": "14/17: 5 Swipes UP",
        "prompt": "Perform 5 deliberate whole-hand swipes UP (move hand up ~4 inches, return to center).",
        "duration_s": 12.0,
    },
    {
        "id": "swipe_left",
        "title": "15/17: 5 Swipes LEFT",
        "prompt": "Perform 5 deliberate whole-hand swipes LEFT (move hand left ~4 inches, return to center).",
        "duration_s": 12.0,
    },
    {
        "id": "swipe_right",
        "title": "16/17: 5 Swipes RIGHT",
        "prompt": "Perform 5 deliberate whole-hand swipes RIGHT (move hand right ~4 inches, return to center).",
        "duration_s": 12.0,
    },
    {
        "id": "fist_and_two_finger",
        "title": "17/17: Fist Hold & Two-Finger Hold",
        "prompt": "Hold closed fist for 5 seconds, then hold two fingers (index+middle) up for 5 seconds.",
        "duration_s": 12.0,
    },
]


class GuidedSessionRecorder:
    """
    Orchestrates the 17-step Phase B guided calibration recording session.
    Streams 21-point 3D landmark coordinates and timestamps directly to .jsonl
    in %APPDATA%\\PointerV\\recordings\\ without keeping huge video/image feeds.
    """

    def __init__(self, on_step_change: Optional[Callable] = None, on_complete: Optional[Callable] = None):
        self.is_active = False
        self.current_step_idx = 0
        self.step_start_time: float = 0.0
        self.session_start_time: float = 0.0
        self.step_frame_count = 0
        self.total_frame_count = 0
        self.filepath: Optional[Path] = None
        self._file_handle = None
        self.on_step_change = on_step_change
        self.on_complete = on_complete

    @property
    def current_step(self) -> Dict:
        idx = max(0, min(len(GUIDED_STEPS) - 1, self.current_step_idx))
        return GUIDED_STEPS[idx]

    @property
    def total_steps(self) -> int:
        return len(GUIDED_STEPS)

    def start_session(self, output_filepath: Optional[str] = None) -> str:
        """Starts a fresh guided recording session."""
        if output_filepath:
            self.filepath = Path(output_filepath)
        else:
            rec_dir = get_recordings_dir()
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.filepath = rec_dir / f"session_{ts}.jsonl"

        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(self.filepath, "w", encoding="utf-8")

        self.is_active = True
        self.current_step_idx = 0
        now = time.perf_counter()
        self.session_start_time = now
        self.step_start_time = now
        self.step_frame_count = 0
        self.total_frame_count = 0

        # Write session header
        header = {
            "type": "session_header",
            "version": "2.0.5",
            "start_time_iso": datetime.datetime.now().isoformat(),
            "total_steps": len(GUIDED_STEPS),
            "step_ids": [s["id"] for s in GUIDED_STEPS],
        }
        self._write_line(header)
        self._start_current_step()
        return str(self.filepath)

    def _start_current_step(self):
        step = self.current_step
        self.step_start_time = time.perf_counter()
        self.step_frame_count = 0
        marker = {
            "type": "segment_start",
            "seg": self.current_step_idx,
            "label": step["id"],
            "title": step["title"],
            "prompt": step["prompt"],
            "target_duration_s": step["duration_s"],
            "t_ms": int((time.perf_counter() - self.session_start_time) * 1000),
        }
        self._write_line(marker)
        if self.on_step_change:
            self.on_step_change(self.current_step_idx, step)

    def _end_current_step(self):
        step = self.current_step
        marker = {
            "type": "segment_end",
            "seg": self.current_step_idx,
            "label": step["id"],
            "frames_recorded": self.step_frame_count,
            "t_ms": int((time.perf_counter() - self.session_start_time) * 1000),
        }
        self._write_line(marker)

    def record_frame(self, hand: Optional[HandFrame], fps: float = 30.0):
        """Processes one video frame: records landmarks and checks step countdown."""
        if not self.is_active or self._file_handle is None:
            return

        now = time.perf_counter()
        step = self.current_step
        elapsed_step = now - self.step_start_time

        # Check if step duration has elapsed
        if elapsed_step >= step["duration_s"]:
            self._end_current_step()
            self.current_step_idx += 1
            if self.current_step_idx >= len(GUIDED_STEPS):
                self.finish_session()
                return
            self._start_current_step()
            step = self.current_step

        self.step_frame_count += 1
        self.total_frame_count += 1

        t_ms = int((now - self.session_start_time) * 1000)
        if hand is None:
            entry = {
                "type": "frame",
                "t_ms": t_ms,
                "seg": self.current_step_idx,
                "label": step["id"],
                "fps": round(fps, 1),
                "present": False,
                "handedness": "Unknown",
                "confidence": 0.0,
                "pts": [],
            }
        else:
            pts = [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in hand.landmarks]
            entry = {
                "type": "frame",
                "t_ms": t_ms,
                "seg": self.current_step_idx,
                "label": step["id"],
                "fps": round(fps, 1),
                "present": True,
                "handedness": getattr(hand, "handedness", "Right"),
                "confidence": round(getattr(hand, "confidence", 1.0), 3),
                "pts": pts,
            }
        self._write_line(entry)

    def next_step(self):
        """Manually advance to the next step before countdown finishes."""
        if not self.is_active:
            return
        self._end_current_step()
        self.current_step_idx += 1
        if self.current_step_idx >= len(GUIDED_STEPS):
            self.finish_session()
            return
        self._start_current_step()

    def previous_step(self):
        """Step back to re-record previous step."""
        if not self.is_active or self.current_step_idx <= 0:
            return
        self._end_current_step()
        self.current_step_idx -= 1
        self._start_current_step()

    def finish_session(self) -> str:
        """Finishes the guided recording session and flushes the file."""
        if not self.is_active:
            return str(self.filepath) if self.filepath else ""

        self._end_current_step()
        total_duration = time.perf_counter() - self.session_start_time
        avg_fps = self.total_frame_count / max(0.1, total_duration)

        summary = {
            "type": "session_summary",
            "total_frames": self.total_frame_count,
            "total_duration_s": round(total_duration, 2),
            "avg_fps": round(avg_fps, 1),
            "completed_all_steps": self.current_step_idx >= len(GUIDED_STEPS),
        }
        self._write_line(summary)

        if self._file_handle:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

        self.is_active = False
        saved_path = str(self.filepath) if self.filepath else ""
        if self.on_complete:
            self.on_complete(saved_path, summary)
        return saved_path

    def cancel_session(self):
        """Cancels recording without finalizing."""
        self.is_active = False
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    def _write_line(self, obj: Dict):
        if self._file_handle:
            try:
                self._file_handle.write(json.dumps(obj) + "\n")
            except Exception:
                pass

    def get_status(self) -> Dict:
        """Returns live state dictionary for UI presentation."""
        now = time.perf_counter()
        step = self.current_step
        elapsed_step = (now - self.step_start_time) if self.is_active else 0.0
        remaining_s = max(0.0, step["duration_s"] - elapsed_step)
        progress = min(1.0, elapsed_step / max(0.1, step["duration_s"]))
        return {
            "is_active": self.is_active,
            "step_idx": self.current_step_idx,
            "total_steps": len(GUIDED_STEPS),
            "title": step["title"],
            "prompt": step["prompt"],
            "elapsed_s": round(elapsed_step, 1),
            "remaining_s": round(remaining_s, 1),
            "target_duration_s": step["duration_s"],
            "progress": progress,
            "step_frames": self.step_frame_count,
            "total_frames": self.total_frame_count,
            "filepath": str(self.filepath) if self.filepath else "",
        }


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
