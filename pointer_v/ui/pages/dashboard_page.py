"""
Pointer V - Dashboard Page
Clean pro interface:
- Modern ToggleSwitch for Pointer V ON/OFF
- Mode indicator
- Live camera thumbnail with hand skeleton
- High-level telemetry stats
- Last typed text strip (respecting privacy setting, with Clear button)
- Quick actions: Open Keyboard, Paint Mode, Pause Tracking, Launch Calibration
"""

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BORDER, BORDER_STRONG,
    CYAN, GREEN, RADIUS_CONTROL, RADIUS_PANEL, RED, TEXT_PRIMARY, TEXT_SECONDARY, VIOLET, get_mono_font, get_ui_font
)
from ui.widgets import ModeChip, ToggleSwitch


class DashboardPage(QWidget):
    """Primary operational dashboard."""

    toggle_pointer_requested = Signal(bool)
    toggle_keyboard_requested = Signal()
    toggle_paint_requested = Signal()
    toggle_pause_requested = Signal()
    calibrate_requested = Signal()
    clear_typed_requested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 1. Header Card: Power Toggle + Mode
        top_card = QFrame()
        top_card.setObjectName("PanelFrame")
        top_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(20, 16, 20, 16)

        title_box = QVBoxLayout()
        title_lbl = QLabel("Pointer V System")
        title_lbl.setFont(get_ui_font(16, bold=True))
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        tagline = QLabel("Control your PC in the air with one hand.")
        tagline.setFont(get_ui_font(11))
        tagline.setStyleSheet(f"color: {TEXT_SECONDARY};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(tagline)
        top_layout.addLayout(title_box)

        top_layout.addStretch()

        self.mode_chip = ModeChip("POINTER", parent=self)
        top_layout.addWidget(self.mode_chip)

        top_layout.addSpacing(16)

        self.power_toggle = ToggleSwitch(checked=False, parent=self)
        self.power_toggle.toggled.connect(self.toggle_pointer_requested.emit)
        top_layout.addWidget(self.power_toggle)

        layout.addWidget(top_card)

        # 1.5 Pipeline Status Strip
        self.pipeline_strip = QFrame()
        self.pipeline_strip.setStyleSheet(
            f"background-color: {BG2_CARDS}; border: 1px solid {BORDER}; border-radius: {RADIUS_CONTROL}px;"
        )
        strip_layout = QHBoxLayout(self.pipeline_strip)
        strip_layout.setContentsMargins(16, 8, 16, 8)
        strip_layout.setSpacing(16)

        self.strip_master = QLabel("Pipeline: STANDBY")
        self.strip_master.setFont(get_mono_font(10, bold=True))
        self.strip_master.setStyleSheet(f"color: {AMBER};")
        strip_layout.addWidget(self.strip_master)

        self.strip_hand = QLabel("Hand: None")
        self.strip_hand.setFont(get_mono_font(10))
        self.strip_hand.setStyleSheet(f"color: {TEXT_SECONDARY};")
        strip_layout.addWidget(self.strip_hand)

        self.strip_target = QLabel("Target: (--, --)")
        self.strip_target.setFont(get_mono_font(10))
        self.strip_target.setStyleSheet(f"color: {TEXT_SECONDARY};")
        strip_layout.addWidget(self.strip_target)

        self.strip_output = QLabel("SendInput: M-OK / K-OK")
        self.strip_output.setFont(get_mono_font(10))
        self.strip_output.setStyleSheet(f"color: {GREEN};")
        strip_layout.addWidget(self.strip_output)

        strip_layout.addStretch()
        layout.addWidget(self.pipeline_strip)

        # Top Warning Banner for Model Failure
        self.model_banner = QLabel("⚠ Hand Landmarker model failed to load. Check assets/models/hand_landmarker.task.")
        self.model_banner.setFixedHeight(30)
        self.model_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model_banner.setStyleSheet(f"background-color: #2D1515; color: {RED}; border: 1px solid rgba(240, 80, 110, 0.4); border-radius: {RADIUS_CONTROL}px; font-size: 11px; font-weight: 600; padding: 4px;")
        self.model_banner.hide()
        layout.addWidget(self.model_banner)

        # 1.6 First-Run Pipeline Checklist
        self.checklist_card = QFrame()
        self.checklist_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        chk_layout = QHBoxLayout(self.checklist_card)
        chk_layout.setContentsMargins(16, 10, 16, 10)
        chk_layout.setSpacing(14)

        chk_title = QLabel("Pipeline Checklist:")
        chk_title.setFont(get_ui_font(11, bold=True))
        chk_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        chk_layout.addWidget(chk_title)

        self.chk_1_cam = QLabel("1 Camera: --")
        self.chk_2_model = QLabel("2 Model: --")
        self.chk_3_hand = QLabel("3 Hand: --")
        self.chk_4_on = QLabel("4 Pointer V: OFF")
        self.chk_5_move = QLabel("5 Cursor: --")
        self.chk_6_kb = QLabel("6 Keyboard: Closed")

        for c in (self.chk_1_cam, self.chk_2_model, self.chk_3_hand, self.chk_4_on, self.chk_5_move, self.chk_6_kb):
            c.setFont(get_mono_font(10, bold=True))
            c.setStyleSheet(f"color: {TEXT_SECONDARY};")
            chk_layout.addWidget(c)

        chk_layout.addStretch()
        layout.addWidget(self.checklist_card)

        # 2. Main Grid: Left Video Preview, Right Telemetry & Actions
        grid = QGridLayout()
        grid.setSpacing(16)

        # Camera Thumbnail Card
        cam_card = QFrame()
        cam_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        cam_layout = QVBoxLayout(cam_card)
        cam_layout.setContentsMargins(16, 16, 16, 16)

        cam_title = QLabel("Live Camera Feed")
        cam_title.setFont(get_ui_font(13, bold=True))
        cam_title.setStyleSheet(f"color: {TEXT_PRIMARY}; margin-bottom: 8px;")
        cam_layout.addWidget(cam_title)

        self.video_label = QLabel()
        self.video_label.setFixedSize(400, 240)
        self.video_label.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS_CONTROL}px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_layout.addWidget(self.video_label)
        grid.addWidget(cam_card, 0, 0)

        # Telemetry & Quick Actions Card
        side_card = QFrame()
        side_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        side_layout = QVBoxLayout(side_card)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(10)

        stats_title = QLabel("Telemetry & Status")
        stats_title.setFont(get_ui_font(13, bold=True))
        stats_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        side_layout.addWidget(stats_title)

        self.lbl_fps = QLabel("FPS: --")
        self.lbl_latency = QLabel("Latency: -- ms")
        self.lbl_pose = QLabel("Hand Pose: Searching...")
        self.lbl_gesture = QLabel("Gesture: None")
        self.lbl_keyboard = QLabel("Keyboard: Zone [Main] · Row 4")
        self.lbl_click_mode = QLabel("Click Mode: Left clicks only")
        self.lbl_recent_events = QLabel("Recent Events: Listening...")
        self.lbl_recent_events.setWordWrap(True)

        for lbl in (self.lbl_fps, self.lbl_latency, self.lbl_pose, self.lbl_gesture, self.lbl_keyboard, self.lbl_click_mode, self.lbl_recent_events):
            lbl.setFont(get_mono_font(10))
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            side_layout.addWidget(lbl)

        side_layout.addSpacing(6)

        # Quick Actions
        actions_title = QLabel("Quick Actions")
        actions_title.setFont(get_ui_font(13, bold=True))
        actions_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        side_layout.addWidget(actions_title)

        btn_row = QHBoxLayout()
        btn_kb = QPushButton("Open Keyboard")
        btn_kb.clicked.connect(self.toggle_keyboard_requested.emit)
        btn_row.addWidget(btn_kb)

        btn_paint = QPushButton("Paint Mode")
        btn_paint.clicked.connect(self.toggle_paint_requested.emit)
        btn_row.addWidget(btn_paint)

        btn_pause = QPushButton("Pause Tracking")
        btn_pause.clicked.connect(self.toggle_pause_requested.emit)
        btn_row.addWidget(btn_pause)
        side_layout.addLayout(btn_row)

        btn_calib = QPushButton("Launch Calibration Wizard")
        btn_calib.clicked.connect(self.calibrate_requested.emit)
        side_layout.addWidget(btn_calib)

        side_layout.addStretch()
        grid.addWidget(side_card, 0, 1)

        layout.addLayout(grid)

        # 3. Last Typed History Strip
        self.typed_card = QFrame()
        self.typed_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        typed_layout = QHBoxLayout(self.typed_card)
        typed_layout.setContentsMargins(16, 12, 16, 12)

        lbl_typed_header = QLabel("Last Typed:")
        lbl_typed_header.setFont(get_ui_font(11, bold=True))
        lbl_typed_header.setStyleSheet(f"color: {TEXT_SECONDARY};")
        typed_layout.addWidget(lbl_typed_header)

        self.lbl_typed_stream = QLabel("Ready")
        self.lbl_typed_stream.setFont(get_mono_font(11))
        self.lbl_typed_stream.setStyleSheet(f"color: {TEXT_PRIMARY};")
        typed_layout.addWidget(self.lbl_typed_stream)

        typed_layout.addStretch()

        self.btn_clear_typed = QPushButton("Clear")
        self.btn_clear_typed.setFixedSize(60, 26)
        self.btn_clear_typed.clicked.connect(self.clear_typed_requested.emit)
        typed_layout.addWidget(self.btn_clear_typed)

        layout.addWidget(self.typed_card)
        layout.addStretch()

    def update_telemetry(self, telemetry: dict, frame_bgr=None):
        fps = telemetry.get("fps", 0.0)
        latency = telemetry.get("latency_ms", 0.0)
        pose = telemetry.get("pose", "UNKNOWN")
        status_text = telemetry.get("status_text", "NONE")
        kb_zone = telemetry.get("kb_zone", "MAIN")
        kb_row = telemetry.get("kb_row", 3)
        mode = telemetry.get("mode", "POINTER")
        is_paused = telemetry.get("is_paused", False)
        is_yielding = telemetry.get("is_yielding", "YIELDING" in status_text)

        is_active = telemetry.get("is_active", False)
        raw_hand = telemetry.get("raw_hand")
        handedness = getattr(raw_hand, "handedness", "") if raw_hand else ""
        hand_detected = raw_hand is not None
        scr_pos = telemetry.get("screen_coords", (0, 0))
        m_ret = telemetry.get("mouse_sendinput_ret", 1)
        k_ret = telemetry.get("key_sendinput_ret", 1)

        # Update status strip
        if not is_active:
            self.strip_master.setText("Pipeline: STANDBY (OFF)")
            self.strip_master.setStyleSheet(f"color: {AMBER};")
        elif is_paused:
            self.strip_master.setText("Pipeline: PAUSED")
            self.strip_master.setStyleSheet(f"color: {AMBER};")
        else:
            self.strip_master.setText("Pipeline: ACTIVE (ON)")
            self.strip_master.setStyleSheet(f"color: {GREEN};")

        # Model Load Status & Banner
        model_loaded = telemetry.get("model_loaded", True)
        model_error = telemetry.get("model_error")
        if not model_loaded:
            self.model_banner.setText(f"⚠ Hand model failed to load: {model_error or 'File not found'}. Tracking unavailable.")
            self.model_banner.show()
            self.chk_2_model.setText("2 Model: FAILED")
            self.chk_2_model.setStyleSheet(f"color: {RED};")
        else:
            self.model_banner.hide()
            self.chk_2_model.setText("2 Model: LOADED")
            self.chk_2_model.setStyleSheet(f"color: {GREEN};")

        if not model_loaded:
            self.strip_hand.setText("Hand: Model Offline")
            self.strip_hand.setStyleSheet(f"color: {RED};")
            self.strip_target.setText("Target: (--, --)")
        elif hand_detected:
            conf = int(telemetry.get("hand_confidence", 0.95) * 100)
            self.strip_hand.setText(f"Hand: {handedness or 'Detected'} ({conf}%)")
            self.strip_hand.setStyleSheet(f"color: {CYAN};")
            self.strip_target.setText(f"Target: ({scr_pos[0]}, {scr_pos[1]})")
        else:
            self.strip_hand.setText("Hand: Searching")
            self.strip_hand.setStyleSheet(f"color: {TEXT_SECONDARY};")
            self.strip_target.setText("Target: (--, --)")

        out_ok = (m_ret > 0 and k_ret > 0)
        self.strip_output.setText(f"SendInput: {'OK' if out_ok else 'WARN'}")
        self.strip_output.setStyleSheet(f"color: {GREEN if out_ok else RED};")

        # Update First-Run Pipeline Checklist
        cam_ok = telemetry.get("camera_connected", True)
        self.chk_1_cam.setText("1 Camera: OK" if cam_ok else "1 Camera: ERR")
        self.chk_1_cam.setStyleSheet(f"color: {GREEN if cam_ok else RED};")

        self.chk_3_hand.setText(f"3 Hand: {handedness or 'OK'}" if hand_detected else "3 Hand: Searching")
        self.chk_3_hand.setStyleSheet(f"color: {GREEN if hand_detected else TEXT_SECONDARY};")

        self.chk_4_on.setText("4 Pointer V: ON" if is_active else "4 Pointer V: OFF")
        self.chk_4_on.setStyleSheet(f"color: {GREEN if is_active else AMBER};")

        cursor_moving = (is_active and not is_paused and pose == "POINTING" and hand_detected)
        self.chk_5_move.setText("5 Cursor: MOVING" if cursor_moving else "5 Cursor: Standby")
        self.chk_5_move.setStyleSheet(f"color: {GREEN if cursor_moving else TEXT_SECONDARY};")

        kb_open = (mode == "KEYBOARD")
        self.chk_6_kb.setText("6 Keyboard: OPEN" if kb_open else "6 Keyboard: Closed")
        self.chk_6_kb.setStyleSheet(f"color: {VIOLET if kb_open else TEXT_SECONDARY};")

        self.lbl_fps.setText(f"FPS: {fps:.1f}")
        self.lbl_latency.setText(f"Latency: {latency:.1f} ms")
        self.lbl_pose.setText(f"Hand Pose: {pose}")
        self.lbl_gesture.setText(f"Gesture: {status_text}")
        self.lbl_keyboard.setText(f"Keyboard: Zone [{kb_zone}] · Row {kb_row + 1}")

        click_mode = telemetry.get("click_mode", "left_only")
        cm_text = "Off" if click_mode == "off" else ("Left clicks only" if click_mode == "left_only" else "All")
        self.lbl_click_mode.setText(f"Click Mode: {cm_text}")

        events = telemetry.get("gesture_events", [])
        if events:
            lines = [f"{e.get('time', '')} {e.get('action', '')} ({e.get('pose', '')})" for e in events[-2:]]
            self.lbl_recent_events.setText("Recent: " + " | ".join(lines))
        else:
            self.lbl_recent_events.setText("Recent: Listening...")

        self.mode_chip.set_status(
            mode,
            is_paused=is_paused,
            is_yielding=is_yielding,
            hand_visible=hand_detected,
            is_active=is_active,
        )

        # Privacy: Hide last typed strip if requested
        if getattr(self.settings.privacy, "hide_last_typed", False):
            self.typed_card.setVisible(False)
        else:
            self.typed_card.setVisible(True)

        # Update thumbnail (throttled to 10 Hz with fast transformation to protect UI thread)
        now = time.perf_counter()
        if not hasattr(self, "_last_thumb_time"):
            self._last_thumb_time = 0.0

        if frame_bgr is not None and (now - self._last_thumb_time >= 0.10) and self.isVisible():
            self._last_thumb_time = now
            h, w, ch = frame_bgr.shape
            rgb = frame_bgr[:, :, ::-1].copy()
            q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(q_img).scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
            )
            self.video_label.setPixmap(pix)

