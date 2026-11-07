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

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG,
    CYAN, GREEN, RADIUS_CONTROL, RADIUS_PANEL, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
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
        self.video_label.setAlignment(Qt.AlignCenter)
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

        for lbl in (self.lbl_fps, self.lbl_latency, self.lbl_pose, self.lbl_gesture, self.lbl_keyboard):
            lbl.setFont(get_mono_font(11))
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

        self.lbl_fps.setText(f"FPS: {fps:.1f}")
        self.lbl_latency.setText(f"Latency: {latency:.1f} ms")
        self.lbl_pose.setText(f"Hand Pose: {pose}")
        self.lbl_gesture.setText(f"Gesture: {status_text}")
        self.lbl_keyboard.setText(f"Keyboard: Zone [{kb_zone}] · Row {kb_row + 1}")
        self.mode_chip.set_status(mode, is_paused)

        # Privacy: Hide last typed strip if requested
        if getattr(self.settings.privacy, "hide_last_typed", False):
            self.typed_card.setVisible(False)
        else:
            self.typed_card.setVisible(True)

        # Update thumbnail
        if frame_bgr is not None:
            h, w, ch = frame_bgr.shape
            rgb = frame_bgr[:, :, ::-1].copy()
            q_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(q_img).scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.video_label.setPixmap(pix)

