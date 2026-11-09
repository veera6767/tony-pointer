"""
Pointer V - Camera Configuration Page
Camera device selector, resolution options, FPS cap (15/30/60), Battery Saver,
lighting warnings, monitor re-mapping selector, and interactive active-region editor.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QSlider, QVBoxLayout, QWidget
)

from camera import list_available_cameras
from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BORDER, BORDER_STRONG,
    GREEN, RADIUS_CONTROL, RADIUS_PANEL, TEXT_PRIMARY, get_ui_font
)


class ActiveRegionCanvas(QLabel):
    """Interactive preview canvas allowing dragging active region boundaries."""

    region_changed = Signal(float, float, float, float)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setFixedSize(520, 320)
        self.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS_CONTROL}px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_frame = None

    def set_frame(self, frame_bgr):
        self.current_frame = frame_bgr
        if frame_bgr is not None:
            h, w, ch = frame_bgr.shape
            rgb = frame_bgr[:, :, ::-1].copy()
            q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(q_img).scaled(
                self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(pix)


class CameraPage(QWidget):
    """Camera settings, resolution, FPS cap, and active region configuration."""

    camera_changed = Signal(int, str)
    fps_cap_changed = Signal(int)
    monitor_changed = Signal(int)
    settings_saved = Signal()

    def __init__(self, settings, mouse_controller, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.mouse = mouse_controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Camera & Display Calibration")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left: Interactive Viewport
        view_card = QFrame()
        view_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        view_layout = QVBoxLayout(view_card)
        view_layout.setContentsMargins(16, 16, 16, 16)

        self.canvas = ActiveRegionCanvas(settings, self)
        view_layout.addWidget(self.canvas)

        # Lighting Status Warning Banner
        self.warning_label = QLabel("Lighting: Optimal")
        self.warning_label.setFont(get_ui_font(11))
        self.warning_label.setStyleSheet(f"color: {GREEN}; margin-top: 6px;")
        view_layout.addWidget(self.warning_label)
        content_layout.addWidget(view_card)

        # Right: Camera Controls
        ctrl_card = QFrame()
        ctrl_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(16, 16, 16, 16)
        ctrl_layout.setSpacing(12)

        # 1. Camera Selector
        ctrl_layout.addWidget(QLabel("Camera Device:"))
        self.combo_cam = QComboBox()
        self.cameras = list_available_cameras()
        for idx, name in self.cameras:
            self.combo_cam.addItem(name, idx)
        self.combo_cam.currentIndexChanged.connect(self._on_cam_selected)
        ctrl_layout.addWidget(self.combo_cam)

        # 2. FPS Cap Selector (15 / 30 / 60)
        ctrl_layout.addWidget(QLabel("Inference FPS Cap:"))
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["60 FPS (Ultra Smooth)", "30 FPS (Balanced)", "15 FPS (Power Saver)"])
        fps_val = self.settings.target_fps
        fps_idx = 0 if fps_val >= 60 else (1 if fps_val >= 30 else 2)
        self.combo_fps.setCurrentIndex(fps_idx)
        self.combo_fps.currentIndexChanged.connect(self._on_fps_changed)
        ctrl_layout.addWidget(self.combo_fps)

        # 3. Battery Saver Mode
        self.chk_battery = QCheckBox("Battery Saver (Throttle when idle or on battery)")
        self.chk_battery.setChecked(getattr(self.settings, "battery_saver", True))
        self.chk_battery.toggled.connect(self._save_settings)
        ctrl_layout.addWidget(self.chk_battery)

        # 4. Monitor Selector
        ctrl_layout.addWidget(QLabel("Active Desktop Monitor:"))
        self.combo_monitors = QComboBox()
        self.combo_monitors.addItem("All Monitors (Virtual Desktop)", -1)
        monitors = self.mouse.refresh_monitors()
        for m_idx, (mx, my, mw, mh) in enumerate(monitors):
            self.combo_monitors.addItem(f"Monitor {m_idx + 1} ({mw}x{mh} at {mx},{my})", m_idx)

        current_mon = getattr(self.settings.monitors, "monitor_index", -1)
        found_idx = self.combo_monitors.findData(current_mon)
        if found_idx >= 0:
            self.combo_monitors.setCurrentIndex(found_idx)
        self.combo_monitors.currentIndexChanged.connect(self._on_monitor_changed)
        ctrl_layout.addWidget(self.combo_monitors)

        # 5. Active Region Sliders
        ctrl_layout.addWidget(QLabel("Active Region Bounds:"))

        ar_grid = QGridLayout()
        self.slider_xmin = QSlider(Qt.Orientation.Horizontal)
        self.slider_xmin.setRange(5, 40)
        self.slider_xmin.setValue(int(self.settings.active_region.x_min * 100))
        self.slider_xmin.valueChanged.connect(self._save_settings)
        ar_grid.addWidget(QLabel("Left Margin:"), 0, 0)
        ar_grid.addWidget(self.slider_xmin, 0, 1)

        self.slider_xmax = QSlider(Qt.Orientation.Horizontal)
        self.slider_xmax.setRange(60, 95)
        self.slider_xmax.setValue(int(self.settings.active_region.x_max * 100))
        self.slider_xmax.valueChanged.connect(self._save_settings)
        ar_grid.addWidget(QLabel("Right Margin:"), 1, 0)
        ar_grid.addWidget(self.slider_xmax, 1, 1)

        self.slider_ymin = QSlider(Qt.Orientation.Horizontal)
        self.slider_ymin.setRange(5, 40)
        self.slider_ymin.setValue(int(self.settings.active_region.y_min * 100))
        self.slider_ymin.valueChanged.connect(self._save_settings)
        ar_grid.addWidget(QLabel("Top Margin:"), 2, 0)
        ar_grid.addWidget(self.slider_ymin, 2, 1)

        self.slider_ymax = QSlider(Qt.Orientation.Horizontal)
        self.slider_ymax.setRange(60, 95)
        self.slider_ymax.setValue(int(self.settings.active_region.y_max * 100))
        self.slider_ymax.valueChanged.connect(self._save_settings)
        ar_grid.addWidget(QLabel("Bottom Margin:"), 3, 0)
        ar_grid.addWidget(self.slider_ymax, 3, 1)

        ctrl_layout.addLayout(ar_grid)
        ctrl_layout.addStretch()

        content_layout.addWidget(ctrl_card)
        layout.addLayout(content_layout)
        layout.addStretch()

    def update_frame(self, frame_bgr, is_low_light: bool = False, is_over_exposed: bool = False):
        self.canvas.set_frame(frame_bgr)
        if is_low_light:
            self.warning_label.setText("Warning: Environment too dark. Tracking accuracy may be reduced.")
            self.warning_label.setStyleSheet(f"color: {AMBER};")
        elif is_over_exposed:
            self.warning_label.setText("Warning: Environment over-exposed / bright glare detected.")
            self.warning_label.setStyleSheet(f"color: {AMBER};")
        else:
            self.warning_label.setText("Lighting: Optimal")
            self.warning_label.setStyleSheet(f"color: {GREEN};")

    def _on_cam_selected(self, index):
        idx = self.combo_cam.currentData()
        name = self.combo_cam.currentText()
        self.settings.camera_index = idx
        self.settings.camera_name = name
        self.camera_changed.emit(idx, name)
        self.settings_saved.emit()

    def _on_fps_changed(self, index):
        fps_map = [60, 30, 15]
        target = fps_map[index]
        self.settings.target_fps = target
        self.fps_cap_changed.emit(target)
        self.settings_saved.emit()

    def _on_monitor_changed(self, index):
        mon_idx = self.combo_monitors.currentData()
        self.settings.monitors.monitor_index = mon_idx
        self.monitor_changed.emit(mon_idx)
        self.settings_saved.emit()

    def _save_settings(self):
        self.settings.battery_saver = self.chk_battery.isChecked()
        self.settings.active_region.x_min = self.slider_xmin.value() / 100.0
        self.settings.active_region.x_max = self.slider_xmax.value() / 100.0
        self.settings.active_region.y_min = self.slider_ymin.value() / 100.0
        self.settings.active_region.y_max = self.slider_ymax.value() / 100.0
        self.settings_saved.emit()

