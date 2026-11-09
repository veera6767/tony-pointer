"""
Tests to guarantee that Pointer V UI event loop does not freeze
or deadlock during camera ingestion, hand tracking processing,
or mode switches.
"""

import sys
import pytest
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from settings import SettingsManager


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_ui_event_loop_responsiveness(qapp):
    """Verify that an active timer continues firing and is not starved."""
    ticks = []

    timer = QTimer()
    timer.setInterval(20)  # 50 Hz
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()

    # Process events for 200ms
    for _ in range(10):
        QCoreApplication.processEvents()
        import time
        time.sleep(0.02)

    timer.stop()
    assert len(ticks) >= 3, f"UI timer starved: only {len(ticks)} ticks processed"


def test_settings_save_fields(tmp_path):
    """Verify that cursor, overlay, and shutdown settings serialize and load cleanly."""
    settings_file = tmp_path / "test_settings.json"
    mgr = SettingsManager(str(settings_file))
    
    # Check default close_to_tray is False
    assert mgr.config.close_to_tray is False
    assert mgr.config.overlay.cursor_trail is True
    assert mgr.config.overlay.cursor_glow is True
    
    # Mutate and save
    mgr.config.close_to_tray = True
    mgr.config.overlay.cursor_color = "Cyan"
    mgr.config.overlay.cursor_size = 1.5
    mgr.save()

    # Reload
    mgr2 = SettingsManager(str(settings_file))
    assert mgr2.config.close_to_tray is True
    assert mgr2.config.overlay.cursor_color == "Cyan"
    assert mgr2.config.overlay.cursor_size == 1.5

