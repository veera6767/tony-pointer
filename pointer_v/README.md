# Pointer V — Native Windows Desktop Application
### High-Performance In-Air Gesture Controller & Floating Keyboard

Pointer V is a native Windows 10/11 system utility built with Python 3.12, PySide6 (Qt6), MediaPipe Tasks HandLandmarker, and Win32 hardware-level `SendInput`.

---

## Architecture Overview

```
                 +---------------------------+
                 |       Webcam Feed         |
                 +-------------+-------------+
                               | (Threaded Capture, 60 FPS)
                               v
                 +---------------------------+
                 |  MediaPipe HandLandmarker |
                 +-------------+-------------+
                               | (21 3D Landmarks)
                               v
                 +---------------------------+
                 | Gesture & Pose Classifier |
                 +------+--------------+-----+
                        |              |
          (Pointer / Paint)            (Keyboard Mode)
                        |              |
                        v              v
     +--------------------+          +--------------------+
     |  One Euro Filter   |          | Mode Manager       |
     |  & Anti-Jitter     |          | (Sliding Door &    |
     |  Lookback Buffer   |          |  Window Hop)       |
     +----------+---------+          +---------+----------+
                |                              |
                v                              v
     +--------------------+          +--------------------+
     | Win32 SendInput    |          | Win32 SendInput    |
     | Mouse Event Stream |          | Keyboard Scancodes |
     +--------------------+          +--------------------+
```

---

## Modules Directory

- `main.py`: Application coordinator, thread-safe Qt worker signal bridge, global hotkeys (`Ctrl+Alt+T`, `Ctrl+Alt+Space`, `Ctrl+Alt+K`, `Ctrl+Alt+S`, `Ctrl+Alt+P`), single-instance mutex, and system tray integration.
- `theme.py`: Centralized design tokens (colors `#0B0E13`, `#11151C`, `#171C25`, `#2F7BFF`, fonts Inter and JetBrains Mono, 8px grid, global stylesheet).
- `settings.py`: JSON settings persistence in `%APPDATA%\PointerV\settings.json`, deep-merge loader, export/import, and automatic one-time migration from legacy `%APPDATA%\TonyPointer`.
- `tracker.py`: MediaPipe Tasks API hand tracker with automatic local bundle fallback (`assets/models/hand_landmarker.task`), CPU/GPU delegate negotiation, and normalized landmark extraction.
- `gestures.py`: Real-time hand pose classification (`POINTING`, `OPEN_PALM`, `FIST`, `PINCH`, `TWO_FINGERS`), fist-hold auto-pause (1.5 s countdown), and auto-pause inactivity watchdog (10 s).
- `mouse.py`: Per-Monitor DPI V2 awareness, multi-monitor coordinate normalization to `0..65535`, 150 ms anti-jitter lookback buffer, and emergency button release.
- `keyboard_layout.py`: Standard 6-row Main Keyboard (26 letters, functions, modifiers) and aligned 6-row Symbols Panel with 4-key progressive window geometry.
- `keyboard_out.py`: Hardware-level Win32 `SendInput` keystroke dispatch with scancode mapping, automatic Shift-character resolution, and sticky modifier states (`Shift`, `Ctrl`, `Alt`, `Win`, `CapsLock`).
- `keyboard_ui.py`: Transparent frameless dark-glass keyboard HUD with `WS_EX_NOACTIVATE` and `WS_EX_TOOLWINDOW` flags, 4-key blue glow, and symbol zone navigation.
- `finger_taps.py`: Independent per-finger curl and velocity detector, inter-finger neighbor lockout (160 ms default), and configurable key repeat rate (15 cps default).
- `mode_manager.py`: Sliding door navigation state machine with normalized hand-size thresholds, single jump per swipe enforcement, neutral return hysteresis, and inter-zone crossing.
- `camera.py`: Threaded OpenCV video capture engine with frame-drop protection, 2-second reconnect watchdog for disconnected/busy cameras, luminance warning (<40 low light, >220 glare), and battery saver modes.
- `filters.py`: Dual-axis One Euro adaptive low-pass filter for jitter-free cursor tracking.
- `overlay.py`: PySide6 holographic cyan reticle overlay with dwell indicator ring and click ripple animation.
- `preview.py`: Independent draggable floating picture-in-picture webcam preview with blue corner brackets and FPS chip.
- `sound.py`: Asynchronous audio cues for clicks, double clicks, mode switches, and locks with volume control and global mute.
- `recorder.py`: Raw landmark stream recorder (21 points with timestamps, zero images) and deterministic replay engine for offline testing.
- `logger.py`: Sanitized rotating file logger in `%APPDATA%\PointerV\logs\pointer_v.log` (2MB max) with strict privacy enforcement (no typed keys recorded).
- `ui/`: Complete modular UI suite containing custom title bar, sidebar rail, status bar, and 9 dedicated view pages (`Dashboard`, `Camera`, `Gestures`, `Keyboard`, `Practice`, `Settings`, `Calibration`, `About`, `Developer`).

---

## Development & Testing

```bash
# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run pytest unit test suite
pytest tests -v

# Run desktop application
python main.py
```

## Building Executables

```cmd
:: Build PyInstaller standalone onedir bundle
build_exe.bat
```
Output is created in `dist\PointerV\PointerV.exe`.
