"""
Tony Pointer - PySide6 Main Window & Calibration Studio
Stark Industries / JARVIS Holographic Sci-Fi UI.
Provides the master Arc-Reactor toggle, live landmark monitor, telemetry readouts,
interactive 4-corner screen calibration wizard, finger curl debug bars, and settings tabs.
"""

import math
import sys
import time
from typing import Callable, Dict, Optional

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Dark Iron-Man Holographic Stylesheet
HUD_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #07090e;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Plus Jakarta Sans', sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0b0f19;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #0d1322;
    color: #94a3b8;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border: 1px solid #1e293b;
    border-bottom: none;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #0b0f19;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-bottom: 1px solid #0b0f19;
}

QGroupBox {
    border: 1px solid #1e293b;
    border-radius: 6px;
    margin-top: 18px;
    padding-top: 12px;
    font-weight: 600;
    color: #00e5ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}

QLabel {
    color: #cbd5e1;
}

QPushButton {
    background-color: #0d1b2a;
    border: 1px solid #00e5ff;
    color: #00e5ff;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #00e5ff;
    color: #07090e;
}

QPushButton:pressed {
    background-color: #00b4d8;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #1e293b;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #00e5ff;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #00e5ff;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {
    background-color: #0d1322;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 4px 8px;
    color: #00e5ff;
}

QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid #00e5ff;
}

QProgressBar {
    border: 1px solid #1e293b;
    border-radius: 3px;
    background-color: #0d1322;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #00e5ff;
    border-radius: 2px;
}
"""


class ArcReactorButton(QPushButton):
    """Circular glowing Arc-Reactor master power button for Tony Pointer Mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.is_active = False
        self.pulse_phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._pulse)
        self.timer.start(30)

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def _pulse(self):
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * 3.14159)
        if self.is_active:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx, cy = 70.0, 70.0
        glow = math.sin(self.pulse_phase) * 0.3 + 0.7 if self.is_active else 0.4

        accent = QColor(0, 229, 255) if self.is_active else QColor(100, 116, 139)
        core_bg = QColor(0, 20, 30) if self.is_active else QColor(15, 23, 42)

        # Outer ring
        painter.setPen(QPen(accent, 2.5))
        painter.setBrush(core_bg)
        painter.drawEllipse(QPoint(int(cx), int(cy)), 64, 64)

        # Radial Arc-Reactor coils (10 segments)
        for i in range(10):
            angle = i * (360.0 / 10.0)
            rad = math.radians(angle)
            x1 = cx + math.cos(rad) * 44
            y1 = cy + math.sin(rad) * 44
            x2 = cx + math.cos(rad) * 58
            y2 = cy + math.sin(rad) * 58
            painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), int(180 * glow)), 3.0))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Inner Glowing Core
        painter.setPen(QPen(accent, 2.0))
        core_color = QColor(accent.red(), accent.green(), accent.blue(), int(120 * glow))
        painter.setBrush(core_color)
        painter.drawEllipse(QPoint(int(cx), int(cy)), 36, 36)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor(255, 255, 255) if self.is_active else QColor(148, 163, 184))
        text = "ACTIVE" if self.is_active else "ENGAGE"
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class CornerCalibrationDialog(QDialog):
    """
    Interactive Calibration Wizard:
    (a) 4 screen corners for active region mapping
    (b) Per-finger tap calibration (Index, Middle, Ring, Pinky, Thumb)
    (c) Swipe distance calibration
    """

    def __init__(self, settings, current_hand_fn, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.get_hand = current_hand_fn
        self.setWindowTitle("Tony Pointer Calibration Wizard")
        self.setFixedSize(580, 420)
        self.setStyleSheet(HUD_STYLESHEET)

        self.current_step = 0
        self.steps = [
            ("STEP 1 / 4: TOP-LEFT CORNER", "Point comfortably at the TOP-LEFT corner of your screen."),
            ("STEP 2 / 4: TOP-RIGHT CORNER", "Point comfortably at the TOP-RIGHT corner of your screen."),
            ("STEP 3 / 4: BOTTOM-RIGHT CORNER", "Point comfortably at the BOTTOM-RIGHT corner of your screen."),
            ("STEP 4 / 4: BOTTOM-LEFT CORNER", "Point comfortably at the BOTTOM-LEFT corner of your screen."),
        ]
        self.samples = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        self.title_lbl = QLabel(self.steps[0][0])
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e5ff;")
        layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(self.steps[0][1])
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("font-size: 13px; color: #94a3b8; margin-bottom: 12px;")
        layout.addWidget(self.desc_lbl)

        self.box_view = QLabel()
        self.box_view.setFixedHeight(160)
        self.box_view.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px;")
        self.box_view.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.box_view)

        self.coord_lbl = QLabel("Current Finger: Detecting...")
        self.coord_lbl.setStyleSheet("color: #ffb300; font-family: monospace;")
        layout.addWidget(self.coord_lbl)

        btn_layout = QHBoxLayout()
        self.capture_btn = QPushButton("Capture Calibration Point")
        self.capture_btn.setFixedHeight(36)
        self.capture_btn.clicked.connect(self._capture_step)
        btn_layout.addWidget(self.capture_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_poll)
        self.timer.start(50)

    def _update_poll(self):
        hand = self.get_hand()
        if hand:
            tip = hand.get(8)
            self.coord_lbl.setText(f"Normalized Position: X: {tip.x:.3f}, Y: {tip.y:.3f}")
        else:
            self.coord_lbl.setText("Normalized Position: Hand not in frame")

    def _capture_step(self):
        hand = self.get_hand()
        if not hand:
            QMessageBox.warning(self, "No Hand Detected", "Please keep your index finger in view of the webcam.")
            return

        tip = hand.get(8)
        self.samples.append((tip.x, tip.y))
        self.current_step += 1

        if self.current_step < 4:
            self.title_lbl.setText(self.steps[self.current_step][0])
            self.desc_lbl.setText(self.steps[self.current_step][1])
        else:
            xs = [pt[0] for pt in self.samples]
            ys = [pt[1] for pt in self.samples]

            x_min = max(0.05, min(xs))
            x_max = min(0.95, max(xs))
            y_min = max(0.05, min(ys))
            y_max = min(0.95, max(ys))

            self.settings.active_region.x_min = round(x_min, 3)
            self.settings.active_region.x_max = round(x_max, 3)
            self.settings.active_region.y_min = round(y_min, 3)
            self.settings.active_region.y_max = round(y_max, 3)

            QMessageBox.information(
                self,
                "Calibration Complete",
                f"Active Region successfully calibrated!\nX: [{x_min:.2f} .. {x_max:.2f}], Y: [{y_min:.2f} .. {y_max:.2f}]",
            )
            self.accept()


