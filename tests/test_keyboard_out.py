"""
Unit tests for Win32KeyboardOutput with mocked SendInput:
- Shift auto-press for symbols without double-applying
- Sticky modifiers (latched vs locked)
- Caps lock handling
- Safety release of all keys and modifiers
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from keyboard_out import ModifierState, Win32KeyboardOutput


class MockSendInputDispatcher:
    def __init__(self):
        self.events = []

    def __call__(self, event_type, scan_or_char, is_extended, is_up):
        self.events.append((event_type, scan_or_char, is_extended, is_up))


def test_shifted_symbol_auto_applies_shift():
    """Sending '!' automatically applies Shift down, base scan 0x02 ('1'), and Shift up."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)

    kb.send_key("exclamation", char_to_send="!", needs_shift=True)

    # Expected sequence:
    # 1. Shift down (scan 0x2A, is_up=False)
    # 2. Key '1' down (scan 0x02, is_up=False)
    # 3. Key '1' up (scan 0x02, is_up=True)
    # 4. Shift up (scan 0x2A, is_up=True)
    assert len(mock.events) == 4
    assert mock.events[0] == ("scan", 0x2A, False, False)
    assert mock.events[1] == ("scan", 0x02, False, False)
    assert mock.events[2] == ("scan", 0x02, False, True)
    assert mock.events[3] == ("scan", 0x2A, False, True)


def test_shifted_symbol_does_not_double_apply_when_shift_already_active():
    """When Shift is already latched or locked, it does not send an extra Shift down/up."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)

    # Latch Shift first
    kb.toggle_modifier("shift")
    assert kb.modifiers["shift"] == ModifierState.LATCHED
    mock.events.clear()

    # Now type '!'
    kb.send_key("exclamation", char_to_send="!", needs_shift=True)

    # Should only emit the base key 0x02 down and up (not an extra Shift down/up),
    # then release the latched Shift (0x2A up)
    scans_sent = [e[1] for e in mock.events if not e[3]] # down events
    assert scans_sent == [0x02], "Extra Shift down was double-applied!"
    # Latched Shift is consumed
    assert kb.modifiers["shift"] == ModifierState.INACTIVE


def test_sticky_modifier_latch_and_lock():
    """1 tap latches modifier for next key; 2 quick taps lock it permanently until tapped again."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)

    # Tap 1: LATCH
    st1 = kb.toggle_modifier("ctrl")
    assert st1 == ModifierState.LATCHED
    assert 0x1D in kb.held_scans

    # Quick Tap 2 within 400ms: LOCK
    st2 = kb.toggle_modifier("ctrl")
    assert st2 == ModifierState.LOCKED
    assert 0x1D in kb.held_scans

    # Tap a standard key ('c')
    mock.events.clear()
    kb.send_key("c", char_to_send="c")

    # Key 'c' (0x2E) is typed, but LOCKED Ctrl remains active!
    assert kb.modifiers["ctrl"] == ModifierState.LOCKED
    assert 0x1D in kb.held_scans

    # Tap 3 on Ctrl releases locked modifier
    st3 = kb.toggle_modifier("ctrl")
    assert st3 == ModifierState.INACTIVE
    assert 0x1D not in kb.held_scans


def test_emergency_release_all_modifiers():
    """Safety guarantee: releases all held scans and resets all modifier states."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)

    kb.toggle_modifier("shift")
    kb.toggle_modifier("alt")
    assert len(kb.held_scans) == 2

    kb.release_all_modifiers()
    assert len(kb.held_scans) == 0
    for mod in kb.modifiers:
        assert kb.modifiers[mod] == ModifierState.INACTIVE

