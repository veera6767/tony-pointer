"""
Pointer V - Hardware Keystroke Dispatch via Win32 SendInput
Uses hardware scan codes (KEYEVENTF_SCANCODE) for authentic OS typing into any window,
with KEYEVENTF_UNICODE fallback for complex symbols.
Manages single-handed sticky modifiers (Shift, Ctrl, Alt, Win, CapsLock),
auto-shifting for symbol characters, and key repeats without double-applying Shift.
"""

import ctypes
import enum
import sys
import time
from typing import Callable, Dict, Optional, Set, Tuple

# Win32 Constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

VK_CAPITAL = 0x14


class ModifierState(enum.Enum):
    INACTIVE = "INACTIVE"
    LATCHED = "LATCHED"   # Single-tap: active for the immediate next key, then auto-releases
    LOCKED = "LOCKED"     # Double-tap: locked on until tapped again to release


# Ctypes structures for Win32 SendInput (aligned to Windows SDK x64 40-byte tagINPUT)
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


# Hardware Direct Scan Codes for US Keyboard Layout
SCAN_CODES: Dict[str, Tuple[int, bool]] = {
    # Key: (scancode, is_extended)
    "esc": (0x01, False),
    "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False),
    "5": (0x06, False), "6": (0x07, False), "7": (0x08, False), "8": (0x09, False),
    "9": (0x0A, False), "0": (0x0B, False), "-": (0x0C, False), "=": (0x0D, False),
    "backspace": (0x0E, False),
    "tab": (0x0F, False),
    "q": (0x10, False), "w": (0x11, False), "e": (0x12, False), "r": (0x13, False),
    "t": (0x14, False), "y": (0x15, False), "u": (0x16, False), "i": (0x17, False),
    "o": (0x18, False), "p": (0x19, False), "[": (0x1A, False), "]": (0x1B, False),
    "enter": (0x1C, False),
    "ctrl_l": (0x1D, False),
    "a": (0x1E, False), "s": (0x1F, False), "d": (0x20, False), "f": (0x21, False),
    "g": (0x22, False), "h": (0x23, False), "j": (0x24, False), "k": (0x25, False),
    "l": (0x26, False), ";": (0x27, False), "'": (0x28, False), "`": (0x29, False),
    "shift_l": (0x2A, False),
    "\\": (0x2B, False),
    "z": (0x2C, False), "x": (0x2D, False), "c": (0x2E, False), "v": (0x2F, False),
    "b": (0x30, False), "n": (0x31, False), "m": (0x32, False), ",": (0x33, False),
    ".": (0x34, False), "/": (0x35, False),
    "shift_r": (0x36, False),
    "alt_l": (0x38, False),
    "space": (0x39, False),
    "capslock": (0x3A, False),
    "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False), "f4": (0x3E, False),
    "f5": (0x3F, False), "f6": (0x40, False), "f7": (0x41, False), "f8": (0x42, False),
    "f9": (0x43, False), "f10": (0x44, False), "f11": (0x57, False), "f12": (0x58, False),

    # Extended Keys
    "ctrl_r": (0x1D, True),
    "alt_r": (0x38, True),
    "win": (0x5B, True),
    "home": (0x47, True),
    "up": (0x48, True),
    "pgup": (0x49, True),
    "left": (0x4B, True),
    "right": (0x4D, True),
    "end": (0x4F, True),
    "down": (0x50, True),
    "pgdn": (0x51, True),
    "ins": (0x52, True),
    "del": (0x53, True),
    "prtsc": (0x37, True),
    "pause": (0x45, True),
    "scrlk": (0x46, False),
}

# Shifted symbol map on standard US keyboard
SHIFT_SYMBOL_MAP: Dict[str, str] = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
    ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
    "~": "`",
}


