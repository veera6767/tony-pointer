# Pointer V - Complete Architecture and Freeze Audit (Phase A)

**Date**: 2026-11-11  
**Target**: Pointer V v2.0.2 / v2.0.3  
**Auditor**: Senior Systems & Windows Software Engineer  
**Scope**: All threading, event loops, timers, Qt signals, Win32 hooks, SendInput call sites, GIL contention, and Windows message pump health.

---

## 1. System Inventory

### 1.1 Threads & Worker Loops
| Thread Name | Owner / Origin | Type | Blocking / Sleep Behavior | Touches Qt Widgets? | Description |
|---|---|---|---|---|---|
| **Main UI Thread** | `QApplication.exec()` | Main OS / Qt Thread | Event-driven (`GetMessage`/`DispatchMessage`) | **YES (Primary)** | Runs Qt UI event loop, renders all windows (`MainWindow`, `CursorOverlayWindow`, `FloatingAirKeyboardWidget`, `CameraPreviewOverlay`), processes timer callbacks, and handles Windows window messages. |
| **Camera Reader Thread** | `CameraStream._capture_worker` | Python `threading.Thread` (daemon) | `cap.read()` blocks on DirectShow driver; `time.sleep(2.0)` on reconnect. | **NO** | Continuously reads camera frames via OpenCV DirectShow, mirrors horizontally, calculates average luminance, and stores in `self.latest_frame` under `threading.Lock`. |
| **Vision & Pipeline Thread** | `PointerVApp._processing_loop` | Python `threading.Thread` (daemon) | `camera.get_frame()`, MediaPipe CPU inference, gesture processing, sleep pacing (`time.sleep(sleep_time)`). | **NO (Emits signals)** | Central 30-60 Hz loop: fetches camera frame, runs MediaPipe HandLandmarker inference, evaluates gestures, calls SendInput for mouse/keystrokes, draws HUD landmarks with OpenCV, and emits Qt queued signals to UI thread. |
| **Global Keyboard Hook Thread** | Python `keyboard` library | OS Thread via `SetWindowsHookExW(WH_KEYBOARD_LL)` | Blocks on Win32 message pump for OS keyboard hook. | **NO (Calls lambda)** | Intercepts EVERY keystroke on the entire Windows operating system. Invokes Python callbacks for global hotkeys (`Ctrl+Alt+T`, `Ctrl+Alt+K`, `Ctrl+Alt+S`, `Ctrl+Alt+P`, `Ctrl+Alt+Space`, `Esc`). |

---

### 1.2 QTimers & Periodic Intervals
| Timer | Interval | Thread | Callback / Action | Touches Qt Widgets? |
|---|---|---|---|---|
| `MainWindow.telemetry_timer` | 33 ms (~30 Hz) | Main UI Thread | `_refresh_telemetry()`: pulls telemetry dict and latest frame, updates 15+ QLabel texts, re-evaluates stylesheets, and performs CPU bicubic image scaling (`QPixmap.fromImage(q_img).scaled(..., SmoothTransformation)`). | **YES (Heavy)** |
| `CursorOverlayWindow.anim_timer` | 16 ms (~60 Hz) | Main UI Thread | `_animate_step()`: increments ripple radius, tap ring contraction, comet trail cleanup, mode chip opacity, and triggers `self.update()` (repaints radial gradients, comet trail circles, gaming reticle). | **YES (Heavy)** |
| `FloatingAirKeyboardWidget.anim_timer` | 16 ms (~60 Hz) | Main UI Thread | `_on_animate()`: advances glow phase, flash opacity, slide-and-fade window translation/opacity, and calls `self.update()`. | **YES (Moderate)** |
| `PointerVApp.fg_timer` | 500 ms (2 Hz) | Main UI Thread | `_check_foreground_window()`: calls `user32.GetForegroundWindow()`, queries `psutil.Process(pid).name()`, and performs auto-paint / password field detection. | **YES (Queries psutil on UI thread)** |
| `PointerVApp.heartbeat_timer` | 100 ms (10 Hz) | Main UI Thread | `_ui_heartbeat_tick()`: updates `self.ui_heartbeat_timestamp = time.perf_counter()` and re-arms `faulthandler.dump_traceback_later(3)`. | **NO** |

