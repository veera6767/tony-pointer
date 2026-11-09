"""
Pointer V - Headless UI Screenshot Generator
Runs with QT_QPA_PLATFORM=offscreen, renders every page, keyboard HUD, and tutorial dialog,
and outputs high-resolution PNG screenshots into docs/screenshots/.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication

from keyboard_layout import KeyboardLayoutManager, Zone
from keyboard_out import ModifierState
from keyboard_ui import FloatingAirKeyboardWidget
from mouse import MouseController
from recorder import LandmarkRecorder
from settings import SettingsManager
from ui.main_window import MainWindow
from ui.tutorial_dialog import TutorialDialog


def capture_all_screenshots():
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)

    settings_manager = SettingsManager()
    mouse = MouseController()
    recorder = LandmarkRecorder()

    dummy_telemetry = {
        "fps": 59.8,
        "latency_ms": 7.4,
        "mode": "POINTER",
        "pose": "POINTING",
        "action": "MOVE",
        "status_text": "POINTING (TRACKING OK)",
        "brush_locked": False,
        "foreground_app": "DESKTOP",
        "raw_hand": None,
        "kb_zone": "MAIN",
        "kb_row": 3,
        "kb_win_keys": ["A", "S", "D", "F"],
        "curls": {"thumb": 0.1, "index": 0.05, "middle": 0.85, "ring": 0.90, "pinky": 0.92},
        "is_paused": False,
        "is_active": True,
        "camera_connected": True,
        "is_low_light": False,
        "is_over_exposed": False,
        "camera_brightness": 124.0,
        "monitor_count": 1,
        "total_frames": 1840,
        "frames_with_hand": 1820,
        "active_pos": (0.512, 0.428),
        "screen_coords": (980, 540),
        "mouse_sendinput_ret": 1,
        "mouse_sendinput_err": 0,
        "mouse_last_action": "MOVE",
        "key_sendinput_ret": 1,
        "key_sendinput_err": 0,
        "key_last_action": "IDLE",
        "internal_errors": [],
    }

    win = MainWindow(
        settings_manager=settings_manager,
        mouse_controller=mouse,
        recorder=recorder,
        get_status_fn=lambda: dummy_telemetry,
        get_frame_fn=lambda: None,
        keyboard_output=None,
    )
    win.resize(1120, 720)
    win.show()

    # Capture every page in the stacked deck
    page_names = [
        "dashboard",
        "camera",
        "gestures",
        "keyboard",
        "practice",
        "settings",
        "calibration",
        "about",
        "developer"
    ]

    for i, name in enumerate(page_names):
        win.deck.setCurrentIndex(i)
        app.processEvents()
        pix = win.grab()
        file_path = out_dir / f"{i}_{name}.png"
        pix.save(str(file_path), "PNG")
        print(f"Captured: {file_path.name}")

    # Capture Floating Air Keyboard HUD
    layout_mgr = KeyboardLayoutManager()
    kb_hud = FloatingAirKeyboardWidget(settings_manager.config, layout_mgr)
    kb_hud.resize(980, 360)
    kb_hud.update_state(
        zone=Zone.MAIN,
        row_idx=3,
        window_idx=0,
        modifiers={"shift": ModifierState.INACTIVE, "ctrl": ModifierState.INACTIVE, "alt": ModifierState.INACTIVE, "win": ModifierState.INACTIVE, "caps": ModifierState.INACTIVE}
    )
    kb_hud.show()
    app.processEvents()
    kb_pix = kb_hud.grab()
    kb_file = out_dir / "keyboard_hud.png"
    kb_pix.save(str(kb_file), "PNG")
    print(f"Captured: {kb_file.name}")

    # Capture Tutorial Dialog
    tut = TutorialDialog(settings_manager.config, lambda: dummy_telemetry)
    tut.show()
    app.processEvents()
    tut_pix = tut.grab()
    tut_file = out_dir / "tutorial_dialog.png"
    tut_pix.save(str(tut_file), "PNG")
    print(f"Captured: {tut_file.name}")

    # Capture Camera Preview Overlay
    from preview import CameraPreviewOverlay
    prev = CameraPreviewOverlay(settings_manager.config)
    prev.show()
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    prev.update_frame(dummy_frame, fps=59.4)
    app.processEvents()
    prev_pix = prev.grab()
    prev_file = out_dir / "camera_preview_overlay.png"
    prev_pix.save(str(prev_file), "PNG")
    print(f"Captured: {prev_file.name}")

    print("All screenshots generated successfully.")

if __name__ == "__main__":
    capture_all_screenshots()

