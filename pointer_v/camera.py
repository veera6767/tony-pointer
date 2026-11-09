"""
Pointer V - High-Speed Asynchronous Camera Capture & Telemetry
Runs OpenCV VideoCapture in a dedicated background worker thread with automatic
reconnect on camera unplug/replug, luminance monitoring (low-light and over-exposure),
multi-camera enumeration, dynamic FPS throttling (15/30/60 FPS, battery saver),
and zero-lag frame dropping.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple

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


def list_available_cameras(max_tested: int = 4) -> List[Tuple[int, str]]:
    """Probes available video devices and returns list of (index, label)."""
    available = []
    for idx in range(max_tested):
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap is not None and cap.isOpened():
                available.append((idx, f"Camera {idx} (DirectShow)"))
                cap.release()
            else:
                cap = cv2.VideoCapture(idx)
                if cap is not None and cap.isOpened():
                    available.append((idx, f"Camera {idx}"))
                    cap.release()
        except Exception:
            pass
    if not available:
        available.append((0, "Default Camera 0"))
    return available


class CameraStream:
    """Threaded OpenCV capture engine with auto-reconnect and frame dropping."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        target_fps: int = 60,
        camera_name: str = ""
    ):
        self.camera_index = camera_index
        self.camera_name = camera_name
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

        # Lighting and health status
        self.is_low_light: bool = False
        self.is_over_exposed: bool = False
        self.avg_brightness: float = 128.0
        self.error_message: Optional[str] = None
        self.is_connected: bool = False
        self.reconnecting: bool = False

    def start(self) -> bool:
        """Initializes camera capture and launches reader thread."""
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()
        return True

    def _open_device(self) -> bool:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)
        except Exception as e:
            self.error_message = f"Failed to open camera #{self.camera_index}: {e}"
            self.is_connected = False
            return False

        if not self.cap or not self.cap.isOpened():
            self.error_message = f"Camera #{self.camera_index} unavailable. Retrying..."
            self.is_connected = False
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested_height)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.is_connected = True
        self.reconnecting = False
        self.error_message = None
        return True

    def _capture_worker(self):
        frame_count = 0
        start_time = time.perf_counter()
        consecutive_failures = 0

        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self.reconnecting = True
                success = self._open_device()
                if not success:
                    time.sleep(2.0)
                    continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                consecutive_failures += 1
                if consecutive_failures > 15:
                    self.is_connected = False
                    self.reconnecting = True
                    self.error_message = "Camera disconnected or unplugged. Reconnecting..."
                    if self.cap:
                        self.cap.release()
                        self.cap = None
                    time.sleep(2.0)
                else:
                    time.sleep(0.02)
                continue

            consecutive_failures = 0
            self.is_connected = True
            self.reconnecting = False

            # Mirror horizontally
            frame_mirrored = cv2.flip(frame, 1)

            # Analyze average luminance
            gray = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2GRAY)
            self.avg_brightness = float(np.mean(gray))
            self.is_low_light = self.avg_brightness < 40.0
            self.is_over_exposed = self.avg_brightness > 220.0

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

    def change_camera(self, new_index: int, new_name: str = ""):
        """Dynamically switch to a different camera device without crashing."""
        self.camera_index = new_index
        self.camera_name = new_name
        if self.cap:
            self.cap.release()
            self.cap = None

    def set_target_fps(self, fps: int):
        self.target_fps = max(15, min(60, fps))
        if self.cap and self.cap.isOpened():
            try:
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None


