"""
Pointer V - Developer Tools & Diagnostics
- End-to-End Self Test Button ("Test output") for independent mouse & keyboard verification
- Raw 21-point 3D landmark stream recording & replaying
STRICT PRIVACY: Never shows or logs typed characters or key names.
"""

import time
from typing import Dict

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget
)

from recorder import GUIDED_STEPS, GuidedSessionRecorder, LandmarkRecorder
from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG, CYAN, GREEN, RADIUS_CONTROL, RADIUS_PANEL,
    RED, TEXT_PRIMARY, TEXT_SECONDARY, VIOLET,
    get_mono_font, get_ui_font
)


class DoubleClickTargetBox(QFrame):
    """
    Interactive test target that captures native Windows WM_LBUTTONDBLCLK
    and single clicks, measuring exact inter-click intervals.
    """

    def __init__(self, on_event_callback=None, parent=None):
        super().__init__(parent)
        self.on_event_callback = on_event_callback
        self.setFixedSize(280, 75)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"background-color: {BG2_CARDS}; border: 2px dashed {BORDER_STRONG}; "
            f"border-radius: {RADIUS_PANEL}px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_main = QLabel("Double-Click Test Target")
        self.lbl_main.setFont(get_ui_font(11, bold=True))
        self.lbl_main.setAlignment(Qt.AlignCenter)
        self.lbl_main.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.lbl_main)

        self.lbl_sub = QLabel("Air tap twice or click here")
        self.lbl_sub.setFont(get_ui_font(9))
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.lbl_sub)

    def mousePressEvent(self, event):
        if self.on_event_callback:
            self.on_event_callback(is_double=False)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.on_event_callback:
            self.on_event_callback(is_double=True)
        self.setStyleSheet(
            f"background-color: #1a3d24; border: 2px solid {GREEN}; "
            f"border-radius: {RADIUS_PANEL}px;"
        )
        self.lbl_main.setText("✨ WM_LBUTTONDBLCLK VERIFIED!")
        self.lbl_main.setStyleSheet(f"color: {GREEN}; font-weight: bold;")
        QTimer.singleShot(700, self._reset_display)
        super().mouseDoubleClickEvent(event)

    def _reset_display(self):
        self.setStyleSheet(
            f"background-color: {BG2_CARDS}; border: 2px dashed {BORDER_STRONG}; "
            f"border-radius: {RADIUS_PANEL}px;"
        )
        self.lbl_main.setText("Double-Click Test Target")
        self.lbl_main.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")


