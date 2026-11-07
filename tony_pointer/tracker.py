"""
Tony Pointer - MediaPipe Tasks API Hand Landmarker Tracker
Tracks 21 3D hand landmarks in real time with sub-10ms inference.
Auto-downloads 'hand_landmarker.task' on first launch and configures
hardware acceleration (GPU delegate with automated CPU fallback).
"""

import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

# Official Google MediaPipe Task Model URL
TASK_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)


class LandmarkPoint:
    """Normalized and relative 3D coordinate of a hand landmark."""
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


class HandFrame:
    """Container for detected landmarks in a video frame."""
    def __init__(self, landmarks: List[LandmarkPoint], timestamp_ms: int, handedness: str = "Right"):
        self.landmarks = landmarks
        self.timestamp_ms = timestamp_ms
        self.handedness = handedness

    def get(self, index: int) -> LandmarkPoint:
        return self.landmarks[index]

    def distance_3d(self, idx_a: int, idx_b: int) -> float:
        """Computes Euclidean distance in normalized 3D space."""
        a = self.landmarks[idx_a]
        b = self.landmarks[idx_b]
        return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)

    def get_hand_size(self) -> float:
        """Returns normalized hand scale from wrist (0) to middle MCP (9)."""
        return max(0.04, self.distance_3d(0, 9))

    def get_palm_center(self) -> Tuple[float, float, float]:
        """Computes average center point of palm landmarks (0, 5, 9, 13, 17)."""
        pts = [self.landmarks[i] for i in (0, 5, 9, 13, 17)]
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        cz = sum(p.z for p in pts) / len(pts)
        return (cx, cy, cz)

    def angle_deg(self, idx_a: int, idx_b: int, idx_c: int) -> float:
        """
        Calculates joint angle at landmark B formed by ray B->A and ray B->C.
        180 deg = completely straight finger.
        < 90 deg = deeply curled finger.
        """
        a = self.landmarks[idx_a]
        b = self.landmarks[idx_b]
        c = self.landmarks[idx_c]

        v1 = np.array([a.x - b.x, a.y - b.y, a.z - b.z], dtype=np.float32)
        v2 = np.array([c.x - b.x, c.y - b.y, c.z - b.z], dtype=np.float32)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 180.0

        dot = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
        return float(np.degrees(np.arccos(dot)))


class HandTracker:
    """Initializes and runs Google MediaPipe Tasks HandLandmarker."""

    def __init__(self, model_dir: Optional[str] = None):
        if model_dir is None:
            model_dir = str(Path.home() / ".tony_pointer" / "models")
        os.makedirs(model_dir, exist_ok=True)
        self.model_path = os.path.join(model_dir, "hand_landmarker.task")

        self._ensure_model_downloaded()
        self.landmarker = self._create_landmarker()
        self.last_result: Optional[HandFrame] = None
        self.last_seen_time: float = 0.0

    def _ensure_model_downloaded(self):
        """Downloads hand_landmarker.task from Google Storage if not yet present."""
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000000:
            return

        print(f"[TonyPointer] Downloading hand_landmarker.task to {self.model_path}...")
        try:
            urllib.request.urlretrieve(TASK_MODEL_URL, self.model_path)
            print("[TonyPointer] Model download complete!")
        except Exception as e:
            print(f"[TonyPointer] Warning: Auto-download failed ({e}). Checking local dir...")
            local_fallback = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
            if os.path.exists(local_fallback):
                self.model_path = local_fallback

    def _create_landmarker(self):
        """Creates MediaPipe HandLandmarker with GPU delegate and CPU fallback."""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            base_options = python.BaseOptions(
                model_asset_path=self.model_path,
                delegate=python.BaseOptions.Delegate.GPU,
            )
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            return vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            print(f"[TonyPointer] GPU delegate init failed ({e}), falling back to CPU...")
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision

                base_options = python.BaseOptions(
                    model_asset_path=self.model_path,
                    delegate=python.BaseOptions.Delegate.CPU,
                )
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                    min_hand_detection_confidence=0.5,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                return vision.HandLandmarker.create_from_options(options)
            except Exception as ex2:
                print(f"[TonyPointer] Critical: Could not initialize HandLandmarker: {ex2}")
                return None

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[HandFrame]:
        """
        Runs inference on a mirrored camera frame and returns HandFrame if hand detected.
        """
        if self.landmarker is None or frame_bgr is None:
            return None

        import mediapipe as mp

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        try:
            result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as e:
            # Timestamp monotonicity guarantee
            return self.last_result

        if not result or not result.hand_landmarks or len(result.hand_landmarks) == 0:
            return None

        raw_landmarks = result.hand_landmarks[0]
        landmarks = [LandmarkPoint(pt.x, pt.y, pt.z) for pt in raw_landmarks]

        handedness = "Right"
        if result.handedness and len(result.handedness) > 0 and len(result.handedness[0]) > 0:
            handedness = result.handedness[0][0].category_name

        hand_frame = HandFrame(landmarks=landmarks, timestamp_ms=timestamp_ms, handedness=handedness)
        self.last_result = hand_frame
        self.last_seen_time = time.perf_counter()
        return hand_frame

    def close(self):
        if self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass
            self.landmarker = None
