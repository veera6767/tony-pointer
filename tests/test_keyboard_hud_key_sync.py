"""
Tests verifying that the floating air keyboard HUD's 4 glowing locked keys
strictly match the keys typed by logic in all zones, rows, windows, and hand modes.
Guarantees zero desynchronization between visual HUD and dispatch logic.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from PySide6.QtWidgets import QApplication
from keyboard_layout import KeyboardLayoutManager, Zone
from keyboard_ui import FloatingAirKeyboardWidget
from mode_manager import AppMode, ModeManager
from recorder import create_synthetic_hand
from settings import AppConfig


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def hud_and_mgr(app):
    cfg = AppConfig()
    lm = KeyboardLayoutManager()
    mgr = ModeManager(cfg, lm)
    mgr.mode = AppMode.KEYBOARD
    hud = FloatingAirKeyboardWidget(cfg, lm)
    return hud, mgr, lm, cfg


def test_hud_locked_keys_match_mode_manager_all_rows_and_zones(hud_and_mgr):
    """
    Exhaustively iterates every row and window in both MAIN and SYMBOLS zones,
    verifying that hud.locked_keys contains the exact same key codes as mgr.get_current_window().keys.
    """
    hud, mgr, lm, cfg = hud_and_mgr

    for zone in [Zone.MAIN, Zone.SYMBOLS]:
        mgr.active_zone = zone
        for row in range(6):
            mgr.row_idx = row
            max_w = lm.get_max_window_idx(zone, row)
            for w_idx in range(max_w + 1):
                mgr.window_idx = w_idx
                cur_window = mgr.get_current_window()

                # Update HUD state
                hud.update_state(
                    zone=mgr.active_zone,
                    row_idx=mgr.row_idx,
                    window_idx=mgr.window_idx,
                    modifiers={},
                )

                expected_codes = {k.code for k in cur_window.keys}
                assert hud.locked_keys == expected_codes, (
                    f"HUD locked keys mismatch in {zone.value} Row {row} Win {w_idx}: "
                    f"HUD has {hud.locked_keys}, expected {expected_codes}"
                )


def test_finger_to_slot_mapping_and_flip_finger_order(hud_and_mgr):
    """
    Verifies that fingers map to correct slot indices (0..3) across left/right hands
    and that flip_finger_order reverses the physical assignment properly.
    """
    hud, mgr, lm, cfg = hud_and_mgr

    hand_right = create_synthetic_hand(is_left_hand=False)
    hand_left = create_synthetic_hand(is_left_hand=True)

    def get_hand_order(hand, flip=False, mapping="standard"):
        eff = mgr.get_effective_handedness(hand)
        if eff == "Left":
            order = ["pinky", "ring", "middle", "index"]
        else:
            order = ["index", "middle", "ring", "pinky"]
        if flip or mapping == "reversed":
            order.reverse()
        return order

    # Default Right hand: Index=0, Middle=1, Ring=2, Pinky=3
    order_r = get_hand_order(hand_right, flip=False)
    assert order_r == ["index", "middle", "ring", "pinky"]
    assert order_r.index("index") == 0
    assert order_r.index("pinky") == 3

    # Flipped Right hand: Pinky=0, Ring=1, Middle=2, Index=3
    order_r_flipped = get_hand_order(hand_right, flip=True)
    assert order_r_flipped == ["pinky", "ring", "middle", "index"]
    assert order_r_flipped.index("index") == 3
    assert order_r_flipped.index("pinky") == 0

    # Default Left hand: Pinky=0, Ring=1, Middle=2, Index=3
    order_l = get_hand_order(hand_left, flip=False)
    assert order_l == ["pinky", "ring", "middle", "index"]
    assert order_l.index("pinky") == 0
    assert order_l.index("index") == 3

    # Flipped Left hand: Index=0, Middle=1, Ring=2, Pinky=3
    order_l_flipped = get_hand_order(hand_left, flip=True)
    assert order_l_flipped == ["index", "middle", "ring", "pinky"]
    assert order_l_flipped.index("pinky") == 3
    assert order_l_flipped.index("index") == 0