def draw_hud_landmarks(
    frame_bgr: np.ndarray,
    hand: Optional[HandFrame],
    active_region,
    status_text: str = "",
    dwell_progress: float = 0.0,
    brush_locked: bool = False,
    pause_progress: float = 0.0,
    is_paused: bool = False
) -> np.ndarray:
    """
    Renders the clean Pointer V engineering-grade HUD:
    - Subtle 1px lines and small corner brackets on active region
    - Clean hand skeleton
    - Reticle and dwell/pause progress ring
    """
    h, w, _ = frame_bgr.shape
    vis = frame_bgr.copy()

    # 1. Active Region Bounding Box with subtle corner brackets
    ar = active_region
    ax1, ay1 = int(ar.x_min * w), int(ar.y_min * h)
    ax2, ay2 = int(ar.x_max * w), int(ar.y_max * h)

    cv2.rectangle(vis, (ax1, ay1), (ax2, ay2), (47, 57, 72), 1)

    c_len = min(16, (ax2 - ax1) // 8)
    accent_bgr = (255, 123, 47) if not is_paused else (117, 101, 91)  # #2F7BFF blue in BGR

    # Corner brackets (1px, 40% subtle accent)
    cv2.line(vis, (ax1, ay1), (ax1 + c_len, ay1), accent_bgr, 1)
    cv2.line(vis, (ax1, ay1), (ax1, ay1 + c_len), accent_bgr, 1)
    cv2.line(vis, (ax2, ay1), (ax2 - c_len, ay1), accent_bgr, 1)
    cv2.line(vis, (ax2, ay1), (ax2, ay1 + c_len), accent_bgr, 1)
    cv2.line(vis, (ax1, ay2), (ax1 + c_len, ay2), accent_bgr, 1)
    cv2.line(vis, (ax1, ay2), (ax1, ay2 - c_len), accent_bgr, 1)
    cv2.line(vis, (ax2, ay2), (ax2 - c_len, ay2), accent_bgr, 1)
    cv2.line(vis, (ax2, ay2), (ax2, ay2 - c_len), accent_bgr, 1)

    # 2. Hand Landmarks Skeleton
    if hand is not None:
        coords = []
        for lm in hand.landmarks:
            px = int(lm.x * w)
            py = int(lm.y * h)
            coords.append((px, py))

        # Vibrant skeleton colors (Cyan / Blue neon for tracking)
        bone_color = (110, 80, 240) if brush_locked else (238, 211, 34)  # Cyan #22D3EE in BGR
        joint_color = (255, 123, 47) if not brush_locked else (80, 50, 240) # Blue #2F7BFF in BGR
        if is_paused:
            bone_color = (117, 101, 91)
            joint_color = (117, 101, 91)

        # Draw bones
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            cv2.line(vis, coords[p1_idx], coords[p2_idx], bone_color, 2)

        # Draw joints
        for i, (px, py) in enumerate(coords):
            if i == 8:  # Index fingertip hotspot
                reticle_color = (110, 80, 240) if brush_locked else (255, 123, 47)
                if is_paused:
                    reticle_color = (117, 101, 91)
                # Outer target rings
                cv2.circle(vis, (px, py), 14, reticle_color, 2)
                cv2.circle(vis, (px, py), 5, (255, 255, 255), -1)

                # Dwell progress arc
                if dwell_progress > 0.0 and not brush_locked:
                    axes = (20, 20)
                    cv2.ellipse(vis, (px, py), axes, 0, -90, int(-90 + (360 * dwell_progress)), (36, 165, 245), 3)

                # Pause countdown ring
                if pause_progress > 0.0:
                    axes = (26, 26)
                    cv2.ellipse(vis, (px, py), axes, 0, -90, int(-90 + (360 * pause_progress)), (36, 165, 245), 3)

            elif i in (4, 12, 16, 20):  # Fingertips
                cv2.circle(vis, (px, py), 5, joint_color, -1)
                cv2.circle(vis, (px, py), 5, (255, 255, 255), 1)
            elif i == 0:  # Wrist
                cv2.circle(vis, (px, py), 6, (255, 123, 47), -1)
            else:
                cv2.circle(vis, (px, py), 3, (255, 255, 255), -1)

        # Top status chip with hand info & confidence
        conf_pct = int(getattr(hand, "confidence", 0.95) * 100)
        chip_label = f"{status_text}  |  {hand.handedness} Hand ({conf_pct}%)"
    else:
        chip_label = status_text if status_text else "SEARCHING FOR HAND"

    # Status Chip in Top Left
    cv2.putText(
        vis,
        chip_label,
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 123, 47) if not is_paused else (150, 150, 150),
        2,
        cv2.LINE_AA,
    )

    return vis