---

### 1.3 Qt Signals & Data Flow
| Signal Name | Source Thread | Destination Thread | Payload Data | Frequency | Evaluation & Risk |
|---|---|---|---|---|---|
| `signals.frame_updated` | Worker Thread | Main UI Thread | `numpy.ndarray` (360x202x3 BGR frame), `fps` float | 30 - 60 Hz | **HIGH RISK**: Marshals large numpy array across Qt queued signal mechanism on every frame. Receiver in `preview.py` allocates new `QPixmap` and converts colorspace on the UI thread. |
| `signals.cursor_updated` | Worker Thread | Main UI Thread | `(int x, int y, str state, float dwell, float hold, str kind)` | 30 - 60 Hz | **HIGH RISK**: Triggers `CursorOverlayWindow.move(x, y)` on every frame. Calling `move()` on a transparent top-level QWidget sends `WM_MOVE`/`WM_PAINT` through Windows DWM at 60 Hz. |
| `signals.keyboard_updated` | Worker Thread | Main UI Thread | `(Zone, int row, int win, dict modifiers, bool bounce)` | 10 - 30 Hz | Low payload, safe dictionary. |
| `signals.key_typed` | Worker Thread | Main UI Thread | `(str code, str label)` | Event-based | Low payload, safe. |
| `signals.keyboard_visibility_requested` | Worker Thread | Main UI Thread | `bool` | Event-based | Mode change only. Safe now that it is queued. |
| `signals.tray_notification_requested` | Worker Thread | Main UI Thread | `(str title, str message)` | Low (alerts only) | Safe. |
| `signals.tray_visuals_requested` | Worker Thread | Main UI Thread | None | Low (state changes) | Safe. |

---

### 1.4 Global Hooks & SendInput Call Sites
| Subsystem | Hook / API | Location | Mechanism & Latency |
|---|---|---|---|
| Global Hotkeys | `SetWindowsHookExW(WH_KEYBOARD_LL)` | `keyboard.add_hotkey(...)` in `main.py:456` | Installed system-wide. Every keystroke across Windows enters this Python hook. If Python GIL is blocked for > 200ms, Windows `LowLevelHooksTimeout` drops the hook or stalls input. |
| Mouse Cursor Movement | `user32.SendInput` | `mouse.py:293` (`move_to`) | `MOUSEEVENTF_MOVE \| MOUSEEVENTF_ABSOLUTE \| MOUSEEVENTF_VIRTUALDESK`. Called up to 60 Hz. |
| Mouse Left Click / Up / Down | `user32.SendInput` | `mouse.py:350, 316, 323` | `MOUSEEVENTF_LEFTDOWN`, `MOUSEEVENTF_LEFTUP`. Includes `time.sleep(0.015)` between down and up. |
| Mouse Right Click | `user32.SendInput` | `mouse.py:370` | `MOUSEEVENTF_RIGHTDOWN`, `MOUSEEVENTF_RIGHTUP`. Includes `time.sleep(0.02)` between down and up. |
| Keystrokes & Modifiers | `user32.SendInput` | `keyboard_out.py:270-380` | `KEYEVENTF_SCANCODE` with `KEYEVENTF_KEYUP`. Injected keystrokes loop directly back into the `WH_KEYBOARD_LL` hook! |

---

## 2. Ranked List of Suspected Causes for the ~5-Second Freeze

