# Tony Pointer ⚡
### Iron-Man Holographic Hand Gesture PC Controller & Floating Air Keyboard

**Tony Pointer** is a dual-target system:
1. **A Native Windows Desktop Application** (Python 3.11, MediaPipe Tasks HandLandmarker, PySide6, Win32 SendInput) that lets you control your entire PC and type in the air with one hand using any webcam.
2. **An Interactive Web Studio & Simulator** (React 19, Vite, Tailwind CSS v4) allowing you to test hand gestures, simulate the 6-row Main Keyboard & docked Symbols Panel, calibrate One Euro filter thresholds, inspect Python source code, and download the full desktop project as a `.zip`.

---

## 🚀 Key Highlights

- **Whole-OS Control**: Control Windows outside the app across all monitors, desktop, browsers, games, and creative software via Win32 hardware `SendInput` (no PyAutoGUI focus traps).
- **Floating Air Keyboard + Docked Symbols Panel**:
  - **Main Keyboard (Left)**: Exact 6-row laptop layout with standard 26 letters (`10 + 9 + 7`), F1–F12, Esc, Del, Shift, Ctrl, Alt, Win, Space, and Arrow keys.
  - **Symbols Panel (Right)**: Aligned horizontally across 6 rows with distinct violet/teal holographic accent and glowing vertical divider labeled `SYMBOLS`.
  - **4-Key Progressive Windows**: Exactly 4 adjacent keys glow in electric blue under your 4 fingers (`Index`, `Middle`, `Ring`, `Pinky`).
  - **Sliding-Door Navigation**: Swipe whole hand Up/Down to switch rows; swipe Left/Right to hop 4-key windows.
  - **Inter-Zone Crossing**: Swipe right from the last window of Main keyboard across the glowing divider into Symbols; swipe left from Symbols to return to Main. Toggle anytime with `Ctrl + Alt + S`.
  - **Independent Finger Air-Taps**: Flex any of the 4 fingers to type that key. Thumb air-tap triggers `[SPACE]`.
  - **Hold-to-Repeat**: Holding any finger curled for >0.5s triggers repeating keystrokes at 30 chars/sec.
  - **Sticky Modifiers**: Single tap latches `Shift`, `Ctrl`, `Alt`, or `Win` for the next key; double tap locks it on; third tap clears.
- **Air Double-Tap Detection**: Rapid flex-and-release of the index finger twice within 500ms triggers double click to open files, folders, and applications.
- **Anti-Jitter Lookback Buffer**: Freezes cursor coordinates 150ms before tap initiation so physical finger motion never jerks the cursor off target icons.
- **One Euro Filter**: Dual-axis mathematical adaptive low-pass filter completely eliminates hand jitter at rest while keeping zero lag on rapid flicks.
- **Brush Lock (Paint Mode)**: Dwell still for 0.6s or pinch index + thumb to lock left click down for continuous painting in Photoshop, Krita, Clip Studio, or Figma.
- **Global Hotkeys**:
  - `Ctrl + Alt + T`: Toggle Tony Pointer Mode ON / OFF (minimizes to system tray).
  - `Ctrl + Alt + K`: Toggle Floating Air Keyboard HUD.
  - `Ctrl + Alt + S`: Toggle Keyboard Zone (Main ↔ Symbols).
  - `Ctrl + Alt + P`: Toggle Paint Mode Profile (Enhanced Brush Stabilizer).
  - `Esc`: Emergency release for mouse buttons and modifier keys.

---

## 🖐️ Hand Gesture Cheat Sheet

| Gesture | Pose / Motion | Action |
| :--- | :--- | :--- |
| **Move Cursor** | Pointing (Index finger extended, other fingers curled) | Moves mouse pointer with One Euro smoothing |
| **Air Double-Tap** | Quick curl-and-release flexure of index finger 2× within 500ms | Double Left Click (opens apps/folders) |
| **Air Single-Tap** | Single swift flexure of index finger | Single Left Click (configurable) |
| **Open Air Keyboard** | Hold OPEN PALM facing camera for ~0.5s | Launches Floating Air Keyboard HUD; pauses cursor |
| **Close Air Keyboard** | Hold FIST for ~0.5s, Pointing pose, or press `Esc` | Closes keyboard HUD; resumes Pointer mode |
| **Air Type Key** | Quick curl-and-release of Index, Middle, Ring, or Pinky | Types the locked key glowing electric blue |
| **Thumb Air-Tap** | Quick curl-and-release of Thumb | Types `[SPACE]` |
| **Slide Row (Up/Down)** | Move whole open hand up or down deliberately | Jumps active 4-key window up or down one row |
| **Hop Window (Left/Right)** | Move whole open hand left or right deliberately | Hops to next 4-key progressive window |
| **Cross into Symbols** | Swipe Right from the last window of Main keyboard | Glides blue focus across divider into Symbols panel |
| **Right Click** | Index + Middle fingers extended and held still for 0.5s | Opens Windows Context Menu |
| **Two-Finger Scroll** | Index + Middle fingers extended, move up/down vertically | Smoothly scrolls pages / documents |
| **Brush Lock (Pinch)** | Touch Thumb tip to Index fingertip | Locks left mouse button DOWN for drawing/painting |
| **Brush Lock (Dwell)** | Hold index finger stationary for 0.6 seconds | Locks left mouse button DOWN |
| **Emergency Safety** | Press `Esc` or take hand out of view for > 1.0s | Releases all mouse buttons and keyboard modifiers |

---

## 🎹 Keyboard Layout Architecture

