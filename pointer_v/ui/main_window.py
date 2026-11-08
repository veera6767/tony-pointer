"""
Pointer V - Application Shell & Main Window
Assembles the custom title bar, responsive collapsible sidebar rail,
central stacked page deck (Dashboard, Camera, Gestures, Keyboard, Practice, Settings,
Calibration, About, Developer), and bottom telemetry status bar.
"""

from typing import Callable, Dict, Optional
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget
)

from recorder import LandmarkRecorder
from theme import (
    BG0_WINDOW, BORDER, RADIUS_WINDOW, TEXT_PRIMARY, get_global_stylesheet,
    init_fonts
)
from ui.pages.about_page import AboutPage
from ui.pages.calibration_page import CalibrationPage
from ui.pages.camera_page import CameraPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.developer_page import DeveloperPage
from ui.pages.gestures_page import GesturesPage
from ui.pages.keyboard_page import KeyboardPage
from ui.pages.practice_page import PracticePage
from ui.pages.settings_page import SettingsPage
from ui.tutorial_dialog import TutorialDialog
from ui.widgets import CustomTitleBar, SidebarRail, StatusBarWidget


class MainWindow(QMainWindow):
    """Pointer V Frameless Pro Application Shell."""

    toggle_mode_requested = Signal(bool)
    toggle_keyboard_requested = Signal()
    toggle_paint_requested = Signal()
    toggle_pause_requested = Signal()
    settings_changed = Signal()
    camera_device_changed = Signal(int, str)
    fps_cap_changed = Signal(int)
    monitor_changed = Signal(int)

    def __init__(
        self,
        settings_manager,
        mouse_controller,
        recorder: LandmarkRecorder,
        get_status_fn: Callable,
        get_frame_fn: Callable,
        parent=None
    ):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings = settings_manager.config
        self.mouse = mouse_controller
        self.recorder = recorder
        self.get_status = get_status_fn
        self.get_frame = get_frame_fn

        # Initialize fonts and master stylesheet
        init_fonts()
        self.setStyleSheet(get_global_stylesheet())

        # Frameless window with custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.setMinimumSize(1000, 640)
        self._restore_geometry()

        self._build_ui()

        # Telemetry refresh timer
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._refresh_telemetry)
        self.telemetry_timer.start(33)

        # Check first-run tutorial
        if getattr(self.settings, "show_tutorial_on_startup", True) and not getattr(self.settings, "tutorial_completed", False):
            QTimer.singleShot(500, self._show_first_run_tutorial)

    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Custom Frameless Title Bar
        self.title_bar = CustomTitleBar(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.hide)  # Close minimizes to tray
        root_layout.addWidget(self.title_bar)

        # 1.1 Camera Disconnect Reconnect Warning Banner
        self.camera_banner = QLabel("⚠ Camera disconnected or unavailable. Retrying every 2 seconds... (Auto-resumes on replug)")
        self.camera_banner.setFixedHeight(28)
        self.camera_banner.setAlignment(Qt.AlignCenter)
        self.camera_banner.setStyleSheet("background-color: #2D1515; color: #F0506E; border-bottom: 1px solid rgba(240, 80, 110, 0.4); font-size: 11px; font-weight: 600;")
        self.camera_banner.hide()
        root_layout.addWidget(self.camera_banner)

        # 2. Main Body Split: Left Sidebar Rail, Right Stacked Pages
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = SidebarRail(self)
        self.sidebar.page_selected.connect(self._on_page_selected)
        body_layout.addWidget(self.sidebar)

        self.deck = QStackedWidget(self)
        self.deck.setStyleSheet(f"background-color: {BG0_WINDOW};")

        # Page 0: Dashboard
        self.page_dash = DashboardPage(self.settings, self)
        self.page_dash.toggle_pointer_requested.connect(self.toggle_mode_requested.emit)
        self.page_dash.toggle_keyboard_requested.connect(self.toggle_keyboard_requested.emit)
        self.page_dash.toggle_paint_requested.connect(self.toggle_paint_requested.emit)
        self.page_dash.toggle_pause_requested.connect(self.toggle_pause_requested.emit)
        self.page_dash.calibrate_requested.connect(lambda: self.deck.setCurrentIndex(6))
        self.deck.addWidget(self.page_dash)

        # Page 1: Camera
        self.page_cam = CameraPage(self.settings, self.mouse, self)
        self.page_cam.camera_changed.connect(self.camera_device_changed.emit)
        self.page_cam.fps_cap_changed.connect(self.fps_cap_changed.emit)
        self.page_cam.monitor_changed.connect(self.monitor_changed.emit)
        self.page_cam.settings_saved.connect(self._on_settings_saved)
        self.deck.addWidget(self.page_cam)

        # Page 2: Gestures
        self.page_gest = GesturesPage(self.settings, self)
        self.deck.addWidget(self.page_gest)

        # Page 3: Keyboard
        self.page_kb = KeyboardPage(self.settings, self)
        self.page_kb.settings_changed.connect(self._on_settings_saved)
        self.deck.addWidget(self.page_kb)

        # Page 4: Practice
        self.page_prac = PracticePage(self.settings, self)
        self.deck.addWidget(self.page_prac)

        # Page 5: Settings
        self.page_set = SettingsPage(self.settings_manager, self)
        self.page_set.settings_changed.connect(self._on_settings_saved)
        self.deck.addWidget(self.page_set)

        # Page 6: Calibration
        self.page_calib = CalibrationPage(self.settings, self)
        self.page_calib.calibration_completed.connect(self._on_calibration_done)
        self.deck.addWidget(self.page_calib)

        # Page 7: About
        self.page_about = AboutPage(self.get_status, self)
        self.deck.addWidget(self.page_about)

        # Page 8: Developer Tools (Hidden by default)
        self.page_dev = DeveloperPage(self.settings, self.recorder, self)
        self.deck.addWidget(self.page_dev)

        body_layout.addWidget(self.deck, stretch=1)
        root_layout.addLayout(body_layout, stretch=1)

        # 3. Telemetry Status Bar
        self.status_bar = StatusBarWidget(self)
        root_layout.addWidget(self.status_bar)

        self._update_developer_mode_visibility()

    def _show_first_run_tutorial(self):
        dlg = TutorialDialog(self.settings, self.get_status, self)
        dlg.exec()
        self.settings_manager.save()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_page_selected(self, index: int):
        self.deck.setCurrentIndex(index)

    def _on_calibration_done(self):
        self.settings_manager.save()
        self.settings_changed.emit()
        self.deck.setCurrentIndex(0)

    def _on_settings_saved(self):
        self.settings_manager.save()
        self.settings_changed.emit()
        self._update_developer_mode_visibility()

    def _update_developer_mode_visibility(self):
        dev_enabled = getattr(self.settings, "developer_mode_enabled", False)
        self.sidebar.set_developer_mode_visible(dev_enabled)

    def set_system_active(self, active: bool):
        self.page_dash.power_toggle.setChecked(active)

    def _refresh_telemetry(self):
        telem = self.get_status()
        frame = self.get_frame()

        fps = telem.get("fps", 0.0)
        latency = telem.get("latency_ms", 0.0)
        mode = telem.get("mode", "POINTER")
        is_paused = telem.get("is_paused", False)
        cam_conn = telem.get("camera_connected", True)
        curls = telem.get("curls", {})
        status_text = telem.get("status_text", "NONE")

        # Update Title Bar & Status Bar
        self.title_bar.mode_chip.set_status(mode, is_paused)
        self.status_bar.update_telemetry(fps, latency, cam_conn, is_paused)

        # Show camera disconnect banner if camera is offline
        if not cam_conn:
            self.camera_banner.show()
        else:
            self.camera_banner.hide()

        # Active page refresh
        cur_idx = self.deck.currentIndex()
        if cur_idx == 0:
            self.page_dash.update_telemetry(telem, frame)
        elif cur_idx == 1:
            self.page_cam.update_frame(
                frame,
                is_low_light=telem.get("is_low_light", False),
                is_over_exposed=telem.get("is_over_exposed", False),
            )
        elif cur_idx == 2:
            self.page_gest.update_telemetry(curls, status_text)
        elif cur_idx == 4:
            self.page_prac.update_telemetry(telem)

    def _restore_geometry(self):
        from PySide6.QtCore import QPoint, QRect, QSize
        from PySide6.QtGui import QGuiApplication

        geom = self.settings.window_geometry.get("main", [100, 100, 1080, 700])
        x, y, w, h = geom
        # Clamp to reasonable bounds
        w = max(1000, w)
        h = max(640, h)
        self.resize(w, h)

        # Check if saved (x, y) coordinates intersect any currently connected monitor
        target_rect = QRect(x, y, w, h)
        is_visible = any(s.geometry().intersects(target_rect) for s in QGuiApplication.screens())

        if is_visible and x >= -500 and y >= -500:
            self.move(x, y)
        else:
            # Fallback to centering on primary monitor
            primary = QGuiApplication.primaryScreen()
            if primary:
                geo = primary.availableGeometry()
                cx = geo.x() + max(0, (geo.width() - w) // 2)
                cy = geo.y() + max(0, (geo.height() - h) // 2)
                self.move(cx, cy)
            else:
                self.move(100, 100)

    def closeEvent(self, event):
        # Save geometry
        pos = self.pos()
        size = self.size()
        self.settings.window_geometry["main"] = [pos.x(), pos.y(), size.width(), size.height()]
        self.settings_manager.save()
        super().closeEvent(event)