### Rank 1: Windows 5000 ms `HungWindowTimeout` due to UI Thread Overload & GIL Starvation
* **Mechanism**: Windows User32 tracks whether top-level windows service their message queue. If a thread owning a window does not process messages for **5.0 seconds** (the exact default Windows `HungWindowTimeout`), Windows Desktop Window Manager (DWM) flags the window as **"Not Responding"**, covers it with a ghost window, and disables button interactions.
* **Why it happens after ~5 seconds**:
  1. Turning Pointer V ON starts the 60 Hz worker thread running CPU-heavy MediaPipe CPU inference and OpenCV HUD drawing.
  2. The worker thread floods the Qt message queue with `signals.cursor_updated` (60 Hz) and `signals.frame_updated` (30-60 Hz).
  3. `MainWindow.telemetry_timer` ticks every 33 ms, performing CPU bicubic smooth transformation scaling of video thumbnails and calling `setStyleSheet()` across 15 labels (forcing full CSS stylesheet re-parsing).
  4. Both `overlay.py` and `keyboard_ui.py` run independent 16 ms (60 Hz) animation timers painting radial gradients and bezier paths.
  5. Under Python 3.12's GIL, 4 active threads compete for CPU time. The UI thread's event loop falls behind the incoming Windows message rate, triggering the 5-second hung window watchdog.

### Rank 2: Self-Feedback Loop from Injected Mouse Move onto Pointer V Windows
* **Mechanism**: When `self.mouse.move_to(cx, cy)` injects mouse movements across the screen, the cursor frequently glides over Pointer V's own `MainWindow` or `CursorOverlayWindow`.
* **Consequence**: Windows injects `WM_MOUSEMOVE` and `WM_NCHITTEST` back into Pointer V's UI thread message queue at 60 Hz. Qt's internal event dispatcher processes hover states, stylesheet `:hover` recalculations, and layout updates on the UI thread for its own injected movements.

### Rank 3: Global `keyboard` Library `WH_KEYBOARD_LL` Hook Collision & Timeout
* **Mechanism**: `keyboard.add_hotkey` installs a low-level OS keyboard hook. On Windows, low-level hooks have a strict OS timeout (typically 200-300 ms).
* **Consequence**: When the vision loop and UI thread saturate the GIL, the `keyboard` hook thread cannot respond to OS hook queries within the timeout. Windows marks the hook as timed out, leading to input hitches or deadlocks when `SendInput` sends keystrokes that attempt to route through the stalled hook.

### Rank 4: Frame Flooding via Qt Queued Signals
* **Mechanism**: Emitting large numpy arrays (`signals.frame_updated.emit(thumb)`) 30-60 times a second creates Python object references in the Qt event queue. If the UI thread spends more than 16 ms processing a frame, queued frame signals accumulate in memory, creating event-loop backlog and memory growth.

### Rank 5: Camera Never Released (`cap.release()` lifecycle bug)
* **Mechanism**: In `main.py`, `self.camera.start()` is called at startup. In `set_active(False)`, `camera.stop()` is never called.
* **Consequence**: The camera hardware handle remains open indefinitely, the webcam activity LED remains permanently illuminated, and DirectShow capture threads continue burning CPU in the background even when Pointer V is turned OFF.

---

## 3. Specific Audit Findings

1. **GIL Starvation**: High risk. MediaPipe CPU inference (12-18 ms) and OpenCV HUD drawing (4-6 ms) in the vision thread run back-to-back with almost zero sleep. The UI thread's timer-driven smooth image scaling and stylesheet updates contend for the GIL simultaneously.
2. **Signal / Event Flooding**: Full image numpy arrays and 60 Hz cursor positions are emitted across threads. Must be replaced with a lockless latest-value mailbox (UI pulls frame at 10-15 Hz only when preview is visible) and cursor position throttling.
3. **Cursor Overlay Heavy Painting**: `overlay.py` repaints at 60 Hz using radial gradients, dynamic polygon math, and dynamic comet trail loops, moving a top-level window with `self.move()`. This must be pre-rendered into cached pixmap sprites.
4. **Camera Lifecycle**: Camera is opened on startup and never released until entire process shutdown. Must be tied strictly to active tracking or open preview pages.
5. **Win32 Hotkeys**: `keyboard` library's `WH_KEYBOARD_LL` hook should be replaced with clean native Win32 `RegisterHotKey`, eliminating low-level hook timeouts entirely.
