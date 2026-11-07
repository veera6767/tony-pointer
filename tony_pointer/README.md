# Tony Pointer 🚀
### Iron-Man Holographic Hand Gesture PC Controller & Floating Air Keyboard

Control your entire Windows PC with one hand using any standard webcam. Designed with a Stark Industries / JARVIS aesthetic, low-latency MediaPipe Tasks vision inference, Win32 hardware-level SendInput mouse and keyboard dispatch, and intelligent air-tap stabilization.

---

## ⚡ Key Features

- **Whole-OS Control**: Control your PC anywhere (desktop, browser, games, Windows Explorer, full-screen apps) without focus traps.
- **Floating Air Keyboard + Symbols Panel**:
  - Type in the air with one hand into ANY application on Windows.
  - **Main 6-Row Laptop Keyboard** on the left with exact 26-letter standard layout.
  - **Dedicated Symbols Panel** docked on the right side with violet/teal accents and 6 matching horizontal rows (Navigation, Shifted Symbols, Math/Operators, Brackets/Quotes, Punctuation, Editing).
  - **4-Key Window Geometry**: Exactly 4 adjacent keys glow in bright electric BLUE neon under your 4 fingers (Index, Middle, Ring, Pinky).
  - **"Sliding Door" Navigation**: Swipe whole hand Up/Down to jump rows; swipe Left/Right to hop 4-key windows.
  - **Zone Crossing**: Swiping Right from the last window of Main keyboard smoothly crosses the divider into the Symbols panel; swiping Left from Symbols returns to Main.
  - **Independent Finger Air-Taps**: Curl any of your 4 fingers to type the exact key under it. Thumb tap triggers Space bar.
  - **Sticky Modifiers**: Shift, Ctrl, Alt, Win, CapsLock. 1 tap latches modifier for next key; double tap locks it on.
- **Air Double-Tap Detection**: Rapid double-tap with index finger to open apps, files, and folders in Pointer mode.
- **Lookback Anti-Jitter Anchoring**: Captures cursor coordinates 150ms before tap start using a historical ring buffer so mechanical finger flexure never jerks the cursor off targets.
- **One Euro Filter**: Mathematical dual-axis adaptive smoothing that completely eliminates human hand tremor while preserving instantaneous twitch responsiveness during fast motions.
- **Brush Lock (Paint Mode)**: Dwell still for 0.6s or pinch index+thumb to lock left click down for continuous painting in Photoshop, Krita, MS Paint, Clip Studio, or Figma.
- **Holographic Overlays**: Click-through transparent cyan reticle, shockwave ripple pulses, and mini floating camera HUD.
- **Global Hotkeys**:
  - `Ctrl + Alt + T`: Toggle Tony Pointer Mode ON / OFF
  - `Ctrl + Alt + K`: Toggle Floating Air Keyboard ON / OFF
  - `Ctrl + Alt + S`: Toggle Keyboard Zone (Main <-> Symbols)
  - `Ctrl + Alt + P`: Toggle Paint Mode Profile (Enhanced Stabilizer)
  - `Esc`: Emergency Release for all mouse buttons and keyboard modifiers

---

## 🖐️ Gesture Reference Guide

| Gesture | Hand Posture | Action |
| :--- | :--- | :--- |
| **Move Cursor** | Pointing (Index finger extended, other fingers curled) | Moves mouse cursor with One Euro Filter smoothing |
| **Air Double-Tap** | Quick curl-and-release flexure of index finger 2x within 500ms | Double Left Click (opens apps/folders) |
| **Air Single-Tap** | Single swift flexure of index finger | Single Left Click (configurable) |
| **Open Air Keyboard** | Hold OPEN PALM for ~0.5s (with radial progress ring) | Opens Floating Air Keyboard HUD & pauses cursor |
| **Close Air Keyboard**| Hold FIST for ~0.5s, Pointing pose, or press Esc | Closes Keyboard HUD & returns to Pointer mode |
| **Air Type Key** | Quick curl-and-release of Index, Middle, Ring, or Pinky | Types the exact key glowing blue under that finger |
| **Thumb Air-Tap** | Quick curl-and-release of Thumb | Types Space bar |
| **Slide Row (Up/Down)**| Move whole open hand up or down deliberately | Jumps active 4-key window up or down one row |
| **Hop Window (Left/Right)**| Move whole open hand left or right deliberately | Hops to next 4-key window; crosses between Main & Symbols |
| **Cross into Symbols** | Swipe Right from the last window of Main keyboard | Slides blue focus across divider into Symbols panel |
| **Right Click** | Index + Middle fingers both extended and held still for 0.5s | Opens Windows Context Menu |
| **Two-Finger Scroll**| Index + Middle fingers extended, move up/down vertically | Smoothly scrolls pages / documents up or down |
| **Brush Lock (Pinch)**| Touch Thumb tip to Index fingertip | Locks left mouse button DOWN for drawing/painting |
| **Brush Lock (Dwell)**| Hold index finger stationary for 0.6 seconds | Locks left mouse button DOWN |
| **Emergency Safety** | Press `Esc` or take hand out of view for > 1.0s | Releases all mouse buttons and keyboard modifiers |

