"""
Pointer V - MediaPipe Diagnostic & Self-Test Script
1. Prints Python and mediapipe versions.
2. Locates and loads hand_landmarker.task using model_asset_buffer (CPU delegate).
3. Grabs frames from webcam for 5 seconds.
4. Reports total frames, frames with hand detected, handedness, and confidence.
5. Saves an annotated frame to disk.
"""

import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pointer_v"))

print(f"=== MEDIAPIPE SELF-TEST ===")
print(f"Python: {sys.version}")

try:
    import mediapipe as mp

    print(f"MediaPipe version: {mp.__version__}")
except ImportError as e:
    print(f"[FATAL] Could not import mediapipe: {e}")
    sys.exit(1)

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Locate model
candidates = [
    ROOT / "pointer_v" / "assets" / "models" / "hand_landmarker.task",
    ROOT / "pointer_v" / "hand_landmarker.task",
    Path(os.environ.get("APPDATA", "")) / "PointerV" / "models" / "hand_landmarker.task",
]

model_path = None
for c in candidates:
    if c.exists() and c.stat().st_size > 1000000:
        model_path = c
        break

if not model_path:
    print(f"[ERROR] hand_landmarker.task not found in any candidate path!")
    for c in candidates:
        print(f"  Checked: {c} (exists: {c.exists()})")
    sys.exit(1)

print(f"Found model at: {model_path} ({model_path.stat().st_size} bytes)")

# Read bytes for model_asset_buffer
try:
    with open(model_path, "rb") as f:
        model_buffer = f.read()
    print(f"Read {len(model_buffer)} bytes into buffer.")
except Exception as e:
    print(f"[ERROR] Failed to read model buffer: {e}")
    sys.exit(1)

# Initialize HandLandmarker with CPU delegate
try:
    base_options = python.BaseOptions(model_asset_buffer=model_buffer, delegate=python.BaseOptions.Delegate.CPU)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)
    print("HandLandmarker initialized successfully with CPU delegate!")
except Exception as e:
    import traceback

    print(f"[FATAL] Failed to create HandLandmarker: {e}")
    traceback.print_exc()
    sys.exit(1)

# Open Camera
print("Opening camera index 0...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("[WARNING] Could not open camera 0. Trying camera 1...")
    cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("[ERROR] No webcam available to test.")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

print("Starting 5-second capture and detection loop...")
start_time = time.perf_counter()
total_frames = 0
hand_frames = 0
last_ts_ms = -1
annotated_saved = False

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
]

while time.perf_counter() - start_time < 5.0:
    ret, frame = cap.read()
    if not ret or frame is None:
        time.sleep(0.01)
        continue

    total_frames += 1
    # Frame horizontally flipped as user expects mirrored webcam
    frame = cv2.flip(frame, 1)

    # Monotonic millisecond timestamp
    ts_ms = int(time.perf_counter() * 1000)
    if ts_ms <= last_ts_ms:
        ts_ms = last_ts_ms + 1
    last_ts_ms = ts_ms

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    try:
        result = landmarker.detect_for_video(mp_image, ts_ms)
        if result and result.hand_landmarks:
            hand_frames += 1
            handedness = "Right"
            score = 1.0
            if result.handedness and len(result.handedness) > 0:
                cat = result.handedness[0][0]
                handedness = cat.category_name
                score = cat.score

            if not annotated_saved:
                # Annotate and save frame
                h, w, _ = frame.shape
                landmarks = result.hand_landmarks[0]
                pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
                for p1, p2 in HAND_CONNECTIONS:
                    cv2.line(frame, pts[p1], pts[p2], (0, 255, 0), 2)
                for pt in pts:
                    cv2.circle(frame, pt, 4, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    f"Hand: {handedness} ({score:.2f})",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 0),
                    2,
                )
                save_path = ROOT / "scripts" / "mediapipe_selftest_frame.jpg"
                cv2.imwrite(str(save_path), frame)
                print(f"Saved annotated frame to: {save_path}")
                annotated_saved = True

    except Exception as e:
        print(f"detect_for_video error: {e}")

cap.release()
landmarker.close()

duration = time.perf_counter() - start_time
fps = total_frames / duration if duration > 0 else 0
print(f"\n=== RESULTS ===")
print(f"Duration: {duration:.2f}s")
print(f"Total Frames: {total_frames} ({fps:.1f} FPS)")
print(f"Hand Detected Frames: {hand_frames} / {total_frames} ({(hand_frames / max(1, total_frames) * 100):.1f}%)")
print(f"Annotated frame saved: {annotated_saved}")
print(f"=== END OF TEST ===")
