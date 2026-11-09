"""
Pointer V - UI Smoke Tests
Guarantees every page, dialog, overlay, and HUD instantiates and renders
cleanly without NameError, AttributeError, or layout exceptions.
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Enforce offscreen Qt rendering for headless automated test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QFileDialog, QMessageBox, QPushButton, QSystemTrayIcon
)

from keyboard_layout import KeyboardLayoutManager
from mouse import MouseController
from recorder import LandmarkRecorder
from settings import SettingsManager
from ui.main_window import MainWindow
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
from overlay import CursorOverlayWindow
from preview import CameraPreviewOverlay
from keyboard_ui import FloatingAirKeyboardWidget
from ui.widgets import ToggleSwitch


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_environment(tmp_path):
    settings_file = tmp_path / "smoke_settings.json"
    settings_mgr = SettingsManager(str(settings_file))
    mouse = MouseController()
    recorder = LandmarkRecorder()
    layout_mgr = KeyboardLayoutManager()

    mock_status = {
        "is_active": True,
        "is_paused": False,
        "mode": "POINTER",
        "pose": "POINTING",
        "fps": 60.0,
        "inference_ms": 12.0,
        "model_loaded": True,
        "camera_connected": True,
        "hand_detected": True,
        "handedness": "Right",
        "hand_curl_values": [0.1, 0.2, 0.8, 0.8, 0.9],
        "screen_coords": (500, 400),
        "active_pos": (0.5, 0.4),
        "mouse_sendinput_ret": 1,
        "key_sendinput_ret": 1,
        "internal_errors": [],
    }

    return {
        "settings_mgr": settings_mgr,
        "mouse": mouse,
        "recorder": recorder,
        "layout_mgr": layout_mgr,
        "mock_status": mock_status,
    }


def test_main_window_and_every_page_renders_cleanly(qapp, mock_environment):
    """Instantiates MainWindow and navigates through EVERY page, asserting no crashes."""
    env = mock_environment
    main_win = MainWindow(
        settings_manager=env["settings_mgr"],
        mouse_controller=env["mouse"],
        recorder=env["recorder"],
        get_status_fn=lambda: env["mock_status"],
        get_frame_fn=lambda: None,
        keyboard_output=MagicMock(),
    )

    main_win.show()

    # Step through all sidebar pages in the central stacked deck
    page_count = main_win.deck.count()
    assert page_count >= 9, f"Expected at least 9 pages, found {page_count}"

    for i in range(page_count):
        main_win.deck.setCurrentIndex(i)
        current_page = main_win.deck.currentWidget()
        assert current_page is not None
        # Process events for this page
        for _ in range(5):
            QCoreApplication.processEvents()
            time.sleep(0.01)

    main_win.close()


def test_individual_pages_direct_instantiation(qapp, mock_environment):
    """Instantiates every individual page widget directly with full telemetry update."""
    env = mock_environment
    cfg = env["settings_mgr"].config

    pages = [
        DashboardPage(cfg),
        CameraPage(cfg, env["mouse"]),
        GesturesPage(cfg),
        KeyboardPage(cfg),
        PracticePage(cfg),
        SettingsPage(env["settings_mgr"]),
        CalibrationPage(cfg),
        AboutPage(lambda: env["mock_status"]),
        DeveloperPage(cfg, env["recorder"]),
    ]

    for page in pages:
        page.show()
        if hasattr(page, "update_telemetry"):
            if isinstance(page, GesturesPage):
                page.update_telemetry(env["mock_status"], "TEST_STATUS")
            else:
                page.update_telemetry(env["mock_status"])
        for _ in range(5):
            QCoreApplication.processEvents()
            time.sleep(0.01)
        page.close()


def test_dialogs_overlays_and_hud_render_cleanly(qapp, mock_environment):
    """Tests TutorialDialog, CameraPreviewOverlay, CursorOverlayWindow, and FloatingAirKeyboardWidget."""
    env = mock_environment
    cfg = env["settings_mgr"].config

    tut = TutorialDialog(cfg, lambda: env["mock_status"])
    tut.show()
    for _ in range(3):
        QCoreApplication.processEvents()
    tut.close()

    preview = CameraPreviewOverlay(cfg)
    preview.show()
    for _ in range(3):
        QCoreApplication.processEvents()
    preview.close()

    cursor_overlay = CursorOverlayWindow(cfg)
    cursor_overlay.show()
    cursor_overlay.update_position(100, 100, "NORMAL", 0.0, False, "POINTER")
    for _ in range(3):
        QCoreApplication.processEvents()
    cursor_overlay.close()

    corner_kb = FloatingAirKeyboardWidget(cfg, env["layout_mgr"])
    corner_kb.show()
    for _ in range(3):
        QCoreApplication.processEvents()
    corner_kb.close()

    # Tray icon
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon()
        tray.show()
        tray.hide()


@patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=("", ""))
@patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", ""))
@patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes)
@patch("PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Ok)
@patch("PySide6.QtWidgets.QMessageBox.information", return_value=QMessageBox.Ok)
@patch("mouse.ctypes.windll.user32.SendInput", return_value=1)
def test_click_every_button_and_toggle(mock_sendinput, mock_info, mock_warn, mock_quest, mock_save, mock_open, qapp, mock_environment):
    """Finds all buttons and toggle switches on every page and triggers them without exception."""
    env = mock_environment
    cfg = env["settings_mgr"].config

    pages = [
        DashboardPage(cfg),
        CameraPage(cfg, env["mouse"]),
        GesturesPage(cfg),
        KeyboardPage(cfg),
        PracticePage(cfg),
        SettingsPage(env["settings_mgr"]),
        CalibrationPage(cfg),
        AboutPage(lambda: env["mock_status"]),
        DeveloperPage(cfg, env["recorder"]),
    ]

    for page in pages:
        page.show()
        buttons = page.findChildren(QAbstractButton)
        for btn in buttons:
            try:
                btn.click()
                QCoreApplication.processEvents()
            except Exception as e:
                pytest.fail(f"Button {btn} on page {page} raised exception on click: {e}")

        toggles = page.findChildren(ToggleSwitch)
        for toggle in toggles:
            try:
                toggle.setChecked(not toggle.isChecked())
                QCoreApplication.processEvents()
            except Exception as e:
                pytest.fail(f"ToggleSwitch {toggle} on page {page} raised exception: {e}")

        page.close()
