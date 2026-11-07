"""
Tony Pointer - High-Speed Asynchronous Camera Capture & HUD Overlay
Runs OpenCV VideoCapture in a dedicated background worker thread.
Guarantees zero frame lag by immediately dropping stale intermediate frames.
Draws mirrored Iron-Man holographic hand skeleton and active region boundaries.
"""

import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from tracker import HandFrame

# MediaPipe Hand Landmark Connections (21 points)
HAND_CONNECTIONS = [
    # Palm
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17)                                 # Wrist to Pinky base
]


class CameraStream:
    """Threaded OpenCV capture engine with drop-old-frame queue."""

    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720, target_fps: int = 60):
        self.camera_index = camera_index
        self.requested_width = width
        self.requested_height = height
        self.target_fps = target_fps

        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_timestamp_ms: int = 0
        self.fps_actual: float = 0.0

        self.is_low_light: bool = False
        self.error_message: Optional[str] = None

    def start(self) -> bool:
        """Initializes camera capture and launches reader thread."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)  # CAP_DSHOW on Windows for fast startup
            if not self.cap.isOpened():
                # Fallback to default backend
                self.cap = cv2.VideoCapture(self.camera_index)
        except Exception as e:
            self.error_message = f"Failed to open camera #{self.camera_index}: {e}"
            return False

        if not self.cap.isOpened():
            self.error_message = f"Camera #{self.camera_index} is unavailable or in use by another app."
            return False

        # Configure resolution and hardware buffers
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested_height)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer to prevent latency accumulation

        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()
        return True

    def _capture_worker(self):
        frame_count = 0
        start_time = time.perf_counter()

        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Mirror horizontally so hand movements match user's physical direction
            frame_mirrored = cv2.flip(frame, 1)

            # Analyze average luminance for low-light warning
            gray = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray)
            self.is_low_light = avg_brightness < 45.0

            timestamp_ms = int(time.time() * 1000)

            with self.lock:
                self.latest_frame = frame_mirrored
                self.latest_timestamp_ms = timestamp_ms

            frame_count += 1
            elapsed = time.perf_counter() - start_time
            if elapsed >= 1.0:
                self.fps_actual = frame_count / elapsed
                frame_count = 0
                start_time = time.perf_counter()

    def get_frame(self) -> Tuple[Optional[np.ndarray], int]:
        """Returns the most recent available mirrored frame and timestamp."""
        with self.lock:
            if self.latest_frame is None:
                return None, 0
            return self.latest_frame.copy(), self.latest_timestamp_ms

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None


def draw_hud_landmarks(
    frame_bgr: np.ndarray,
    hand: Optional[HandFrame],
    active_region,
    status_text: str = "",
    dwell_progress: float = 0.0,
    brush_locked: bool = False
) -> np.ndarray:
    """
    Renders the Stark Industries / JARVIS style HUD visualization:
    - Glowing cyan bone connections
    - Amber/Cyan landmark nodes
    - Active Region corner bracket box
    - Pointer reticle with dwell charge progress ring
    """
    h, w, _ = frame_bgr.shape
    vis = frame_bgr.copy()

    # 1. Draw Active Region Bounding Box (Golden Amber Corners)
    ar = active_region
    ax1, ay1 = int(ar.x_min * w), int(ar.y_min * h)
    ax2, ay2 = int(ar.x_max * w), int(ar.y_max * h)

    # Hairline dashed / subtle active rectangle
    cv2.rectangle(vis, (ax1, ay1), (ax2, ay2), (255, 180, 0), 1)

    # Sci-fi corner brackets
    c_len = min(20, (ax2 - ax1) // 6)
    # Top-left
    cv2.line(vis, (ax1, ay1), (ax1 + c_len, ay1), (0, 229, 255), 2)
    cv2.line(vis, (ax1, ay1), (ax1, ay1 + c_len), (0, 229, 255), 2)
    # Top-right
    cv2.line(vis, (ax2, ay1), (ax2 - c_len, ay1), (0, 229, 255), 2)
    cv2.line(vis, (ax2, ay1), (ax2, ay1 + c_len), (0, 229, 255), 2)
    # Bottom-left
    cv2.line(vis, (ax1, ay2), (ax1 + c_len, ay2), (0, 229, 255), 2)
    cv2.line(vis, (ax1, ay2), (ax1, ay2 - c_len), (0, 229, 255), 2)
    # Bottom-right
    cv2.line(vis, (ax2, ay2), (ax2 - c_len, ay2), (0, 229, 255), 2)
    cv2.line(vis, (ax2, ay2), (ax2, ay2 - c_len), (0, 229, 255), 2)

    # 2. Draw Hand Landmarks
    if hand is not None:
        coords = []
        for lm in hand.landmarks:
            px = int(lm.x * w)
            py = int(lm.y * h)
            coords.append((px, py))

        # Draw skeleton bone lines
        bone_color = (0, 80, 255) if brush_locked else (255, 230, 0)  # BGR
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            cv2.line(vis, coords[p1_idx], coords[p2_idx], bone_color, 2)

        # Draw landmark nodes
        for i, (px, py) in enumerate(coords):
            if i == 8:
                # Index Tip - Tony Pointer Primary Reticle!
                reticle_color = (0, 85, 255) if brush_locked else (255, 229, 0)  # Orange-red if locked, cyan if free
                cv2.circle(vis, (px, py), 8, reticle_color, -1)
                cv2.circle(vis, (px, py), 16, reticle_color, 2)

                # Dwell Arc Sweep
                if dwell_progress > 0.0 and not brush_locked:
                    axes = (24, 24)
                    angle = 0
                    startAngle = -90
                    endAngle = int(-90 + (360 * dwell_progress))
                    cv2.ellipse(vis, (px, py), axes, angle, startAngle, endAngle, (0, 140, 255), 3)

            elif i in [4, 12, 16, 20]:
                # Fingertips
                cv2.circle(vis, (px, py), 5, (0, 229, 255), -1)
            else:
                # Joints
                cv2.circle(vis, (px, py), 3, (200, 200, 200), -1)

    # Status Telemetry HUD in Top Left
    cv2.putText(
        vis,
        status_text,
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 229, 255) if not brush_locked else (0, 80, 255),
        2,
        cv2.LINE_AA,
    )

    return vis
