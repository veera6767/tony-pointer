======================================================================
                     POINTER V (PV) - v2.0.5
       Native Windows Hand Gesture Mouse & Air Keyboard Controller
======================================================================

Thank you for trying Pointer V! This standalone setup package allows you
to control Windows with your hand using an ordinary webcam.

----------------------------------------------------------------------
1. SYSTEM REQUIREMENTS
----------------------------------------------------------------------
- OS: Windows 10 or Windows 11 (64-bit x64)
- Camera: Any built-in or USB webcam (720p or 1080p recommended, 30+ FPS)
- VC++ Redistributable: Microsoft Visual C++ 2015-2022 Redistributable (x64)
  (The installer will automatically detect if it is present and offer to open
   the official Microsoft download page if missing.)

----------------------------------------------------------------------
2. HOW TO INSTALL
----------------------------------------------------------------------
1. Double-click "PointerV-Setup-2.0.5.exe".
2. If Windows SmartScreen displays "Windows protected your PC":
   - Click "More info"
   - Click "Run anyway"
   (This is normal for newly packaged open-source executables.)
3. Choose your install location (defaults to your user Programs folder,
   no administrator permissions required).
4. Optionally check "Create a desktop icon".
5. Click "Install" and then "Finish". Pointer V will launch immediately.

----------------------------------------------------------------------
3. FIRST RUN CHECKLIST
----------------------------------------------------------------------
When the Pointer V window opens, check the 6-item Dashboard status:
1. Camera: Green checkmark showing connected webcam and FPS (~30-60 FPS).
2. Model: Shows "HandLandmarker Loaded (CPU)".
3. Hand: Hold up your hand facing the camera at a distance of 1.5 to 3 feet.
   The status will turn Green with detected pose and neon skeleton tracking.
4. Pointer V: Click the large "POINTER MODE" button or press Ctrl+Alt+T
   to activate cursor control.
5. Cursor: The blue gaming reticle will follow your index fingertip.
6. Air Keyboard: Open your palm flat for 0.8 seconds, or press Ctrl+Alt+K,
   to open the floating corner Air Keyboard.

----------------------------------------------------------------------
4. GESTURE QUICK REFERENCE
----------------------------------------------------------------------
- Move Cursor: Point index finger (or index + thumb).
- Left Click: Air double-tap or single tap with index finger.
- Right Click: Extend index and middle finger together for 0.4 seconds.
- Drag & Drop: Close fist over an item to hold; move hand; open hand to drop.
- Scroll: Move index and middle finger up/down together.
- Air Keyboard (Floating HUD):
  - Hold open palm flat for 0.8s to show keyboard docked in corner.
  - Swipe hand left / right / up / down to navigate between letter clusters.
  - Curl your index, middle, ring, or pinky finger to strike keys.
  - Hold fist for 0.5s or press Esc to close keyboard.
- Emergency Safety Release: Press the ESC key at any time.

----------------------------------------------------------------------
5. GLOBAL SHORTCUTS
----------------------------------------------------------------------
- Ctrl + Alt + T          : Toggle Pointer V ON / OFF
- Ctrl + Alt + K          : Toggle Floating Air Keyboard
- Ctrl + Alt + S          : Switch Keyboard Zone (Main QWERTY <-> Symbols)
- Ctrl + Alt + P          : Toggle Creative / Paint Mode
- Ctrl + Alt + Space      : Pause / Resume Tracking
- Esc                     : Safety release (releases all held buttons)
- Ctrl + Alt + Shift + Esc: Panic killswitch (immediate disengage)

----------------------------------------------------------------------
6. CONTROLLING ELEVATED / ADMINISTRATOR WINDOWS
----------------------------------------------------------------------
Standard Windows UIPI (User Interface Privilege Isolation) prevents normal
applications from injecting mouse clicks into Administrator command prompts,
Task Manager, or UAC prompts.
If you need Pointer V to click inside elevated windows:
- Go to the "Settings" tab in Pointer V.
- Click "Restart Pointer V as Administrator".

----------------------------------------------------------------------
7. UNINSTALLING
----------------------------------------------------------------------
To uninstall Pointer V:
- Open Windows "Settings" -> "Installed apps" -> "Pointer V" -> "Uninstall",
  OR run the uninstaller from the Start Menu:
  "Start Menu" -> "Pointer V" -> "Uninstall Pointer V".
- The uninstaller will ask if you want to keep or delete your custom
  settings and logs stored in %APPDATA%\PointerV.

----------------------------------------------------------------------
8. FILE CHECKSUMS (SHA-256)
----------------------------------------------------------------------
PointerV-Setup-2.0.5.exe:
423e58b7ee278c5629da4b0044595d27214fbda9258efed38c94b05537e0629c

