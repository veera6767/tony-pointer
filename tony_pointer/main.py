"""
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

# Platform-specific sound feedback
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

        # Wire key typed feedback
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

        # 9. Foreground Window Inspector Timer (every 500ms)
        self.fg_timer = QTimer(self)
        self.fg_timer.timeout.connect(self._check_foreground_window)
        self.fg_timer.start(500)

        # Show main window or start minimized
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
        """Immediate safety release on pressing Esc."""
        if self.gesture_engine.brush_locked:
            self.gesture_engine.brush_locked = False
            self.mouse.emergency_release()
            play_sound(400, 100)

        # Also release any held keyboard modifiers/keys and return to POINTER mode
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
        """Auto-detects creative suites (Paint, Photoshop, Krita) and switches profile."""
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
        """Turns Tony Pointer Mode ON or OFF."""
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
            # Position keyboard horizontally centered near the bottom of primary screen
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
        """Continuous low-latency frame ingestion and gesture/keyboard execution thread."""
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

            # 1. Evaluate Poses & Mode Transitions
            current_mode_name = self.mode_manager.mode.value
            eval_res = self.gesture_engine.process(
                hand=hand,
                screen_bounds=self.screen_bounds,
                filter_2d=self.filter,
                current_mode=current_mode_name,
            )

            # Check mode change triggers (Open Palm hold -> Enter Keyboard, Fist/Pointing -> Exit Keyboard)
            action = eval_res["action"]
            if action == GestureAction.ENTER_KEYBOARD.value and self.mode_manager.mode != AppMode.KEYBOARD:
                self.mode_manager.mode = AppMode.KEYBOARD
                self._update_keyboard_visibility(True)
                play_sound(1300, 80)
            elif action == GestureAction.EXIT_KEYBOARD.value and self.mode_manager.mode == AppMode.KEYBOARD:
                self.mode_manager.mode = AppMode.POINTER
                self._update_keyboard_visibility(False)
                play_sound(600, 80)

            # 2. KEYBOARD MODE PROCESSING
            bounce_triggered = False
            curls_dict = {}

            if self.mode_manager.mode == AppMode.KEYBOARD and self.is_active:
                # Per-Finger Tap Detection
                tapped_finger, is_repeat, curls_dict = self.finger_tap_detector.process(hand)

                # Get currently locked 4-key window
                cur_window = self.mode_manager.get_current_window()

                if tapped_finger is not None:
                    if tapped_finger == "thumb":
                        # Thumb = Space bar
                        self.keyboard_out.send_key("space", char_to_send=" ")
                        self.key_typed_signal.emit("space", "Space")
                        play_sound(900, 25)
                    else:
                        # Map tapped finger (index, middle, ring, pinky) to 4-key window
                        # Default "visual order": leftmost finger on screen types Key 0
                        finger_names = ["index", "middle", "ring", "pinky"]
                        if hand is not None:
                            # Sort fingertip landmarks by screen X coordinate for true visual order
                            tip_indices = [8, 12, 16, 20] # index, middle, ring, pinky tips
                            # Pair (finger_name, tip_x)
                            finger_x_pairs = [(finger_names[i], hand.get(tip_indices[i]).x) for i in range(4)]
                            finger_x_pairs.sort(key=lambda p: p[1])
                            sorted_finger_names = [p[0] for p in finger_x_pairs]

                            if self.settings.keyboard.finger_mapping == "reversed":
                                sorted_finger_names.reverse()

                            # Find which slot (0..3) this tapped finger corresponds to
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

                # Whole-hand Swipes for Row / Window navigation ("sliding door")
                tap_in_progress = (tapped_finger is not None)
                swipe_dir = self.mode_manager.evaluate_swipes(hand, tap_in_progress=tap_in_progress)

                if swipe_dir in ("UP", "DOWN", "LEFT", "RIGHT", "CROSS_INTO_SYMBOLS", "CROSS_INTO_MAIN"):
                    play_sound(1000 if "CROSS" in swipe_dir else 850, 40)
                elif swipe_dir == "BOUNCE":
                    bounce_triggered = True
                    play_sound(450, 50)

                # Update Keyboard Window Visuals
                self.keyboard_overlay.update_state(
                    zone=self.mode_manager.active_zone,
                    row_idx=self.mode_manager.row_idx,
                    window_idx=self.mode_manager.window_idx,
                    modifiers=self.keyboard_out.modifiers,
                    bounce=bounce_triggered,
                )

            # 3. Update Telemetry Cache
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

            # 4. Render HUD visualization onto camera frame
            vis_frame = draw_hud_landmarks(
                frame_bgr=frame,
                hand=hand,
                active_region=self.settings.active_region,
                status_text=eval_res["status_text"],
                dwell_progress=eval_res["dwell_progress"],
                brush_locked=eval_res["brush_locked"],
            )
            self.latest_vis_frame = vis_frame

            # 5. POINTER MODE: Dispatch Mouse & Overlay actions
            if self.is_active and self.mode_manager.mode == AppMode.POINTER:
                cx = eval_res["cursor_x"]
                cy = eval_res["cursor_y"]

                # Move OS Mouse Cursor via Win32 SendInput
                if eval_res["hand_visible"] and action != GestureAction.PAUSE.value:
                    self.mouse.move_to(cx, cy)

                # Update Holographic Cursor Reticle Overlay
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

                # Clicks & Scroll Input Events
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

            # Update camera preview HUD
            if self.is_active and self.settings.overlay.preview_visible:
                self.camera_overlay.update_frame(vis_frame)

            # Measure FPS
            frame_count += 1
            elapsed = time.perf_counter() - fps_start
            if elapsed >= 1.0:
                self.telemetry["fps"] = frame_count / elapsed
                frame_count = 0
                fps_start = time.perf_counter()

            # Maintain target loop rate
            frame_time = time.perf_counter() - loop_start
            target_time = 1.0 / self.settings.target_fps
            sleep_time = target_time - frame_time
            if sleep_time > 0.001:
                time.sleep(sleep_time)

    def shutdown(self):
        """Clean resource shutdown."""
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
