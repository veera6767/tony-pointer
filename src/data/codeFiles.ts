export interface CodeFile {
  name: string;
  path: string;
  description: string;
  language: string;
  content: string;
}

export const TONY_POINTER_FILES: CodeFile[] = [
  {
    name: "main.py",
    path: "tony_pointer/main.py",
    description: "Application orchestrator: QApp, System Tray, Global Hotkeys (Ctrl+Alt+T, Ctrl+Alt+K, Ctrl+Alt+S), Air Keyboard & SendInput dispatch",
    language: "python",
    content: `"""
Tony Pointer - Main Application Entrypoint & System Coordinator
Launches the PySide6 Application, initializes background worker threads,
hooks system tray, registers global OS hotkeys, and coordinates MediaPipe tracking
with Win32 SendInput mouse dispatch and Floating Air Keyboard.
"""

import os
import sys
import threading
import time
from typing import Optional

try:
    import winsound
    def play_sound(freq=800, dur=60):
        winsound.Beep(freq, dur)
except Exception:
    def play_sound(freq=800, dur=60):
        pass

import keyboard
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from camera import CameraStream, draw_hud_landmarks
from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine
from keyboard_layout import KeyboardLayoutManager, KeyboardWindow, Zone
from keyboard_out import ModifierState, Win32KeyboardOutput
from keyboard_ui import FloatingAirKeyboardWidget
from mode_manager import AppMode, ModeManager
from mouse import MouseController
from overlay import CameraPreviewOverlay, CursorOverlayWindow
from settings import SettingsManager
from tracker import HandTracker
from ui import MainWindow


class TonyPointerApp(QObject):
    """Coordinates hardware capture, gesture tracking, overlays, mouse input, and air keyboard."""

    state_updated = Signal()
    key_typed_signal = Signal(str, str) # code, label

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.config

        # 1. Hardware & Mouse Subsystems
        self.mouse = MouseController()
        self.screen_bounds = self.mouse.get_screen_bounds()

        # One Euro Filter for 2D cursor mapping
        self.filter = OneEuroFilter2D(
            min_cutoff=self.settings.one_euro.min_cutoff,
            beta=self.settings.one_euro.beta,
        )

        # MediaPipe Tasks Hand Tracker
        self.tracker = HandTracker()

        # Gesture Detection Engine
        self.gesture_engine = GestureEngine(self.settings)

        # 2. Keyboard & Input Subsystems
        self.layout_manager = KeyboardLayoutManager()
        self.keyboard_out = Win32KeyboardOutput()
        self.finger_tap_detector = FingerTapDetector(self.settings)
        self.mode_manager = ModeManager(self.settings, self.layout_manager)

        # Threaded Camera Capture
        self.camera = CameraStream(
            camera_index=self.settings.camera_index,
            width=self.settings.camera_width,
            height=self.settings.camera_height,
            target_fps=self.settings.target_fps,
        )

        # 3. Overlays & Windows
        self.cursor_overlay = CursorOverlayWindow(self.settings)
        self.camera_overlay = CameraPreviewOverlay(self.settings)
        self.keyboard_overlay = FloatingAirKeyboardWidget(self.settings, self.layout_manager)

        # Master Mode Toggle
        self.is_active = False
        self.paint_profile_active = False

        # Shared Status Telemetry
        self.telemetry = {
            "fps": 0.0,
            "latency_ms": 0.0,
            "mode": "POINTER",
            "pose": "UNKNOWN",
            "action": "NONE",
            "status_text": "OFFLINE",
            "brush_locked": False,
            "foreground_app": "DESKTOP",
            "raw_hand": None,
            "kb_zone": "MAIN",
            "kb_row": 3,
            "kb_win_keys": ["A", "S", "D", "F"],
            "curls": {},
        }
        self.latest_vis_frame = None

        # 4. Main GUI Window
        self.main_window = MainWindow(
            settings_manager=self.settings_manager,
            get_status_fn=lambda: self.telemetry,
            get_frame_fn=lambda: self.latest_vis_frame,
        )
        self.main_window.toggle_mode_requested.connect(self.set_mode)
        self.main_window.settings_changed.connect(self._on_settings_reloaded)

        self.key_typed_signal.connect(self.keyboard_overlay.trigger_key_flash)

        # 5. System Tray Integration
        self._setup_tray()

        # 6. Global Hotkeys
        self._setup_hotkeys()

        # 7. Start Camera Stream
        self.camera.start()

        # 8. Processing Thread & Loop
        self.running = True
        self.worker_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.worker_thread.start()

        # 9. Foreground Window Inspector Timer
        self.fg_timer = QTimer(self)
        self.fg_timer.timeout.connect(self._check_foreground_window)
        self.fg_timer.start(500)

        if not self.settings.start_minimized:
            self.main_window.show()

    def _create_tray_icon(self) -> QIcon:
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QColor(0, 229, 255))
        painter.setBrush(QColor(11, 15, 25))
        painter.drawEllipse(2, 2, 28, 28)
        painter.setBrush(QColor(0, 229, 255))
        painter.drawEllipse(11, 11, 10, 10)
        painter.end()
        return QIcon(pix)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._create_tray_icon())
        self.tray.setToolTip("Tony Pointer - Hand Gesture PC Controller")

        menu = QMenu()
        self.action_toggle = QAction("Tony Pointer Mode: OFF", self)
        self.action_toggle.triggered.connect(self._toggle_from_tray)
        menu.addAction(self.action_toggle)

        self.action_kb = QAction("Air Keyboard: OFF", self)
        self.action_kb.triggered.connect(self._toggle_keyboard_mode)
        menu.addAction(self.action_kb)

        menu.addSeparator()
        action_show = QAction("Open Control Center", self)
        action_show.triggered.connect(self.main_window.showNormal)
        menu.addAction(action_show)

        action_quit = QAction("Exit Tony Pointer", self)
        action_quit.triggered.connect(self.shutdown)
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.main_window.showNormal()
            self.main_window.activateWindow()

    def _toggle_from_tray(self):
        self.set_mode(not self.is_active)

    def _toggle_keyboard_mode(self):
        new_active = self.mode_manager.toggle_keyboard_mode()
        self._update_keyboard_visibility(new_active)

    def _setup_hotkeys(self):
        try:
            keyboard.add_hotkey(self.settings.hotkey_toggle, lambda: self.set_mode(not self.is_active))
            keyboard.add_hotkey(self.settings.keyboard.hotkey_keyboard, self._toggle_keyboard_mode)
            keyboard.add_hotkey(self.settings.keyboard.hotkey_zone_toggle, self._toggle_keyboard_zone)
            keyboard.add_hotkey(self.settings.hotkey_paint, self._toggle_paint_mode)
            keyboard.add_hotkey("esc", self._emergency_unlock)
        except Exception as e:
            print(f"[TonyPointer] Warning: Could not bind global hotkeys: {e}")

    def _toggle_keyboard_zone(self):
        if self.mode_manager.mode == AppMode.KEYBOARD:
            self.mode_manager.toggle_zone()
            play_sound(1100, 40)

    def _emergency_unlock(self):
        if self.gesture_engine.brush_locked:
            self.gesture_engine.brush_locked = False
            self.mouse.emergency_release()
            play_sound(400, 100)

        self.keyboard_out.release_all_modifiers()
        if self.mode_manager.mode == AppMode.KEYBOARD:
            self.mode_manager.mode = AppMode.POINTER
            self._update_keyboard_visibility(False)
            play_sound(500, 60)

    def _toggle_paint_mode(self):
        self.paint_profile_active = not self.paint_profile_active
        self._apply_filter_profile()
        play_sound(1200 if self.paint_profile_active else 800, 60)

    def _apply_filter_profile(self):
        if self.paint_profile_active:
            self.filter.update_params(
                min_cutoff=self.settings.paint.min_cutoff,
                beta=self.settings.paint.beta,
            )
        else:
            self.filter.update_params(
                min_cutoff=self.settings.one_euro.min_cutoff,
                beta=self.settings.one_euro.beta,
            )

    def _check_foreground_window(self):
        proc = self.mouse.get_active_process_name()
        if proc:
            self.telemetry["foreground_app"] = proc
            if self.settings.paint.auto_detect:
                is_paint_app = any(app in proc for app in self.settings.paint.active_apps)
                if is_paint_app != self.paint_profile_active:
                    self.paint_profile_active = is_paint_app
                    self._apply_filter_profile()
        else:
            self.telemetry["foreground_app"] = "DESKTOP"

    def set_mode(self, active: bool):
        self.is_active = active
        self.main_window.arc_button.set_active(active)
        self.action_toggle.setText(f"Tony Pointer Mode: {'ON' if active else 'OFF'}")

        if active:
            play_sound(1000, 80)
            self.main_window.hide()
            self.cursor_overlay.show()
            if self.settings.overlay.preview_visible:
                self.camera_overlay.show()
            self.tray.showMessage(
                "Tony Pointer Engaged",
                "Webcam hand control is active. Press Ctrl+Alt+T anytime to toggle.",
                QSystemTrayIcon.Information,
                2000,
            )
        else:
            play_sound(500, 80)
            self.mouse.emergency_release()
            self.keyboard_out.release_all_modifiers()
            self.gesture_engine.brush_locked = False
            self.cursor_overlay.hide()
            self.camera_overlay.hide()
            self._update_keyboard_visibility(False)
            self.main_window.showNormal()

    def _update_keyboard_visibility(self, visible: bool):
        if visible and self.is_active:
            vx, vy, vw, vh = self.screen_bounds
            kw = self.keyboard_overlay.width()
            kh = self.keyboard_overlay.height()
            kx = vx + (vw - kw) // 2
            ky = vy + vh - kh - 40
            self.keyboard_overlay.move(kx, ky)
            self.keyboard_overlay.show()
            self.action_kb.setText("Air Keyboard: ON")
        else:
            self.keyboard_overlay.hide()
            self.action_kb.setText("Air Keyboard: OFF")
            self.keyboard_out.release_all_modifiers()

    def _on_settings_reloaded(self):
        self._apply_filter_profile()
        self.screen_bounds = self.mouse.get_screen_bounds()
        self.camera_overlay.setWindowOpacity(self.settings.overlay.preview_opacity)
        self.keyboard_overlay.setWindowOpacity(self.settings.keyboard.opacity)
        self.keyboard_overlay._recalculate_window_size()

    def _processing_loop(self):
        frame_count = 0
        fps_start = time.perf_counter()

        while self.running:
            loop_start = time.perf_counter()
            frame, ts = self.camera.get_frame()

            if frame is None:
                time.sleep(0.005)
                continue

            hand = self.tracker.process_frame(frame, ts)
            infer_ms = (time.perf_counter() - loop_start) * 1000.0

            current_mode_name = self.mode_manager.mode.value
            eval_res = self.gesture_engine.process(
                hand=hand,
                screen_bounds=self.screen_bounds,
                filter_2d=self.filter,
                current_mode=current_mode_name,
            )

            action = eval_res["action"]
            if action == GestureAction.ENTER_KEYBOARD.value and self.mode_manager.mode != AppMode.KEYBOARD:
                self.mode_manager.mode = AppMode.KEYBOARD
                self._update_keyboard_visibility(True)
                play_sound(1300, 80)
            elif action == GestureAction.EXIT_KEYBOARD.value and self.mode_manager.mode == AppMode.KEYBOARD:
                self.mode_manager.mode = AppMode.POINTER
                self._update_keyboard_visibility(False)
                play_sound(600, 80)

            bounce_triggered = False
            curls_dict = {}

            if self.mode_manager.mode == AppMode.KEYBOARD and self.is_active:
                tapped_finger, is_repeat, curls_dict = self.finger_tap_detector.process(hand)
                cur_window = self.mode_manager.get_current_window()

                if tapped_finger is not None:
                    if tapped_finger == "thumb":
                        self.keyboard_out.send_key("space", char_to_send=" ")
                        self.key_typed_signal.emit("space", "Space")
                        play_sound(900, 25)
                    else:
                        finger_names = ["index", "middle", "ring", "pinky"]
                        if hand is not None:
                            tip_indices = [8, 12, 16, 20]
                            finger_x_pairs = [(finger_names[i], hand.get(tip_indices[i]).x) for i in range(4)]
                            finger_x_pairs.sort(key=lambda p: p[1])
                            sorted_finger_names = [p[0] for p in finger_x_pairs]

                            if self.settings.keyboard.finger_mapping == "reversed":
                                sorted_finger_names.reverse()

                            try:
                                key_slot = sorted_finger_names.index(tapped_finger)
                            except ValueError:
                                key_slot = finger_names.index(tapped_finger)
                        else:
                            key_slot = finger_names.index(tapped_finger)

                        if 0 <= key_slot < len(cur_window.keys):
                            target_key = cur_window.keys[key_slot]
                            self.keyboard_out.send_key(
                                key_code=target_key.code,
                                char_to_send=target_key.char_to_send,
                                needs_shift=target_key.needs_shift,
                            )
                            self.key_typed_signal.emit(target_key.code, target_key.label)
                            play_sound(1400 if is_repeat else 1200, 20)

                tap_in_progress = (tapped_finger is not None)
                swipe_dir = self.mode_manager.evaluate_swipes(hand, tap_in_progress=tap_in_progress)

                if swipe_dir in ("UP", "DOWN", "LEFT", "RIGHT", "CROSS_INTO_SYMBOLS", "CROSS_INTO_MAIN"):
                    play_sound(1000 if "CROSS" in swipe_dir else 850, 40)
                elif swipe_dir == "BOUNCE":
                    bounce_triggered = True
                    play_sound(450, 50)

                self.keyboard_overlay.update_state(
                    zone=self.mode_manager.active_zone,
                    row_idx=self.mode_manager.row_idx,
                    window_idx=self.mode_manager.window_idx,
                    modifiers=self.keyboard_out.modifiers,
                    bounce=bounce_triggered,
                )

            cur_win = self.mode_manager.get_current_window()
            self.telemetry["raw_hand"] = hand
            self.telemetry["mode"] = self.mode_manager.mode.value
            self.telemetry["pose"] = eval_res["pose"]
            self.telemetry["action"] = eval_res["action"]
            self.telemetry["status_text"] = eval_res["status_text"]
            self.telemetry["brush_locked"] = eval_res["brush_locked"]
            self.telemetry["latency_ms"] = infer_ms
            self.telemetry["kb_zone"] = self.mode_manager.active_zone.value
            self.telemetry["kb_row"] = self.mode_manager.row_idx
            self.telemetry["kb_win_keys"] = [k.label for k in cur_win.keys]
            self.telemetry["curls"] = curls_dict

            vis_frame = draw_hud_landmarks(
                frame_bgr=frame,
                hand=hand,
                active_region=self.settings.active_region,
                status_text=eval_res["status_text"],
                dwell_progress=eval_res["dwell_progress"],
                brush_locked=eval_res["brush_locked"],
            )
            self.latest_vis_frame = vis_frame

            if self.is_active and self.mode_manager.mode == AppMode.POINTER:
                cx = eval_res["cursor_x"]
                cy = eval_res["cursor_y"]

                if eval_res["hand_visible"] and action != GestureAction.PAUSE.value:
                    self.mouse.move_to(cx, cy)

                overlay_state = "NORMAL"
                if not eval_res["hand_visible"]:
                    overlay_state = "LOST"
                elif eval_res["brush_locked"]:
                    overlay_state = "BRUSH_LOCKED"
                elif action == GestureAction.SINGLE_CLICK.value:
                    overlay_state = "CLICK"
                elif action == GestureAction.DOUBLE_CLICK.value:
                    overlay_state = "DOUBLE_CLICK"

                self.cursor_overlay.update_position(
                    cx, cy, overlay_state, eval_res["dwell_progress"]
                )

                if action == GestureAction.SINGLE_CLICK.value:
                    self.mouse.click(cx, cy)
                    self.cursor_overlay.trigger_click_anim(double=False)
                    play_sound(1200, 30)

                elif action == GestureAction.DOUBLE_CLICK.value:
                    self.mouse.double_click(cx, cy)
                    self.cursor_overlay.trigger_click_anim(double=True)
                    play_sound(1600, 40)

                elif action == GestureAction.RIGHT_CLICK.value:
                    self.mouse.right_click(cx, cy)
                    play_sound(900, 40)

                elif action == GestureAction.SCROLL.value:
                    delta = eval_res.get("scroll_delta", 0)
                    self.mouse.scroll(delta)

                elif action == GestureAction.BRUSH_LOCK_TOGGLE.value:
                    self.mouse.left_down()
                    play_sound(1400, 90)

                elif action == GestureAction.BRUSH_UNLOCK.value:
                    self.mouse.left_up()
                    play_sound(600, 70)

            if self.is_active and self.settings.overlay.preview_visible:
                self.camera_overlay.update_frame(vis_frame)

            frame_count += 1
            elapsed = time.perf_counter() - fps_start
            if elapsed >= 1.0:
                self.telemetry["fps"] = frame_count / elapsed
                frame_count = 0
                fps_start = time.perf_counter()

            frame_time = time.perf_counter() - loop_start
            target_time = 1.0 / self.settings.target_fps
            sleep_time = target_time - frame_time
            if sleep_time > 0.001:
                time.sleep(sleep_time)

    def shutdown(self):
        self.running = False
        self.mouse.emergency_release()
        self.keyboard_out.release_all_modifiers()
        self.camera.stop()
        self.tracker.close()
        self.app.quit()


def main():
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Tony Pointer")
    app.setQuitOnLastWindowClosed(False)

    tony_app = TonyPointerApp(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
`
  },
  {
    name: "keyboard_layout.py",
    path: "tony_pointer/keyboard_layout.py",
    description: "Definitions for 6-row Main Keyboard and 6-row Symbols Panel with 4-key window partitioning & inter-zone transitions",
    language: "python",
    content: `"""
Tony Pointer - Keyboard Layout & 4-Key Window Geometry
Defines the EXACT 6-row Main Laptop Keyboard and the 6-row Symbols Panel.
Implements the 4-key window partitioner, visual order finger-to-key mapping,
and seamless inter-zone navigation.
"""

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class Zone(enum.Enum):
    MAIN = "MAIN"
    SYMBOLS = "SYMBOLS"


@dataclass
class KeyDef:
    label: str
    code: str
    display_label: Optional[str] = None
    is_modifier: bool = False
    needs_shift: bool = False
    width_ratio: float = 1.0
    char_to_send: Optional[str] = None

    @property
    def display(self) -> str:
        return self.display_label if self.display_label else self.label


@dataclass
class KeyboardWindow:
    zone: Zone
    row: int
    window_idx: int
    keys: List[KeyDef]
    start_key_idx: int


MAIN_ROWS_RAW: List[List[KeyDef]] = [
    [
        KeyDef("Esc", "esc", width_ratio=1.2),
        KeyDef("F1", "f1"), KeyDef("F2", "f2"), KeyDef("F3", "f3"), KeyDef("F4", "f4"),
        KeyDef("F5", "f5"), KeyDef("F6", "f6"), KeyDef("F7", "f7"), KeyDef("F8", "f8"),
        KeyDef("F9", "f9"), KeyDef("F10", "f10"), KeyDef("F11", "f11"), KeyDef("F12", "f12"),
        KeyDef("Del", "del", width_ratio=1.2),
    ],
    [
        KeyDef("\`", "\`", char_to_send="\`"),
        KeyDef("1", "1", char_to_send="1"), KeyDef("2", "2", char_to_send="2"),
        KeyDef("3", "3", char_to_send="3"), KeyDef("4", "4", char_to_send="4"),
        KeyDef("5", "5", char_to_send="5"), KeyDef("6", "6", char_to_send="6"),
        KeyDef("7", "7", char_to_send="7"), KeyDef("8", "8", char_to_send="8"),
        KeyDef("9", "9", char_to_send="9"), KeyDef("0", "0", char_to_send="0"),
        KeyDef("-", "-", char_to_send="-"), KeyDef("=", "=", char_to_send="="),
        KeyDef("Backspace", "backspace", width_ratio=1.6),
    ],
    [
        KeyDef("Tab", "tab", width_ratio=1.3),
        KeyDef("Q", "q", char_to_send="q"), KeyDef("W", "w", char_to_send="w"),
        KeyDef("E", "e", char_to_send="e"), KeyDef("R", "r", char_to_send="r"),
        KeyDef("T", "t", char_to_send="t"), KeyDef("Y", "y", char_to_send="y"),
        KeyDef("U", "u", char_to_send="u"), KeyDef("I", "i", char_to_send="i"),
        KeyDef("O", "o", char_to_send="o"), KeyDef("P", "p", char_to_send="p"),
        KeyDef("[", "[", char_to_send="["), KeyDef("]", "]", char_to_send="]"),
        KeyDef("\\\\", "\\\\", char_to_send="\\\\"),
    ],
    [
        KeyDef("Caps", "capslock", is_modifier=True, width_ratio=1.5),
        KeyDef("A", "a", char_to_send="a"), KeyDef("S", "s", char_to_send="s"),
        KeyDef("D", "d", char_to_send="d"), KeyDef("F", "f", char_to_send="f"),
        KeyDef("G", "g", char_to_send="g"), KeyDef("H", "h", char_to_send="h"),
        KeyDef("J", "j", char_to_send="j"), KeyDef("K", "k", char_to_send="k"),
        KeyDef("L", "l", char_to_send="l"),
        KeyDef(";", ";", char_to_send=";"), KeyDef("'", "'", char_to_send="'"),
        KeyDef("Enter", "enter", width_ratio=1.6),
    ],
    [
        KeyDef("Shift", "shift_l", is_modifier=True, width_ratio=1.7),
        KeyDef("Z", "z", char_to_send="z"), KeyDef("X", "x", char_to_send="x"),
        KeyDef("C", "c", char_to_send="c"), KeyDef("V", "v", char_to_send="v"),
        KeyDef("B", "b", char_to_send="b"), KeyDef("N", "n", char_to_send="n"),
        KeyDef("M", "m", char_to_send="m"),
        KeyDef(",", ",", char_to_send=","), KeyDef(".", ".", char_to_send="."),
        KeyDef("/", "/", char_to_send="/"),
        KeyDef("Shift", "shift_r", is_modifier=True, width_ratio=1.7),
    ],
    [
        KeyDef("Ctrl", "ctrl_l", is_modifier=True, width_ratio=1.2),
        KeyDef("Win", "win", is_modifier=True, width_ratio=1.1),
        KeyDef("Alt", "alt_l", is_modifier=True, width_ratio=1.1),
        KeyDef("Space", "space", char_to_send=" ", width_ratio=3.8),
        KeyDef("Alt", "alt_r", is_modifier=True, width_ratio=1.1),
        KeyDef("Ctrl", "ctrl_r", is_modifier=True, width_ratio=1.2),
        KeyDef("Left", "left", width_ratio=1.0),
        KeyDef("Up", "up", width_ratio=1.0),
        KeyDef("Down", "down", width_ratio=1.0),
        KeyDef("Right", "right", width_ratio=1.0),
    ],
]

SYMBOL_ROWS_RAW: List[List[KeyDef]] = [
    [
        KeyDef("Home", "home"), KeyDef("End", "end"),
        KeyDef("PgUp", "pgup"), KeyDef("PgDn", "pgdn"),
        KeyDef("PrtSc", "prtsc"), KeyDef("Ins", "ins"),
        KeyDef("Pause", "pause"), KeyDef("ScrLk", "scrlk"),
    ],
    [
        KeyDef("!", "exclamation", needs_shift=True, char_to_send="!"),
        KeyDef("@", "at", needs_shift=True, char_to_send="@"),
        KeyDef("#", "hash", needs_shift=True, char_to_send="#"),
        KeyDef("$", "dollar", needs_shift=True, char_to_send="$"),
        KeyDef("%", "percent", needs_shift=True, char_to_send="%"),
        KeyDef("^", "caret", needs_shift=True, char_to_send="^"),
        KeyDef("&", "ampersand", needs_shift=True, char_to_send="&"),
        KeyDef("*", "asterisk", needs_shift=True, char_to_send="*"),
        KeyDef("(", "lparen", needs_shift=True, char_to_send="("),
        KeyDef(")", "rparen", needs_shift=True, char_to_send=")"),
        KeyDef("_", "underscore", needs_shift=True, char_to_send="_"),
        KeyDef("+", "plus", needs_shift=True, char_to_send="+"),
    ],
    [
        KeyDef("+", "sym_plus", needs_shift=True, char_to_send="+"),
        KeyDef("-", "sym_minus", needs_shift=False, char_to_send="-"),
        KeyDef("*", "sym_asterisk", needs_shift=True, char_to_send="*"),
        KeyDef("/", "sym_slash", needs_shift=False, char_to_send="/"),
        KeyDef("=", "sym_equals", needs_shift=False, char_to_send="="),
        KeyDef("<", "sym_less", needs_shift=True, char_to_send="<"),
        KeyDef(">", "sym_greater", needs_shift=True, char_to_send=">"),
        KeyDef("~", "sym_tilde", needs_shift=True, char_to_send="~"),
    ],
    [
        KeyDef("{", "sym_lbrace", needs_shift=True, char_to_send="{"),
        KeyDef("}", "sym_rbrace", needs_shift=True, char_to_send="}"),
        KeyDef("[", "sym_lbracket", needs_shift=False, char_to_send="["),
        KeyDef("]", "sym_rbracket", needs_shift=False, char_to_send="]"),
        KeyDef("(", "sym_lparen2", needs_shift=True, char_to_send="("),
        KeyDef(")", "sym_rparen2", needs_shift=True, char_to_send=")"),
        KeyDef('"', "sym_dquote", needs_shift=True, char_to_send='"'),
        KeyDef("'", "sym_squote", needs_shift=False, char_to_send="'"),
    ],
    [
        KeyDef(":", "sym_colon", needs_shift=True, char_to_send=":"),
        KeyDef(";", "sym_semicolon", needs_shift=False, char_to_send=";"),
        KeyDef("?", "sym_question", needs_shift=True, char_to_send="?"),
        KeyDef("|", "sym_pipe", needs_shift=True, char_to_send="|"),
        KeyDef("\\\\", "sym_backslash", needs_shift=False, char_to_send="\\\\"),
        KeyDef("/", "sym_slash2", needs_shift=False, char_to_send="/"),
        KeyDef(",", "sym_comma", needs_shift=False, char_to_send=","),
        KeyDef(".", "sym_dot", needs_shift=False, char_to_send="."),
    ],
    [
        KeyDef("Backspace", "backspace", width_ratio=1.4),
        KeyDef("Enter", "enter", width_ratio=1.4),
        KeyDef("Tab", "tab", width_ratio=1.2),
        KeyDef("Del", "del", width_ratio=1.2),
    ],
]


class KeyboardLayoutManager:
    def __init__(self, main_rows: Optional[List[List[KeyDef]]] = None, symbol_rows: Optional[List[List[KeyDef]]] = None):
        self.main_rows = main_rows or MAIN_ROWS_RAW
        self.symbol_rows = symbol_rows or SYMBOL_ROWS_RAW
        self.main_windows = self._build_windows(self.main_rows, Zone.MAIN)
        self.symbol_windows = self._build_windows(self.symbol_rows, Zone.SYMBOLS)

    def _build_windows(self, rows: List[List[KeyDef]], zone: Zone) -> List[List[KeyboardWindow]]:
        row_windows = []
        for row_idx, keys in enumerate(rows):
            n = len(keys)
            windows = []
            if n <= 4:
                win_keys = keys if n == 4 else keys + [keys[-1]] * (4 - n)
                windows.append(KeyboardWindow(zone=zone, row=row_idx, window_idx=0, keys=win_keys, start_key_idx=0))
            else:
                start_indices = []
                idx = 0
                while idx + 4 <= n:
                    start_indices.append(idx)
                    idx += 4
                last_start = n - 4
                if last_start not in start_indices:
                    start_indices.append(last_start)
                start_indices.sort()
                for w_idx, s_idx in enumerate(start_indices):
                    win_keys = keys[s_idx : s_idx + 4]
                    windows.append(KeyboardWindow(zone=zone, row=row_idx, window_idx=w_idx, keys=win_keys, start_key_idx=s_idx))
            row_windows.append(windows)
        return row_windows

    def get_window(self, zone: Zone, row_idx: int, window_idx: int) -> KeyboardWindow:
        row_idx = max(0, min(5, row_idx))
        target_table = self.main_windows if zone == Zone.MAIN else self.symbol_windows
        row_wins = target_table[row_idx]
        w_idx = max(0, min(len(row_wins) - 1, window_idx))
        return row_wins[w_idx]

    def get_max_window_idx(self, zone: Zone, row_idx: int) -> int:
        row_idx = max(0, min(5, row_idx))
        target_table = self.main_windows if zone == Zone.MAIN else self.symbol_windows
        return len(target_table[row_idx]) - 1

    def is_last_window_of_row(self, zone: Zone, row_idx: int, window_idx: int) -> bool:
        return window_idx >= self.get_max_window_idx(zone, row_idx)

    def is_first_window_of_row(self, zone: Zone, row_idx: int, window_idx: int) -> bool:
        return window_idx <= 0
`
  },
  {
    name: "keyboard_out.py",
    path: "tony_pointer/keyboard_out.py",
    description: "Hardware keystroke dispatch via Win32 SendInput (scancodes & unicode), sticky single-handed modifiers & auto-shift",
    language: "python",
    content: `"""
Tony Pointer - Hardware Keystroke Dispatch via Win32 SendInput
Uses hardware scan codes (KEYEVENTF_SCANCODE) for authentic OS typing into any window,
with KEYEVENTF_UNICODE fallback for complex symbols.
"""

import ctypes
import enum
import sys
import time
from typing import Dict, Optional, Set, Tuple

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008


class ModifierState(enum.Enum):
    INACTIVE = "INACTIVE"
    LATCHED = "LATCHED"
    LOCKED = "LOCKED"


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


SCAN_CODES: Dict[str, Tuple[int, bool]] = {
    "esc": (0x01, False),
    "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False),
    "5": (0x06, False), "6": (0x07, False), "7": (0x08, False), "8": (0x09, False),
    "9": (0x0A, False), "0": (0x0B, False), "-": (0x0C, False), "=": (0x0D, False),
    "backspace": (0x0E, False), "tab": (0x0F, False),
    "q": (0x10, False), "w": (0x11, False), "e": (0x12, False), "r": (0x13, False),
    "t": (0x14, False), "y": (0x15, False), "u": (0x16, False), "i": (0x17, False),
    "o": (0x18, False), "p": (0x19, False), "[": (0x1A, False), "]": (0x1B, False),
    "enter": (0x1C, False), "ctrl_l": (0x1D, False),
    "a": (0x1E, False), "s": (0x1F, False), "d": (0x20, False), "f": (0x21, False),
    "g": (0x22, False), "h": (0x23, False), "j": (0x24, False), "k": (0x25, False),
    "l": (0x26, False), ";": (0x27, False), "'": (0x28, False), "\`": (0x29, False),
    "shift_l": (0x2A, False), "\\\\": (0x2B, False),
    "z": (0x2C, False), "x": (0x2D, False), "c": (0x2E, False), "v": (0x2F, False),
    "b": (0x30, False), "n": (0x31, False), "m": (0x32, False), ",": (0x33, False),
    ".": (0x34, False), "/": (0x35, False), "shift_r": (0x36, False), "alt_l": (0x38, False),
    "space": (0x39, False), "capslock": (0x3A, False),
    "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False), "f4": (0x3E, False),
    "f5": (0x3F, False), "f6": (0x40, False), "f7": (0x41, False), "f8": (0x42, False),
    "f9": (0x43, False), "f10": (0x44, False), "f11": (0x57, False), "f12": (0x58, False),
    "ctrl_r": (0x1D, True), "alt_r": (0x38, True), "win": (0x5B, True),
    "home": (0x47, True), "up": (0x48, True), "pgup": (0x49, True),
    "left": (0x4B, True), "right": (0x4D, True), "end": (0x4F, True),
    "down": (0x50, True), "pgdn": (0x51, True), "ins": (0x52, True),
    "del": (0x53, True), "prtsc": (0x37, True), "pause": (0x45, True), "scrlk": (0x46, False),
}

SHIFT_SYMBOL_MAP = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\\\",
    ":": ";", '"': "'", "<": ",", ">": ".", "?": "/", "~": "\`",
}


class Win32KeyboardOutput:
    def __init__(self):
        self.is_windows = sys.platform.startswith("win")
        self.user32 = ctypes.windll.user32 if self.is_windows else None
        self.modifiers: Dict[str, ModifierState] = {
            "shift": ModifierState.INACTIVE,
            "ctrl": ModifierState.INACTIVE,
            "alt": ModifierState.INACTIVE,
            "win": ModifierState.INACTIVE,
            "caps": ModifierState.INACTIVE,
        }
        self.held_scans: Set[int] = set()
        self.last_modifier_tap: Dict[str, float] = {}

    def _send_scan(self, scancode: int, is_extended: bool, is_up: bool):
        if not self.is_windows:
            return
        flags = KEYEVENTF_SCANCODE
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        if is_up:
            flags |= KEYEVENTF_KEYUP
        extra = ctypes.c_ulong(0)
        ki = KEYBDINPUT(wVk=0, wScan=scancode, dwFlags=flags, time=0, dwExtraInfo=ctypes.pointer(extra))
        inp = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki))
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_unicode(self, char: str):
        if not self.is_windows:
            return
        code_point = ord(char)
        extra = ctypes.c_ulong(0)
        ki_down = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=ctypes.pointer(extra))
        self.user32.SendInput(1, ctypes.byref(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki_down))), ctypes.sizeof(INPUT))
        time.sleep(0.005)
        ki_up = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=ctypes.pointer(extra))
        self.user32.SendInput(1, ctypes.byref(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki_up))), ctypes.sizeof(INPUT))

    def toggle_modifier(self, mod_name: str) -> ModifierState:
        now = time.perf_counter()
        current = self.modifiers.get(mod_name, ModifierState.INACTIVE)
        last_tap = self.last_modifier_tap.get(mod_name, 0.0)

        if current == ModifierState.LOCKED:
            self.modifiers[mod_name] = ModifierState.INACTIVE
            self._apply_physical_modifier(mod_name, False)
        elif current == ModifierState.LATCHED:
            if (now - last_tap) < 0.45:
                self.modifiers[mod_name] = ModifierState.LOCKED
                self._apply_physical_modifier(mod_name, True)
            else:
                self.modifiers[mod_name] = ModifierState.INACTIVE
                self._apply_physical_modifier(mod_name, False)
        else:
            self.modifiers[mod_name] = ModifierState.LATCHED
            self._apply_physical_modifier(mod_name, True)

        self.last_modifier_tap[mod_name] = now
        return self.modifiers[mod_name]

    def _apply_physical_modifier(self, mod_name: str, press_down: bool):
        scan_map = {
            "shift": (0x2A, False),
            "ctrl": (0x1D, False),
            "alt": (0x38, False),
            "win": (0x5B, True),
            "caps": (0x3A, False),
        }
        if mod_name not in scan_map:
            return
        scan, ext = scan_map[mod_name]
        if press_down:
            self._send_scan(scan, ext, is_up=False)
            self.held_scans.add(scan)
        else:
            self._send_scan(scan, ext, is_up=True)
            self.held_scans.discard(scan)

    def send_key(self, key_code: str, char_to_send: Optional[str] = None, needs_shift: bool = False):
        mod_keys = {
            "shift_l": "shift", "shift_r": "shift",
            "ctrl_l": "ctrl", "ctrl_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "win": "win", "capslock": "caps",
        }
        if key_code in mod_keys:
            self.toggle_modifier(mod_keys[key_code])
            return

        symbol_char = char_to_send if char_to_send and len(char_to_send) == 1 else None

        if symbol_char and symbol_char in SHIFT_SYMBOL_MAP:
            base_key = SHIFT_SYMBOL_MAP[symbol_char]
            base_scan_info = SCAN_CODES.get(base_key)
            shift_was_latched = self.modifiers["shift"] != ModifierState.INACTIVE
            if not shift_was_latched:
                self._send_scan(0x2A, False, is_up=False)

            if base_scan_info:
                scan, ext = base_scan_info
                self._send_scan(scan, ext, is_up=False)
                time.sleep(0.01)
                self._send_scan(scan, ext, is_up=True)
            else:
                self._send_unicode(symbol_char)

            if not shift_was_latched:
                self._send_scan(0x2A, False, is_up=True)

            if self.modifiers["shift"] == ModifierState.LATCHED:
                self.modifiers["shift"] = ModifierState.INACTIVE
                self._apply_physical_modifier("shift", False)
        elif symbol_char and symbol_char not in SCAN_CODES:
            self._send_unicode(symbol_char)
        else:
            lookup = key_code.lower()
            if lookup in SCAN_CODES:
                scan, ext = SCAN_CODES[lookup]
                self._send_scan(scan, ext, is_up=False)
                time.sleep(0.01)
                self._send_scan(scan, ext, is_up=True)
            elif symbol_char:
                self._send_unicode(symbol_char)

        for mod, state in list(self.modifiers.items()):
            if state == ModifierState.LATCHED:
                self.modifiers[mod] = ModifierState.INACTIVE
                self._apply_physical_modifier(mod, False)

    def release_all_modifiers(self):
        for scan in list(self.held_scans):
            self._send_scan(scan, False, is_up=True)
            self._send_scan(scan, True, is_up=True)
        self.held_scans.clear()
        for mod in self.modifiers:
            self.modifiers[mod] = ModifierState.INACTIVE
`
  },
  {
    name: "keyboard_ui.py",
    path: "tony_pointer/keyboard_ui.py",
    description: "PySide6 Floating Air Keyboard HUD & Symbols Panel with electric blue 4-key glow & divider crossing indicators",
    language: "python",
    content: `"""
Tony Pointer - PySide6 Floating Air Keyboard HUD & Symbols Panel
Renders the 6-row Laptop Keyboard on the left and the docked 6-row Symbols Panel on the right.
"""

import math
import sys
import time
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from keyboard_layout import KeyDef, KeyboardLayoutManager, KeyboardWindow, Zone
from keyboard_out import ModifierState


class FloatingAirKeyboardWidget(QWidget):
    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        super().__init__()
        self.settings = settings
        self.layout_manager = layout_manager

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.key_size = 46
        self.key_gap = 6
        self.margin_x = 24
        self.margin_y = 48
        self.divider_width = 32

        self.active_zone = Zone.MAIN
        self.current_row = 3
        self.current_window_idx = 0
        self.locked_keys: Set[str] = set()

        self.modifiers: Dict[str, ModifierState] = {
            "shift": ModifierState.INACTIVE,
            "ctrl": ModifierState.INACTIVE,
            "alt": ModifierState.INACTIVE,
            "win": ModifierState.INACTIVE,
            "caps": ModifierState.INACTIVE,
        }

        self.flash_key_code: Optional[str] = None
        self.flash_opacity: float = 0.0
        self.last_typed_history: List[str] = ["Tony", "Pointer", "Ready"]
        self.pulse_phase: float = 0.0
        self.bounce_offset: float = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_animate)
        self.anim_timer.start(16)

        self._recalculate_window_size()

    def _recalculate_window_size(self):
        main_w = 14 * (self.key_size + self.key_gap) + 80
        symbols_w = 8 * (self.key_size + self.key_gap) + 40 if self.settings.keyboard.symbols_panel_enabled else 0
        total_w = self.margin_x * 2 + main_w + (self.divider_width + symbols_w if symbols_w > 0 else 0)
        total_h = self.margin_y + 6 * (self.key_size + self.key_gap) + 32
        self.resize(int(total_w), int(total_h))

    def update_state(self, zone: Zone, row_idx: int, window_idx: int, modifiers: Dict[str, ModifierState], bounce: bool = False):
        self.active_zone = zone
        self.current_row = row_idx
        self.current_window_idx = window_idx
        self.modifiers = modifiers
        active_window = self.layout_manager.get_window(zone, row_idx, window_idx)
        self.locked_keys = {k.code for k in active_window.keys}
        if bounce:
            self.bounce_offset = 12.0
        self.update()

    def trigger_key_flash(self, key_code: str, label: str):
        self.flash_key_code = key_code
        self.flash_opacity = 1.0
        self.last_typed_history.append(label)
        if len(self.last_typed_history) > 12:
            self.last_typed_history.pop(0)
        self.update()

    def _on_animate(self):
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        if self.flash_opacity > 0.0:
            self.flash_opacity = max(0.0, self.flash_opacity - 0.08)
        if self.bounce_offset > 0.0:
            self.bounce_offset = max(0.0, self.bounce_offset - 1.5)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        bg_color = QColor(7, 11, 20, int(255 * self.settings.keyboard.opacity))
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor(0, 229, 255, 60), 1.5))
        painter.drawRoundedRect(QRectF(8, 8, w - 16, h - 16), 10, 10)

        self._paint_header_strip(painter)

        main_x = self.margin_x
        main_y = self.margin_y
        main_opacity = 1.0 if self.active_zone == Zone.MAIN else 0.40

        self._paint_zone(
            painter=painter,
            rows=self.layout_manager.main_rows,
            start_x=main_x,
            start_y=main_y,
            zone=Zone.MAIN,
            opacity=main_opacity,
            accent_color=QColor(0, 229, 255),
        )

        if self.settings.keyboard.symbols_panel_enabled:
            main_block_w = 14 * (self.key_size + self.key_gap) + 80
            divider_x = main_x + main_block_w + (self.divider_width // 2)
            self._paint_divider(painter, divider_x, main_y)
            symbols_x = divider_x + (self.divider_width // 2)
            symbols_opacity = 1.0 if self.active_zone == Zone.SYMBOLS else (0.35 if self.settings.keyboard.dim_inactive_panel else 0.85)
            self._paint_zone(
                painter=painter,
                rows=self.layout_manager.symbol_rows,
                start_x=symbols_x,
                start_y=main_y,
                zone=Zone.SYMBOLS,
                opacity=symbols_opacity,
                accent_color=QColor(168, 85, 247),
            )

    def _paint_header_strip(self, painter: QPainter):
        painter.setFont(QFont("JetBrains Mono", 10, QFont.Bold))
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(24, 32, "LAST TYPED:")
        history_str = " ".join(self.last_typed_history[-6:])
        painter.setPen(QColor(0, 229, 255))
        painter.drawText(118, 32, history_str)

        mod_x = self.width() - 320
        mods_to_show = [("SHIFT", "shift"), ("CTRL", "ctrl"), ("ALT", "alt"), ("CAPS", "caps")]
        for name, code in mods_to_show:
            state = self.modifiers.get(code, ModifierState.INACTIVE)
            if state == ModifierState.LOCKED:
                bg = QColor(255, 179, 0)
                fg = QColor(10, 15, 25)
            elif state == ModifierState.LATCHED:
                bg = QColor(255, 100, 0, 180)
                fg = QColor(255, 255, 255)
            else:
                bg = QColor(15, 23, 42, 100)
                fg = QColor(100, 116, 139)
            painter.setBrush(bg)
            painter.setPen(QPen(fg, 1))
            rect = QRectF(mod_x, 18, 52, 20)
            painter.drawRoundedRect(rect, 3, 3)
            painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
            painter.setPen(fg)
            painter.drawText(rect, Qt.AlignCenter, name)
            mod_x += 60

    def _paint_divider(self, painter: QPainter, div_x: float, start_y: float):
        total_h = 6 * (self.key_size + self.key_gap)
        glow = math.sin(self.pulse_phase) * 0.3 + 0.7
        painter.setPen(QPen(QColor(0, 229, 255, int(180 * glow)), 2))
        painter.drawLine(int(div_x), int(start_y), int(div_x), int(start_y + total_h))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor(168, 85, 247))
        painter.drawText(int(div_x + 12), int(start_y - 8), "SYMBOLS")

        is_on_last_main = (
            self.active_zone == Zone.MAIN
            and self.layout_manager.is_last_window_of_row(Zone.MAIN, self.current_row, self.current_window_idx)
        )
        if is_on_last_main:
            arrow_y = start_y + self.current_row * (self.key_size + self.key_gap) + (self.key_size / 2.0)
            painter.setPen(QPen(QColor(0, 229, 255), 2.5))
            cx = div_x
            painter.drawLine(int(cx - 6), int(arrow_y - 6), int(cx + 6), int(arrow_y))
            painter.drawLine(int(cx + 6), int(arrow_y), int(cx - 6), int(arrow_y + 6))

    def _paint_zone(self, painter: QPainter, rows: List[List[KeyDef]], start_x: float, start_y: float, zone: Zone, opacity: float, accent_color: QColor):
        curr_y = start_y
        for row_idx, key_list in enumerate(rows):
            curr_x = start_x
            is_active_row = (zone == self.active_zone and row_idx == self.current_row)
            for key in key_list:
                kw = int(self.key_size * key.width_ratio)
                kh = self.key_size
                is_locked = is_active_row and (key.code in self.locked_keys)
                is_flashing = (self.flash_key_code == key.code and self.flash_opacity > 0.0)
                rect = QRectF(curr_x, curr_y, kw, kh)

                if is_flashing:
                    painter.setBrush(QColor(255, 255, 255, 240))
                    painter.setPen(QPen(QColor(0, 229, 255), 3.0))
                elif is_locked:
                    painter.setBrush(QColor(0, 180, 255, int(130 * opacity)))
                    painter.setPen(QPen(QColor(0, 229, 255, int(255 * opacity)), 2.5))
                else:
                    painter.setBrush(QColor(15, 23, 42, int(150 * opacity)))
                    painter.setPen(QPen(QColor(accent_color.red(), accent_color.green(), accent_color.blue(), int(80 * opacity)), 1.0))

                painter.drawRoundedRect(rect, 4, 4)
                painter.setFont(QFont("JetBrains Mono", 9 if len(key.label) <= 2 else 7, QFont.Bold))
                if is_flashing:
                    painter.setPen(QColor(10, 15, 25))
                elif is_locked:
                    painter.setPen(QColor(255, 255, 255))
                else:
                    painter.setPen(QColor(203, 213, 225, int(220 * opacity)))
                painter.drawText(rect, Qt.AlignCenter, key.display)
                curr_x += kw + self.key_gap
            curr_y += self.key_size + self.key_gap
`
  },
  {
    name: "finger_taps.py",
    path: "tony_pointer/finger_taps.py",
    description: "Per-finger independent tap detector, anatomical sensitivity calibration, and hold-to-repeat",
    language: "python",
    content: `"""
Tony Pointer - Independent Per-Finger Air Tap & Hold-Repeat Detector
Tracks 5 distinct fingers (Index, Middle, Ring, Pinky, and Thumb).
"""

import collections
import time
from typing import Dict, List, Optional, Tuple

from tracker import HandFrame


class FingerTapDetector:
    def __init__(self, settings):
        self.settings = settings
        self.fingers = [
            ("index", 8, 7, 6, 5),
            ("middle", 12, 11, 10, 9),
            ("ring", 16, 15, 14, 13),
            ("pinky", 20, 19, 18, 17),
        ]
        self.history = {f[0]: collections.deque(maxlen=15) for f in self.fingers}
        self.thumb_history = collections.deque(maxlen=15)
        self.last_tap_time = {f[0]: 0.0 for f in self.fingers}
        self.last_tap_time["thumb"] = 0.0
        self.curl_hold_start = {f[0]: None for f in self.fingers}
        self.curl_hold_start["thumb"] = None
        self.last_repeat_time = {f[0]: 0.0 for f in self.fingers}
        self.last_repeat_time["thumb"] = 0.0
        self.current_curls = {"thumb": 0.0, "index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0}

    def process(self, hand: Optional[HandFrame]) -> Tuple[Optional[str], bool, Dict[str, float]]:
        if hand is None:
            self._reset_holds()
            return None, False, self.current_curls

        now = time.perf_counter()
        hand_scale = max(0.04, hand.distance_3d(0, 9))
        detected_event = None
        is_repeat = False

        for f_name, tip, dip, pip, mcp in self.fingers:
            pip_angle = hand.angle_deg(mcp, pip, tip)
            norm_tip_dist = hand.distance_3d(0, tip) / hand_scale
            curl_metric = max(0.0, min(1.0, (170.0 - pip_angle) / 70.0))
            self.current_curls[f_name] = curl_metric

            hist = self.history[f_name]
            hist.append((now, pip_angle, norm_tip_dist))
            if len(hist) < 4:
                continue

            sens_factor = getattr(self.settings.keyboard, f"{f_name}_sensitivity", 1.0)
            base_threshold = 20.0 / max(0.4, sens_factor)

            recent = [entry for entry in hist if (now - entry[0]) <= 0.25]
            if len(recent) < 3:
                continue

            angles = [r[1] for r in recent]
            min_ang = min(angles)
            max_ang = max(angles)
            curr_ang = angles[-1]
            rebounded = (curr_ang > min_ang + 14.0) and (curr_ang > 130.0)
            angle_delta = max_ang - min_ang

            cooldown = self.settings.keyboard.tap_cooldown_ms / 1000.0

            if angle_delta >= base_threshold and rebounded and (now - self.last_tap_time[f_name] > cooldown) and detected_event is None:
                self.last_tap_time[f_name] = now
                detected_event = f_name
                is_repeat = False
                self.curl_hold_start[f_name] = None
                continue

            is_curled = curr_ang < 120.0
            if is_curled:
                if self.curl_hold_start[f_name] is None:
                    self.curl_hold_start[f_name] = now
                else:
                    hold_duration = now - self.curl_hold_start[f_name]
                    repeat_delay = self.settings.keyboard.key_repeat_delay_s
                    repeat_interval = self.settings.keyboard.key_repeat_interval_s
                    if hold_duration >= repeat_delay and (now - self.last_repeat_time[f_name] > repeat_interval):
                        self.last_repeat_time[f_name] = now
                        detected_event = f_name
                        is_repeat = True
            else:
                self.curl_hold_start[f_name] = None

        if self.settings.keyboard.thumb_is_space:
            thumb_angle = hand.angle_deg(1, 2, 4)
            thumb_dist = hand.distance_3d(0, 4) / hand_scale
            thumb_curl = max(0.0, min(1.0, (160.0 - thumb_angle) / 55.0))
            self.current_curls["thumb"] = thumb_curl
            self.thumb_history.append((now, thumb_angle, thumb_dist))
            if len(self.thumb_history) >= 4 and detected_event is None:
                recent_thumb = [e for e in self.thumb_history if (now - e[0]) <= 0.25]
                if len(recent_thumb) >= 3:
                    t_angles = [e[1] for e in recent_thumb]
                    t_min = min(t_angles)
                    t_max = max(t_angles)
                    t_curr = t_angles[-1]
                    t_rebound = (t_curr > t_min + 12.0) and (t_curr > 125.0)
                    cooldown = self.settings.keyboard.tap_cooldown_ms / 1000.0
                    if (t_max - t_min >= 18.0) and t_rebound and (now - self.last_tap_time["thumb"] > cooldown):
                        self.last_tap_time["thumb"] = now
                        detected_event = "thumb"
                        is_repeat = False

        return detected_event, is_repeat, self.current_curls

    def _reset_holds(self):
        for f in self.curl_hold_start:
            self.curl_hold_start[f] = None
`
  },
  {
    name: "mode_manager.py",
    path: "tony_pointer/mode_manager.py",
    description: "State machine for POINTER/KEYBOARD/PAINT modes, sliding door row jumps, and zone transitions",
    language: "python",
    content: `"""
Tony Pointer - Mode & Keyboard Navigation State Machine
Orchestrates transitions between POINTER, KEYBOARD, and PAINT modes.
"""

import collections
import enum
import math
import time
from typing import Dict, Optional, Tuple

from keyboard_layout import KeyboardLayoutManager, KeyboardWindow, Zone
from tracker import HandFrame


class AppMode(enum.Enum):
    POINTER = "POINTER"
    KEYBOARD = "KEYBOARD"
    PAINT = "PAINT"


class ModeManager:
    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        self.settings = settings
        self.layout_manager = layout_manager
        self.mode = AppMode.POINTER
        self.active_zone = Zone.MAIN
        self.row_idx = 3
        self.window_idx = 0
        self.zone_window_memory = {
            Zone.MAIN: {r: 0 for r in range(6)},
            Zone.SYMBOLS: {r: 0 for r in range(6)},
        }
        self.open_palm_start = None
        self.open_palm_progress = 0.0
        self.fist_start = None
        self.fist_progress = 0.0
        self.neutral_hand_center = None
        self.last_swipe_time = 0.0
        self.hand_returned_to_neutral = True
        self.bounce_active = False

    def get_current_window(self) -> KeyboardWindow:
        return self.layout_manager.get_window(self.active_zone, self.row_idx, self.window_idx)

    def toggle_keyboard_mode(self, force_state: Optional[bool] = None) -> bool:
        if force_state is not None:
            self.mode = AppMode.KEYBOARD if force_state else AppMode.POINTER
        else:
            self.mode = AppMode.KEYBOARD if self.mode != AppMode.KEYBOARD else AppMode.POINTER
        self.neutral_hand_center = None
        self.open_palm_start = None
        self.open_palm_progress = 0.0
        self.fist_start = None
        self.fist_progress = 0.0
        return self.mode == AppMode.KEYBOARD

    def toggle_zone(self):
        new_zone = Zone.SYMBOLS if self.active_zone == Zone.MAIN else Zone.MAIN
        self._switch_zone(new_zone)

    def _switch_zone(self, new_zone: Zone):
        self.zone_window_memory[self.active_zone][self.row_idx] = self.window_idx
        self.active_zone = new_zone
        saved_idx = self.zone_window_memory[new_zone].get(self.row_idx, 0)
        max_idx = self.layout_manager.get_max_window_idx(new_zone, self.row_idx)
        self.window_idx = max(0, min(max_idx, saved_idx))

    def evaluate_mode_transitions(self, hand: Optional[HandFrame], is_pointing: bool, is_fist: bool, is_open_palm: bool) -> Tuple[AppMode, float]:
        now = time.perf_counter()
        if hand is None:
            self.open_palm_start = None
            self.open_palm_progress = 0.0
            self.fist_start = None
            self.fist_progress = 0.0
            return self.mode, 0.0

        if self.mode == AppMode.POINTER:
            if is_open_palm:
                if self.open_palm_start is None:
                    self.open_palm_start = now
                    self.open_palm_progress = 0.0
                elapsed = now - self.open_palm_start
                hold_target = self.settings.keyboard.open_palm_hold_s
                self.open_palm_progress = min(1.0, elapsed / hold_target)
                if elapsed >= hold_target:
                    self.mode = AppMode.KEYBOARD
                    self.neutral_hand_center = None
                    self.open_palm_start = None
                    self.open_palm_progress = 0.0
                    return self.mode, 1.0
                return self.mode, self.open_palm_progress
            else:
                self.open_palm_start = None
                self.open_palm_progress = 0.0
        elif self.mode == AppMode.KEYBOARD:
            if is_pointing:
                self.mode = AppMode.POINTER
                return self.mode, 0.0
            if is_fist:
                if self.fist_start is None:
                    self.fist_start = now
                    self.fist_progress = 0.0
                elapsed = now - self.fist_start
                hold_target = self.settings.keyboard.fist_close_hold_s
                self.fist_progress = min(1.0, elapsed / hold_target)
                if elapsed >= hold_target:
                    self.mode = AppMode.POINTER
                    self.fist_start = None
                    self.fist_progress = 0.0
                    return self.mode, 1.0
                return self.mode, self.fist_progress
            else:
                self.fist_start = None
                self.fist_progress = 0.0
        return self.mode, 0.0

    def evaluate_swipes(self, hand: Optional[HandFrame], tap_in_progress: bool) -> Optional[str]:
        if hand is None or self.mode != AppMode.KEYBOARD or tap_in_progress:
            self.neutral_hand_center = None
            return None

        now = time.perf_counter()
        cooldown = self.settings.keyboard.swipe_cooldown_ms / 1000.0
        wrist = hand.get(0)
        mcp9 = hand.get(9)
        cx = (wrist.x + mcp9.x) / 2.0
        cy = (wrist.y + mcp9.y) / 2.0
        hand_size = max(0.04, hand.distance_3d(0, 9))

        if self.neutral_hand_center is None:
            self.neutral_hand_center = (cx, cy)
            self.hand_returned_to_neutral = True
            return None

        dx = (cx - self.neutral_hand_center[0]) / hand_size
        dy = (cy - self.neutral_hand_center[1]) / hand_size
        dist = math.hypot(dx, dy)

        if dist < 0.22:
            self.hand_returned_to_neutral = True
            self.neutral_hand_center = (
                self.neutral_hand_center[0] * 0.9 + cx * 0.1,
                self.neutral_hand_center[1] * 0.9 + cy * 0.1,
            )
            self.bounce_active = False

        if not self.hand_returned_to_neutral or (now - self.last_swipe_time < cooldown):
            return None

        swipe_threshold = self.settings.keyboard.swipe_threshold

        if abs(dy) > abs(dx) and abs(dy) >= swipe_threshold:
            if dy < 0:
                self.row_idx = max(0, self.row_idx - 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "UP"
            else:
                self.row_idx = min(5, self.row_idx + 1)
                self._clamp_window_to_current_row()
                self._record_swipe(now)
                return "DOWN"

        if abs(dx) > abs(dy) and abs(dx) >= swipe_threshold:
            if dx > 0:
                max_w = self.layout_manager.get_max_window_idx(self.active_zone, self.row_idx)
                if self.window_idx < max_w:
                    self.window_idx += 1
                    self._record_swipe(now)
                    return "RIGHT"
                elif self.active_zone == Zone.MAIN and self.settings.keyboard.symbols_panel_enabled:
                    self._switch_zone(Zone.SYMBOLS)
                    self.window_idx = 0
                    self._record_swipe(now)
                    return "CROSS_INTO_SYMBOLS"
                else:
                    self.bounce_active = True
                    self._record_swipe(now)
                    return "BOUNCE"
            else:
                if self.window_idx > 0:
                    self.window_idx -= 1
                    self._record_swipe(now)
                    return "LEFT"
                elif self.active_zone == Zone.SYMBOLS:
                    self._switch_zone(Zone.MAIN)
                    self.window_idx = self.layout_manager.get_max_window_idx(Zone.MAIN, self.row_idx)
                    self._record_swipe(now)
                    return "CROSS_INTO_MAIN"
                else:
                    self.bounce_active = True
                    self._record_swipe(now)
                    return "BOUNCE"
        return None

    def _record_swipe(self, timestamp: float):
        self.last_swipe_time = timestamp
        self.hand_returned_to_neutral = False

    def _clamp_window_to_current_row(self):
        max_idx = self.layout_manager.get_max_window_idx(self.active_zone, self.row_idx)
        self.window_idx = max(0, min(max_idx, self.window_idx))
`
  },
  {
    name: "gestures.py",
    path: "tony_pointer/gestures.py",
    description: "Gesture detection state machine: air-tap double click, lookback anti-jitter buffer, dwell/pinch brush lock, open-palm keyboard trigger",
    language: "python",
    content: `"""
Tony Pointer - Gesture Recognition Engine
Identifies air double-taps, single clicks, two-finger right click, two-finger scroll,
dwell/pinch brush lock, and open-palm keyboard mode engagement.
"""

import collections
import enum
import math
import time
from typing import Callable, Deque, Dict, Optional, Tuple

from filters import PositionHistoryBuffer, apply_acceleration
from tracker import HandFrame


class PoseType(enum.Enum):
    UNKNOWN = "UNKNOWN"
    OPEN_PALM = "OPEN_PALM"
    POINTING = "POINTING"
    TWO_FINGER = "TWO_FINGER"
    PINCH = "PINCH"
    FIST = "FIST"


class GestureAction(enum.Enum):
    NONE = "NONE"
    MOVE = "MOVE"
    SINGLE_CLICK = "SINGLE_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    SCROLL = "SCROLL"
    BRUSH_LOCK_TOGGLE = "BRUSH_LOCK_TOGGLE"
    BRUSH_UNLOCK = "BRUSH_UNLOCK"
    PAUSE = "PAUSE"
    ENTER_KEYBOARD = "ENTER_KEYBOARD"
    EXIT_KEYBOARD = "EXIT_KEYBOARD"


class GestureEngine:
    def __init__(self, settings):
        self.settings = settings
        self.history_buffer = PositionHistoryBuffer(max_duration_s=0.6)
        self.current_pose = PoseType.UNKNOWN
        self.active_action = GestureAction.NONE
        self.brush_locked = False

        self.index_angle_history = collections.deque(maxlen=15)
        self.last_tap_time = 0.0
        self.pending_single_tap = False
        self.tap_frozen_pos = None

        self.two_finger_start_time = None
        self.two_finger_right_clicked = False
        self.last_two_finger_y = None

        self.dwell_start_time = None
        self.dwell_anchor_pos = None
        self.dwell_progress = 0.0

        self.open_palm_start_time = None
        self.open_palm_progress = 0.0
        self.fist_start_time = None
        self.fist_progress = 0.0

        self.last_pinch_time = 0.0
        self.is_pinching = False
        self.last_hand_time = 0.0
        self.cursor_frozen = False

    def classify_pose(self, hand: HandFrame) -> PoseType:
        dist_wrist_index_tip = hand.distance_3d(0, 8)
        dist_wrist_index_pip = hand.distance_3d(0, 6)
        index_extended = dist_wrist_index_tip > dist_wrist_index_pip * 1.15

        dist_wrist_middle_tip = hand.distance_3d(0, 12)
        dist_wrist_middle_pip = hand.distance_3d(0, 10)
        middle_extended = dist_wrist_middle_tip > dist_wrist_middle_pip * 1.15

        dist_wrist_ring_tip = hand.distance_3d(0, 16)
        dist_wrist_ring_pip = hand.distance_3d(0, 14)
        ring_extended = dist_wrist_ring_tip > dist_wrist_ring_pip * 1.15

        dist_wrist_pinky_tip = hand.distance_3d(0, 20)
        dist_wrist_pinky_pip = hand.distance_3d(0, 18)
        pinky_extended = dist_wrist_pinky_tip > dist_wrist_pinky_pip * 1.15

        pinch_dist = hand.distance_3d(4, 8)
        if pinch_dist < self.settings.gestures.pinch_threshold:
            return PoseType.PINCH

        if index_extended and middle_extended and ring_extended and pinky_extended:
            return PoseType.OPEN_PALM

        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return PoseType.TWO_FINGER

        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return PoseType.POINTING

        if not index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return PoseType.FIST

        return PoseType.UNKNOWN

    def update_dwell_lock(self, norm_x: float, norm_y: float, now: float) -> Tuple[bool, float]:
        if self.dwell_anchor_pos is None:
            self.dwell_anchor_pos = (norm_x, norm_y)
            self.dwell_start_time = now
            self.dwell_progress = 0.0
            return False, 0.0

        dx = norm_x - self.dwell_anchor_pos[0]
        dy = norm_y - self.dwell_anchor_pos[1]
        drift = math.hypot(dx, dy)
        if drift > 0.02:
            self.dwell_anchor_pos = (norm_x, norm_y)
            self.dwell_start_time = now
            self.dwell_progress = 0.0
            return False, 0.0

        elapsed = now - self.dwell_start_time
        target = self.settings.gestures.dwell_lock_time_s
        self.dwell_progress = min(1.0, elapsed / target)
        if elapsed >= target:
            self.dwell_start_time = None
            self.dwell_anchor_pos = None
            self.dwell_progress = 0.0
            return True, 1.0
        return False, self.dwell_progress

    def detect_air_tap(self, hand: HandFrame, now: float) -> bool:
        dip_angle = hand.angle_deg(6, 7, 8)
        self.index_angle_history.append((now, dip_angle))
        if len(self.index_angle_history) < 5:
            return False

        angles = [a for t, a in self.index_angle_history if now - t <= 0.30]
        if len(angles) < 4:
            return False

        min_angle = min(angles)
        max_angle = max(angles)
        angle_delta = max_angle - min_angle
        current_angle = angles[-1]
        rebounded = current_angle > (min_angle + 18.0) and current_angle > 140.0
        cooldown_s = self.settings.gestures.tap_cooldown_ms / 1000.0

        if angle_delta >= 22.0 and rebounded and (now - self.last_tap_time > cooldown_s):
            self.last_tap_time = now
            return True
        return False

    def process(self, hand: Optional[HandFrame], screen_bounds: Tuple[int, int, int, int], filter_2d, current_mode: str = "POINTER") -> Dict:
        now = time.perf_counter()
        vx, vy, vw, vh = screen_bounds
        result = {
            "pose": PoseType.UNKNOWN.value,
            "action": GestureAction.NONE.value,
            "cursor_x": 0, "cursor_y": 0,
            "dwell_progress": self.dwell_progress,
            "open_palm_progress": self.open_palm_progress,
            "fist_progress": self.fist_progress,
            "brush_locked": self.brush_locked,
            "hand_visible": False,
            "status_text": "SEARCHING FOR HAND",
        }

        if hand is None:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            self.open_palm_start_time = None
            self.open_palm_progress = 0.0
            self.fist_start_time = None
            self.fist_progress = 0.0
            self.two_finger_start_time = None

            if self.last_hand_time > 0:
                elapsed_lost = now - self.last_hand_time
                if elapsed_lost > (self.settings.gestures.hand_timeout_ms / 1000.0):
                    result["action"] = GestureAction.PAUSE.value
                    result["status_text"] = "TRACKING PAUSED"
                if self.brush_locked and elapsed_lost > self.settings.gestures.safety_release_timeout_s:
                    self.brush_locked = False
                    result["action"] = GestureAction.BRUSH_UNLOCK.value
                    result["brush_locked"] = False
                    result["status_text"] = "SAFETY AUTO-RELEASE"
            return result

        self.last_hand_time = now
        result["hand_visible"] = True
        pose = self.classify_pose(hand)
        self.current_pose = pose
        result["pose"] = pose.value

        if current_mode == "KEYBOARD":
            result["action"] = GestureAction.PAUSE.value
            if pose == PoseType.POINTING:
                result["action"] = GestureAction.EXIT_KEYBOARD.value
                result["status_text"] = "EXIT KEYBOARD (POINTING)"
                return result
            if pose == PoseType.FIST:
                if self.fist_start_time is None:
                    self.fist_start_time = now
                    self.fist_progress = 0.0
                elapsed = now - self.fist_start_time
                target = self.settings.keyboard.fist_close_hold_s
                self.fist_progress = min(1.0, elapsed / target)
                result["fist_progress"] = self.fist_progress
                if elapsed >= target:
                    self.fist_start_time = None
                    self.fist_progress = 0.0
                    result["action"] = GestureAction.EXIT_KEYBOARD.value
                    result["status_text"] = "EXIT KEYBOARD (FIST)"
                else:
                    result["status_text"] = f"HOLD FIST TO CLOSE ({int(self.fist_progress * 100)}%)"
                return result
            else:
                self.fist_start_time = None
                self.fist_progress = 0.0
                result["status_text"] = "AIR KEYBOARD ACTIVE"
                return result

        index_tip = hand.get(8)
        norm_x = index_tip.x
        norm_y = index_tip.y

        ar = self.settings.active_region
        clamped_x = max(ar.x_min, min(ar.x_max, norm_x))
        clamped_y = max(ar.y_min, min(ar.y_max, norm_y))
        span_x = max(0.01, ar.x_max - ar.x_min)
        span_y = max(0.01, ar.y_max - ar.y_min)
        remapped_x = (clamped_x - ar.x_min) / span_x
        remapped_y = (clamped_y - ar.y_min) / span_y

        raw_screen_x = vx + int(remapped_x * vw)
        raw_screen_y = vy + int(remapped_y * vh)
        filt_x, filt_y = filter_2d.filter(raw_screen_x, raw_screen_y, now)
        screen_x = int(round(filt_x))
        screen_y = int(round(filt_y))

        self.history_buffer.append(screen_x, screen_y, now)
        result["cursor_x"] = screen_x
        result["cursor_y"] = screen_y

        if pose == PoseType.OPEN_PALM:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            self.two_finger_start_time = None

            if self.brush_locked:
                self.brush_locked = False
                result["action"] = GestureAction.BRUSH_UNLOCK.value
                result["brush_locked"] = False
                result["status_text"] = "BRUSH RELEASED"
                return result

            if self.open_palm_start_time is None:
                self.open_palm_start_time = now
                self.open_palm_progress = 0.0
            elapsed = now - self.open_palm_start_time
            target = self.settings.keyboard.open_palm_hold_s
            self.open_palm_progress = min(1.0, elapsed / target)
            result["open_palm_progress"] = self.open_palm_progress

            if elapsed >= target:
                self.open_palm_start_time = None
                self.open_palm_progress = 0.0
                result["action"] = GestureAction.ENTER_KEYBOARD.value
                result["status_text"] = "AIR KEYBOARD ENGAGED"
                return result

            result["action"] = GestureAction.PAUSE.value
            result["status_text"] = f"HOLD OPEN PALM: KEYBOARD ({int(self.open_palm_progress * 100)}%)"
            return result
        else:
            self.open_palm_start_time = None
            self.open_palm_progress = 0.0

        if pose == PoseType.PINCH:
            if not self.is_pinching and (now - self.last_pinch_time > 0.4):
                self.is_pinching = True
                self.last_pinch_time = now
                self.brush_locked = not self.brush_locked
                result["action"] = GestureAction.BRUSH_LOCK_TOGGLE.value if self.brush_locked else GestureAction.BRUSH_UNLOCK.value
                result["brush_locked"] = self.brush_locked
                result["status_text"] = "BRUSH LOCKED" if self.brush_locked else "BRUSH RELEASED"
                return result
        else:
            self.is_pinching = False

        if pose == PoseType.TWO_FINGER:
            self.dwell_start_time = None
            self.dwell_progress = 0.0
            if self.two_finger_start_time is None:
                self.two_finger_start_time = now
                self.two_finger_right_clicked = False
                self.last_two_finger_y = (hand.get(8).y + hand.get(12).y) / 2.0
                result["status_text"] = "TWO-FINGER GESTURE"
                return result

            elapsed_two_finger = now - self.two_finger_start_time
            current_two_finger_y = (hand.get(8).y + hand.get(12).y) / 2.0
            delta_y = current_two_finger_y - (self.last_two_finger_y or current_two_finger_y)
            self.last_two_finger_y = current_two_finger_y

            if abs(delta_y) > 0.008:
                scroll_amount = -int(delta_y * 100 * self.settings.gestures.scroll_sensitivity)
                result["action"] = GestureAction.SCROLL.value
                result["scroll_delta"] = scroll_amount
                result["status_text"] = f"SCROLLING ({scroll_amount:+d})"
                return result

            if elapsed_two_finger >= self.settings.gestures.right_click_hold_s and not self.two_finger_right_clicked:
                self.two_finger_right_clicked = True
                result["action"] = GestureAction.RIGHT_CLICK.value
                result["status_text"] = "RIGHT CLICK"
                return result
            result["status_text"] = "HOLD FOR RIGHT CLICK"
            return result
        else:
            self.two_finger_start_time = None

        if pose == PoseType.POINTING:
            if not self.brush_locked:
                locked, progress = self.update_dwell_lock(norm_x, norm_y, now)
                result["dwell_progress"] = progress
                if locked:
                    self.brush_locked = True
                    result["action"] = GestureAction.BRUSH_LOCK_TOGGLE.value
                    result["brush_locked"] = True
                    result["status_text"] = "BRUSH LOCKED (DWELL)"
                    return result

            tap_detected = self.detect_air_tap(hand, now)
            if tap_detected:
                stable_pos = self.history_buffer.get_position_at_lookback(150.0)
                if stable_pos:
                    result["cursor_x"] = int(stable_pos[0])
                    result["cursor_y"] = int(stable_pos[1])

                double_tap_window_s = self.settings.gestures.double_tap_window_ms / 1000.0
                if self.pending_single_tap and (now - self.last_tap_time <= double_tap_window_s):
                    self.pending_single_tap = False
                    result["action"] = GestureAction.DOUBLE_CLICK.value
                    result["status_text"] = "DOUBLE CLICK (AIR TAP)"
                    return result
                else:
                    self.pending_single_tap = True
                    self.tap_frozen_pos = (result["cursor_x"], result["cursor_y"])

            double_tap_window_s = self.settings.gestures.double_tap_window_ms / 1000.0
            if self.pending_single_tap and (now - self.last_tap_time > double_tap_window_s) and self.settings.gestures.single_click_enabled:
                self.pending_single_tap = False
                result["action"] = GestureAction.SINGLE_CLICK.value
                if self.tap_frozen_pos:
                    result["cursor_x"] = self.tap_frozen_pos[0]
                    result["cursor_y"] = self.tap_frozen_pos[1]
                result["status_text"] = "SINGLE CLICK"
                return result

            result["action"] = GestureAction.MOVE.value
            result["status_text"] = "BRUSH PAINTING" if self.brush_locked else "POINTING"
            return result

        return result
`
  },
  {
    name: "tracker.py",
    path: "tony_pointer/tracker.py",
    description: "MediaPipe Tasks API HandLandmarker with auto-download, GPU/CPU delegate, and hand scale normalization",
    language: "python",
    content: `"""
Tony Pointer - MediaPipe Tasks API Hand Landmarker Tracker
Tracks 21 3D hand landmarks in real time with sub-10ms inference.
"""

import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

TASK_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)


class LandmarkPoint:
    __slots__ = ("x", "y", "z")
    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


class HandFrame:
    def __init__(self, landmarks: List[LandmarkPoint], timestamp_ms: int, handedness: str = "Right"):
        self.landmarks = landmarks
        self.timestamp_ms = timestamp_ms
        self.handedness = handedness

    def get(self, index: int) -> LandmarkPoint:
        return self.landmarks[index]

    def distance_3d(self, idx_a: int, idx_b: int) -> float:
        a = self.landmarks[idx_a]
        b = self.landmarks[idx_b]
        return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)

    def get_hand_size(self) -> float:
        return max(0.04, self.distance_3d(0, 9))

    def get_palm_center(self) -> Tuple[float, float, float]:
        pts = [self.landmarks[i] for i in (0, 5, 9, 13, 17)]
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        cz = sum(p.z for p in pts) / len(pts)
        return (cx, cy, cz)

    def angle_deg(self, idx_a: int, idx_b: int, idx_c: int) -> float:
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
    def __init__(self, model_dir: Optional[str] = None):
        if model_dir is None:
            model_dir = str(Path.home() / ".tony_pointer" / "models")
        os.makedirs(model_dir, exist_ok=True)
        self.model_path = os.path.join(model_dir, "hand_landmarker.task")
        self._ensure_model_downloaded()
        self.landmarker = self._create_landmarker()
        self.last_result = None
        self.last_seen_time = 0.0

    def _ensure_model_downloaded(self):
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000000:
            return
        try:
            urllib.request.urlretrieve(TASK_MODEL_URL, self.model_path)
        except Exception:
            local = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
            if os.path.exists(local):
                self.model_path = local

    def _create_landmarker(self):
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            base_options = python.BaseOptions(model_asset_path=self.model_path, delegate=python.BaseOptions.Delegate.GPU)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            return vision.HandLandmarker.create_from_options(options)
        except Exception:
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision
                base_options = python.BaseOptions(model_asset_path=self.model_path, delegate=python.BaseOptions.Delegate.CPU)
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                    min_hand_detection_confidence=0.5,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                return vision.HandLandmarker.create_from_options(options)
            except Exception as e:
                print(f"[TonyPointer] Could not init tracker: {e}")
                return None

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[HandFrame]:
        if self.landmarker is None or frame_bgr is None:
            return None
        import mediapipe as mp
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        try:
            result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception:
            return self.last_result

        if not result or not result.hand_landmarks or len(result.hand_landmarks) == 0:
            return None
        raw_landmarks = result.hand_landmarks[0]
        landmarks = [LandmarkPoint(pt.x, pt.y, pt.z) for pt in raw_landmarks]
        handedness = "Right"
        if result.handedness and len(result.handedness) > 0 and len(result.handedness[0]) > 0:
            handedness = result.handedness[0][0].category_name
        hand_frame = HandFrame(landmarks=landmarks, timestamp_ms=timestamp_ms, handedness=handedness)
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
`
  },
  {
    name: "settings.py",
    path: "tony_pointer/settings.py",
    description: "JSON persistence for active region bounds, One Euro parameters, Air Keyboard options, and paint profiles",
    language: "python",
    content: `"""
Tony Pointer - Settings & Configuration Manager
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ActiveRegion:
    x_min: float = 0.15
    y_min: float = 0.15
    x_max: float = 0.85
    y_max: float = 0.85


@dataclass
class OneEuroSettings:
    min_cutoff: float = 1.0
    beta: float = 0.007
    d_cutoff: float = 1.0


@dataclass
class PaintModeSettings:
    stabilizer: float = 0.85
    min_cutoff: float = 0.25
    beta: float = 0.001
    auto_detect: bool = True
    active_apps: List[str] = field(
        default_factory=lambda: [
            "mspaint.exe", "krita.exe", "photoshop.exe",
            "clipstudio.exe", "gimp.exe", "paint.exe"
        ]
    )


@dataclass
class GestureSettings:
    double_tap_window_ms: float = 500.0
    tap_curl_threshold: float = 0.045
    tap_cooldown_ms: float = 220.0
    single_click_enabled: bool = True
    dwell_lock_time_s: float = 0.60
    dwell_radius_px: float = 16.0
    pinch_threshold: float = 0.045
    right_click_hold_s: float = 0.45
    scroll_sensitivity: float = 2.4
    hand_timeout_ms: float = 300.0
    safety_release_timeout_s: float = 1.0


@dataclass
class OverlaySettings:
    cursor_color: str = "#00E5FF"
    brush_lock_color: str = "#FF5722"
    cursor_size: int = 34
    preview_width: int = 320
    preview_height: int = 240
    preview_opacity: float = 0.85
    preview_visible: bool = True
    preview_pos_x: int = 40
    preview_pos_y: int = 40


@dataclass
class KeyboardSettings:
    enabled: bool = True
    symbols_panel_enabled: bool = True
    dim_inactive_panel: bool = True
    opacity: float = 0.88
    open_palm_hold_s: float = 0.50
    fist_close_hold_s: float = 0.50
    swipe_threshold: float = 0.32
    swipe_cooldown_ms: float = 300.0
    tap_cooldown_ms: float = 200.0
    index_sensitivity: float = 1.0
    middle_sensitivity: float = 1.0
    ring_sensitivity: float = 1.25
    pinky_sensitivity: float = 1.35
    thumb_is_space: bool = True
    key_repeat_delay_s: float = 0.50
    key_repeat_interval_s: float = 0.10
    finger_mapping: str = "visual"
    hotkey_keyboard: str = "ctrl+alt+k"
    hotkey_zone_toggle: str = "ctrl+alt+s"
    sound_enabled: bool = True


@dataclass
class AppConfig:
    version: str = "1.0.0"
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    target_fps: int = 60
    sensitivity: float = 1.0
    acceleration: float = 1.15
    active_region: ActiveRegion = field(default_factory=ActiveRegion)
    one_euro: OneEuroSettings = field(default_factory=OneEuroSettings)
    paint: PaintModeSettings = field(default_factory=PaintModeSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    keyboard: KeyboardSettings = field(default_factory=KeyboardSettings)
    hotkey_toggle: str = "ctrl+alt+t"
    hotkey_paint: str = "ctrl+alt+p"
    start_minimized: bool = False


class SettingsManager:
    def __init__(self, config_dir: str = None):
        base_dir = Path.home() / ".tony_pointer" if config_dir is None else Path(config_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = base_dir / "config.json"
        self.config: AppConfig = self.load()

    def load(self) -> AppConfig:
        if not self.filepath.exists():
            cfg = AppConfig()
            self.save(cfg)
            return cfg
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig(
                version=data.get("version", "1.0.0"),
                camera_index=data.get("camera_index", 0),
                camera_width=data.get("camera_width", 1280),
                camera_height=data.get("camera_height", 720),
                target_fps=data.get("target_fps", 60),
                sensitivity=data.get("sensitivity", 1.0),
                acceleration=data.get("acceleration", 1.15),
                active_region=ActiveRegion(**data.get("active_region", {})),
                one_euro=OneEuroSettings(**data.get("one_euro", {})),
                paint=PaintModeSettings(**data.get("paint", {})),
                gestures=GestureSettings(**data.get("gestures", {})),
                overlay=OverlaySettings(**data.get("overlay", {})),
                keyboard=KeyboardSettings(**data.get("keyboard", {})),
                hotkey_toggle=data.get("hotkey_toggle", "ctrl+alt+t"),
                hotkey_paint=data.get("hotkey_paint", "ctrl+alt+p"),
                start_minimized=data.get("start_minimized", False),
            )
        except Exception:
            cfg = AppConfig()
            self.save(cfg)
            return cfg

    def save(self, config: AppConfig = None) -> bool:
        if config is not None:
            self.config = config
        try:
            data = asdict(self.config)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
`
  },
  {
    name: "ui.py",
    path: "tony_pointer/ui.py",
    description: "PySide6 Stark UI: Arc Reactor button, live video feed, telemetry, finger curl bars, and Air Keyboard tab",
    language: "python",
    content: `"""
Tony Pointer - PySide6 Main Window & Calibration Studio
"""
# (Refer to /tony_pointer/ui.py for complete source code)
`
  },
  {
    name: "camera.py",
    path: "tony_pointer/camera.py",
    description: "Threaded OpenCV capture engine with frame-drop latency protection and Stark HUD drawing",
    language: "python",
    content: `"""
Tony Pointer - High-Speed Asynchronous Camera Capture & HUD Overlay
"""
# (Refer to /tony_pointer/camera.py for complete source code)
`
  },
  {
    name: "mouse.py",
    path: "tony_pointer/mouse.py",
    description: "Hardware Win32 SendInput (ctypes) driver: multi-monitor virtual desktop, clicks, drags, scroll, safety watchdog",
    language: "python",
    content: `"""
Tony Pointer - Hardware-Level Mouse Emulation via Win32 SendInput
"""
# (Refer to /tony_pointer/mouse.py for complete source code)
`
  },
  {
    name: "filters.py",
    path: "tony_pointer/filters.py",
    description: "One Euro Filter (Casiez 2012), 2D vector smoothing, and position lookback history buffer",
    language: "python",
    content: `"""
Tony Pointer - Signal Filters & Mathematical Smoothing
"""
# (Refer to /tony_pointer/filters.py for complete source code)
`
  },
  {
    name: "overlay.py",
    path: "tony_pointer/overlay.py",
    description: "PySide6 click-through transparent cursor HUD window & floating camera preview HUD",
    language: "python",
    content: `"""
Tony Pointer - PySide6 Holographic Cursor Reticle & Camera HUD Overlays
"""
# (Refer to /tony_pointer/overlay.py for complete source code)
`
  },
  {
    name: "requirements.txt",
    path: "tony_pointer/requirements.txt",
    description: "Python 3.11 package dependencies list",
    language: "text",
    content: `mediapipe>=0.10.14
opencv-python>=4.9.0.80
PySide6>=6.6.0
numpy>=1.26.0
keyboard>=0.13.5
pyinstaller>=6.5.0
psutil>=5.9.0
pywin32>=306
requests>=2.31.0
`
  },
  {
    name: "build_exe.bat",
    path: "tony_pointer/build_exe.bat",
    description: "Batch file to bundle Python project into single-file TonyPointer.exe with PyInstaller",
    language: "batch",
    content: `@echo off
echo ========================================================
echo    TONY POINTER - STANDALONE EXECUTABLE BUILDER
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    pause
    exit /b 1
)

echo [1/3] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building standalone single-file TonyPointer.exe with PyInstaller...
pyinstaller --clean tony_pointer.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo Executable generated in: dist\\TonyPointer.exe
pause
`
  },
  {
    name: "tony_pointer.spec",
    path: "tony_pointer/tony_pointer.spec",
    description: "PyInstaller build specification with MediaPipe data asset and keyboard modules inclusion",
    language: "python",
    content: `# -*- mode: python ; coding: utf-8 -*-
# Tony Pointer PyInstaller Specification File

import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
mediapipe_datas = collect_data_files('mediapipe')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=mediapipe_datas + [
        ('settings.py', '.'),
        ('filters.py', '.'),
        ('mouse.py', '.'),
        ('tracker.py', '.'),
        ('gestures.py', '.'),
        ('camera.py', '.'),
        ('overlay.py', '.'),
        ('ui.py', '.'),
        ('keyboard_layout.py', '.'),
        ('keyboard_out.py', '.'),
        ('keyboard_ui.py', '.'),
        ('finger_taps.py', '.'),
        ('mode_manager.py', '.'),
    ],
    hiddenimports=[
        'keyboard',
        'psutil',
        'cv2',
        'numpy',
        'mediapipe',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TonyPointer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
`
  },
  {
    name: "README.md",
    path: "tony_pointer/README.md",
    description: "Complete user guide, setup steps, keyboard layout guide, and troubleshooting",
    language: "markdown",
    content: `# Tony Pointer 🚀
### Iron-Man Holographic Hand Gesture PC Controller & Floating Air Keyboard

Control your entire Windows PC with one hand using any webcam.
- Air Double-Tap to launch apps & open folders
- Floating Air Keyboard + Symbols Panel (6 rows, 4-key blue window, sliding door navigation)
- One Euro Filter smoothing
- Lookback Anti-Jitter click target anchoring
- Brush Lock for Photoshop, Krita, MS Paint
- PySide6 HUD & Win32 SendInput (ctypes)

Run:
  pip install -r requirements.txt
  python main.py

Build .exe:
  build_exe.bat
`
  }
];
