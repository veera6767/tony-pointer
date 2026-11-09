"""
Pointer V - Corner Keyboard & Caps Lock Tests
Tests corner docking calculation, work area clamping, drag snap math,
avoiding active window, and Caps Lock behavior for letters vs symbols.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication
from keyboard_layout import KeyboardLayoutManager
from keyboard_ui import FloatingAirKeyboardWidget
from settings import SettingsManager
from keyboard_out import ModifierState, Win32KeyboardOutput


class MockSendInputDispatcher:
    def __init__(self):
        self.events = []

    def __call__(self, event_type, code, is_vk, is_up):
        self.events.append((event_type, code, is_vk, is_up))


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def hud(app):
    sm = SettingsManager()
    lm = KeyboardLayoutManager()
    h = FloatingAirKeyboardWidget(sm.config, lm)
    return h


class MockScreen:
    def __init__(self, rect: QRect):
        self._rect = rect

    def availableGeometry(self) -> QRect:
        return self._rect

    def geometry(self) -> QRect:
        return self._rect


def test_corner_docking_positions(hud):
    """Verifies that corner docking calculates correct positions inside work area."""
    work_area = QRect(0, 0, 1920, 1040)  # Standard 1080p with 40px taskbar at bottom
    screen = MockScreen(work_area)
    hud.setFixedSize(768, 280)
    margin = 16

    # Bottom-right
    pos_br = hud.calculate_corner_position("bottom-right", screen=screen)
    expected_x = work_area.right() - hud.width() - margin
    expected_y = work_area.bottom() - hud.height() - margin
    assert pos_br.x() == expected_x
    assert pos_br.y() == expected_y

    # Bottom-left
    pos_bl = hud.calculate_corner_position("bottom-left", screen=screen)
    assert pos_bl.x() == work_area.left() + margin
    assert pos_bl.y() == expected_y

    # Bottom-center
    pos_bc = hud.calculate_corner_position("bottom-center", screen=screen)
    assert pos_bc.x() == work_area.left() + (work_area.width() - hud.width()) // 2
    assert pos_bc.y() == expected_y

    # Top-right
    pos_tr = hud.calculate_corner_position("top-right", screen=screen)
    assert pos_tr.x() == expected_x
    assert pos_tr.y() == work_area.top() + margin

    # Top-left
    pos_tl = hud.calculate_corner_position("top-left", screen=screen)
    assert pos_tl.x() == work_area.left() + margin
    assert pos_tl.y() == work_area.top() + margin


def test_work_area_clamping(hud):
    """Verifies that the keyboard never overlaps the taskbar or falls off-screen."""
    # Simulated top taskbar (work area starts at y=48)
    work_area = QRect(0, 48, 1920, 1032)
    screen = MockScreen(work_area)
    hud.setFixedSize(768, 280)
    pos = hud.calculate_corner_position("top-left", screen=screen)
    assert pos.y() >= 48 + 16

    # Simulated left taskbar (work area starts at x=64)
    work_area_left = QRect(64, 0, 1856, 1080)
    screen_l = MockScreen(work_area_left)
    pos_l = hud.calculate_corner_position("top-left", screen=screen_l)
    assert pos_l.x() >= 64 + 16


def test_nearest_corner_snap(hud, monkeypatch):
    """Verifies Euclidean distance nearest corner resolution."""
    work_area = QRect(0, 0, 1920, 1080)
    screen = MockScreen(work_area)
    hud.setFixedSize(768, 280)
    monkeypatch.setattr(hud, "_get_target_screen", lambda: screen)

    # Place window near top-right
    hud.move(1700, 50)
    corner = hud._snap_to_nearest_corner()
    assert corner == "top-right"

    # Place window near bottom-left
    hud.move(50, 900)
    corner = hud._snap_to_nearest_corner()
    assert corner == "bottom-left"

    # Place window near bottom-center
    hud.move(600, 900)
    corner = hud._snap_to_nearest_corner()
    assert corner == "bottom-center"


def test_caps_lock_rules():
    """
    Caps Lock Rule Verification:
    - Caps Lock ON affects ONLY letters (VK_A through VK_Z).
    - Shifted symbols (!, @, #, $, etc.) ALWAYS send Shift + base key,
      regardless of Caps Lock state.
    """
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)

    # 1. Caps Lock ON + symbol "!" -> sends Shift (0x2A) down, base key down, base key up, Shift up
    kb.toggle_modifier("caps")
    assert kb.modifiers["caps"] == ModifierState.LOCKED
    mock.events.clear()

    kb.send_key("exclamation", char_to_send="!", needs_shift=True)
    scans_sent = [e[1] for e in mock.events if not e[3]]  # down events
    assert 0x2A in scans_sent, "Shift down must be sent for '!' even with Caps Lock ON"

    # 2. Caps Lock ON + letter "a" -> sends base key "a" (Caps Lock state in OS capitalizes it)
    mock.events.clear()
    kb.send_key("a", char_to_send="a", needs_shift=False)
    a_scans = [e[1] for e in mock.events if not e[3]]
    # Scan code for 'a' is 0x1E
    assert 0x1E in a_scans
    assert 0x2A not in a_scans, "Shift must NOT be artificially forced for letter 'a' when Caps Lock is already ON"

    # 3. Shift latched + symbol "!" -> Shift already held, does not double-down
    kb.modifiers["caps"] = ModifierState.INACTIVE
    kb.toggle_modifier("shift")
    mock.events.clear()
    kb.send_key("exclamation", char_to_send="!", needs_shift=True)
    shift_excl_scans = [e[1] for e in mock.events if not e[3]]
    assert shift_excl_scans == [0x02], "Base key 0x02 only, no double Shift down"

    # 4. Shift latched + letter "a" -> Shift down already active, sends 'a'
    kb.toggle_modifier("shift")
    mock.events.clear()
    kb.send_key("a", char_to_send="A", needs_shift=False)
    shift_a_scans = [e[1] for e in mock.events if not e[3]]
    assert 0x1E in shift_a_scans

    # 5. Neither + symbol "!" -> sends Shift + base key
    kb.modifiers["caps"] = ModifierState.INACTIVE
    kb.modifiers["shift"] = ModifierState.INACTIVE
    mock.events.clear()
    kb.send_key("exclamation", char_to_send="!", needs_shift=True)
    neither_scans = [e[1] for e in mock.events if not e[3]]
    assert 0x2A in neither_scans
    assert 0x02 in neither_scans
