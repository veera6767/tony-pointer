"""
Pointer V - Native Win32 RegisterHotKey Manager
Replaces problematic WH_KEYBOARD_LL low-level hooks with clean, OS-native
RegisterHotKey APIs that post WM_HOTKEY messages directly to the window message pump.
Zero hook timeouts, zero GIL contention, and immune to OS hook drops.
"""

import ctypes
import sys
from typing import Callable, Dict

# Win32 Constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Virtual Key Codes
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_K = 0x4B
VK_P = 0x50
VK_S = 0x53
VK_T = 0x54

# Hotkey Identifiers
HOTKEY_ID_TOGGLE = 1001       # Ctrl+Alt+T
HOTKEY_ID_KEYBOARD = 1002     # Ctrl+Alt+K
HOTKEY_ID_ZONE = 1003         # Ctrl+Alt+S
HOTKEY_ID_PAINT = 1004        # Ctrl+Alt+P
HOTKEY_ID_PAUSE = 1005        # Ctrl+Alt+Space
HOTKEY_ID_ESC = 1006          # Esc (when active)
HOTKEY_ID_PANIC = 1007        # Ctrl+Alt+Shift+Esc (Panic Force Release & Exit)


class Win32HotKeyManager:
    """Manages system-wide global hotkeys via Win32 RegisterHotKey."""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.is_windows = sys.platform.startswith("win")
        self.user32 = ctypes.windll.user32 if self.is_windows else None
        self.callbacks: Dict[int, Callable[[], None]] = {}
        self.registered_ids: set[int] = set()

    def register(self, hotkey_id: int, modifiers: int, vk: int, callback: Callable[[], None]) -> bool:
        if not self.user32 or not self.hwnd:
            return False

        # Apply MOD_NOREPEAT to avoid rapid repeat message flooding
        mods = modifiers | MOD_NOREPEAT
        success = self.user32.RegisterHotKey(self.hwnd, hotkey_id, mods, vk)
        if success:
            self.callbacks[hotkey_id] = callback
            self.registered_ids.add(hotkey_id)
            return True
        else:
            err = ctypes.windll.kernel32.GetLastError()
            print(f"[HotKeys] Warning: RegisterHotKey({hotkey_id}) failed with code {err}")
            return False

    def unregister(self, hotkey_id: int):
        if self.user32 and self.hwnd and hotkey_id in self.registered_ids:
            self.user32.UnregisterHotKey(self.hwnd, hotkey_id)
            self.registered_ids.discard(hotkey_id)
            self.callbacks.pop(hotkey_id, None)

    def unregister_all(self):
        if not self.user32 or not self.hwnd:
            return
        for hid in list(self.registered_ids):
            self.user32.UnregisterHotKey(self.hwnd, hid)
        self.registered_ids.clear()
        self.callbacks.clear()

    def handle_wm_hotkey(self, hotkey_id: int) -> bool:
        """Invoked when WM_HOTKEY message is received by the window."""
        cb = self.callbacks.get(hotkey_id)
        if cb:
            cb()
            return True
        return False