class Win32KeyboardOutput:
    """Manages real OS keystroke emission and single-handed sticky modifier tracking."""

    def __init__(self, send_hook: Optional[Callable] = None):
        self.is_windows = sys.platform.startswith("win")
        self.user32 = ctypes.windll.user32 if self.is_windows else None
        self.send_hook = send_hook  # Optional mock injection for unit tests

        # Sticky Modifiers: "shift", "ctrl", "alt", "win", "caps"
        self.modifiers: Dict[str, ModifierState] = {
            "shift": ModifierState.INACTIVE,
            "ctrl": ModifierState.INACTIVE,
            "alt": ModifierState.INACTIVE,
            "win": ModifierState.INACTIVE,
            "caps": ModifierState.INACTIVE,
        }

        # Track currently physically pressed modifier scan keys
        self.held_scans: Set[int] = set()

        # Last tapped modifier for double-tap lock detection
        self.last_modifier_tap: Dict[str, float] = {}

        # Optional override for deterministic unit testing
        self._caps_lock_override: Optional[bool] = None

        # Diagnostics (NO KEY NAMES OR CHARACTERS STORED)
        self.last_sendinput_ret: int = 1
        self.last_sendinput_err: int = 0
        self.last_event_kind: str = "IDLE"

    def is_caps_lock_on(self) -> bool:
        """Inspects physical Windows Caps Lock toggle status."""
        if self._caps_lock_override is not None:
            return self._caps_lock_override
        if self.modifiers.get("caps") == ModifierState.LOCKED:
            return True
        if self.is_windows and self.user32 and not self.send_hook:
            try:
                return (self.user32.GetKeyState(VK_CAPITAL) & 0x0001) != 0
            except Exception:
                pass
        return False

    def _send_scan(self, scancode: int, is_extended: bool, is_up: bool):
        self.last_event_kind = "SCAN_UP" if is_up else "SCAN_DOWN"
        if self.send_hook:
            self.send_hook("scan", scancode, is_extended, is_up)
            return

        if not self.is_windows or not self.user32:
            return

        flags = KEYEVENTF_SCANCODE
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        if is_up:
            flags |= KEYEVENTF_KEYUP

        ki = KEYBDINPUT(
            wVk=0,
            wScan=scancode,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        inp = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki))
        ret = self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.last_sendinput_ret = ret
        if ret == 0:
            self.last_sendinput_err = ctypes.windll.kernel32.GetLastError()
        else:
            self.last_sendinput_err = 0

    def _send_unicode(self, char: str):
        """Sends exact unicode character directly via SendInput."""
        self.last_event_kind = "UNICODE"
        if self.send_hook:
            self.send_hook("unicode", char, False, False)
            return

        if not self.is_windows or not self.user32:
            return

        code_point = ord(char)

        # Key down
        ki_down = KEYBDINPUT(
            wVk=0,
            wScan=code_point,
            dwFlags=KEYEVENTF_UNICODE,
            time=0,
            dwExtraInfo=0,
        )
        inp_down = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki_down))
        ret = self.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
        self.last_sendinput_ret = ret
        if ret == 0:
            self.last_sendinput_err = ctypes.windll.kernel32.GetLastError()
        else:
            self.last_sendinput_err = 0

        time.sleep(0.005)

        # Key up
        ki_up = KEYBDINPUT(
            wVk=0,
            wScan=code_point,
            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=0,
        )
        inp_up = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki_up))
        self.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

    def toggle_modifier(self, mod_name: str) -> ModifierState:
        """
        Handles single-handed modifier latches:
        - 1 tap: LATCHED. Applies to next key, then auto-releases.
        - 2 taps within 450ms: LOCKED. Remains held until tapped again.
        """
        now = time.perf_counter()
        current = self.modifiers.get(mod_name, ModifierState.INACTIVE)
        last_tap = self.last_modifier_tap.get(mod_name, 0.0)

        if mod_name == "caps":
            # CapsLock is a toggle key on Windows
            self._send_scan(0x3A, False, is_up=False)
            self._send_scan(0x3A, False, is_up=True)
            new_state = ModifierState.INACTIVE if self.is_caps_lock_on() else ModifierState.LOCKED
            self.modifiers["caps"] = new_state
            self.last_modifier_tap[mod_name] = now
            return self.modifiers["caps"]

        if current == ModifierState.LOCKED:
            self.modifiers[mod_name] = ModifierState.INACTIVE
            self._apply_physical_modifier(mod_name, False)
        elif current == ModifierState.LATCHED:
            if (now - last_tap) < 0.45:
                self.modifiers[mod_name] = ModifierState.LOCKED
                self._apply_physical_modifier(mod_name, True)
            else:
                self.modifiers[mod_name] = ModifierState.INACTIVE
                self._apply_physical_modifier(mod_name, False)
        else:
            self.modifiers[mod_name] = ModifierState.LATCHED
            self._apply_physical_modifier(mod_name, True)

        self.last_modifier_tap[mod_name] = now
        return self.modifiers[mod_name]

    def _apply_physical_modifier(self, mod_name: str, press_down: bool):
        scan_map = {
            "shift": (0x2A, False), # Left shift
            "ctrl": (0x1D, False),  # Left ctrl
            "alt": (0x38, False),   # Left alt
            "win": (0x5B, True),    # Left win
        }
        if mod_name not in scan_map:
            return

        scan, ext = scan_map[mod_name]
        if press_down:
            self._send_scan(scan, ext, is_up=False)
            self.held_scans.add(scan)
        else:
            self._send_scan(scan, ext, is_up=True)
            self.held_scans.discard(scan)

    def send_key(self, key_code: str, char_to_send: Optional[str] = None, needs_shift: bool = False):
        """
        Sends the requested key to the active foreground application.
        Handles literal symbols, auto-shifting, and sticky modifier consumption without double-shifting.
        """
        # 1. Handle Sticky Modifiers click
        mod_keys = {
            "shift_l": "shift", "shift_r": "shift",
            "ctrl_l": "ctrl", "ctrl_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "win": "win",
            "capslock": "caps",
        }
        if key_code in mod_keys:
            self.toggle_modifier(mod_keys[key_code])
            return

        # 2. Check auto-shift requirements
        symbol_char = char_to_send if char_to_send and len(char_to_send) == 1 else None
        is_shifted_symbol = (symbol_char is not None and symbol_char in SHIFT_SYMBOL_MAP) or needs_shift

        shift_active = self.modifiers["shift"] != ModifierState.INACTIVE
        caps_on = self.is_caps_lock_on()

        if is_shifted_symbol and symbol_char in SHIFT_SYMBOL_MAP:
            base_key = SHIFT_SYMBOL_MAP[symbol_char]
            base_scan_info = SCAN_CODES.get(base_key)

            # Auto-press Shift if not already active
            need_temporary_shift = not shift_active
            if need_temporary_shift:
                self._send_scan(0x2A, False, is_up=False) # Shift down

            if base_scan_info:
                scan, ext = base_scan_info
                self._send_scan(scan, ext, is_up=False)
                time.sleep(0.01)
                self._send_scan(scan, ext, is_up=True)
            else:
                self._send_unicode(symbol_char)

            if need_temporary_shift:
                self._send_scan(0x2A, False, is_up=True) # Shift up

            # Consume sticky shift if it was latched
            if self.modifiers["shift"] == ModifierState.LATCHED:
                self.modifiers["shift"] = ModifierState.INACTIVE
                self._apply_physical_modifier("shift", False)

        elif symbol_char and symbol_char.isalpha():
            # Letter key with potential Caps Lock or Shift interaction
            lookup = symbol_char.lower()
            scan_info = SCAN_CODES.get(lookup)
            is_upper = symbol_char.isupper() or (shift_active ^ caps_on)

            if scan_info:
                scan, ext = scan_info
                need_temp_shift = is_upper and not shift_active and not caps_on
                if need_temp_shift:
                    self._send_scan(0x2A, False, is_up=False)

                self._send_scan(scan, ext, is_up=False)
                time.sleep(0.01)
                self._send_scan(scan, ext, is_up=True)

                if need_temp_shift:
                    self._send_scan(0x2A, False, is_up=True)
            else:
                self._send_unicode(symbol_char)

        elif symbol_char and symbol_char not in SCAN_CODES:
            self._send_unicode(symbol_char)
        else:
            # Standard Scan Code dispatch (Numbers, Enter, Space, Arrows, F1-F12)
            lookup = key_code.lower()
            if lookup in SCAN_CODES:
                scan, ext = SCAN_CODES[lookup]
                self._send_scan(scan, ext, is_up=False)
                time.sleep(0.01)
                self._send_scan(scan, ext, is_up=True)
            elif symbol_char:
                self._send_unicode(symbol_char)

        # 3. Release any LATCHED modifiers (single-use sticky behavior)
        for mod, state in list(self.modifiers.items()):
            if state == ModifierState.LATCHED:
                self.modifiers[mod] = ModifierState.INACTIVE
                self._apply_physical_modifier(mod, False)

    def release_all_modifiers(self):
        """Safety guarantee: releases all held physical keys on exit, lost hand, or pause."""
        for scan in list(self.held_scans):
            self._send_scan(scan, False, is_up=True)
            self._send_scan(scan, True, is_up=True)
        self.held_scans.clear()

        for mod in self.modifiers:
            self.modifiers[mod] = ModifierState.INACTIVE
