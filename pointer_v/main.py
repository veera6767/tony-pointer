"""
Pointer V - Main Application Entrypoint & System Coordinator
Launches the PySide6 Application, manages background vision worker threads,
hooks system tray, registers global OS hotkeys, coordinates MediaPipe tracking
with Win32 SendInput mouse/keyboard dispatch, and delivers thread-safe UI signals.
"""

import atexit
import collections
import ctypes
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import keyboard
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

from camera import CameraStream, draw_hud_landmarks
from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine
from keyboard_layout import KeyboardLayoutManager, KeyboardWindow, Zone
from keyboard_out import ModifierState, Win32KeyboardOutput
from keyboard_ui import FloatingAirKeyboardWidget
from logger import log_input_event, setup_logger
from mode_manager import AppMode, ModeManager
from mouse import MouseController
from overlay import CursorOverlayWindow
from preview import CameraPreviewOverlay
from recorder import LandmarkRecorder
from settings import SettingsManager
from sound import SoundManager
from tracker import HandTracker
from ui.main_window import MainWindow
from version import (
    APP_NAME, APP_SHORT_NAME, APP_TAGLINE, MUTEX_NAME, __version__
)


class WorkerSignals(QObject):
    """Thread-safe Qt signal bridge between background vision loop and main Qt UI."""
    cursor_updated = Signal(int, int, str, float, float, str)
    click_animated = Signal(bool)
    frame_updated = Signal(object, float)
    keyboard_updated = Signal(object, int, int, object, bool)
    key_typed = Signal(str, str)
    telemetry_updated = Signal()
    tray_notification_requested = Signal(str, str)
    toggle_active_requested = Signal(bool, bool)


