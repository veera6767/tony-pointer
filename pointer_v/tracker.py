"""
Pointer V - MediaPipe Tasks API Hand Landmarker Tracker
Tracks 21 3D hand landmarks in real time with sub-10ms inference.
Bundles local model checks, GPU delegate acceleration with automated CPU fallback,
and dominant hand detection.
"""

import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from version import APP_NAME, APPDATA_DIR_NAME

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
    def __init__(self, landmarks: List[LandmarkPoint], timestamp_ms: int, handedness: str = "Right", confidence: float = 1.0):
        self.landmarks = landmarks
        self.timestamp_ms = timestamp_ms
        self.handedness = handedness
        self.confidence = float(confidence)

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
        base_dir = Path(__file__).resolve().parent

        # 1. Check local assets / PyInstaller frozen bundle (_MEIPASS)
        candidate_paths = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass_dir = Path(getattr(sys, "_MEIPASS", ""))
            candidate_paths.extend([
                meipass_dir / "pointer_v" / "assets" / "models" / "hand_landmarker.task",
                meipass_dir / "assets" / "models" / "hand_landmarker.task",
                meipass_dir / "hand_landmarker.task",
            ])

        candidate_paths.extend([
            base_dir / "assets" / "models" / "hand_landmarker.task",
            base_dir / "hand_landmarker.task",
        ])

        # 2. Check %APPDATA%\PointerV\models\
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidate_paths.append(Path(appdata) / APPDATA_DIR_NAME / "models" / "hand_landmarker.task")
        candidate_paths.append(Path.home() / f".{APPDATA_DIR_NAME.lower()}" / "models" / "hand_landmarker.task")

        found_path = None
        for p in candidate_paths:
            if p.exists() and p.stat().st_size > 1000000:
                found_path = str(p)
                break

        if found_path is None:
            if model_dir is None:
                if appdata:
                    model_dir = str(Path(appdata) / APPDATA_DIR_NAME / "models")
                else:
                    model_dir = str(Path.home() / f".{APPDATA_DIR_NAME.lower()}" / "models")
            os.makedirs(model_dir, exist_ok=True)
            self.model_path = os.path.join(model_dir, "hand_landmarker.task")
            self._ensure_model_downloaded()
        else:
            self.model_path = found_path

        import logging
        logging.getLogger(APP_NAME).info(f"Loaded MediaPipe HandLandmarker model from: {self.model_path}")

        self.is_loaded = False
        self.load_error: Optional[str] = None
        self.last_inference_ms: float = 0.0
        self.last_confidence: float = 0.0

        self.landmarker = self._create_landmarker()
        self.last_result: Optional[HandFrame] = None
        self.last_seen_time: float = 0.0
        self._last_timestamp_ms: int = -1
        self.last_error: Optional[str] = None

    def _ensure_model_downloaded(self):
        """Downloads hand_landmarker.task from Google Storage if not yet present."""
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000000:
            return

        print(f"[{APP_NAME}] Downloading hand_landmarker.task to {self.model_path}...")
        try:
            urllib.request.urlretrieve(TASK_MODEL_URL, self.model_path)
            print(f"[{APP_NAME}] Model download complete!")
        except Exception as e:
            print(f"[{APP_NAME}] Warning: Auto-download failed ({e}). Checking local dir...")
            local_fallback = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
            if os.path.exists(local_fallback):
                self.model_path = local_fallback

    def _create_landmarker(self):
        """Creates MediaPipe HandLandmarker with CPU delegate and in-memory buffer."""
        import logging
        import traceback
        logger = logging.getLogger(APP_NAME)

        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # Read model file into memory buffer to avoid Windows path/space/unicode issues
            model_bytes = Path(self.model_path).read_bytes()
            if len(model_bytes) < 1000000:
                raise ValueError(f"Model file at {self.model_path} is incomplete ({len(model_bytes)} bytes)")

            # Use CPU delegate ONLY on Windows (GPU delegate is not supported in mediapipe python on Windows)
            base_options = python.BaseOptions(
                model_asset_buffer=model_bytes,
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
            lm = vision.HandLandmarker.create_from_options(options)
            self.is_loaded = True
            self.load_error = None
            logger.info("MediaPipe HandLandmarker initialized successfully with CPU delegate.")
            return lm
        except Exception as e:
            err_details = traceback.format_exc()
            logger.error(f"Failed to initialize MediaPipe HandLandmarker: {e}\n{err_details}")
            self.is_loaded = False
            self.load_error = f"{type(e).__name__}: {str(e)[:80]}"
            return None

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int = 0) -> Optional[HandFrame]:
        """Runs inference on camera frame and returns HandFrame if hand detected."""
        if self.landmarker is None or frame_bgr is None or frame_bgr.size == 0:
            return None

        # Guarantee strictly monotonic millisecond timestamps for MediaPipe VIDEO mode
        t_mono_ms = int(time.perf_counter() * 1000)
        if t_mono_ms <= self._last_timestamp_ms:
            t_mono_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = t_mono_ms

        import mediapipe as mp

        t_start = time.perf_counter()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        try:
            result = self.landmarker.detect_for_video(mp_image, t_mono_ms)
            self.last_error = None
            self.last_inference_ms = (time.perf_counter() - t_start) * 1000.0
        except Exception as e:
            import traceback
            self.last_error = f"Landmarker error: {type(e).__name__} ({str(e)[:50]})"
            import logging
            logging.getLogger(APP_NAME).warning(f"HandLandmarker detection error: {e}\n{traceback.format_exc()}")
            return None

        if not result or not result.hand_landmarks or len(result.hand_landmarks) == 0:
            self.last_result = None
            return None

        raw_landmarks = result.hand_landmarks[0]
        landmarks = [LandmarkPoint(pt.x, pt.y, pt.z) for pt in raw_landmarks]

        handedness = "Right"
        confidence = 0.95
        if result.handedness and len(result.handedness) > 0 and len(result.handedness[0]) > 0:
            cat = result.handedness[0][0]
            raw_cat = cat.category_name
            confidence = getattr(cat, "score", 0.95)
            # Frame is mirrored horizontally (cv2.flip(frame, 1)), so invert Left <-> Right
            handedness = "Right" if raw_cat == "Left" else "Left"

        self.last_confidence = confidence
        hand_frame = HandFrame(
            landmarks=landmarks,
            timestamp_ms=t_mono_ms,
            handedness=handedness,
            confidence=confidence
        )
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