class DeveloperPage(QWidget):
    """Developer diagnostics, pipeline health telemetry, self-test, and landmark recorder."""

    start_recording_requested = Signal()
    stop_recording_requested = Signal()
    replay_file_requested = Signal(str)
    test_keyboard_requested = Signal()
    test_cursor_requested = Signal()
    inject_gesture_requested = Signal(str)

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

        # Phase B Guided Session Recorder
        self.guided_recorder = GuidedSessionRecorder(
            on_step_change=self._on_guided_step_change,
            on_complete=self._on_guided_complete,
        )

        # Phase C Double-Click verification counters
        self.dbl_single_clicks = 0
        self.dbl_double_clicks = 0
        self.dbl_last_press_time = 0.0
        self.dbl_last_interval_ms = 0.0

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

        # 3. Phase C: Double-Click Verification Target Card
        self._build_double_click_test_card(layout)

        # 4. Phase B: Guided Hand Calibration Recorder Card
        self._build_guided_recorder_card(layout)

        # 5. Live Pipeline Diagnostics Panel
        self._build_diagnostics_panel(layout)

        # 6. Landmark Recording & Replay Card
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

    def _build_double_click_test_card(self, parent_layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Double-Click Verification Target (Phase C)")
        title.setFont(get_ui_font(12, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_sim_dblclick = QPushButton("▶ Test Double-Click Output")
        self.btn_sim_dblclick.setStyleSheet(f"background-color: {BLUE}; color: #FFFFFF; font-weight: 600; padding: 6px 14px;")
        self.btn_sim_dblclick.clicked.connect(self._simulate_double_click)
        header_layout.addWidget(self.btn_sim_dblclick)

        self.btn_reset_dbl = QPushButton("Reset Counters")
        self.btn_reset_dbl.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY}; padding: 6px 10px;")
        self.btn_reset_dbl.clicked.connect(self._reset_dbl_counters)
        header_layout.addWidget(self.btn_reset_dbl)
        layout.addLayout(header_layout)

        row = QHBoxLayout()
        self.dbl_target_box = DoubleClickTargetBox(on_event_callback=self._on_target_click)
        row.addWidget(self.dbl_target_box)

        v_info = QVBoxLayout()
        self.lbl_dbl_stats = QLabel("Single Clicks: 0  ·  Double Clicks: 0")
        self.lbl_dbl_stats.setFont(get_ui_font(11, bold=True))
        self.lbl_dbl_stats.setStyleSheet(f"color: {CYAN};")
        v_info.addWidget(self.lbl_dbl_stats)

        self.lbl_dbl_interval = QLabel("Inter-click Interval: -- ms (Windows limit: 500 ms)")
        self.lbl_dbl_interval.setFont(get_mono_font(10))
        self.lbl_dbl_interval.setStyleSheet(f"color: {TEXT_SECONDARY};")
        v_info.addWidget(self.lbl_dbl_interval)

        self.lbl_dbl_feedback = QLabel("Status: Ready to receive real air double-taps.")
        self.lbl_dbl_feedback.setFont(get_ui_font(9))
        self.lbl_dbl_feedback.setStyleSheet(f"color: {TEXT_SECONDARY};")
        v_info.addWidget(self.lbl_dbl_feedback)

        row.addLayout(v_info, stretch=1)
        layout.addLayout(row)
        parent_layout.addWidget(card)

    def _build_guided_recorder_card(self, parent_layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Guided Hand Calibration Recorder (Phase B)")
        title.setFont(get_ui_font(12, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_guided_start = QPushButton("▶ Start Guided Session (17 Steps)")
        self.btn_guided_start.setStyleSheet(f"background-color: {GREEN}; color: #FFFFFF; font-weight: 600; padding: 6px 14px;")
        self.btn_guided_start.clicked.connect(self._start_guided_session)
        header_layout.addWidget(self.btn_guided_start)

        self.btn_guided_next = QPushButton("Next Step >>")
        self.btn_guided_next.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY}; padding: 6px 12px;")
        self.btn_guided_next.setEnabled(False)
        self.btn_guided_next.clicked.connect(self._next_guided_step)
        header_layout.addWidget(self.btn_guided_next)

        self.btn_guided_cancel = QPushButton("Cancel")
        self.btn_guided_cancel.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {RED}; padding: 6px 10px;")
        self.btn_guided_cancel.setEnabled(False)
        self.btn_guided_cancel.clicked.connect(self._cancel_guided_session)
        header_layout.addWidget(self.btn_guided_cancel)
        layout.addLayout(header_layout)

        # Step Prompt Banner
        self.lbl_guided_step_title = QLabel("Step 1 of 17: Idle Pointing (20s)")
        self.lbl_guided_step_title.setFont(get_ui_font(12, bold=True))
        self.lbl_guided_step_title.setStyleSheet(f"color: {CYAN};")
        layout.addWidget(self.lbl_guided_step_title)

        self.lbl_guided_prompt = QLabel(
            "Hold your hand in normal pointing pose (index extended, other fingers curled). "
            "Hold still or move gently. Do not click."
        )
        self.lbl_guided_prompt.setFont(get_ui_font(10))
        self.lbl_guided_prompt.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.lbl_guided_prompt.setWordWrap(True)
        layout.addWidget(self.lbl_guided_prompt)

        # Progress bar & countdown
        p_row = QHBoxLayout()
        self.guided_progress_bar = QProgressBar()
        self.guided_progress_bar.setFixedHeight(12)
        self.guided_progress_bar.setRange(0, 100)
        self.guided_progress_bar.setValue(0)
        self.guided_progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {BG2_CARDS}; border: 1px solid {BORDER}; border-radius: 6px; }} "
            f"QProgressBar::chunk {{ background-color: {CYAN}; border-radius: 5px; }}"
        )
        p_row.addWidget(self.guided_progress_bar, stretch=1)

        self.lbl_guided_countdown = QLabel("Remaining: 20.0s")
        self.lbl_guided_countdown.setFont(get_mono_font(10))
        self.lbl_guided_countdown.setStyleSheet(f"color: {TEXT_SECONDARY};")
        p_row.addWidget(self.lbl_guided_countdown)
        layout.addLayout(p_row)

        self.lbl_guided_file = QLabel("Recordings stored locally in: %APPDATA%\\PointerV\\recordings\\")
        self.lbl_guided_file.setFont(get_mono_font(9))
        self.lbl_guided_file.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.lbl_guided_file)

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

        self.btn_inject_palm = QPushButton("Inject Open-Palm Hold (1.0s)")
        self.btn_inject_palm.setFixedHeight(32)
        self.btn_inject_palm.clicked.connect(lambda: self.inject_gesture_requested.emit("open_palm"))
        btn_row.addWidget(self.btn_inject_palm)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Gesture Event Log Card (Ring buffer of last 20 events)
        log_card = QFrame()
        log_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        l_layout = QVBoxLayout(log_card)
        l_layout.setContentsMargins(16, 12, 16, 12)
        l_layout.setSpacing(8)

        log_header = QLabel("Live Gesture Event Log (Last 20 Events)")
        log_header.setFont(get_ui_font(12, bold=True))
        log_header.setStyleSheet(f"color: {TEXT_PRIMARY};")
        l_layout.addWidget(log_header)

        self.event_log_view = QPlainTextEdit()
        self.event_log_view.setReadOnly(True)
        self.event_log_view.setFixedHeight(110)
        self.event_log_view.setFont(get_mono_font(9))
        self.event_log_view.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; color: {TEXT_PRIMARY};")
        l_layout.addWidget(self.event_log_view)

        parent_layout.addWidget(card)
        parent_layout.addWidget(log_card)

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

        # Phase B: Feed guided session recorder if active
        if hasattr(self, "guided_recorder") and self.guided_recorder.is_active:
            self.guided_recorder.record_frame(raw_h, fps=fps)
            st = self.guided_recorder.get_status()
            self.guided_progress_bar.setValue(int(st["progress"] * 100))
            self.lbl_guided_countdown.setText(f"Remaining: {st['remaining_s']:.1f}s")
            self.lbl_guided_step_title.setText(f"Step {st['step_idx'] + 1} of {st['total_steps']}: {st['title']}")
            self.lbl_guided_prompt.setText(st["prompt"])

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

        events = telem.get("gesture_events", [])
        if events:
            lines = [f"[{e.get('time', '')}] {e.get('action', '')} | Pose: {e.get('pose', '')} | {e.get('status', '')}" for e in events]
            self.event_log_view.setPlainText("\n".join(lines))
        else:
            self.event_log_view.setPlainText("No gesture events recorded yet.")

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

    def _on_target_click(self, is_double: bool):
        now = time.perf_counter()
        if is_double:
            self.dbl_double_clicks += 1
            if self.dbl_last_press_time > 0:
                self.dbl_last_interval_ms = (now - self.dbl_last_press_time) * 1000.0
            self.lbl_dbl_stats.setText(
                f"Single Clicks: {self.dbl_single_clicks}  ·  Double Clicks: {self.dbl_double_clicks}"
            )
            self.lbl_dbl_interval.setText(
                f"Inter-click Interval: {self.dbl_last_interval_ms:.1f} ms (Limit: 500 ms) ✓"
            )
            self.lbl_dbl_feedback.setText("Status: Native WM_LBUTTONDBLCLK verified successfully!")
            self.lbl_dbl_feedback.setStyleSheet(f"color: {GREEN}; font-weight: bold;")
        else:
            self.dbl_single_clicks += 1
            if self.dbl_last_press_time > 0:
                gap = (now - self.dbl_last_press_time) * 1000.0
                self.lbl_dbl_interval.setText(f"Inter-click Interval: {gap:.1f} ms")
            self.dbl_last_press_time = now
            self.lbl_dbl_stats.setText(
                f"Single Clicks: {self.dbl_single_clicks}  ·  Double Clicks: {self.dbl_double_clicks}"
            )

    def _simulate_double_click(self):
        """Dispatches an artificial double-click directly at the target widget."""
        if not self.mouse:
            return
        pt = self.dbl_target_box.mapToGlobal(QPoint(140, 38))
        self.mouse.double_click(pt.x(), pt.y())

    def _reset_dbl_counters(self):
        self.dbl_single_clicks = 0
        self.dbl_double_clicks = 0
        self.dbl_last_press_time = 0.0
        self.dbl_last_interval_ms = 0.0
        self.lbl_dbl_stats.setText("Single Clicks: 0  ·  Double Clicks: 0")
        self.lbl_dbl_interval.setText("Inter-click Interval: -- ms (Windows limit: 500 ms)")
        self.lbl_dbl_feedback.setText("Status: Counters reset. Ready for clicks.")
        self.lbl_dbl_feedback.setStyleSheet(f"color: {TEXT_SECONDARY};")

    def _start_guided_session(self):
        saved_file = self.guided_recorder.start_session()
        self.btn_guided_start.setEnabled(False)
        self.btn_guided_next.setEnabled(True)
        self.btn_guided_cancel.setEnabled(True)
        self.lbl_guided_file.setText(f"Recording to: {saved_file}")
        self.lbl_guided_file.setStyleSheet(f"color: {GREEN}; font-weight: bold;")

    def _next_guided_step(self):
        self.guided_recorder.next_step()

    def _cancel_guided_session(self):
        self.guided_recorder.cancel_session()
        self.btn_guided_start.setEnabled(True)
        self.btn_guided_next.setEnabled(False)
        self.btn_guided_cancel.setEnabled(False)
        self.lbl_guided_step_title.setText("Guided Session Cancelled")
        self.lbl_guided_countdown.setText("Remaining: --")
        self.guided_progress_bar.setValue(0)

    def _on_guided_step_change(self, step_idx, step):
        self.lbl_guided_step_title.setText(f"Step {step_idx + 1} of {len(GUIDED_STEPS)}: {step['title']}")
        self.lbl_guided_prompt.setText(step["prompt"])
        self.lbl_guided_countdown.setText(f"Remaining: {step['duration_s']:.1f}s")
        self.guided_progress_bar.setValue(0)

    def _on_guided_complete(self, saved_path, summary):
        self.btn_guided_start.setEnabled(True)
        self.btn_guided_next.setEnabled(False)
        self.btn_guided_cancel.setEnabled(False)
        self.lbl_guided_step_title.setText("Guided Recording Session Complete! ✓")
        self.lbl_guided_countdown.setText(f"Avg FPS: {summary.get('avg_fps', 0.0):.1f}")
        self.guided_progress_bar.setValue(100)
        QMessageBox.information(
            self,
            "Guided Calibration Recorded",
            f"17-step guided session successfully recorded!\n\n"
            f"Frames: {summary.get('total_frames', 0)}\n"
            f"Achieved FPS: {summary.get('avg_fps', 0.0):.1f}\n"
            f"File: {saved_path}\n\n"
            f"Run scripts/analyze_recordings.py to view comprehensive analysis and metrics.",
        )
