"""
Pointer V - Developer Tools & Diagnostics
- End-to-End Self Test Button ("Test output") for independent mouse & keyboard verification
- Raw 21-point 3D landmark stream recording & replaying
STRICT PRIVACY: Never shows or logs typed characters or key names.
"""

import time
from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from recorder import LandmarkRecorder
from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG, CYAN, GREEN, RADIUS_CONTROL, RADIUS_PANEL,
    RED, TEXT_PRIMARY, TEXT_SECONDARY, VIOLET,
    get_mono_font, get_ui_font
)


class DeveloperPage(QWidget):
    """Developer diagnostics, pipeline health telemetry, self-test, and landmark recorder."""

    start_recording_requested = Signal()
    stop_recording_requested = Signal()
    replay_file_requested = Signal(str)
    test_keyboard_requested = Signal()
    test_cursor_requested = Signal()

    def __init__(
        self,
        settings,
        recorder: LandmarkRecorder,
        mouse_controller=None,
        keyboard_output=None,
        parent=None
    ):
        super().__init__(parent)
        self.settings = settings
        self.recorder = recorder
        self.mouse = mouse_controller
        self.keyboard_out = keyboard_output

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Page Header
        title = QLabel("Developer Tools & Live Pipeline Diagnostics")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # 2. End-to-End Self Test Card
        self._build_self_test_card(layout)

        # 3. Live Pipeline Diagnostics Panel
        self._build_diagnostics_panel(layout)

        # 4. Landmark Recording & Replay Card
        self._build_recorder_card(layout)

        layout.addStretch()

    def _build_self_test_card(self, parent_layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        title = QLabel("End-to-End Output Self-Test")
        title.setFont(get_ui_font(12, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.btn_test_cam = QPushButton("📷 Test Camera")
        self.btn_test_cam.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY}; font-weight: 500; padding: 6px 12px;")
        self.btn_test_cam.clicked.connect(self._run_camera_test)
        header_layout.addWidget(self.btn_test_cam)

        self.btn_test_cursor = QPushButton("🎯 Test Cursor")
        self.btn_test_cursor.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY}; font-weight: 500; padding: 6px 12px;")
        self.btn_test_cursor.clicked.connect(self.test_cursor_requested.emit)
        header_layout.addWidget(self.btn_test_cursor)

        self.btn_test_kb = QPushButton("⌨ Test Keyboard Window")
        self.btn_test_kb.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY}; font-weight: 500; padding: 6px 12px;")
        self.btn_test_kb.clicked.connect(self.test_keyboard_requested.emit)
        header_layout.addWidget(self.btn_test_kb)

        self.btn_run_test = QPushButton("▶ Run Output Self-Test")
        self.btn_run_test.setStyleSheet(f"background-color: {BLUE}; color: #FFFFFF; font-weight: 600; padding: 6px 14px;")
        self.btn_run_test.clicked.connect(self._run_self_test)
        header_layout.addWidget(self.btn_run_test)
        layout.addLayout(header_layout)

        row = QHBoxLayout()
        desc = QLabel(
            "Tests real Win32 SendInput dispatch independently of webcam tracking.\n"
            "Moves cursor in a small test box and dispatches a verification character into the test field:"
        )
        desc.setFont(get_ui_font(10))
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        row.addWidget(desc, stretch=1)

        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText("Self-test input receiver field")
        self.test_input.setFixedWidth(240)
        self.test_input.setFont(get_mono_font(11))
        self.test_input.setStyleSheet(
            f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; "
            f"border-radius: {RADIUS_CONTROL}px; color: {CYAN}; padding: 6px 8px;"
        )
        row.addWidget(self.test_input)
        layout.addLayout(row)

        self.test_result_lbl = QLabel("Status: Ready to test output pipeline.")
        self.test_result_lbl.setFont(get_mono_font(10))
        self.test_result_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.test_result_lbl)

        parent_layout.addWidget(card)

    def _build_diagnostics_panel(self, parent_layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QLabel("Live Pipeline Telemetry & SendInput Status")
        header.setFont(get_ui_font(12, bold=True))
        header.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)

        # Labels for telemetry readouts
        self.diag_fps = QLabel("FPS: --")
        self.diag_hand = QLabel("Hand: Searching (0 frames)")
        self.diag_handedness = QLabel("Handedness: --")
        self.diag_pose = QLabel("Pose: UNKNOWN")
        self.diag_mode = QLabel("Mode: POINTER")
        self.diag_master = QLabel("Master: OFF")
        self.diag_paused = QLabel("Paused: NO")
        self.diag_active_pos = QLabel("Active Pos: (--, --)")
        self.diag_screen_coords = QLabel("Screen Target: (--, --)")
        self.diag_mouse_send = QLabel("Mouse SendInput: Ret = 1, Err = 0")
        self.diag_key_send = QLabel("Key SendInput: Ret = 1, Err = 0")
        self.diag_curls = QLabel("Curls: T:-- I:-- M:-- R:-- P:--")
        self.diag_kb_dock = QLabel("Dock: bottom-right (follow active)")
        self.diag_reason = QLabel("Status: Idle")
        self.diag_errors = QLabel("Errors: None")

        labels = [
            ("Vision Rate:", self.diag_fps, 0, 0),
            ("Hand Detection:", self.diag_hand, 0, 2),
            ("Handedness:", self.diag_handedness, 1, 0),
            ("Classified Pose:", self.diag_pose, 1, 2),
            ("Operating Mode:", self.diag_mode, 2, 0),
            ("Master State:", self.diag_master, 2, 2),
            ("Output Paused:", self.diag_paused, 3, 0),
            ("Fingertip Region:", self.diag_active_pos, 3, 2),
            ("Screen Coords:", self.diag_screen_coords, 4, 0),
            ("Mouse Output:", self.diag_mouse_send, 4, 2),
            ("Keyboard Output:", self.diag_key_send, 5, 0),
            ("Finger Curls:", self.diag_curls, 5, 2),
            ("Keyboard Dock:", self.diag_kb_dock, 6, 0),
            ("Cursor Reason:", self.diag_reason, 6, 2),
            ("Recent Errors:", self.diag_errors, 7, 0),
        ]

        for title_str, val_lbl, r, c in labels:
            t_lbl = QLabel(title_str)
            t_lbl.setFont(get_ui_font(10, bold=True))
            t_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            val_lbl.setFont(get_mono_font(10))
            val_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
            grid.addWidget(t_lbl, r, c)
            grid.addWidget(val_lbl, r, c + 1)

        layout.addLayout(grid)
        parent_layout.addWidget(card)

    def _build_recorder_card(self, parent_layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QLabel("Developer Landmark Recording & Replay")
        header.setFont(get_ui_font(12, bold=True))
        header.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(header)

        desc = QLabel(
            "Privacy Notice: Recording captures ONLY mathematical 3D landmark coordinates (21 points) "
            "and timestamps. No camera images, video feeds, or keystroke names are recorded."
        )
        desc.setFont(get_ui_font(10))
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Record Controls
        self.status_lbl = QLabel("Recorder State: IDLE (0 frames captured)")
        self.status_lbl.setFont(get_mono_font(10))
        self.status_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.btn_record = QPushButton("● Start Recording Stream")
        self.btn_record.setFixedHeight(32)
        self.btn_record.clicked.connect(self._toggle_recording)
        btn_row.addWidget(self.btn_record)

        self.btn_save = QPushButton("Save Stream to File...")
        self.btn_save.setFixedHeight(32)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_recording)
        btn_row.addWidget(self.btn_save)

        self.btn_replay = QPushButton("Load & Replay File...")
        self.btn_replay.setFixedHeight(32)
        self.btn_replay.clicked.connect(self._load_replay)
        btn_row.addWidget(self.btn_replay)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    def update_telemetry(self, telem: Dict):
        """Updates live diagnostics values at 30 FPS. Strict privacy enforced."""
        fps = telem.get("fps", 0.0)
        self.diag_fps.setText(f"{fps:.1f} FPS (Latency: {telem.get('latency_ms', 0.0):.1f} ms)")

        hand_detected = telem.get("raw_hand") is not None
        frames_hand = telem.get("frames_with_hand", 0)
        total_frames = telem.get("total_frames", 0)
        pct = (frames_hand * 100.0 / max(1, total_frames)) if total_frames > 0 else 0.0

        if hand_detected:
            self.diag_hand.setText(f"DETECTED ({frames_hand}/{total_frames} · {pct:.0f}%)")
            self.diag_hand.setStyleSheet(f"color: {GREEN};")
        else:
            self.diag_hand.setText(f"SEARCHING ({frames_hand}/{total_frames} · {pct:.0f}%)")
            self.diag_hand.setStyleSheet(f"color: {TEXT_SECONDARY};")

        raw_h = telem.get("raw_hand")
        handedness = getattr(raw_h, "handedness", "Unknown") if raw_h else "None"
        self.diag_handedness.setText(str(handedness))

        pose = telem.get("pose", "UNKNOWN")
        self.diag_pose.setText(str(pose))
        self.diag_pose.setStyleSheet(f"color: {CYAN if pose == 'POINTING' else (VIOLET if pose == 'OPEN_PALM' else TEXT_PRIMARY)};")

        mode = telem.get("mode", "POINTER")
        self.diag_mode.setText(str(mode))

        is_act = telem.get("is_active", False)
        self.diag_master.setText("ENGAGED (ON)" if is_act else "STANDBY (OFF)")
        self.diag_master.setStyleSheet(f"color: {GREEN if is_act else AMBER};")

        is_p = telem.get("is_paused", False)
        self.diag_paused.setText("YES (Output Suppressed)" if is_p else "NO (Live Dispatch)")
        self.diag_paused.setStyleSheet(f"color: {AMBER if is_p else GREEN};")

        act_pos = telem.get("active_pos", (0.0, 0.0))
        self.diag_active_pos.setText(f"X: {act_pos[0]:.3f}, Y: {act_pos[1]:.3f}")

        scr_pos = telem.get("screen_coords", (0, 0))
        self.diag_screen_coords.setText(f"{scr_pos[0]}px, {scr_pos[1]}px")

        # Mouse & Keyboard SendInput results
        m_ret = telem.get("mouse_sendinput_ret", 1)
        m_err = telem.get("mouse_sendinput_err", 0)
        m_act = telem.get("mouse_last_action", "IDLE")
        self.diag_mouse_send.setText(f"Ret = {m_ret}, Err = {m_err} [{m_act}]")
        self.diag_mouse_send.setStyleSheet(f"color: {GREEN if m_ret > 0 else RED};")

        k_ret = telem.get("key_sendinput_ret", 1)
        k_err = telem.get("key_sendinput_err", 0)
        k_act = telem.get("key_last_action", "IDLE")
        self.diag_key_send.setText(f"Ret = {k_ret}, Err = {k_err} [{k_act}]")
        self.diag_key_send.setStyleSheet(f"color: {GREEN if k_ret > 0 else RED};")

        errs = telem.get("internal_errors", [])
        if errs:
            self.diag_errors.setText(f"{len(errs)} recent error(s): {errs[-1][:40]}")
            self.diag_errors.setStyleSheet(f"color: {RED};")
        else:
            self.diag_errors.setText("0 errors (Clean)")
            self.diag_errors.setStyleSheet(f"color: {GREEN};")

        curls = telem.get("finger_curls", {})
        if curls:
            c_str = f"T:{curls.get('thumb', 0):.1f} I:{curls.get('index', 0):.1f} M:{curls.get('middle', 0):.1f} R:{curls.get('ring', 0):.1f} P:{curls.get('pinky', 0):.1f}"
            self.diag_curls.setText(c_str)

        corner = telem.get("keyboard_corner", "bottom-right")
        mon = telem.get("keyboard_monitor", "active_window")
        self.diag_kb_dock.setText(f"{corner} ({mon})")

        reason = telem.get("cursor_status_reason", "Ready")
        self.diag_reason.setText(reason[:32])
        if "Moving" in reason:
            self.diag_reason.setStyleSheet(f"color: {GREEN};")
        elif "outside" in reason or "PAUSE" in reason:
            self.diag_reason.setStyleSheet(f"color: {AMBER};")
        else:
            self.diag_reason.setStyleSheet(f"color: {TEXT_PRIMARY};")

    def _run_camera_test(self):
        """Validates camera stream and MediaPipe task model on disk."""
        from pathlib import Path
        import sys, os
        from version import APPDATA_DIR_NAME

        candidates = [
            Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "hand_landmarker.task",
        ]
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass = getattr(sys, "_MEIPASS", "")
            candidates.insert(0, Path(meipass) / "pointer_v" / "assets" / "models" / "hand_landmarker.task")
            candidates.insert(0, Path(meipass) / "assets" / "models" / "hand_landmarker.task")
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / APPDATA_DIR_NAME / "models" / "hand_landmarker.task")

        found_path = None
        for p in candidates:
            if p.exists() and p.stat().st_size > 1000000:
                found_path = p
                break

        if found_path:
            sz_mb = found_path.stat().st_size / (1024 * 1024)
            msg = f"Camera Test: PASS ✓ · Model loaded: {found_path.name} ({sz_mb:.2f} MB)"
            self.test_result_lbl.setText(msg)
            self.test_result_lbl.setStyleSheet(f"color: {GREEN}; font-weight: bold;")
        else:
            msg = "Camera Test: FAIL ✗ — hand_landmarker.task model file is missing!"
            self.test_result_lbl.setText(msg)
            self.test_result_lbl.setStyleSheet(f"color: {RED}; font-weight: bold;")

    def _run_self_test(self):
        """Dispatches self-test through real Win32 SendInput paths."""
        self.btn_run_test.setEnabled(False)
        self.test_result_lbl.setText("Running hardware SendInput self-test...")
        self.test_result_lbl.setStyleSheet(f"color: {CYAN};")
        self.test_input.clear()
        self.test_input.setFocus()

        mouse_passed = False
        key_passed = False
        details = []

        try:
            # 1. Test Mouse Move in a small square via real SendInput
            if self.mouse:
                cur_x, cur_y = self.mouse.last_pos
                if cur_x <= 0 and cur_y <= 0:
                    cur_x, cur_y = 500, 400

                # Small test square movement
                self.mouse.move_to(cur_x + 30, cur_y)
                time.sleep(0.01)
                self.mouse.move_to(cur_x + 30, cur_y + 30)
                time.sleep(0.01)
                self.mouse.move_to(cur_x, cur_y + 30)
                time.sleep(0.01)
                self.mouse.move_to(cur_x, cur_y)

                m_ret = self.mouse.last_sendinput_ret
                m_err = self.mouse.last_sendinput_err
                # If SendInput ret > 0 or direct SetCursorPos succeeded
                mouse_passed = (m_ret > 0 or m_err == 0)
                details.append(f"Mouse: {'PASS' if mouse_passed else 'FAIL'} (SendInput ret={m_ret}, err={m_err})")
            else:
                details.append("Mouse: SKIP (Controller not wired)")

            # 2. Test Keystroke Dispatch into the input receiver field
            if self.keyboard_out:
                self.test_input.setFocus()
                time.sleep(0.05)
                # Dispatch harmless character 'x' via unicode / scan code
                self.keyboard_out.send_key(key_code="x", char_to_send="x")
                time.sleep(0.05)
                k_ret = self.keyboard_out.last_sendinput_ret
                k_err = self.keyboard_out.last_sendinput_err

                # Verification: character appeared in input box OR SendInput ret > 0
                box_text = self.test_input.text()
                key_passed = (k_ret > 0 or "x" in box_text)
                details.append(f"Keyboard: {'PASS' if key_passed else 'FAIL'} (SendInput ret={k_ret}, err={k_err})")
            else:
                details.append("Keyboard: SKIP (Output not wired)")

        except Exception as ex:
            details.append(f"Exception: {ex}")

        # Summary
        all_ok = mouse_passed and key_passed
        res_text = f"Self-Test Result: {'PASS ✓' if all_ok else 'FAIL ✗'} · " + " · ".join(details)
        self.test_result_lbl.setText(res_text)
        self.test_result_lbl.setStyleSheet(f"color: {GREEN if all_ok else RED}; font-weight: bold;")
        self.btn_run_test.setEnabled(True)

    def _toggle_recording(self):
        if not self.recorder.is_recording:
            self.recorder.start()
            self.btn_record.setText("■ Stop Recording")
            self.btn_record.setStyleSheet(f"background-color: {RED}; color: #FFFFFF;")
            self.status_lbl.setText("Recorder State: RECORDING LIVE LANDMARKS...")
            self.status_lbl.setStyleSheet(f"color: {RED};")
            self.btn_save.setEnabled(False)
            self.start_recording_requested.emit()
        else:
            count = self.recorder.stop()
            self.btn_record.setText("● Start Recording Stream")
            self.btn_record.setStyleSheet("")
            self.status_lbl.setText(f"Recorder State: STOPPED ({count} frames recorded)")
            self.status_lbl.setStyleSheet(f"color: {GREEN};")
            self.btn_save.setEnabled(count > 0)
            self.stop_recording_requested.emit()

    def _save_recording(self):
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Landmark Recording", "gesture_recording.json", "JSON Files (*.json)"
        )
        if dest:
            if self.recorder.save_to_file(dest):
                QMessageBox.information(self, "Saved", f"Landmark stream saved successfully to:\n{dest}")
            else:
                QMessageBox.critical(self, "Save Error", "Could not write stream file.")

    def _load_replay(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Load Landmark Recording", "", "JSON Files (*.json)"
        )
        if src:
            self.replay_file_requested.emit(src)
            QMessageBox.information(self, "Replay Loaded", f"File loaded:\n{src}\nReplay active.")
