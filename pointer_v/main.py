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
import traceback
from pathlib import Path
from typing import Optional


def _install_startup_safety():
    """Top-level exception hook that intercepts unhandled startup exceptions,

    logs them to %APPDATA%\\PointerV\\logs\\startup.log, and shows a friendly error dialog.
    """
    def _handle_exception(exc_type, exc_value, exc_tb):
        try:
            appdata = os.environ.get("APPDATA")
            log_dir = Path(appdata) / "PointerV" / "logs" if appdata else Path.home() / ".pointerv" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "startup.log"
            tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNHANDLED STARTUP EXCEPTION:\n{tb_str}\n")
        except Exception:
            pass

        try:
            if sys.platform.startswith("win"):
                msg = (
                    f"Pointer V encountered a problem during startup:\n\n"
                    f"{exc_type.__name__}: {exc_value}\n\n"
                    f"A detailed error log has been saved to:\n%APPDATA%\\PointerV\\logs\\startup.log\n\n"
                    f"Please check your system drivers or copy the log details."
                )
                ctypes.windll.user32.MessageBoxW(0, msg, "Pointer V - Startup Error", 0x10)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception


_install_startup_safety()

import argparse
import subprocess
import cv2
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from camera import CameraStream, draw_hud_landmarks
from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine, PoseType
from hotkeys import (
    Win32HotKeyManager, MOD_CONTROL, MOD_ALT, MOD_SHIFT,
    VK_T, VK_K, VK_S, VK_P, VK_SPACE, VK_ESCAPE,
    HOTKEY_ID_TOGGLE, HOTKEY_ID_KEYBOARD, HOTKEY_ID_ZONE,
    HOTKEY_ID_PAINT, HOTKEY_ID_PAUSE, HOTKEY_ID_ESC, HOTKEY_ID_PANIC
)
from instrumentation import MetricsCollector, set_collector
from keyboard_layout import KeyboardLayoutManager
from keyboard_out import Win32KeyboardOutput
from keyboard_ui import FloatingAirKeyboardWidget
from logger import log_input_event, setup_logger
from mode_manager import AppMode, ModeManager
from mouse import MouseController
from overlay import CursorOverlayWindow
from preview import CameraPreviewOverlay
from recorder import LandmarkRecorder
from scenario_generator import SyntheticScenarioGenerator
from settings import SettingsManager
from sound import SoundManager
from tracker import HandTracker
from ui.main_window import MainWindow
from version import (
    APP_NAME, MUTEX_NAME, __version__
)


def configure_process_priority_and_power():
    """Sets ABOVE_NORMAL_PRIORITY_CLASS and disables Windows 11 EcoQoS PowerThrottling."""
    if not sys.platform.startswith("win"):
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetCurrentProcess()
        # ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
        kernel32.SetPriorityClass(handle, 0x00008000)

        # Disable ProcessPowerThrottling (Windows 11 EcoQoS)
        class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
            _fields_ = [
                ("Version", ctypes.c_uint32),
                ("ControlMask", ctypes.c_uint32),
                ("StateMask", ctypes.c_uint32),
            ]
        throttle = PROCESS_POWER_THROTTLING_STATE()
        throttle.Version = 1
        throttle.ControlMask = 0x1
        throttle.StateMask = 0
        kernel32.SetProcessInformation(
            handle,
            4, # ProcessPowerThrottling
            ctypes.byref(throttle),
            ctypes.sizeof(throttle)
        )
    except Exception:
        pass


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
    keyboard_visibility_requested = Signal(bool)
    tray_visuals_requested = Signal()