### 1. Main Keyboard (Left Zone — Exact 6 Rows)
```
Row 1: [Esc] [F1] [F2] [F3] [F4] [F5] [F6] [F7] [F8] [F9] [F10] [F11] [F12] [Del]
Row 2: [`] [1] [2] [3] [4] [5] [6] [7] [8] [9] [0] [-] [=] [Backspace]
Row 3: [Tab] [Q] [W] [E] [R] [T] [Y] [U] [I] [O] [P] [[] []] [\]
Row 4: [Caps Lock] [A] [S] [D] [F] [G] [H] [J] [K] [L] [;] ['] [Enter]
Row 5: [Shift] [Z] [X] [C] [V] [B] [N] [M] [,] [.] [/] [Shift]
Row 6: [Ctrl] [Win] [Alt] [         SPACE         ] [Alt] [Ctrl] [←] [↑] [↓] [→]
```
*(Total: 26 standard letters = 10 in Row 3 + 9 in Row 4 + 7 in Row 5)*

### 2. Symbols Panel (Right Zone — Docked, 6 Matching Rows)
```
Row 1 (Navigation)    : [Home] [End] [PgUp] [PgDn] [PrtSc] [Ins] [Pause] [ScrLk]
Row 2 (Shifted Numbers): [!] [@] [#] [$] [%] [^] [&] [*] [(] [)] [_] [+]
Row 3 (Math/Operators) : [+] [-] [*] [/] [=] [<] [>] [~]
Row 4 (Brackets/Quotes): [{] [}] [[] []] [(] [)] ["] [']
Row 5 (Punctuation)    : [:] [;] [?] [|] [\] [/] [,] [.]
Row 6 (Editing)        : [Backspace] [Enter] [Tab] [Del]
```

---

## 💻 Native Windows Desktop Setup (Python 3.11)

### Requirements
- **OS**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.11.x
- **Hardware**: Standard 720p or 1080p USB webcam

### Quick Start
```bash
# 1. Clone repository and navigate to desktop app folder
cd tony_pointer

# 2. Create and activate a Python virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run Tony Pointer
python main.py
```

### Packaging into a Standalone `.exe`
Run the included batch script:
```cmd
build_exe.bat
```
The compiled, standalone single executable will be generated at:
```
dist\TonyPointer.exe
```

---

## 🌐 Web Studio & Simulator (Vite + React)

The web studio runs directly in the browser and provides:
- **Live Chamber & PC Sandbox**: Test hand tracking with live camera feed, active region boundary calibration, and interactive desktop simulator (paint canvas, desktop icons, browser tab).
- **Air Keyboard Simulator**: Experience the full dual-zone floating keyboard HUD with keyboard hotkeys (`1-4` for fingers, `Space` for thumb, arrow keys for sliding door navigation, and real-time typed output stream).
- **Python Source Explorer**: View, browse, and copy all 13 Python desktop modules.
- **One Euro & Calibration Studio**: Fine-tune cutoff frequencies (`fc_min`), speed coefficient (`beta`), swipe sensitivity, and gesture dwell timers.
- **One-Click ZIP Downloader**: Download the entire Python desktop codebase packaged with PyInstaller build scripts directly from the header.

### Running the Web Studio Locally
```bash
# Install dependencies
npm install

# Start Vite dev server on port 3000
npm run dev
```

---

## 📁 Repository File Tree

```
├── README.md                      # Project documentation and guide
├── index.html                     # Web entry point
├── metadata.json                  # AI Studio metadata & capabilities
├── package.json                   # Web studio dependencies
├── vite.config.ts                 # Vite + Tailwind configuration
├── src/
│   ├── App.tsx                    # Main web studio coordinator & tab router
│   ├── components/
│   │   ├── AirKeyboardSimulator.tsx # Interactive dual-zone keyboard simulator
│   │   ├── ArcReactorButton.tsx   # Holographic Tony Stark power toggle
│   │   ├── CodeStudio.tsx         # In-browser Python source explorer
│   │   ├── SettingsStudio.tsx     # Calibration and One Euro filter controls
│   │   ├── SetupGuide.tsx         # Windows installation & build guide
│   │   ├── VirtualPcScreen.tsx    # Interactive PC sandbox canvas
│   │   └── WebcamSimulator.tsx    # Webcam preview HUD simulator
│   └── data/
│       └── codeFiles.ts           # Python codebase repository for viewer & ZIP
└── tony_pointer/                  # Native Windows Desktop Application
    ├── README.md                  # Desktop application documentation
    ├── requirements.txt           # Python package requirements
    ├── tony_pointer.spec          # PyInstaller single-exe packaging configuration
    ├── build_exe.bat              # One-click Windows build batch script
    ├── main.py                    # Application coordinator, hotkeys & system tray
    ├── tracker.py                 # MediaPipe Tasks HandLandmarker tracking engine
    ├── gestures.py                # Pose classifier (pointing, palm, fist, pinch)
    ├── keyboard_layout.py         # Main 6-row & Symbols 6-row layout definitions
    ├── keyboard_out.py            # Win32 SendInput scancode & unicode output
    ├── keyboard_ui.py             # PySide6 transparent holographic keyboard HUD
    ├── finger_taps.py             # Independent per-finger curl & velocity detector
    ├── mode_manager.py            # POINTER / KEYBOARD / PAINT mode state machine
    ├── mouse.py                   # Win32 SendInput mouse dispatch & jitter buffer
    ├── filters.py                 # One Euro adaptive low-pass filter
    ├── overlay.py                 # PySide6 holographic cyan reticle overlay
    ├── preview.py                 # Picture-in-picture webcam feed overlay
    ├── ui.py                      # PySide6 desktop settings & calibration window
    └── settings.py                # JSON settings persistence & profiles
```

---

## 🛡️ License

Apache-2.0 License. Designed for Stark Industries enthusiasts and touch-free accessibility.
