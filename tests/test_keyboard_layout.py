"""
Unit tests for KeyboardLayoutManager, 4-key progressive window builder,
clamping, and complete reachability of all keys in every row.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from keyboard_layout import KeyboardLayoutManager, Zone, MAIN_ROWS_RAW, SYMBOL_ROWS_RAW


def test_every_key_is_reachable_main():
    """Verify every key in every row of the Main Keyboard layout is covered in at least one window."""
    mgr = KeyboardLayoutManager()

    for row_idx, raw_keys in enumerate(MAIN_ROWS_RAW):
        windows = mgr.main_windows[row_idx]
        assert len(windows) > 0

        covered_codes = set()
        for win in windows:
            assert len(win.keys) == 4, f"Window in row {row_idx} must have exactly 4 keys"
            for k in win.keys:
                covered_codes.add(k.code)

        for raw_k in raw_keys:
            assert raw_k.code in covered_codes, (
                f"Key '{raw_k.label}' ({raw_k.code}) in row {row_idx} of MAIN is not reachable!"
            )


def test_every_key_is_reachable_symbols():
    """Verify every key in every row of the Symbols Panel is covered in at least one window."""
    mgr = KeyboardLayoutManager()

    for row_idx, raw_keys in enumerate(SYMBOL_ROWS_RAW):
        windows = mgr.symbol_windows[row_idx]
        assert len(windows) > 0

        covered_codes = set()
        for win in windows:
            assert len(win.keys) == 4, f"Window in row {row_idx} must have exactly 4 keys"
            for k in win.keys:
                covered_codes.add(k.code)

        for raw_k in raw_keys:
            assert raw_k.code in covered_codes, (
                f"Key '{raw_k.label}' ({raw_k.code}) in row {row_idx} of SYMBOLS is not reachable!"
            )


def test_final_window_clamped_to_exact_last_4_keys():
    """The last window of any row must be clamped to the exact final 4 keys of that row."""
    mgr = KeyboardLayoutManager()

    for zone in (Zone.MAIN, Zone.SYMBOLS):
        rows = mgr.main_rows if zone == Zone.MAIN else mgr.symbol_rows
        for row_idx, raw_keys in enumerate(rows):
            max_w_idx = mgr.get_max_window_idx(zone, row_idx)
            last_win = mgr.get_window(zone, row_idx, max_w_idx)

            expected_last_4 = [k.code for k in raw_keys[-4:]]
            actual_last_4 = [k.code for k in last_win.keys]
            assert actual_last_4 == expected_last_4, (
                f"Zone {zone.value} Row {row_idx} final window does not clamp to the last 4 keys!"
            )