class PointerVApp(QObject):
    """Coordinates hardware capture, gesture tracking, overlays, mouse input, and air keyboard."""

    def __init__(
        self,
        app: QApplication,
        args: Optional[argparse.Namespace] = None,
        **kwargs
    ):
        super().__init__()
        self.app = app

        if args is None:
            class _DefaultArgs:
                pass
            args = _DefaultArgs()
            args.selftest = kwargs.get("is_selftest", False)
            args.debug = kwargs.get("is_debug", False)
            args.autostart = kwargs.get("autostart", False)
            args.inject = kwargs.get("inject_path", None)
            args.safe_sink = kwargs.get("safe_sink", False)
            args.no_overlay = kwargs.get("no_overlay", False)
            args.no_keyboard_hud = kwargs.get("no_keyboard_hud", False)
            args.no_preview = kwargs.get("no_preview", False)
            args.no_hooks = kwargs.get("no_hooks", False)
            args.no_output = kwargs.get("no_output", False)
            args.no_gestures = kwargs.get("no_gestures", False)
            args.no_ui_frames = kwargs.get("no_ui_frames", False)
            args.no_sound = kwargs.get("no_sound", False)
            args.no_battery_saver = kwargs.get("no_battery_saver", False)

        self.args = args
        self.is_selftest = getattr(args, "selftest", False)
        self.is_debug = getattr(args, "debug", False)
        self.inject_path = getattr(args, "inject", None)
        self.safe_sink = getattr(args, "safe_sink", False)
        self.no_overlay = getattr(args, "no_overlay", False)
        self.no_keyboard_hud = getattr(args, "no_keyboard_hud", False)
        self.no_preview = getattr(args, "no_preview", False)
        self.no_hooks = getattr(args, "no_hooks", False)
        self.no_output = getattr(args, "no_output", False)
        self.no_gestures = getattr(args, "no_gestures", False)
        self.no_ui_frames = getattr(args, "no_ui_frames", False)
        self.no_sound = getattr(args, "no_sound", False)
        self.no_battery_saver = getattr(args, "no_battery_saver", False)

        self.logger = setup_logger()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.config
        self.ui_heartbeat_timestamp = time.perf_counter()
        self._stall_guard_tripped = False
        self.gesture_event_log = collections.deque(maxlen=20)
        self.pause_reason = ""
        self.synthetic_injected_hand = None
        self.main_window_needs_camera = False

        if self.no_sound:
            self.settings.sound_enabled = False

        configure_process_priority_and_power()

        # 1. Hardware & Mouse Subsystems
        self.mouse = MouseController(safe_sink=self.safe_sink)
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
        self.keyboard_out = Win32KeyboardOutput(safe_sink=self.safe_sink)
        self.finger_tap_detector = FingerTapDetector(self.settings)
        self.mode_manager = ModeManager(self.settings, self.layout_manager)

        # Developer stream recorder
        self.recorder = LandmarkRecorder()

        # Audio feedback manager
        self.sound = SoundManager(self.settings)

        # Synthetic Scenario Generator (if inject requested)
        if self.inject_path:
            self.scenario_gen = SyntheticScenarioGenerator(
                scenario_name=self.inject_path,
                target_fps=self.settings.target_fps,
            )
        else:
            self.scenario_gen = None

        # Threaded Camera Capture (lazy start when needed)
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
        self.signals.keyboard_visibility_requested.connect(self._update_keyboard_visibility)
        self.signals.tray_visuals_requested.connect(self._update_tray_visuals)

        # Master Mode Toggle
        self.is_active = False
        self.paint_profile_active = False
        self.was_auto_paused = False
        self.total_frames = 0
        self.frames_with_hand = 0
        self.internal_errors = collections.deque(maxlen=5)
        self.selftest_passed = False

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
        self.main_window.inject_gesture_requested.connect(self.inject_gesture)
        self.main_window.calibration_active_changed.connect(
            lambda active: setattr(self.gesture_engine, "suppress_keyboard_trigger", active)
        )
        self.main_window.camera_needed.connect(self._on_camera_needed)

        # Performance & Freeze Instrumentation
        self.signal_counts = collections.defaultdict(int)
        self.metrics_collector = MetricsCollector(
            is_debug=self.is_debug,
            get_telemetry_fn=lambda: self.telemetry,
            get_signal_counts_fn=lambda: dict(self.signal_counts),
        )
        set_collector(self.metrics_collector)
        self.metrics_collector.start()

        # UI Thread Heartbeat (50ms)
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.setInterval(50)
        self.heartbeat_timer.timeout.connect(self._ui_heartbeat_tick)
        self.heartbeat_timer.start()

        # External Watchdog Guard Process
        self.watchdog_guard_proc = None
        if not self.is_selftest and sys.platform.startswith("win"):
            try:
                guard_script = Path(__file__).resolve().parent.parent / "scripts" / "watchdog_guard.py"
                if guard_script.exists():
                    self.watchdog_guard_proc = subprocess.Popen(
                        [sys.executable, str(guard_script), "--pid", str(os.getpid())],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except Exception as e:
                self.logger.warning(f"Could not spawn watchdog guard process: {e}")

        # 6. System Tray Integration
        self._setup_tray()

        # 7. Global Hotkeys via native Win32
        self.hotkey_manager = None
        self._setup_hotkeys()

        # 8. Register Emergency atexit handler
        atexit.register(self.emergency_release_all)

        # 9. Camera Lifecycle (Only started when active or on camera/calibration pages)
        # Note: Do not start on launch if inactive! Keeps camera LED OFF.
        if getattr(args, "autostart", False):
            self.set_active(True)
        else:
            self._update_camera_state()

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

        if self.is_selftest:
            self._run_selftest_sequence()
        elif self.inject_path:
            QTimer.singleShot(1000, lambda: self.inject_gesture(self.inject_path))

    def _get_tray_icon(self) -> QIcon:
        """Selects tray icon matching current mode and paused state."""
        base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
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
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(47, 123, 255) if self.is_active else QColor(100, 116, 139))
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
        action_test_kb = QAction("Test Air Keyboard", self)
        action_test_kb.triggered.connect(self._toggle_keyboard_mode)
        menu.addAction(action_test_kb)

        action_test_cursor = QAction("Test Cursor Overlay", self)
        action_test_cursor.triggered.connect(self.cursor_overlay.start_test_animation)
        menu.addAction(action_test_cursor)

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
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.main_window.showNormal()
            self.main_window.activateWindow()

    def _toggle_from_tray(self):
        self.set_active(not self.is_active)

    def _toggle_pause(self):
        new_paused = self.mode_manager.toggle_pause()
        if new_paused:
            self.emergency_release_all()
            self.sound.warning()
            self.tray.showMessage(APP_NAME, "Tracking Paused (Output suppressed)", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.sound.lock()
            self.tray.showMessage(APP_NAME, "Tracking Resumed", QSystemTrayIcon.MessageIcon.Information, 1500)
        self._update_tray_visuals()

    def _toggle_keyboard_mode(self):
        new_active = self.mode_manager.toggle_keyboard_mode()
        self.signals.keyboard_visibility_requested.emit(new_active)
        self._update_tray_visuals()

    def _ui_heartbeat_tick(self):
        """Pet the watchdog timer from the UI main thread. Touches heartbeat timestamp."""
        self.ui_heartbeat_timestamp = time.perf_counter()

    def _handle_toggle_active(self, active: bool, hide_window: bool):
        self.set_active(active, hide_window=hide_window)

    def _setup_hotkeys(self):
        if self.no_hooks:
            self.logger.info("Hotkeys disabled via --no-hooks flag.")
            return

        try:
            hwnd = int(self.main_window.winId())
            self.hotkey_manager = Win32HotKeyManager(hwnd)
            self.main_window.hotkey_manager = self.hotkey_manager

            # Ctrl+Alt+T: Toggle Pointer V ON / OFF
            self.hotkey_manager.register(
                HOTKEY_ID_TOGGLE,
                MOD_CONTROL | MOD_ALT,
                VK_T,
                lambda: self.signals.toggle_active_requested.emit(not self.is_active, True)
            )
            # Ctrl+Alt+K: Toggle Air Keyboard
            self.hotkey_manager.register(
                HOTKEY_ID_KEYBOARD,
                MOD_CONTROL | MOD_ALT,
                VK_K,
                lambda: QTimer.singleShot(0, self._toggle_keyboard_mode)
            )
            # Ctrl+Alt+S: Toggle Keyboard Zone
            self.hotkey_manager.register(
                HOTKEY_ID_ZONE,
                MOD_CONTROL | MOD_ALT,
                VK_S,
                lambda: QTimer.singleShot(0, self._toggle_keyboard_zone)
            )
            # Ctrl+Alt+P: Toggle Paint Mode
            self.hotkey_manager.register(
                HOTKEY_ID_PAINT,
                MOD_CONTROL | MOD_ALT,
                VK_P,
                lambda: QTimer.singleShot(0, self._toggle_paint_mode)
            )
            # Ctrl+Alt+Space: Toggle Pause
            self.hotkey_manager.register(
                HOTKEY_ID_PAUSE,
                MOD_CONTROL | MOD_ALT,
                VK_SPACE,
                lambda: QTimer.singleShot(0, self._toggle_pause)
            )
            # Esc: Emergency unlock / dismiss
            self.hotkey_manager.register(
                HOTKEY_ID_ESC,
                0,
                VK_ESCAPE,
                lambda: QTimer.singleShot(0, self._emergency_unlock)
            )
            # Ctrl+Alt+Shift+Esc: Panic killswitch
            self.hotkey_manager.register(
                HOTKEY_ID_PANIC,
                MOD_CONTROL | MOD_ALT | MOD_SHIFT,
                VK_ESCAPE,
                self._panic_disengage
            )
        except Exception as e:
            self.logger.warning(f"Could not bind native Win32 hotkeys: {e}")

    def _panic_disengage(self):
        """Panic hotkey (Ctrl+Alt+Shift+Esc): immediately releases inputs, stops tracking and turns OFF."""
        self.logger.critical("[PANIC HOTKEY] Emergency disengaged by user via Ctrl+Alt+Shift+Esc!")
        self.emergency_release_all()
        self.signals.toggle_active_requested.emit(False, False)
        self.sound.warning()

    def _on_camera_needed(self, needed: bool):
        self.main_window_needs_camera = needed
        self._update_camera_state()

    def _update_camera_state(self):
        """Ensures camera hardware is ONLY open when actively needed, keeping LED OFF otherwise."""
        if self.is_selftest or self.scenario_gen is not None:
            return
        should_run = (
            self.is_active
            or self.main_window_needs_camera
            or (getattr(self.settings.overlay, "preview_visible", False) and self.main_window.isVisible())
        )
        if should_run:
            if not self.camera.running:
                self.camera.start()
        else:
            if self.camera.running:
                self.camera.stop()

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
        except Exception:
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
        self._update_camera_state()

        if active:
            self.sound.lock()
            if hide_window:
                self.main_window.hide()
            if not self.no_overlay:
                self.cursor_overlay.show()
            if self.settings.overlay.preview_visible and not self.no_preview:
                self.camera_overlay.show()
            self.tray.showMessage(
                f"{APP_NAME} Engaged",
                "Webcam hand control is active. Press Ctrl+Alt+T anytime to toggle.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        else:
            self.sound.unlock()
            self.emergency_release_all()
            self.cursor_overlay.hide()
            self.camera_overlay.hide()
            self._update_keyboard_visibility(False)

    def _update_keyboard_visibility(self, visible: bool):
        if self.no_keyboard_hud:
            return
        self.logger.info(f"[Breadcrumb] keyboard window show requested: {visible}")
        if visible and self.is_active:
            self.keyboard_overlay.animate_show()
            self.logger.info("[Breadcrumb] keyboard shown")
            from PySide6.QtCore import QRect
            self.camera_overlay.dodge_rect(QRect(self.keyboard_overlay.pos(), self.keyboard_overlay.size()))
            self.cursor_overlay.hide()
        else:
            self.keyboard_overlay.animate_hide()
            self.keyboard_out.release_all_modifiers()
            if self.is_active and self.mode_manager.mode == AppMode.POINTER and not self.no_overlay:
                self.cursor_overlay.show()

    def inject_gesture(self, gesture_name: str):
        """Injects synthetic gesture frames into vision pipeline for testing."""
        from recorder import create_synthetic_hand
        if gesture_name == "open_palm":
            h = create_synthetic_hand(
                index_curl_angle=170.0,
                middle_curl_angle=170.0,
                ring_curl_angle=170.0,
                pinky_curl_angle=170.0,
                thumb_curl=0.0
            )
            self.synthetic_injected_hand = h
            QTimer.singleShot(1200, lambda: setattr(self, "synthetic_injected_hand", None))
        elif gesture_name == "fist":
            h = create_synthetic_hand(
                index_curl_angle=70.0,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )
            self.synthetic_injected_hand = h
            QTimer.singleShot(1200, lambda: setattr(self, "synthetic_injected_hand", None))
        elif gesture_name == "pointing":
            h = create_synthetic_hand(
                index_curl_angle=170.0,
                middle_curl_angle=70.0,
                ring_curl_angle=70.0,
                pinky_curl_angle=70.0,
                thumb_curl=1.0
            )
            self.synthetic_injected_hand = h
            QTimer.singleShot(1200, lambda: setattr(self, "synthetic_injected_hand", None))

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
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)

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

                # If camera is not running and not injecting, sleep briefly to keep CPU near 0%
                if not self.camera.running and not self.scenario_gen:
                    time.sleep(0.02)
                    continue

                # Stage 1: Camera capture or Synthetic Ingestion
                t_cap_start = time.perf_counter()
                if self.scenario_gen is not None:
                    frame, ts, synth_hand = self.scenario_gen.next_frame()
                else:
                    frame, ts = self.camera.get_frame()
                    synth_hand = None
                t_cap_ms = (time.perf_counter() - t_cap_start) * 1000.0

                if frame is None:
                    time.sleep(0.005)
                    continue

                self.total_frames += 1

                # Stage 2: MediaPipe inference
                t_inf_start = time.perf_counter()
                if synth_hand is not None:
                    hand = synth_hand
                elif self.synthetic_injected_hand is not None:
                    hand = self.synthetic_injected_hand
                else:
                    hand = self.tracker.process_frame(frame, ts)
                t_inf_ms = (time.perf_counter() - t_inf_start) * 1000.0

                if hand is not None:
                    self.frames_with_hand += 1
                    curls_dict = self.finger_tap_detector.compute_curls(hand)
                    self.telemetry["curls"] = curls_dict
                    # Auto-resume if tracking was previously paused due to hand absence
                    if self.was_auto_paused and self.mode_manager.is_paused:
                        self.mode_manager.toggle_pause(force_state=False)
                        self.was_auto_paused = False
                        self.pause_reason = ""
                        self.sound.lock()
                        self.signals.tray_notification_requested.emit(APP_NAME, "Hand detected: Tracking resumed")
                        self.signals.tray_visuals_requested.emit()

                # Watchdog Stall Guard: Emergency release if UI thread heartbeat stalls > 3.0s
                if time.perf_counter() - self.ui_heartbeat_timestamp > 3.0:
                    if not self._stall_guard_tripped:
                        self._stall_guard_tripped = True
                        self.emergency_release_all()
                        self.logger.error("[STALL GUARD] UI thread heartbeat stalled > 3.0s! Emergency released all inputs.")
                else:
                    self._stall_guard_tripped = False

                infer_ms = t_inf_ms

                # Record landmarks if developer recording is active
                if self.recorder.is_recording:
                    self.recorder.record_frame(hand)

                # Stage 3: Gesture Evaluation
                if self.no_gestures:
                    eval_res = {
                        "action": GestureAction.NONE.value,
                        "pose": "UNKNOWN",
                        "status_text": "GESTURES_DISABLED",
                        "hand_visible": hand is not None,
                        "cursor_x": 0,
                        "cursor_y": 0,
                        "dwell_progress": 0.0,
                        "brush_locked": False,
                    }
                    t_gest_ms = 0.0
                else:
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

                if action not in (GestureAction.NONE.value, GestureAction.MOVE.value):
                    self.gesture_event_log.append({
                        "time": time.strftime("%H:%M:%S"),
                        "action": action,
                        "pose": eval_res.get("pose", "UNKNOWN"),
                        "status": eval_res.get("status_text", "")
                    })

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
                    self.pause_reason = "no hand"
                    self.mode_manager.toggle_pause(force_state=True)
                    self.emergency_release_all()
                    self.signals.tray_notification_requested.emit(
                        APP_NAME, f"Auto-paused: No hand seen for {int(self.settings.gestures.auto_pause_timeout_s)}s"
                    )

                # Handle Pause Toggle Gesture (Closed Fist 1.5s)
                if action == GestureAction.PAUSE_TOGGLE.value:
                    self.mode_manager.toggle_pause()
                    self.pause_reason = "closed fist gesture" if self.mode_manager.is_paused else ""
                    self.emergency_release_all()
                    self.sound.warning()
                    self.signals.tray_notification_requested.emit(
                        APP_NAME, "Tracking Paused (Closed Fist Gesture)"
                    )

                # Handle Mode Transitions via Queued Qt Signals to UI thread
                if action == GestureAction.ENTER_KEYBOARD.value and self.mode_manager.mode != AppMode.KEYBOARD:
                    self.mode_manager.mode = AppMode.KEYBOARD
                    self.logger.info("[Breadcrumb] Palm hold complete -> mode change to KEYBOARD")
                    self.signals.keyboard_visibility_requested.emit(True)
                    self.sound.mode_change()
                elif action == GestureAction.EXIT_KEYBOARD.value and self.mode_manager.mode == AppMode.KEYBOARD:
                    self.mode_manager.mode = AppMode.POINTER
                    self.logger.info("[Breadcrumb] Fist hold complete -> mode change to POINTER")
                    self.signals.keyboard_visibility_requested.emit(False)
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

                    if tapped_finger is not None and not self.no_output:
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
                    if not self.no_keyboard_hud:
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

                    if can_move and not self.no_output:
                        self.mouse.move_to(cx, cy)

                    # Update cursor overlay via Qt signal
                    if not self.no_overlay:
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
                    if not is_yielding and eval_res.get("in_active_region", True) and not self.no_output:
                        if action == GestureAction.SINGLE_CLICK.value:
                            tripped = self.mouse.record_click_and_check_breaker(False, cx, cy)
                            if tripped:
                                self.pause_reason = "circuit breaker"
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
                                self.pause_reason = "circuit breaker"
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
                                self.pause_reason = "circuit breaker"
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
                if not self.no_ui_frames and self.is_active and getattr(self.settings.overlay, "preview_visible", True):
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
                self.telemetry["pause_reason"] = self.pause_reason
                self.telemetry["gesture_events"] = list(self.gesture_event_log)
                self.telemetry["click_mode"] = getattr(self.settings.gestures, "click_mode", "left_only")

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
                if self.settings.battery_saver and not self.no_battery_saver and is_idle_5s:
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

        if getattr(self, "watchdog_guard_proc", None):
            try:
                self.watchdog_guard_proc.terminate()
            except Exception:
                pass
            self.watchdog_guard_proc = None

        if hasattr(self, "metrics_collector"):
            self.metrics_collector.stop()

        if hasattr(self, "hotkey_manager") and self.hotkey_manager:
            try:
                self.hotkey_manager.unregister_all()
            except Exception:
                pass

        if hasattr(self, "heartbeat_timer"):
            self.heartbeat_timer.stop()
        if hasattr(self, "fg_timer"):
            self.fg_timer.stop()

        self.emergency_release_all()

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
        watchdog = threading.Timer(3.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()

        self.app.quit()


    def _run_selftest_sequence(self):
        """Executes automated startup validation for CI and build gates.

        Confirms UI event loop, model loading, and overlay initialization,
        then writes PASS/FAIL to %APPDATA%\\PointerV\\logs\\selftest.log and exits.
        """
        self.logger.info("Executing Pointer V automated startup self-test...")

        def _verify():
            try:
                model_loaded = getattr(self.tracker, "is_loaded", False)
                load_error = getattr(self.tracker, "load_error", None)
                ui_active = bool(self.main_window is not None)
                settings_ok = bool(self.settings is not None)
                overlay_ok = bool(getattr(self, "cursor_overlay", None) is not None)
                hud_ok = bool(getattr(self, "keyboard_overlay", None) is not None)

                passed = model_loaded and ui_active and settings_ok and overlay_ok and hud_ok
                status_text = "PASS" if passed else "FAIL"

                appdata = os.environ.get("APPDATA")
                log_dir = Path(appdata) / "PointerV" / "logs" if appdata else Path.home() / ".pointerv" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                selftest_log = log_dir / "selftest.log"

                report = (
                    f"[{status_text}] Pointer V Startup Self-Test Report\n"
                    f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Version: {__version__}\n"
                    f"UI Event Loop: Responsive\n"
                    f"Main Window: {'OK' if ui_active else 'FAIL'}\n"
                    f"Settings System: {'OK' if settings_ok else 'FAIL'}\n"
                    f"MediaPipe Model Loaded: {model_loaded} (details: {load_error or 'OK'})\n"
                    f"Cursor Overlay: {'OK' if overlay_ok else 'FAIL'}\n"
                    f"Corner Keyboard Window: {'OK' if hud_ok else 'FAIL'}\n"
                    f"Overall Result: {status_text}\n"
                )

                try:
                    with open(selftest_log, "w", encoding="utf-8") as f:
                        f.write(report)
                except Exception as e:
                    print(f"[SelfTest] Warning writing log: {e}")

                self.selftest_passed = passed
                print(report)
                self.shutdown()
                threading.Timer(1.0, lambda: os._exit(0 if passed else 1)).start()
            except Exception as e:
                import traceback
                print(f"[SelfTest] Verification error: {e}")
                traceback.print_exc()
                os._exit(1)

        QTimer.singleShot(4000, _verify)


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
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - Hand Gesture PC Controller")
    parser.add_argument("--selftest", action="store_true", help="Run automated startup self-test and exit")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging and diagnostics")
    parser.add_argument("--autostart", action="store_true", help="Start with pointer mode immediately ON")
    parser.add_argument("--inject", type=str, default=None, help="Inject synthetic hand frames (pointing_circle, pointing_still, open_palm_hold, index_taps, swipes, mixed)")
    parser.add_argument("--safe-sink", action="store_true", help="Bypass Win32 SendInput (log synthetic events only)")

    # Subsystem bisection flags
    parser.add_argument("--no-overlay", action="store_true", help="Disable cursor overlay window")
    parser.add_argument("--no-keyboard-hud", action="store_true", help="Disable floating keyboard overlay")
    parser.add_argument("--no-preview", action="store_true", help="Disable camera preview overlay")
    parser.add_argument("--no-hooks", action="store_true", help="Disable global OS hotkey hooks")
    parser.add_argument("--no-output", action="store_true", help="Disable all mouse and keyboard dispatch")
    parser.add_argument("--no-gestures", action="store_true", help="Disable gesture engine processing")
    parser.add_argument("--no-ui-frames", action="store_true", help="Disable emitting frame updates to UI")
    parser.add_argument("--no-sound", action="store_true", help="Mute all audio feedback")
    parser.add_argument("--no-battery-saver", action="store_true", help="Disable battery saver FPS throttling")

    args = parser.parse_args()

    if not args.selftest and not args.debug:
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

    pv_app = PointerVApp(app, args=args)
    ret = app.exec()
    if args.selftest:
        sys.exit(0 if getattr(pv_app, "selftest_passed", False) else 1)
    sys.exit(ret)


if __name__ == "__main__":
    main()
