"""
Tony Pointer - Hardware-Level Mouse Emulation via Win32 SendInput
Uses ctypes to invoke user32.dll SendInput with MOUSEEVENTF_ABSOLUTE and
MOUSEEVENTF_VIRTUALDESK. Unlike PyAutoGUI or mouse_event, SendInput sends
scancode/hardware level input events accepted by all modern Windows applications,
UAC prompts, DirectX/Vulkan games, and creative suites (Photoshop, Krita, Paint).
"""

import ctypes
import os
import sys
import time
from typing import Optional, Tuple

# Win32 Constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x000C
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Ctypes Structures for Win32 SendInput
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


class MouseController:
    """High-performance Win32 SendInput Mouse Controller."""

    def __init__(self):
        self.is_windows = sys.platform.startswith("win")
        self.is_left_down = False
        self.last_pos = (0, 0)

        if self.is_windows:
            self.user32 = ctypes.windll.user32
            # Configure DPI awareness so coordinates match real physical monitor pixels
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor DPI aware
            except Exception:
                try:
                    self.user32.SetProcessDPIAware()
                except Exception:
                    pass
        else:
            self.user32 = None

    def get_screen_bounds(self) -> Tuple[int, int, int, int]:
        """
        Returns (x_origin, y_origin, width, height) of the virtual desktop,
        seamlessly spanning all connected monitors.
        """
        if not self.is_windows:
            return (0, 0, 1920, 1080)

        vx = self.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = self.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = self.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return (vx, vy, vw, vh)

    def _normalize_to_virtual_desktop(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """
        Transforms pixel coordinates into the 0..65535 normalized space
        required by MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK.
        """
        vx, vy, vw, vh = self.get_screen_bounds()
        if vw <= 0 or vh <= 0:
            return 0, 0

        norm_x = int(((screen_x - vx) * 65535) / (vw - 1))
        norm_y = int(((screen_y - vy) * 65535) / (vh - 1))
        return norm_x, norm_y

    def _send_input(self, flags: int, data: int = 0, dx: int = 0, dy: int = 0):
        if not self.is_windows:
            return

        extra = ctypes.c_ulong(0)
        mi = MOUSEINPUT(
            dx=dx,
            dy=dy,
            mouseData=data,
            dwFlags=flags,
            time=0,
            dwExtraInfo=ctypes.pointer(extra),
        )
        inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def move_to(self, screen_x: int, screen_y: int):
        """Move cursor instantly to absolute desktop coordinates."""
        self.last_pos = (screen_x, screen_y)
        if not self.is_windows:
            return

        norm_x, norm_y = self._normalize_to_virtual_desktop(screen_x, screen_y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(flags=flags, dx=norm_x, dy=norm_y)

    def left_down(self):
        """Press and hold left mouse button down (used by Brush Lock / drag)."""
        if not self.is_left_down:
            self._send_input(flags=MOUSEEVENTF_LEFTDOWN)
            self.is_left_down = True

    def left_up(self):
        """Release left mouse button."""
        if self.is_left_down:
            self._send_input(flags=MOUSEEVENTF_LEFTUP)
            self.is_left_down = False

    def click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Standard left click (Down then Up)."""
        if x is not None and y is not None:
            self.move_to(x, y)
        self._send_input(flags=MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.015)  # Realistic tactile hold duration
        self._send_input(flags=MOUSEEVENTF_LEFTUP)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Rapid double left click for opening folders, shortcuts, and files."""
        if x is not None and y is not None:
            self.move_to(x, y)
        self.click()
        time.sleep(0.045)
        self.click()

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Right click for context menus."""
        if x is not None and y is not None:
            self.move_to(x, y)
        self._send_input(flags=MOUSEEVENTF_RIGHTDOWN)
        time.sleep(0.02)
        self._send_input(flags=MOUSEEVENTF_RIGHTUP)

    def scroll(self, amount: int):
        """
        Scroll mouse wheel.
        amount > 0 = scroll up, amount < 0 = scroll down.
        WHEEL_DELTA is 120 per notch.
        """
        delta = int(amount * 120)
        self._send_input(flags=MOUSEEVENTF_WHEEL, data=delta)

    def emergency_release(self):
        """Guarantees all mouse buttons are released safely on lost hand or exit."""
        if self.is_left_down:
            self.left_up()
        self._send_input(flags=MOUSEEVENTF_LEFTUP)
        self._send_input(flags=MOUSEEVENTF_RIGHTUP)
        self.is_left_down = False

    def get_active_process_name(self) -> Optional[str]:
        """Inspects the currently focused foreground window on Windows."""
        if not self.is_windows:
            return None

        try:
            import psutil
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = ctypes.c_ulong()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                proc = psutil.Process(pid.value)
                return proc.name().lower()
        except Exception:
            pass
        return None
