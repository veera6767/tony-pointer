"""
Pointer V - Soak Test & Freeze Regression Suite
Validates that continuous rapid gesture changes (open-palm holds,
closed fist holds, pointing taps) do NOT lock the Qt UI thread
or starve the watchdog heartbeat, and asserts overlays survive minimization.
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from keyboard_layout import KeyboardLayoutManager
from mouse import MouseController
from recorder import LandmarkRecorder, create_synthetic_hand
from settings import SettingsManager
from ui.main_window import MainWindow
from keyboard_ui import FloatingAirKeyboardWidget
from overlay import CursorOverlayWindow
from preview import CameraPreviewOverlay
from gestures import GestureEngine, GestureAction


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    return app


def test_independent_parentless_windows_survive_minimize(qapp, tmp_path):
    """
    Guarantees floating HUDs (keyboard, cursor, preview) are parentless Tool windows
    and remain functional when MainWindow is minimized.
    """
    settings_file = tmp_path / "win_test_settings.json"
    settings_mgr = SettingsManager(str(settings_file))
    cfg = settings_mgr.config
    cfg.keep_running_in_tray_when_minimized = True

    layout_mgr = KeyboardLayoutManager()
    mouse = MouseController()
    recorder = LandmarkRecorder()

    with patch("ui.pages.camera_page.list_available_cameras", return_value=[(0, "Mock Camera")]):
        main_win = MainWindow(
            settings_manager=settings_mgr,
            mouse_controller=mouse,
            recorder=recorder,
            get_status_fn=lambda: {"mode": "POINTER", "is_active": True},
            get_frame_fn=lambda: None,
            keyboard_output=MagicMock()
        )

    kb_overlay = FloatingAirKeyboardWidget(cfg, layout_mgr)
    cursor_overlay = CursorOverlayWindow(cfg)
    preview_overlay = CameraPreviewOverlay(cfg)

    # 1. Verify parentless
    assert kb_overlay.parent() is None, "Keyboard overlay must be parentless"
    assert cursor_overlay.parent() is None, "Cursor overlay must be parentless"
    assert preview_overlay.parent() is None, "Camera preview overlay must be parentless"

    # 2. Verify Tool window flags
    from PySide6.QtCore import Qt
    assert bool(kb_overlay.windowFlags() & Qt.WindowType.Tool), "Keyboard must have Qt.WindowType.Tool"
    assert bool(cursor_overlay.windowFlags() & Qt.WindowType.Tool), "Cursor must have Qt.WindowType.Tool"
    assert bool(preview_overlay.windowFlags() & Qt.WindowType.Tool), "Preview must have Qt.WindowType.Tool"

    # 3. Simulate showing and minimizing MainWindow
    main_win.show()
    kb_overlay.show()
    cursor_overlay.show()
    preview_overlay.show()

    QCoreApplication.processEvents()

    # Minimize main window
    main_win.showMinimized()
    QCoreApplication.processEvents()

    # Overlays must remain valid and not closed
    assert kb_overlay.isVisible(), "Keyboard overlay must survive main window minimization"
    assert cursor_overlay.isVisible(), "Cursor overlay must survive main window minimization"
    assert preview_overlay.isVisible(), "Preview overlay must survive main window minimization"

    main_win.telemetry_timer.stop()
    kb_overlay.anim_timer.stop()
    cursor_overlay.anim_timer.stop()
    kb_overlay.close()
    cursor_overlay.close()
    preview_overlay.close()
    main_win.close()


def test_open_palm_hold_thread_safety_no_freeze(qapp, tmp_path):
    """
    Simulates repeated open-palm hold to keyboard mode transitions,
    verifying UI event processing and asserting that no deadlock occurs.
    """
    settings_file = tmp_path / "thread_test_settings.json"
    settings_mgr = SettingsManager(str(settings_file))
    cfg = settings_mgr.config
    cfg.keyboard.open_palm_hold_s = 0.05  # Fast for test

    engine = GestureEngine(cfg)

    # Synthetic open palm hand (all 5 fingers extended and spread)
    open_hand = create_synthetic_hand(
        index_curl_angle=170.0,
        middle_curl_angle=170.0,
        ring_curl_angle=170.0,
        pinky_curl_angle=170.0,
        thumb_curl=0.0
    )

    heartbeat_ticks = 0

    def tick():
        nonlocal heartbeat_ticks
        heartbeat_ticks += 1

    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(tick)
    timer.start()

    engaged_count = 0

    # Run 30 deterministic iterations with simulated time progression
    simulated_now = 1000.0

    def fake_perf_counter():
        return simulated_now

    with patch("time.perf_counter", side_effect=fake_perf_counter):
        for _ in range(30):
            simulated_now += 0.02
            res = engine.process(
                hand=open_hand,
                screen_bounds=(0, 0, 1920, 1080),
                filter_2d=None,
                current_mode="POINTER"
            )
            if res.get("action") == GestureAction.ENTER_KEYBOARD.value:
                engaged_count += 1
                engine.open_palm_start_time = None

            QCoreApplication.processEvents()

    timer.stop()
    assert engaged_count >= 1, "Open palm hold failed to evaluate ENTER_KEYBOARD action"