class MainWindow(QMainWindow):
    """Tony Pointer Main Holographic Window."""

    toggle_mode_requested = Signal(bool)
    settings_changed = Signal()

    def __init__(self, settings_manager, get_status_fn, get_frame_fn):
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings_manager.config
        self.get_status = get_status_fn
        self.get_frame = get_frame_fn

        self.setWindowTitle("Tony Pointer - Iron-Man Gesture PC Controller")
        self.setFixedSize(920, 740)
        self.setStyleSheet(HUD_STYLESHEET)

        self._build_ui()

        # Telemetry update timer
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._refresh_telemetry)
        self.telemetry_timer.start(33)  # 30 FPS UI refresh

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        # 1. Header Bar: Title + Master Power Toggle
        header_layout = QHBoxLayout()

        title_box = QVBoxLayout()
        main_title = QLabel("TONY POINTER")
        main_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #00e5ff; letter-spacing: 1px;")
        sub_title = QLabel("IRON-MAN HOLOGRAPHIC PC CONTROLLER · AIR KEYBOARD + WIN32 SENDINPUT")
        sub_title.setStyleSheet("font-size: 11px; color: #64748b; letter-spacing: 0.5px;")
        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        self.arc_button = ArcReactorButton(self)
        self.arc_button.clicked.connect(self._on_arc_clicked)
        header_layout.addWidget(self.arc_button)

        root_layout.addLayout(header_layout)

        # 2. Main Content Split: Left Video Feed, Right Telemetry & Quick Action
        split_layout = QHBoxLayout()

        # Video Preview Viewport
        video_group = QGroupBox("LIVE WEBCAM HUD")
        video_layout = QVBoxLayout(video_group)
        self.video_label = QLabel()
        self.video_label.setFixedSize(480, 280)
        self.video_label.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 4px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        video_layout.addWidget(self.video_label)
        split_layout.addWidget(video_group)

        # Right Telemetry Dashboard
        telemetry_group = QGroupBox("SYSTEM TELEMETRY & MODES")
        telemetry_layout = QVBoxLayout(telemetry_group)
        telemetry_layout.setSpacing(8)

        self.lbl_fps = QLabel("FPS: --")
        self.lbl_latency = QLabel("INFERENCE LATENCY: -- ms")
        self.lbl_mode = QLabel("OPERATING MODE: POINTER")
        self.lbl_pose = QLabel("HAND POSE: SEARCHING")
        self.lbl_action = QLabel("ACTIVE GESTURE: NONE")
        self.lbl_kb_status = QLabel("KEYBOARD: ZONE [MAIN] · ROW 4")
        self.lbl_brush = QLabel("BRUSH LOCK: OFF")
        self.lbl_brush.setStyleSheet("color: #64748b; font-weight: bold;")
        self.lbl_window = QLabel("FOREGROUND APP: --")

        for lbl in (
            self.lbl_fps, self.lbl_latency, self.lbl_mode, self.lbl_pose,
            self.lbl_action, self.lbl_kb_status, self.lbl_brush, self.lbl_window
        ):
            lbl.setStyleSheet("font-family: monospace; font-size: 11.5px; color: #00e5ff;")
            telemetry_layout.addWidget(lbl)

        # Live Finger Curl Bars
        curl_box = QVBoxLayout()
        curl_lbl = QLabel("LIVE FINGER CURL DEBUG:")
        curl_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; margin-top: 4px;")
        curl_box.addWidget(curl_lbl)

        self.curl_bars: Dict[str, QProgressBar] = {}
        for f in ("thumb", "index", "middle", "ring", "pinky"):
            row = QHBoxLayout()
            lbl = QLabel(f[:3].upper())
            lbl.setFixedWidth(28)
            lbl.setStyleSheet("font-size: 9px; font-family: monospace; color: #64748b;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(6)
            row.addWidget(lbl)
            row.addWidget(bar)
            curl_box.addLayout(row)
            self.curl_bars[f] = bar

        telemetry_layout.addLayout(curl_box)
        telemetry_layout.addStretch()

        self.calib_btn = QPushButton("Launch Calibration Wizard")
        self.calib_btn.setFixedHeight(30)
        self.calib_btn.clicked.connect(self._launch_calibration)
        telemetry_layout.addWidget(self.calib_btn)

        split_layout.addWidget(telemetry_group)
        root_layout.addLayout(split_layout)

        # 3. Settings Tabs
        self.tabs = QTabWidget()
        self._build_cursor_tab()
        self._build_keyboard_tab()
        self._build_gestures_tab()
        self._build_paint_tab()
        self._build_system_tab()
        root_layout.addWidget(self.tabs)

    def _build_cursor_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.slider_sens = QSlider(Qt.Horizontal)
        self.slider_sens.setRange(5, 30)
        self.slider_sens.setValue(int(self.settings.sensitivity * 10))
        self.slider_sens.valueChanged.connect(self._on_sens_changed)
        layout.addRow("Sensitivity (Speed Multiplier):", self.slider_sens)

        self.spin_cutoff = QDoubleSpinBox()
        self.spin_cutoff.setRange(0.1, 5.0)
        self.spin_cutoff.setSingleStep(0.1)
        self.spin_cutoff.setValue(self.settings.one_euro.min_cutoff)
        self.spin_cutoff.valueChanged.connect(self._save_settings)
        layout.addRow("One Euro Min Cutoff (Jitter suppression at rest):", self.spin_cutoff)

        self.spin_beta = QDoubleSpinBox()
        self.spin_beta.setRange(0.001, 0.05)
        self.spin_beta.setDecimals(4)
        self.spin_beta.setSingleStep(0.001)
        self.spin_beta.setValue(self.settings.one_euro.beta)
        self.spin_beta.valueChanged.connect(self._save_settings)
        layout.addRow("One Euro Beta (Responsiveness during fast motion):", self.spin_beta)

        self.tabs.addTab(tab, "Cursor & Filter")

    def _build_keyboard_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # Symbols panel toggle
        self.chk_symbols_enabled = QCheckBox("Enable Separate Symbols Panel on Right")
        self.chk_symbols_enabled.setChecked(self.settings.keyboard.symbols_panel_enabled)
        self.chk_symbols_enabled.toggled.connect(self._save_settings)
        layout.addRow("Symbols Panel:", self.chk_symbols_enabled)

        # Dim inactive panel
        self.chk_dim_inactive = QCheckBox("Dim Inactive Panel to 40% Opacity")
        self.chk_dim_inactive.setChecked(self.settings.keyboard.dim_inactive_panel)
        self.chk_dim_inactive.toggled.connect(self._save_settings)
        layout.addRow("Zone Focus:", self.chk_dim_inactive)

        # Thumb is space
        self.chk_thumb_space = QCheckBox("Thumb Air-Tap Sends Space Bar")
        self.chk_thumb_space.setChecked(self.settings.keyboard.thumb_is_space)
        self.chk_thumb_space.toggled.connect(self._save_settings)
        layout.addRow("Thumb Shortcut:", self.chk_thumb_space)

        # Swipe threshold
        self.spin_swipe_thresh = QDoubleSpinBox()
        self.spin_swipe_thresh.setRange(0.15, 0.60)
        self.spin_swipe_thresh.setSingleStep(0.02)
        self.spin_swipe_thresh.setValue(self.settings.keyboard.swipe_threshold)
        self.spin_swipe_thresh.valueChanged.connect(self._save_settings)
        layout.addRow("Row / Window Swipe Threshold (Hand-size normalized):", self.spin_swipe_thresh)

        # Finger mapping
        self.combo_mapping = QComboBox()
        self.combo_mapping.addItems(["Visual Order (Left-to-Right)", "Reversed"])
        self.combo_mapping.setCurrentIndex(0 if self.settings.keyboard.finger_mapping == "visual" else 1)
        self.combo_mapping.currentIndexChanged.connect(self._save_settings)
        layout.addRow("Finger-to-Key Mapping:", self.combo_mapping)

        # Hotkeys Note
        lbl_kb_hotkeys = QLabel("Open: Hold Open Palm ~0.5s or Ctrl+Alt+K\nExit: Hold Fist ~0.5s, Pointing, or Esc\nZone Toggle: Ctrl+Alt+S")
        lbl_kb_hotkeys.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 11px;")
        layout.addRow("Keyboard Shortcuts:", lbl_kb_hotkeys)

        self.tabs.addTab(tab, "Air Keyboard")

    def _build_gestures_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.spin_double_tap = QSpinBox()
        self.spin_double_tap.setRange(200, 800)
        self.spin_double_tap.setValue(int(self.settings.gestures.double_tap_window_ms))
        self.spin_double_tap.valueChanged.connect(self._save_settings)
        layout.addRow("Air Double-Tap Window (ms):", self.spin_double_tap)

        self.chk_single_click = QCheckBox("Enable Single Air Tap as Left Click")
        self.chk_single_click.setChecked(self.settings.gestures.single_click_enabled)
        self.chk_single_click.toggled.connect(self._save_settings)
        layout.addRow("Single Click:", self.chk_single_click)

        self.spin_dwell = QDoubleSpinBox()
        self.spin_dwell.setRange(0.3, 1.5)
        self.spin_dwell.setSingleStep(0.05)
        self.spin_dwell.setValue(self.settings.gestures.dwell_lock_time_s)
        self.spin_dwell.valueChanged.connect(self._save_settings)
        layout.addRow("Brush Lock Dwell Hold (seconds):", self.spin_dwell)

        self.spin_right_click = QDoubleSpinBox()
        self.spin_right_click.setRange(0.2, 1.2)
        self.spin_right_click.setValue(self.settings.gestures.right_click_hold_s)
        self.spin_right_click.valueChanged.connect(self._save_settings)
        layout.addRow("Two-Finger Right Click Hold (seconds):", self.spin_right_click)

        self.tabs.addTab(tab, "Click Gestures")

    def _build_paint_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.chk_auto_paint = QCheckBox("Auto-Detect Creative Apps & Elevate Stabilizer")
        self.chk_auto_paint.setChecked(self.settings.paint.auto_detect)
        self.chk_auto_paint.toggled.connect(self._save_settings)
        layout.addWidget(self.chk_auto_paint)

        layout.addWidget(QLabel("Target Paint Processes (Comma-separated exe names):"))
        self.txt_paint_apps = QLineEdit(", ".join(self.settings.paint.active_apps))
        self.txt_paint_apps.editingFinished.connect(self._save_settings)
        layout.addWidget(self.txt_paint_apps)

        self.tabs.addTab(tab, "Paint Mode")

    def _build_system_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.chk_minimized = QCheckBox("Start Minimized to System Tray")
        self.chk_minimized.setChecked(self.settings.start_minimized)
        self.chk_minimized.toggled.connect(self._save_settings)
        layout.addRow("Startup:", self.chk_minimized)

        lbl_hotkeys = QLabel(
            "Ctrl+Alt+T: Toggle Tony Pointer Mode\n"
            "Ctrl+Alt+K: Toggle Air Keyboard Mode\n"
            "Ctrl+Alt+S: Toggle Keyboard Zone (Main / Symbols)\n"
            "Ctrl+Alt+P: Toggle Paint Mode Profile\n"
            "Esc: Emergency Key & Brush Safety Release"
        )
        lbl_hotkeys.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 11px;")
        layout.addRow("Global Hotkeys:", lbl_hotkeys)

        self.tabs.addTab(tab, "System & Hotkeys")

    def _on_arc_clicked(self):
        new_state = not self.arc_button.is_active
        self.arc_button.set_active(new_state)
        self.toggle_mode_requested.emit(new_state)

    def _on_sens_changed(self, val):
        self.settings.sensitivity = val / 10.0
        self._save_settings()

    def _save_settings(self):
        self.settings.one_euro.min_cutoff = self.spin_cutoff.value()
        self.settings.one_euro.beta = self.spin_beta.value()
        self.settings.gestures.double_tap_window_ms = float(self.spin_double_tap.value())
        self.settings.gestures.single_click_enabled = self.chk_single_click.isChecked()
        self.settings.gestures.dwell_lock_time_s = self.spin_dwell.value()
        self.settings.gestures.right_click_hold_s = self.spin_right_click.value()
        self.settings.paint.auto_detect = self.chk_auto_paint.isChecked()
        self.settings.start_minimized = self.chk_minimized.isChecked()

        # Keyboard settings
        self.settings.keyboard.symbols_panel_enabled = self.chk_symbols_enabled.isChecked()
        self.settings.keyboard.dim_inactive_panel = self.chk_dim_inactive.isChecked()
        self.settings.keyboard.thumb_is_space = self.chk_thumb_space.isChecked()
        self.settings.keyboard.swipe_threshold = self.spin_swipe_thresh.value()
        self.settings.keyboard.finger_mapping = "visual" if self.combo_mapping.currentIndex() == 0 else "reversed"

        apps = [x.strip().lower() for x in self.txt_paint_apps.text().split(",") if x.strip()]
        self.settings.paint.active_apps = apps

        self.settings_manager.save()
        self.settings_changed.emit()

    def _launch_calibration(self):
        status = self.get_status()
        dlg = CornerCalibrationDialog(self.settings, lambda: status.get("raw_hand"), self)
        if dlg.exec():
            self._save_settings()

    def _refresh_telemetry(self):
        status = self.get_status()
        self.lbl_fps.setText(f"FPS: {status.get('fps', 0.0):.1f}")
        self.lbl_latency.setText(f"INFERENCE LATENCY: {status.get('latency_ms', 0.0):.1f} ms")
        self.lbl_mode.setText(f"OPERATING MODE: {status.get('mode', 'POINTER')}")
        self.lbl_pose.setText(f"HAND POSE: {status.get('pose', 'UNKNOWN')}")
        self.lbl_action.setText(f"ACTIVE GESTURE: {status.get('status_text', 'NONE')}")

        kb_zone = status.get("kb_zone", "MAIN")
        kb_row = status.get("kb_row", 3)
        kb_win = status.get("kb_win_keys", ["A", "S", "D", "F"])
        self.lbl_kb_status.setText(f"KEYBOARD: ZONE [{kb_zone}] · ROW {kb_row + 1} · LOCKED: [{' '.join(kb_win)}]")

        locked = status.get("brush_locked", False)
        self.lbl_brush.setText("BRUSH LOCK: ACTIVE (DRAGGING)" if locked else "BRUSH LOCK: OFF")
        self.lbl_brush.setStyleSheet(f"color: {'#ff5722' if locked else '#64748b'}; font-weight: bold; font-family: monospace;")

        app_name = status.get("foreground_app", "DESKTOP")
        self.lbl_window.setText(f"FOREGROUND APP: {app_name.upper()}")

        # Update Live Finger Curls
        curls = status.get("curls", {})
        for f, val in curls.items():
            if f in self.curl_bars:
                self.curl_bars[f].setValue(int(val * 100))

        # Update Live Camera Pixmap
        frame = self.get_frame()
        if frame is not None:
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            rgb = frame[:, :, ::-1].copy()
            q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(q_img).scaled(
                self.video_label.width(),
                self.video_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.video_label.setPixmap(pix)