---

## 🎹 Keyboard Layouts

### 1. Main Keyboard (Left) - Exact 6 Rows
- **Row 1**: `Esc` `F1` `F2` `F3` `F4` `F5` `F6` `F7` `F8` `F9` `F10` `F11` `F12` `Del`
- **Row 2**: `` ` `` `1` `2` `3` `4` `5` `6` `7` `8` `9` `0` `-` `=` `Backspace`
- **Row 3**: `Tab` `Q` `W` `E` `R` `T` `Y` `U` `I` `O` `P` `[` `]` `\`
- **Row 4**: `Caps` `A` `S` `D` `F` `G` `H` `J` `K` `L` `;` `'` `Enter`
- **Row 5**: `Shift` `Z` `X` `C` `V` `B` `N` `M` `,` `.` `/` `Shift`
- **Row 6**: `Ctrl` `Win` `Alt` `Space` `Alt` `Ctrl` `Left` `Up` `Down` `Right`

### 2. Symbols Panel (Right) - 6 Matching Rows
- **Row 1 (Navigation)**: `Home` `End` `PgUp` `PgDn` `PrtSc` `Ins` `Pause` `ScrLk`
- **Row 2 (Shifted Symbols)**: `!` `@` `#` `$` `%` `^` `&` `*` `(` `)` `_` `+`
- **Row 3 (Math/Operators)**: `+` `-` `*` `/` `=` `<` `>` `~`
- **Row 4 (Brackets/Quotes)**: `{` `}` `[` `]` `(` `)` `"` `'`
- **Row 5 (Punctuation)**: `:` `;` `?` `|` `\` `/` `,` `.`
- **Row 6 (Editing)**: `Backspace` `Enter` `Tab` `Del`

---

## 🛠️ Installation & Build Instructions

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Tony Pointer
python main.py

# 3. Build standalone single .exe
build_exe.bat
# Output created at dist\TonyPointer.exe
```

---

## 🧪 How to Test the Air Keyboard

1. **Activate Tony Pointer**: Press the big Arc Reactor button or press `Ctrl + Alt + T`.
2. **Open the Air Keyboard**: Raise your open hand in front of the camera (all 5 fingers extended, palm facing camera) and hold for 0.5s until the cyan progress ring completes. The holographic keyboard will float into view.
3. **Inspect the 4-Key Blue Window**: Look at the glowing electric blue keys on Row 4 (default: `[A S D F]`).
4. **Type a Character**: Curl and release your middle finger; the second key (`S`) will flash white-blue and type into your active window!
5. **Slide to Another Row**: Move your whole hand down by a few inches; the blue window will slide down to Row 5 (`[Z X C V]`). Move your hand up to slide to Row 3.
6. **Hop Windows & Cross into Symbols**:
   - Move your hand to the right; the blue window will hop to `[B N M ,]`.
   - On the last window of the row, you will see a pulsing chevron arrow `>` on the divider.
   - Swipe right deliberately once more; the blue glow will glide across the divider directly into the **Symbols Panel**!
   - Press `Ctrl + Alt + S` at any time to toggle between Main and Symbols zones.
7. **Close Keyboard**: Make a tight fist and hold for 0.5s, or extend only your index finger to return instantly to pointer mode.

---

## 🔧 Troubleshooting

- **Keystrokes not typing into an app?**: Some elevated Windows applications (such as Task Manager or admin Command Prompt) require Tony Pointer to be launched as Administrator.
- **Double row jumps when swiping?**: Increase `swipe_cooldown_ms` (e.g. from 300ms to 400ms) or slightly raise `swipe_threshold` in settings.
- **Ring or pinky finger tap sensitivity?**: In the settings panel, tune the `ring_sensitivity` and `pinky_sensitivity` sliders. A higher multiplier lowers the angular flexion needed.
- **Emergency release**: Hit `Esc` at any time to clear all latched modifiers, unpress keys, and release any mouse buttons.