class PointerVApp(QObject):
    """Coordinates hardware capture, gesture tracking, overlays, mouse input, and air keyboard."""

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.logger = setup_logger()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.config

        # 1. Hardware & Mouse Subsystems
        self.mouse = MouseController()
        self.target_bounds = self.mouse.get_target_bounds(
            getattr(self.settings.monitors, "monitor_index", -1)
        )

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

        # Developer stream recorder
        self.recorder = LandmarkRecorder()

        # Audio feedback manager
        self.sound = SoundManager(self.settings)

        # Threaded Camera Capture
        self.camera = CameraStream(
            camera_index=self.settings.camera_index,
            width=self.settings.camera_width,
            height=self.settings.camera_height,
            target_fps=self.settings.target_fps,
            camera_name=self.settings.camera_name,
        )

        # 3. Thread-safe UI Signal Bridge
        self.signals = WorkerSignals()

        # 4. Overlays & Windows
        self.cursor_overlay = CursorOverlayWindow(self.settings)
        self.camera_overlay = CameraPreviewOverlay(self.settings)
        self.keyboard_overlay = FloatingAirKeyboardWidget(self.settings, self.layout_manager)

        # Connect signals directly to UI slots on Main Thread
        self.signals.cursor_updated.connect(self.cursor_overlay.update_position)
        self.signals.click_animated.connect(self.cursor_overlay.trigger_click_anim)
        self.signals.frame_updated.connect(self.camera_overlay.update_frame)
        self.signals.keyboard_updated.connect(self.keyboard_overlay.update_state)
        self.signals.key_typed.connect(self.keyboard_overlay.trigger_key_flash)
        self.signals.tray_notification_requested.connect(self._show_tray_message)
        self.signals.toggle_active_requested.connect(self._handle_toggle_active)

        # Master Mode Toggle
        self.is_active = False
        self.paint_profile_active = False
        self.was_auto_paused = False
        self.total_frames = 0
        self.frames_with_hand = 0
        self.internal_errors = collections.deque(maxlen=5)

        # Shared Status Telemetry (Strict Privacy: No typed characters or key names)
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
            "is_active": False,
            "is_paused": False,
            "camera_connected": True,
            "is_low_light": False,
            "is_over_exposed": False,
            "camera_brightness": 128.0,
            "monitor_count": len(self.mouse.monitors),
            "total_frames": 0,
            "frames_with_hand": 0,
            "active_pos": (0.0, 0.0),
            "screen_coords": (0, 0),
            "mouse_sendinput_ret": 1,
            "mouse_sendinput_err": 0,
            "mouse_last_action": "IDLE",
            "key_sendinput_ret": 1,
            "key_sendinput_err": 0,
            "key_last_action": "IDLE",
            "internal_errors": [],
        }
        self.latest_vis_frame = None

        # 5. Main GUI Window
        self.main_window = MainWindow(
            settings_manager=self.settings_manager,
            mouse_controller=self.mouse,
            recorder=self.recorder,
            get_status_fn=lambda: self.telemetry,
            get_frame_fn=lambda: self.latest_vis_frame,
            keyboard_output=self.keyboard_out,
        )
        self.main_window.toggle_mode_requested.connect(self.set_active)
        self.main_window.toggle_keyboard_requested.connect(self._toggle_keyboard_mode)
        self.main_window.toggle_paint_requested.connect(self._toggle_paint_mode)
        self.main_window.toggle_pause_requested.connect(self._toggle_pause)
        self.main_window.settings_changed.connect(self._on_settings_reloaded)
        self.main_window.camera_device_changed.connect(self._on_camera_device_changed)
        self.main_window.fps_cap_changed.connect(self._on_fps_cap_changed)
        self.main_window.monitor_changed.connect(self._on_monitor_changed)
        self.main_window.restart_admin_requested.connect(self.restart_as_admin)
        self.main_window.app_quit_requested.connect(self.shutdown)
        self.main_window.test_cursor_requested.connect(self.cursor_overlay.start_test_animation)

        # UI Thread Watchdog: Dumps stacks if UI thread stalls > 2s
        import faulthandler
        try:
            faulthandler.enable()
        except Exception:
            pass
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._reset_watchdog)
        self.watchdog_timer.start(1000)
        self._reset_watchdog()

        # 6. System Tray Integration
        self._setup_tray()

        # 7. Global Hotkeys
        self._setup_hotkeys()

        # 8. Register Emergency atexit handler
        atexit.register(self.emergency_release_all)

        # 9. Start Camera Stream
        self.camera.start()

        # 10. Background Vision Processing Loop
        self.running = True
        self.worker_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.worker_thread.start()

        # 11. Foreground Window Inspector Timer (every 500ms)
        self.fg_timer = QTimer(self)
        self.fg_timer.timeout.connect(self._check_foreground_window)
        self.fg_timer.start(500)

        # Show main window or start minimized
        if not self.settings.start_minimized:
            self.main_window.show()

    def _get_tray_icon(self) -> QIcon:
        """Selects tray icon matching current mode and paused state."""
        base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
        if (base / "pointer_v" / "assets" / "icons").exists():
            icons_dir = base / "pointer_v" / "assets" / "icons"
        elif (base / "assets" / "icons").exists():
            icons_dir = base / "assets" / "icons"
        else:
            icons_dir = Path(__file__).resolve().parent / "assets" / "icons"
        if not self.is_active:
            p = icons_dir / "tray_off.png"
        elif self.mode_manager.is_paused:
            p = icons_dir / "tray_paused.png"
        elif self.mode_manager.mode == AppMode.KEYBOARD:
            p = icons_dir / "tray_keyboard.png"
        elif self.mode_manager.mode == AppMode.PAINT or self.paint_profile_active:
            p = icons_dir / "tray_paint.png"
        else:
            p = icons_dir / "tray_pointer.png"

        if p.exists():
            return QIcon(str(p))

        # Fallback dynamic pixmap
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor(47, 123, 255 if self.is_active else 100, 116, 139))
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()
        return QIcon(pix)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._get_tray_icon())
        self.tray.setToolTip(f"{APP_NAME} - Hand Gesture PC Controller")

        menu = QMenu()
        self.action_toggle = QAction(f"{APP_NAME}: OFF", self)
        self.action_toggle.triggered.connect(self._toggle_from_tray)
        menu.addAction(self.action_toggle)

        self.action_pause = QAction("Pause Tracking: OFF", self)
        self.action_pause.triggered.connect(self._toggle_pause)
        menu.addAction(self.action_pause)

        self.action_kb = QAction("Air Keyboard: OFF", self)
        self.action_kb.triggered.connect(self._toggle_keyboard_mode)
        menu.addAction(self.action_kb)

        self.action_paint = QAction("Paint Mode: OFF", self)
        self.action_paint.triggered.connect(self._toggle_paint_mode)
        menu.addAction(self.action_paint)

        menu.addSeparator()
        action_show = QAction("Open Control Center", self)
        action_show.triggered.connect(self.main_window.showNormal)
        menu.addAction(action_show)

        action_quit = QAction(f"Exit {APP_NAME}", self)
        action_quit.triggered.connect(self.shutdown)
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _update_tray_visuals(self):
        self.tray.setIcon(self._get_tray_icon())
        self.action_toggle.setText(f"{APP_NAME}: {'ON' if self.is_active else 'OFF'}")
        self.action_pause.setText(f"Pause Tracking: {'PAUSED' if self.mode_manager.is_paused else 'RESUMED'}")
        self.action_kb.setText(f"Air Keyboard: {'ON' if self.mode_manager.mode == AppMode.KEYBOARD else 'OFF'}")
        self.action_paint.setText(f"Paint Mode: {'ON' if self.paint_profile_active else 'OFF'}")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.main_window.showNormal()
            self.main_window.activateWindow()

    def _toggle_from_tray(self):
        self.set_active(not self.is_active)

    def _toggle_pause(self):
        new_paused = self.mode_manager.toggle_pause()
        if new_paused:
            self.emergency_release_all()
            self.sound.warning()
            self.tray.showMessage(APP_NAME, "Tracking Paused (Output suppressed)", QSystemTrayIcon.Information, 1500)
        else:
            self.sound.lock()
            self.tray.showMessage(APP_NAME, "Tracking Resumed", QSystemTrayIcon.Information, 1500)
        self._update_tray_visuals()

    def _toggle_keyboard_mode(self):
        new_active = self.mode_manager.toggle_keyboard_mode()
        self._update_keyboard_visibility(new_active)
        self._update_tray_visuals()

    def _reset_watchdog(self):
        """Pet the watchdog timer. If UI thread stalls > 2s, faulthandler dumps tracebacks."""
        import faulthandler
        try:
            faulthandler.dump_traceback_later(timeout=2, exit=False)
        except Exception:
            pass

    def _handle_toggle_active(self, active: bool, hide_window: bool):
        self.set_active(active, hide_window=hide_window)

    def _setup_hotkeys(self):
        try:
            keyboard.add_hotkey(self.settings.hotkey_toggle, lambda: self.signals.toggle_active_requested.emit(not self.is_active, True))
            keyboard.add_hotkey(self.settings.keyboard.hotkey_keyboard, lambda: QTimer.singleShot(0, self._toggle_keyboard_mode))
            keyboard.add_hotkey(self.settings.keyboard.hotkey_zone_toggle, lambda: QTimer.singleShot(0, self._toggle_keyboard_zone))
            keyboard.add_hotkey(self.settings.hotkey_paint, lambda: QTimer.singleShot(0, self._toggle_paint_mode))
            keyboard.add_hotkey(getattr(self.settings, "hotkey_pause", "ctrl+alt+space"), lambda: QTimer.singleShot(0, self._toggle_pause))
            keyboard.add_hotkey("esc", lambda: QTimer.singleShot(0, self._emergency_unlock))
        except Exception as e:
            self.logger.warning(f"Could not bind global hotkeys: {e}")

    def _toggle_keyboard_zone(self):
        if self.mode_manager.mode == AppMode.KEYBOARD:
            self.mode_manager.toggle_zone()
            self.sound.mode_change()

    def _emergency_unlock(self):
        """Immediate safety release on pressing Esc."""
        self.emergency_release_all()
        if self.mode_manager.mode == AppMode.KEYBOARD:
            self.mode_manager.mode = AppMode.POINTER
            self._update_keyboard_visibility(False)
        self.sound.unlock()
        self._update_tray_visuals()

    def emergency_release_all(self):
        """Releases every held mouse button and held/sticky keyboard modifier."""
        try:
            self.mouse.emergency_release()
            self.keyboard_out.release_all_modifiers()
            self.gesture_engine.brush_locked = False
        except Exception as e:
            pass

    def _toggle_paint_mode(self):
        self.paint_profile_active = not self.paint_profile_active
        self._apply_filter_profile()
        if self.paint_profile_active:
            self.sound.lock()
        else:
            self.sound.unlock()
        self._update_tray_visuals()

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
        """Detects focused application name, password fields, and fullscreen game mode."""
        proc = self.mouse.get_active_process_name()
        title = self.mouse.get_active_window_title().lower()

        if proc:
            self.telemetry["foreground_app"] = proc

            # Auto-paint mode detection
            if self.settings.paint.auto_detect:
                is_paint_app = any(app in proc for app in self.settings.paint.active_apps)
                if is_paint_app != self.paint_profile_active:
                    self.paint_profile_active = is_paint_app
                    self._apply_filter_profile()
                    self._update_tray_visuals()

            # Game mode fullscreen detection
            if getattr(self.settings.gestures, "game_mode_enabled", False):
                is_fullscreen = self.mouse.is_fullscreen_app_active()
                is_excluded = any(ex in proc for ex in getattr(self.settings.gestures, "game_mode_exclusions", []))
                if is_fullscreen and not is_excluded and not self.mode_manager.is_paused:
                    self.mode_manager.toggle_pause(force_state=True)
                    self._show_tray_message(APP_NAME, f"Game Mode: Tracking auto-paused for {proc}")

            # Privacy Password Field Shield
            if getattr(self.settings.privacy, "auto_hide_passwords", True):
                pw_keywords = ("password", "login", "credential", "keepass", "bitwarden", "1password", "authenticator")
                if any(kw in title for kw in pw_keywords):
                    self.keyboard_overlay.clear_last_typed()
        else:
            self.telemetry["foreground_app"] = "DESKTOP"

    def set_active(self, active: bool, hide_window: bool = False):
        """Turns Pointer V ON or OFF."""
        self.is_active = active
        self.telemetry["is_active"] = active
        self.main_window.set_system_active(active)
        self._update_tray_visuals()

        if active:
            self.sound.lock()
            if hide_window:
                self.main_window.hide()
            self.cursor_overlay.show()
            if self.settings.overlay.preview_visible:
                self.camera_overlay.show()
            self.tray.showMessage(
                f"{APP_NAME} Engaged",
                "Webcam hand control is active. Press Ctrl+Alt+T anytime to toggle.",
                QSystemTrayIcon.Information,
                2000,
            )
        else:
            self.sound.unlock()
            self.emergency_release_all()
            self.cursor_overlay.hide()
            self.camera_overlay.hide()
            self._update_keyboard_visibility(False)

    def _update_keyboard_visibility(self, visible: bool):
        if visible and self.is_active:
            self.keyboard_overlay.animate_show()
            from PySide6.QtCore import QRect
            self.camera_overlay.dodge_rect(QRect(self.keyboard_overlay.pos(), self.keyboard_overlay.size()))
            self.cursor_overlay.hide()
        else:
            self.keyboard_overlay.animate_hide()
            self.keyboard_out.release_all_modifiers()
            if self.is_active and self.mode_manager.mode == AppMode.POINTER:
                self.cursor_overlay.show()

    def restart_as_admin(self):
        """Relaunches Pointer V with elevated Administrator privileges."""
        import ctypes
        if sys.platform.startswith("win"):
            try:
                exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
                args = "" if getattr(sys, "frozen", False) else f'"{os.path.abspath(sys.argv[0])}"'
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
                self.shutdown()
            except Exception as e:
                self.logger.error(f"Failed to elevate to Administrator: {e}")

    def _show_tray_message(self, title: str, message: str):
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 2000)

    def _on_settings_reloaded(self):
        self._apply_filter_profile()
        self.target_bounds = self.mouse.get_target_bounds(
            getattr(self.settings.monitors, "monitor_index", -1)
        )
        self.camera_overlay.setWindowOpacity(self.settings.overlay.preview_opacity)
        self.keyboard_overlay.setWindowOpacity(self.settings.keyboard.opacity)
        self.keyboard_overlay._recalculate_window_size()

    def _on_camera_device_changed(self, idx: int, name: str):
        self.camera.change_camera(idx, name)

    def _on_fps_cap_changed(self, fps: int):
        self.camera.set_target_fps(fps)

    def _on_monitor_changed(self, mon_idx: int):
        self.target_bounds = self.mouse.get_target_bounds(mon_idx)

    def _processing_loop(self):
        """Continuous low-latency frame ingestion and vision/keyboard execution thread."""
        frame_count = 0
        fps_start = time.perf_counter()

        while self.running:
            try:
                loop_start = time.perf_counter()

                # Stage 1: Camera capture
                t_cap_start = time.perf_counter()
                frame, ts = self.camera.get_frame()
                t_cap_ms = (time.perf_counter() - t_cap_start) * 1000.0

                if frame is None:
                    time.sleep(0.005)
                    continue

                self.total_frames += 1

                # Stage 2: MediaPipe inference
                t_inf_start = time.perf_counter()
                hand = self.tracker.process_frame(frame, ts)
                t_inf_ms = (time.perf_counter() - t_inf_start) * 1000.0

                if hand is not None:
                    self.frames_with_hand += 1
                    # Auto-resume if tracking was previously paused due to hand absence
                    if self.was_auto_paused and self.mode_manager.is_paused:
                        self.mode_manager.toggle_pause(force_state=False)
                        self.was_auto_paused = False
                        self.sound.lock()
                        self.signals.tray_notification_requested.emit(APP_NAME, "Hand detected: Tracking resumed")
                        self._update_tray_visuals()

                infer_ms = t_inf_ms

                # Record landmarks if developer recording is active
                if self.recorder.is_recording:
                    self.recorder.record_frame(hand)

                # Stage 3: Gesture Evaluation
                t_gest_start = time.perf_counter()
                current_mode_name = self.mode_manager.mode.value
                eval_res = self.gesture_engine.process(
                    hand=hand,
                    screen_bounds=self.target_bounds,
                    filter_2d=self.filter,
                    current_mode=current_mode_name,
                )
                t_gest_ms = (time.perf_counter() - t_gest_start) * 1000.0

                action = eval_res["action"]

                # Input arbitration check: Detect physical touchpad/mouse movement
                is_yielding = self.mouse.check_physical_move(
                    threshold_px=getattr(self.settings.gestures, "yield_distance_px", 6),
                    yield_duration_s=getattr(self.settings.gestures, "yield_duration_s", 1.5),
                )
                if is_yielding:
                    eval_res["status_text"] = "YIELDING to touchpad"

                # Check safety timeout for held brush lock (max 30s)
                if self.mouse.check_brush_lock_timeout(
                    max_duration_s=getattr(self.settings.gestures, "max_brush_lock_s", 30.0)
                ):
                    self.gesture_engine.brush_locked = False
                    eval_res["brush_locked"] = False
                    self.sound.warning()
                    self.signals.tray_notification_requested.emit(
                        APP_NAME, "Safety: Brush lock auto-released (30s max hold)."
                    )

                # Handle Auto-pause on hand lost
                if action == GestureAction.AUTO_PAUSE.value and not self.mode_manager.is_paused:
                    self.was_auto_paused = True
                    self.mode_manager.toggle_pause(force_state=True)
                    self.emergency_release_all()
                    self.signals.tray_notification_requested.emit(
                        APP_NAME, f"Auto-paused: No hand seen for {int(self.settings.gestures.auto_pause_timeout_s)}s"
                    )

                # Handle Pause Toggle Gesture (Closed Fist 1.5s)
                if action == GestureAction.PAUSE_TOGGLE.value:
                    self.mode_manager.toggle_pause()
                    self.emergency_release_all()
                    self.sound.warning()
                    self.signals.tray_notification_requested.emit(
                        APP_NAME, "Tracking Paused (Closed Fist Gesture)"
                    )

                # Handle Mode Transitions
                if action == GestureAction.ENTER_KEYBOARD.value and self.mode_manager.mode != AppMode.KEYBOARD:
                    self.mode_manager.mode = AppMode.KEYBOARD
                    self._update_keyboard_visibility(True)
                    self.sound.mode_change()
                elif action == GestureAction.EXIT_KEYBOARD.value and self.mode_manager.mode == AppMode.KEYBOARD:
                    self.mode_manager.mode = AppMode.POINTER
                    self._update_keyboard_visibility(False)
                    self.sound.unlock()

                # Safety release on tracking lost or pause
                if not eval_res["hand_visible"] or self.mode_manager.is_paused:
                    self.emergency_release_all()

                # 2. KEYBOARD MODE PROCESSING
                bounce_triggered = False
                curls_dict = {}

                if self.mode_manager.mode == AppMode.KEYBOARD and self.is_active and not self.mode_manager.is_paused:
                    tapped_finger, is_repeat, curls_dict = self.finger_tap_detector.process(hand)
                    cur_window = self.mode_manager.get_current_window()

                    if tapped_finger is not None:
                        t_dispatch_start = time.perf_counter()
                        if tapped_finger == "thumb":
                            self.keyboard_out.send_key("space", char_to_send=" ")
                            self.signals.key_typed.emit("space", "Space")
                            self.sound.key_click()
                            log_input_event("space_tap", count=1, duration_ms=(time.perf_counter() - t_dispatch_start) * 1000.0)
                        else:
                            effective_hand = self.mode_manager.get_effective_handedness(hand)

                            # Deterministic slot mapping matching the 4 on-screen locked keys
                            if effective_hand == "Left":
                                hand_order = ["pinky", "ring", "middle", "index"]
                            else:
                                hand_order = ["index", "middle", "ring", "pinky"]

                            if self.settings.keyboard.finger_mapping == "reversed":
                                hand_order.reverse()

                            try:
                                key_slot = hand_order.index(tapped_finger)
                            except ValueError:
                                key_slot = 0

                            if 0 <= key_slot < len(cur_window.keys):
                                target_key = cur_window.keys[key_slot]
                                self.keyboard_out.send_key(
                                    key_code=target_key.code,
                                    char_to_send=target_key.char_to_send,
                                    needs_shift=target_key.needs_shift,
                                )
                                self.signals.key_typed.emit(target_key.code, target_key.label)
                                if is_repeat:
                                    self.sound.key_repeat()
                                else:
                                    self.sound.key_click()
                                log_input_event("key_tap", count=1, duration_ms=(time.perf_counter() - t_dispatch_start) * 1000.0)

                    # Sliding door navigation swipes
                    tap_in_progress = (tapped_finger is not None)
                    swipe_dir = self.mode_manager.evaluate_swipes(hand, tap_in_progress=tap_in_progress)

                    if swipe_dir in ("UP", "DOWN", "LEFT", "RIGHT", "CROSS_INTO_SYMBOLS", "CROSS_INTO_MAIN"):
                        self.sound.mode_change()
                    elif swipe_dir == "BOUNCE":
                        bounce_triggered = True
                        self.sound.warning()

                    # Send keyboard state update via Qt signal
                    self.signals.keyboard_updated.emit(
                        self.mode_manager.active_zone,
                        self.mode_manager.row_idx,
                        self.mode_manager.window_idx,
                        self.keyboard_out.modifiers,
                        bounce_triggered
                    )

                # Stage 4: Input Output Dispatch
                t_out_start = time.perf_counter()

                # POINTER MODE: Dispatch Mouse Events (if active, not paused, and not yielding)
                if self.is_active and self.mode_manager.mode == AppMode.POINTER and not self.mode_manager.is_paused:
                    cx = eval_res["cursor_x"]
                    cy = eval_res["cursor_y"]

                    can_move = (
                        eval_res["hand_visible"]
                        and eval_res.get("in_active_region", True)
                        and not is_yielding
                        and eval_res["pose"] in (PoseType.POINTING.value, PoseType.TWO_FINGER.value)
                        and action != GestureAction.PAUSE.value
                    )

                    if can_move:
                        self.mouse.move_to(cx, cy)

                    # Update cursor overlay via Qt signal
                    overlay_state = "NORMAL"
                    if not eval_res["hand_visible"]:
                        overlay_state = "LOST"
                    elif is_yielding:
                        overlay_state = "YIELDING"
                    elif eval_res["brush_locked"]:
                        overlay_state = "BRUSH_LOCKED"
                    elif action == GestureAction.SINGLE_CLICK.value:
                        overlay_state = "CLICK"
                    elif action == GestureAction.DOUBLE_CLICK.value:
                        overlay_state = "DOUBLE_CLICK"

                    right_click_prog = eval_res.get("right_click_progress", 0.0)
                    palm_prog = eval_res.get("open_palm_progress", 0.0)
                    fist_prog = eval_res.get("fist_pause_progress", 0.0)

                    hold_prog = max(right_click_prog, palm_prog, fist_prog)
                    hold_kind = (
                        "RIGHT_CLICK" if right_click_prog > 0.0
                        else ("KEYBOARD" if palm_prog > 0.0
                        else ("PAUSE" if fist_prog > 0.0 else ""))
                    )

                    self.signals.cursor_updated.emit(
                        cx, cy, overlay_state, eval_res["dwell_progress"], hold_prog, hold_kind
                    )

                    # Mouse input dispatches with Circuit Breaker
                    if not is_yielding and eval_res.get("in_active_region", True):
                        if action == GestureAction.SINGLE_CLICK.value:
                            tripped = self.mouse.record_click_and_check_breaker(False, cx, cy)
                            if tripped:
                                self.mode_manager.toggle_pause(force_state=True)
                                self.emergency_release_all()
                                self.sound.warning()
                                self.signals.tray_notification_requested.emit(
                                    APP_NAME, "Pointer V paused: possible click loop."
                                )
                            else:
                                self.mouse.click(cx, cy)
                                self.signals.click_animated.emit(False)
                                self.sound.key_click()
                                log_input_event("click_left", count=1)

                        elif action == GestureAction.DOUBLE_CLICK.value:
                            tripped = self.mouse.record_click_and_check_breaker(False, cx, cy)
                            if tripped:
                                self.mode_manager.toggle_pause(force_state=True)
                                self.emergency_release_all()
                                self.sound.warning()
                                self.signals.tray_notification_requested.emit(
                                    APP_NAME, "Pointer V paused: possible click loop."
                                )
                            else:
                                self.mouse.double_click(cx, cy)
                                self.signals.click_animated.emit(True)
                                self.sound.double_click()
                                log_input_event("double_click", count=1)

                        elif action == GestureAction.RIGHT_CLICK.value:
                            tripped = self.mouse.record_click_and_check_breaker(True, cx, cy)
                            if tripped:
                                self.mode_manager.toggle_pause(force_state=True)
                                self.emergency_release_all()
                                self.sound.warning()
                                self.signals.tray_notification_requested.emit(
                                    APP_NAME, "Pointer V paused: possible click loop."
                                )
                            else:
                                self.mouse.right_click(cx, cy)
                                self.sound.key_click()
                                log_input_event("click_right", count=1)

                        elif action == GestureAction.SCROLL.value:
                            delta = eval_res.get("scroll_delta", 0)
                            self.mouse.scroll(delta)

                        elif action == GestureAction.BRUSH_LOCK_TOGGLE.value:
                            self.mouse.left_down()
                            self.sound.lock()
                            log_input_event("brush_lock_down", count=1)

                        elif action == GestureAction.BRUSH_UNLOCK.value:
                            self.mouse.left_up()
                            self.sound.unlock()
                            log_input_event("brush_lock_up", count=1)

                t_out_ms = (time.perf_counter() - t_out_start) * 1000.0

                # Stage 5: Render HUD Visualization onto frame
                t_vis_start = time.perf_counter()
                vis_frame = draw_hud_landmarks(
                    frame_bgr=frame,
                    hand=hand,
                    active_region=self.settings.active_region,
                    status_text=eval_res["status_text"],
                    dwell_progress=eval_res["dwell_progress"],
                    brush_locked=eval_res["brush_locked"],
                    pause_progress=eval_res.get("fist_pause_progress", 0.0),
                    is_paused=self.mode_manager.is_paused,
                )
                thumb = cv2.resize(vis_frame, (360, 202), interpolation=cv2.INTER_AREA)
                self.latest_vis_frame = thumb
                if self.is_active and getattr(self.settings.overlay, "preview_visible", True):
                    self.signals.frame_updated.emit(thumb, self.telemetry["fps"])
                t_vis_ms = (time.perf_counter() - t_vis_start) * 1000.0

                # 3. Update Shared Telemetry
                cur_win = self.mode_manager.get_current_window()
                self.telemetry["raw_hand"] = hand
                self.telemetry["mode"] = self.mode_manager.mode.value
                self.telemetry["pose"] = eval_res["pose"]
                self.telemetry["action"] = eval_res["action"]
                self.telemetry["status_text"] = eval_res["status_text"]
                self.telemetry["brush_locked"] = eval_res["brush_locked"]
                self.telemetry["latency_ms"] = infer_ms
                self.telemetry["is_yielding"] = is_yielding
                self.telemetry["stage_timings"] = {
                    "capture_ms": round(t_cap_ms, 2),
                    "infer_ms": round(t_inf_ms, 2),
                    "gesture_ms": round(t_gest_ms, 2),
                    "output_ms": round(t_out_ms, 2),
                    "vis_ms": round(t_vis_ms, 2),
                }
                self.telemetry["kb_zone"] = self.mode_manager.active_zone.value
                self.telemetry["kb_row"] = self.mode_manager.row_idx
                self.telemetry["kb_win_keys"] = [k.label for k in cur_win.keys]
                self.telemetry["curls"] = curls_dict
                self.telemetry["finger_curls"] = eval_res.get("finger_curls", curls_dict)
                self.telemetry["keyboard_corner"] = getattr(self.settings.keyboard, "corner", "bottom-right")
                self.telemetry["keyboard_monitor"] = getattr(self.settings.keyboard, "monitor_mode", "active_window")
                self.telemetry["in_active_region"] = eval_res.get("in_active_region", True)
                self.telemetry["cursor_status_reason"] = eval_res.get("status_text", "")
                self.telemetry["is_active"] = self.is_active
                self.telemetry["is_paused"] = self.mode_manager.is_paused
                self.telemetry["camera_connected"] = self.camera.is_connected
                self.telemetry["is_low_light"] = self.camera.is_low_light
                self.telemetry["is_over_exposed"] = self.camera.is_over_exposed
                self.telemetry["camera_brightness"] = self.camera.avg_brightness
                self.telemetry["total_frames"] = self.total_frames
                self.telemetry["frames_with_hand"] = self.frames_with_hand
                self.telemetry["active_pos"] = (
                    round(hand.get(8).x, 3) if hand else 0.0,
                    round(hand.get(8).y, 3) if hand else 0.0
                )
                self.telemetry["screen_coords"] = (eval_res["cursor_x"], eval_res["cursor_y"])
                self.telemetry["mouse_sendinput_ret"] = self.mouse.last_sendinput_ret
                self.telemetry["mouse_sendinput_err"] = self.mouse.last_sendinput_err
                self.telemetry["mouse_last_action"] = self.mouse.last_action
                self.telemetry["key_sendinput_ret"] = self.keyboard_out.last_sendinput_ret
                self.telemetry["key_sendinput_err"] = self.keyboard_out.last_sendinput_err
                self.telemetry["key_last_action"] = self.keyboard_out.last_event_kind
                self.telemetry["internal_errors"] = list(self.internal_errors)

                # Measure FPS
                frame_count += 1
                elapsed = time.perf_counter() - fps_start
                if elapsed >= 1.0:
                    self.telemetry["fps"] = frame_count / elapsed
                    frame_count = 0
                    fps_start = time.perf_counter()

                # Intelligent Frame Pacing: Battery Saver throttles ONLY after 5s of no hand
                frame_time = time.perf_counter() - loop_start
                is_idle_5s = (time.perf_counter() - self.gesture_engine.last_hand_time) > 5.0
                if self.settings.battery_saver and is_idle_5s:
                    target_fps = 15
                    self.telemetry["fps_throttle_reason"] = "Battery Saver (5s no hand)"
                else:
                    target_fps = self.settings.target_fps
                    self.telemetry["fps_throttle_reason"] = "Full Speed (Active)"

                target_time = 1.0 / max(15, target_fps)
                sleep_time = target_time - frame_time
                if sleep_time > 0.001:
                    time.sleep(sleep_time)

            except Exception as e:
                # Log error safely without leaking data
                err_msg = f"{time.strftime('%H:%M:%S')} - {type(e).__name__}: {str(e)[:60]}"
                self.internal_errors.append(err_msg)
                self.logger.error(f"Error in vision processing worker: {e}")
                time.sleep(0.02)

    def shutdown(self):
        """Clean resource shutdown with guaranteed release of held inputs and no hanging threads."""
        if not getattr(self, "running", True):
            return
        self.running = False

        import faulthandler
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass

        if hasattr(self, "watchdog_timer"):
            self.watchdog_timer.stop()
        if hasattr(self, "fg_timer"):
            self.fg_timer.stop()

        self.emergency_release_all()

        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass

        self.camera.stop()
        self.tracker.close()

        if hasattr(self, "tray"):
            self.tray.hide()

        if hasattr(self, "cursor_overlay"):
            self.cursor_overlay.close()
        if hasattr(self, "camera_overlay"):
            self.camera_overlay.close()
        if hasattr(self, "keyboard_overlay"):
            self.keyboard_overlay.close()

        from overlay import restore_system_cursor
        restore_system_cursor()

        # Last-resort watchdog: force terminate process if alive after 3.0s
        watchdog = threading.Timer(3.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()

        self.app.quit()


def check_single_instance() -> Optional[int]:
    """Ensures only a single instance of Pointer V runs simultaneously."""
    if not sys.platform.startswith("win"):
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            return None
        return mutex
    except Exception:
        return 1


def main():
    mutex = check_single_instance()
    if mutex is None:
        print(f"[{APP_NAME}] Another instance is already running. Focusing running instance and exiting.")
        sys.exit(0)

    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    # Set Windows Per-Monitor DPI Awareness V2 at earliest startup step
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    pv_app = PointerVApp(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
