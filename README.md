# Pointer V (PV)
### Control your PC in the air with one hand.

**Pointer V** is a native Windows desktop application and interactive Web Studio designed for engineers, creators, and power users. It enables complete, low-latency, touch-free PC control and in-air keyboard typing using a standard USB or laptop webcam.

- **Desktop Application**: Python 3.12, Google MediaPipe Tasks HandLandmarker, PySide6 (Qt6), and Win32 hardware-level `SendInput`.
- **Web Studio & Simulator**: React 19, TypeScript, Vite, Tailwind CSS, providing in-browser gesture simulation, virtual Windows desktop canvas, live One Euro filter calibration, and source code exploration.

---

## Table of Contents
1. [Key Features](#key-features)
2. [Quick Start for Users](#quick-start-for-users)
3. [Quick Start for Developers](#quick-start-for-developers)
4. [Air Gesture Reference](#air-gesture-reference)
5. [Keyboard Layout Architecture](#keyboard-layout-architecture)
6. [Default Settings & Configuration](#default-settings--configuration)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Tips for Best Accuracy](#tips-for-best-accuracy)
9. [Privacy & Security Guarantee](#privacy--security-guarantee)
10. [Repository Structure](#repository-structure)
11. [Roadmap & Credits](#roadmap--credits)

---

## Key Features

- **Hardware-Level OS Navigation**: Traverses all windows, system tray, desktop, browsers, creative applications, and games via Win32 `SendInput` (no PyAutoGUI focus traps).
- **Per-Monitor DPI V2 & Multi-Monitor Support**: Native awareness across mixed-DPI multi-monitor configurations with absolute virtual screen coordinate mapping (`0..65535`).
- **Floating Air Keyboard + Symbols HUD**:
  - Main 6-row full laptop keyboard (left) paired with an aligned 6-row Symbols panel (right).
  - Progressive 4-key windows locked to your four fingers (`Index`, `Middle`, `Ring`, `Pinky`).
  - Single-motion sliding door navigation: swipe whole hand Up/Down to switch rows; swipe Left/Right to hop windows.
  - Inter-zone crossing: swipe right across the vertical divider into Symbols; swipe left back to Main keyboard.
  - Independent finger curl detection with neighbor lockout (prevents adjacent misfires) and configurable hold-to-repeat (15 chars/sec default).
  - Latching and locking sticky modifiers (`Shift`, `Ctrl`, `Alt`, `Win`, `CapsLock`).
- **Air Double-Tap Detection**: Rapid flexure and release of index finger twice within 500 ms triggers a hardware double-click.
- **Anti-Jitter Lookback Ring Buffer**: Freezes cursor coordinates 150 ms prior to tap initiation so physical finger motion never jerks the cursor off targets.
- **One Euro Adaptive Smoothing**: Dual-axis mathematical low-pass filtering eliminates physiological hand tremor while preserving zero lag during rapid flicks.
- **Brush Lock (Paint Mode)**: Dwell still for 0.60 s or pinch thumb to index to lock the left mouse button down for continuous painting in Photoshop, Krita, Clip Studio, or Figma.
- **Dominant Hand Support**: Automatic handedness detection or manual override for Right / Left hand layouts.
- **Safety & Auto-Pause**: Global hotkey `Ctrl + Alt + Space` or fist hold (1.5 s countdown ring); auto-pause after 10 s with no hand in view; automatic release of all keys and buttons on exit, pause, or mode switch.

---

## Quick Start for Users

### Option A: Windows Installer (Recommended)
1. Download `PointerV-Setup-2.0.0.exe` from [Releases](https://github.com/veeraakash/pointer-v/releases).
2. Run the installer. You can optionally enable **Start with Windows** and create a Desktop shortcut.
3. Launch **Pointer V** from your Start Menu.
4. Position your webcam at chest or eye height and follow the interactive 7-step onboarding tutorial.

> [!NOTE]
> **Windows Defender / SmartScreen**: Since this is a newly released independent open-source binary, Windows SmartScreen may show an informational prompt ("Windows protected your PC"). Click **More info** -> **Run anyway**. You can verify the official SHA-256 checksums in the release notes.

### Option B: Portable ZIP Package
1. Download `PointerV-Portable-2.0.0.zip`.
2. Extract the folder anywhere on your PC.
3. Run `PointerV.exe`. No installation, Python setup, or administrator privileges required.

---

## Quick Start for Developers

### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.11 or 3.12 (with `pip`)
- Node.js v18+ and npm (for Web Studio)

### 1. Run the Python Desktop Application
```bash
# Clone the repository
git clone https://github.com/veeraakash/pointer-v.git
cd pointer-v

# Set up virtual environment
python -m venv venv
venv\Scripts\activate

# Install native dependencies
pip install -r pointer_v/requirements.txt

# Run Pointer V
python pointer_v/main.py
```

### 2. Run the Automated Test Suite
```bash
pytest tests -v
```

### 3. Build Standalone Executable & Installer
```cmd
:: Build PyInstaller onedir bundle (output: pointer_v\dist\PointerV\)
cd pointer_v
build_exe.bat

:: Build Inno Setup Windows installer (output: installers\Output\PointerV-Setup-2.0.0.exe)
cd ..\installers
build_installer.bat
```

### 4. Run the Web Studio
```bash
npm install
npm run dev
# Open http://localhost:3000 in your browser
```

---

## Air Gesture Reference

| Gesture | Pose / Posture | Action |
| :--- | :--- | :--- |
| **Move Cursor** | Pointing (Index finger extended, others curled) | Smooth mouse cursor movement with One Euro filtering |
| **Air Double-Tap** | Rapid flex-and-release of index finger 2× within 500 ms | Double Left Click (opens files, folders, applications) |
| **Air Single-Tap** | Swift flex-and-release of index finger | Single Left Click (when enabled) |
| **Pause Tracking** | Closed fist held for 1.5 s (countdown ring) | Pauses cursor output (tray icon turns grey) |
| **Open Air Keyboard** | Open Palm held for 0.5 s facing camera | Launches floating keyboard HUD and pauses cursor |
| **Close Air Keyboard**| Closed fist held for 0.5 s, or press `Esc` | Hides keyboard HUD and returns to Pointer mode |
| **Air Type Key** | Individual curl of Index, Middle, Ring, or Pinky | Types the locked key glowing in the active 4-key window |
| **Thumb Air-Tap** | Swift curl of thumb inward | Types `[SPACE]` |
| **Slide Row (Up/Down)**| Move whole hand vertically by >32% of hand height | Jumps active 4-key window up or down one row |
| **Hop Window (Left/Right)**| Move whole hand horizontally by >32% of hand width | Hops active 4-key window horizontally |
| **Cross into Symbols**| Swipe right past the last window of the Main keyboard | Moves blue focus into the docked Symbols panel |
| **Right Click** | Index + Middle fingers extended and held still for 0.5 s | Triggers Windows right click / context menu |
| **Two-Finger Scroll**| Index + Middle fingers extended, move vertically | Smooth vertical page scrolling |
| **Brush Lock (Dwell)**| Hold index fingertip motionless for 0.60 s | Locks left mouse button DOWN for drawing/dragging |
| **Brush Lock (Pinch)**| Touch thumb tip to index fingertip | Locks left mouse button DOWN |
| **Emergency Safety** | Press `Esc`, take hand out of view (>1 s), or pause | Instantly releases all held mouse buttons and keys |

### Global Hotkeys
- `Ctrl + Alt + T`: Toggle Pointer V ON / OFF.
- `Ctrl + Alt + Space`: Toggle Pause Tracking (freezes cursor output while keeping camera active).
- `Ctrl + Alt + K`: Toggle Floating Air Keyboard HUD.
- `Ctrl + Alt + S`: Toggle Keyboard Zone (Main Keyboard ↔ Symbols Panel).
- `Ctrl + Alt + P`: Toggle Paint Mode Profile (Enhanced Brush Stabilizer).
- `Esc`: Universal Emergency Release (all keys, buttons, and latches reset).

---

## Keyboard Layout Architecture

### Main Keyboard (Left Zone — 6 Rows)
```
Row 1: [Esc] [F1] [F2] [F3] [F4] [F5] [F6] [F7] [F8] [F9] [F10] [F11] [F12] [Del]
Row 2: [`] [1] [2] [3] [4] [5] [6] [7] [8] [9] [0] [-] [=] [Backspace]
Row 3: [Tab] [Q] [W] [E] [R] [T] [Y] [U] [I] [O] [P] [[] []] [\]
Row 4: [Caps Lock] [A] [S] [D] [F] [G] [H] [J] [K] [L] [;] ['] [Enter]
Row 5: [Shift] [Z] [X] [C] [V] [B] [N] [M] [,] [.] [/] [Shift]
Row 6: [Ctrl] [Win] [Alt] [         SPACE         ] [Alt] [Ctrl] [←] [↑] [↓] [→]
```

### Symbols Panel (Right Zone — 6 Matching Rows)
```
Row 1 (Navigation)    : [Home] [End] [PgUp] [PgDn] [PrtSc] [Ins] [Pause] [ScrLk]
Row 2 (Shifted Symbols): [!] [@] [#] [$] [%] [^] [&] [*] [(] [)] [_] [+]
Row 3 (Math/Operators) : [+] [-] [*] [/] [=] [<] [>] [~]
Row 4 (Brackets/Quotes): [{] [}] [[] []] [(] [)] ["] [']
Row 5 (Punctuation)    : [:] [;] [?] [|] [\] [/] [,] [.]
Row 6 (Editing)        : [Backspace] [Enter] [Tab] [Del]
```

---

## Default Settings & Configuration

Settings are saved in `%APPDATA%\PointerV\settings.json`. Legacy configurations from `%APPDATA%\TonyPointer` or `~/.tony_pointer` are migrated automatically on first run.

| Key | Type | Default | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `sensitivity` | `float` | `1.0` | `0.2 .. 3.0` | Cursor motion multiplier |
| `one_euro_min_cutoff` | `float` | `1.0` | `0.1 .. 10.0` | Minimum cutoff frequency in Hz (jitter reduction at rest) |
| `one_euro_beta` | `float` | `0.007` | `0.0001 .. 0.1` | Speed coefficient (eliminates lag during fast flicks) |
| `double_tap_window_ms`| `int` | `500` | `200 .. 1000` | Maximum time between two taps for double-click |
| `dwell_time_s` | `float` | `0.60` | `0.2 .. 2.0` | Stationary hold duration to activate Brush Lock |
| `swipe_threshold` | `float` | `0.32` | `0.15 .. 0.60` | Normalized hand-size threshold to trigger row/window jump |
| `swipe_cooldown_s` | `float` | `0.30` | `0.10 .. 1.00` | Cooldown between swipe events |
| `key_repeat_delay_s` | `float` | `0.50` | `0.20 .. 1.50` | Initial hold delay before key repeat begins |
| `key_repeat_rate_cps` | `float` | `15.0` | `5.0 .. 30.0` | Key repeat rate in characters per second |
| `neighbor_lockout_ms` | `float` | `160.0` | `50.0 .. 400.0` | Lockout duration preventing adjacent finger misfires |
| `auto_pause_timeout_s`| `float` | `10.0` | `3.0 .. 60.0` | Idle timeout before auto-pausing when hand is lost |
| `dominant_hand` | `string`| `"auto"` | `"auto", "right", "left"` | Handedness preference for navigation directions |
| `fps_cap` | `int` | `60` | `15, 30, 60` | Target inference frame rate cap |
| `monitor_index` | `int` | `-1` | `-1 .. N` | `-1` for all monitors (virtual desktop), or specific monitor |
| `sound_enabled` | `bool` | `true` | `true, false` | Audio feedback cues for clicks and mode changes |
| `sound_volume` | `float` | `0.70` | `0.0 .. 1.0` | Sound effects volume level |
| `show_last_typed` | `bool` | `true` | `true, false` | Display recent typed character strip on keyboard HUD |

---

## Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Black camera feed** | Camera in use by Zoom, Teams, or another app | Close other camera apps. Pointer V automatically retries every 2 seconds. |
| **Camera access denied** | Windows Privacy Settings blocking desktop camera | Go to **Windows Settings -> Privacy & Security -> Camera** and enable **"Let desktop apps access your camera"**. |
| **Low Light / Glare Warning** | Ambient illumination is <40 or >220 luminance | Face a soft light source (lamp or monitor). Avoid direct harsh backlighting from windows behind you. |
| **Cannot click in Task Manager or game** | Target application is running with elevated Admin privileges | Launch Pointer V as Administrator (`Run as Administrator`) so `SendInput` has OS permission to inject events into elevated windows. |
| **Cursor jumps or jitters** | Cluttered visual background with hands/faces or reflective surfaces | Point camera toward a plain wall or ensure only one hand is raised within the active region box. |
| **Keys trigger unexpectedly** | Neighbor finger curl threshold too sensitive | In Settings -> Keyboard, increase `Neighbor Lockout` to `200 ms` or adjust finger curl threshold. |
| **SmartScreen warning during install** | Freshly compiled independent open-source binary | Click **More info -> Run anyway**. Checksum can be verified with `certutil -hashfile PointerV-Setup-2.0.0.exe SHA256`. |

---

## Tips for Best Accuracy

1. **Camera Position**: Place your webcam at chest or eye level, tilted slightly down. Avoid extreme upward angles from low laptop keyboards.
2. **Lighting**: Ensure uniform, diffused front lighting on your hand. Avoid bright backlights or direct sunlight behind your head.
3. **Hand Distance**: Keep your hand approximately 1.5 to 2.5 feet (45–75 cm) from the camera lens.
4. **Arm Rest**: Rest your elbow comfortably on your desk or chair armrest to avoid shoulder and arm fatigue during extended sessions.
5. **Practice Mode**: Use the built-in **Practice Page** (`Tab 5`) to test gesture confidence meters and live typing before daily use.

---

## Privacy & Security Guarantee

Pointer V is built from the ground up with a strict **Privacy-First Architecture**:
- **Zero Network Telemetry**: The application makes zero outgoing network calls. No usage metrics, error telemetry, or tracking pings exist.
- **In-Memory Frame Processing**: Camera frames are processed strictly in RAM and discarded immediately. No webcam images or video frames are ever saved to disk or transmitted.
- **Zero Keystroke Logging**: The application's diagnostic log (`%APPDATA%\PointerV\logs\pointer_v.log`) records only event counts, timings, and exceptions. **It never writes typed characters, text snippets, or key identifiers to disk.**
- **Password Field Suppression**: The keyboard HUD automatically suppresses the "Last Typed" preview strip when the active window title suggests a password prompt.

---

## Repository Structure

```
├── README.md                      # Primary project documentation
├── LICENSE                        # Apache-2.0 License (Veera Akash A)
├── index.html                     # Web studio HTML entrypoint
├── package.json                   # Web studio dependencies & scripts
├── vite.config.ts                 # Vite bundler configuration
├── src/                           # React 19 / TypeScript Web Studio
│   ├── App.tsx                    # Main Web Studio coordinator
│   ├── components/                # Web simulators & calibration controls
│   └── data/codeFiles.ts          # Embedded repository source explorer
├── installers/                    # Inno Setup Windows installer bundle
│   ├── PointerV.iss               # Inno Setup 6 compilation script
│   └── build_installer.bat        # Automated installer & checksum generator
└── pointer_v/                     # Native Windows Desktop Application
    ├── README.md                  # Desktop application guide
    ├── requirements.txt           # Python dependencies
    ├── PointerV.spec              # PyInstaller onedir specification
    ├── build_exe.bat              # Standalone PyInstaller build script
    ├── main.py                    # App entrypoint & system coordinator
    ├── theme.py                   # Centralized design tokens (Inter & JetBrains Mono)
    ├── settings.py                # JSON configuration manager & legacy migration
    ├── tracker.py                 # MediaPipe Tasks HandLandmarker vision engine
    ├── gestures.py                # Pose classifier & hold-to-pause logic
    ├── mouse.py                   # Per-Monitor DPI V2 & Win32 SendInput mouse
    ├── keyboard_out.py            # Win32 SendInput keyboard scancodes & modifiers
    ├── keyboard_ui.py             # PySide6 floating dark-glass Air Keyboard HUD
    ├── keyboard_layout.py         # 6-row Main & Symbols layouts and 4-key windows
    ├── finger_taps.py             # Independent per-finger curl detector & lockout
    ├── mode_manager.py            # Mode & sliding-door navigation state machine
    ├── camera.py                  # Threaded OpenCV capture & reconnect watchdog
    ├── filters.py                 # One Euro adaptive low-pass signal filter
    ├── overlay.py                 # PySide6 cursor reticle & dwell indicator
    ├── preview.py                 # Standalone picture-in-picture preview window
    ├── sound.py                   # Non-blocking audio cues & volume control
    ├── recorder.py                # Raw landmark stream recorder & replay engine
    ├── logger.py                  # Sanitized rotating file logger
    ├── ui/                        # Modular PySide6 interface
    │   ├── main_window.py         # Custom frameless main window
    │   ├── widgets.py             # Sidebar, title bar, chips, toggle switches
    │   ├── tutorial_dialog.py     # 7-step live gesture onboarding wizard
    │   └── pages/                 # Dashboard, Camera, Gestures, Keyboard, Practice...
    └── assets/                    # Bundled offline fonts, icons, models, sounds
```

---

## Roadmap & Credits

### Roadmap
- [x] Per-Monitor DPI Awareness V2 & Multi-Monitor normalization.
- [x] Inter-finger neighbor lockout and configurable key repeat rate.
- [x] Latching and locking sticky modifiers (`Shift`, `Ctrl`, `Alt`, `Win`, `CapsLock`).
- [x] Dark engineering pro UI redesign with bundled Inter and JetBrains Mono typography.
- [x] Offline bundled MediaPipe `hand_landmarker.task` model.
- [x] Raw landmark stream recording and deterministic headless replay engine.
- [ ] Custom macro binding for air gestures.
- [ ] Multi-hand two-handed chord typing mode.

### Credits & Citations
- **Google MediaPipe**: HandLandmarker vision pipeline ([Google Research](https://developers.google.com/mediapipe)).
- **One Euro Filter**: Casiez, G., Roussel, N. and Vogel, D. (2012), *1 € Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Human-Computer Interaction*.
- **PySide6**: The Qt Company, official Python bindings for Qt6.
- **Icons & Typography**: Lucide Icons, Rasmus Andersson (*Inter*), JetBrains (*JetBrains Mono*).

---

## License

Licensed under the **Apache License, Version 2.0**. See [LICENSE](LICENSE) for details.

Copyright (c) 2026 Veera Akash A.
