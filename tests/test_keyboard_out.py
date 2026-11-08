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


def test_caps_lock_on_with_shifted_symbol():
    """Caps ON + '!' must still send Shift down/up with base key '1', since CapsLock only affects letters."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)
    kb._caps_lock_override = True

    kb.send_key("exclamation", char_to_send="!", needs_shift=True)

    # Must send Shift down (0x2A), base key 1 down (0x02), base key 1 up (0x02), Shift up (0x2A)
    assert len(mock.events) == 4
    assert mock.events[0] == ("scan", 0x2A, False, False)
    assert mock.events[1] == ("scan", 0x02, False, False)
    assert mock.events[2] == ("scan", 0x02, False, True)
    assert mock.events[3] == ("scan", 0x2A, False, True)


def test_caps_lock_on_with_letter():
    """Caps ON + 'a' should dispatch base key 'a' (0x1E) without adding Shift, because CapsLock alone handles uppercase in Windows."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)
    kb._caps_lock_override = True

    kb.send_key("a", char_to_send="a", needs_shift=False)

    # Shift (0x2A) must NOT be sent; only 'a' (0x1E) down and up
    scans_sent = [e[1] for e in mock.events]
    assert 0x2A not in scans_sent
    assert mock.events == [("scan", 0x1E, False, False), ("scan", 0x1E, False, True)]


def test_shift_latched_with_shifted_symbol():
    """Shift latched + '!' sends base key '1' (0x02) without double-pressing Shift, then consumes latched Shift."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)
    kb._caps_lock_override = False

    kb.toggle_modifier("shift") # Latch Shift (emits 0x2A down)
    assert kb.modifiers["shift"] == ModifierState.LATCHED
    mock.events.clear()

    kb.send_key("exclamation", char_to_send="!", needs_shift=True)

    # Only sends base key '1' down/up, then releases latched Shift
    down_scans = [e[1] for e in mock.events if not e[3]]
    assert down_scans == [0x02], "Shift down was erroneously double-applied!"
    # Latched Shift is consumed and released
    assert mock.events[-1] == ("scan", 0x2A, False, True)
    assert kb.modifiers["shift"] == ModifierState.INACTIVE


def test_shift_latched_with_letter():
    """Shift latched + 'a' sends base key 'a' (0x1E) under existing physical Shift, then consumes latched Shift."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)
    kb._caps_lock_override = False

    kb.toggle_modifier("shift") # Latch Shift
    mock.events.clear()

    kb.send_key("a", char_to_send="a", needs_shift=False)

    down_scans = [e[1] for e in mock.events if not e[3]]
    assert down_scans == [0x1E]
    # Latched Shift is released after typing
    assert mock.events[-1] == ("scan", 0x2A, False, True)
    assert kb.modifiers["shift"] == ModifierState.INACTIVE


def test_neither_shift_nor_caps_with_shifted_symbol():
    """Neither Shift nor CapsLock + '!' sends Shift down, base key '1' down/up, and Shift up."""
    mock = MockSendInputDispatcher()
    kb = Win32KeyboardOutput(send_hook=mock)
    kb._caps_lock_override = False

    kb.send_key("exclamation", char_to_send="!", needs_shift=True)

    assert len(mock.events) == 4
    assert mock.events[0] == ("scan", 0x2A, False, False)
    assert mock.events[1] == ("scan", 0x02, False, False)
    assert mock.events[2] == ("scan", 0x02, False, True)
    assert mock.events[3] == ("scan", 0x2A, False, True)


