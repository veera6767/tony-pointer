"""
Pointer V - Hardware-Level Mouse Emulation via Win32 SendInput
Uses ctypes to invoke user32.dll SendInput with MOUSEEVENTF_ABSOLUTE and
MOUSEEVENTF_VIRTUALDESK. Sets Per-Monitor DPI Awareness V2 so coordinates
line up perfectly with physical pixels across mixed-DPI multi-monitor setups.
"""

import ctypes
from ctypes import wintypes
import os
import sys
import time
from typing import List, Optional, Tuple

# Win32 Constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
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


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


class MouseController:
    """High-performance Win32 SendInput Mouse Controller with multi-monitor support."""

    def __init__(self, send_hook: Optional[callable] = None):
        self.is_windows = sys.platform.startswith("win")
        self.is_left_down = False
        self.last_pos = (0, 0)
        self.send_hook = send_hook
        self.monitors: List[Tuple[int, int, int, int]] = []

        if self.is_windows:
            self.user32 = ctypes.windll.user32
            # Per-Monitor DPI Awareness V2 (-4)
            self._enable_dpi_v2()
            self.refresh_monitors()
        else:
            self.user32 = None

    def _enable_dpi_v2(self):
        """Enables Per-Monitor DPI Awareness V2 for pixel-perfect multi-monitor accuracy."""
        try:
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            self.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            return
        except Exception:
            pass

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass

        try:
            self.user32.SetProcessDPIAware()
        except Exception:
            pass

    def refresh_monitors(self) -> List[Tuple[int, int, int, int]]:
        """Enumerates all active display monitors: (left, top, width, height)."""
        if not self.is_windows or not self.user32:
            self.monitors = [(0, 0, 1920, 1080)]
            return self.monitors

        monitors = []

        def _enum_callback(hmonitor, hdc, lprect, lparam):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if self.user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
                r = mi.rcMonitor
                monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        try:
            self.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_callback), 0)
        except Exception:
            pass

        if not monitors:
            vx, vy, vw, vh = self.get_virtual_desktop_bounds()
            monitors.append((vx, vy, vw, vh))

        self.monitors = monitors
        return self.monitors

    def get_virtual_desktop_bounds(self) -> Tuple[int, int, int, int]:
        """Returns (x_origin, y_origin, width, height) of the entire virtual desktop."""
        if not self.is_windows or not self.user32:
            return (0, 0, 1920, 1080)

        vx = self.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = self.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = self.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return (vx, vy, vw, vh)

    def get_target_bounds(self, monitor_index: int = -1) -> Tuple[int, int, int, int]:
        """
        Returns active bounds for cursor remapping:
        -1: Full virtual desktop (all monitors)
        >= 0: Specific monitor bounds
        """
        if monitor_index < 0 or monitor_index >= len(self.monitors):
            return self.get_virtual_desktop_bounds()
        return self.monitors[monitor_index]

    def normalize_to_virtual_desktop(
        self,
        screen_x: int,
        screen_y: int,
        virtual_bounds: Optional[Tuple[int, int, int, int]] = None
    ) -> Tuple[int, int]:
        """
        Transforms pixel coordinates into the 0..65535 normalized space
        required by MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK.
        """
        vx, vy, vw, vh = virtual_bounds or self.get_virtual_desktop_bounds()
        if vw <= 1 or vh <= 1:
            return 0, 0

        norm_x = int(((screen_x - vx) * 65535) / max(1, vw - 1))
        norm_y = int(((screen_y - vy) * 65535) / max(1, vh - 1))
        # Clamp to 0..65535
        norm_x = max(0, min(65535, norm_x))
        norm_y = max(0, min(65535, norm_y))
        return norm_x, norm_y

    def _send_input(self, flags: int, data: int = 0, dx: int = 0, dy: int = 0):
        if self.send_hook:
            self.send_hook(flags, data, dx, dy)
            return

        if not self.is_windows or not self.user32:
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
        norm_x, norm_y = self.normalize_to_virtual_desktop(screen_x, screen_y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(flags=flags, dx=norm_x, dy=norm_y)

    def left_down(self):
        """Press and hold left mouse button down."""
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
        time.sleep(0.015)
        self._send_input(flags=MOUSEEVENTF_LEFTUP)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Rapid double left click."""
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
        """Scroll mouse wheel."""
        delta = int(amount * 120)
        self._send_input(flags=MOUSEEVENTF_WHEEL, data=delta)

    def emergency_release(self):
        """Guarantees all mouse buttons (left, right, middle) are released safely."""
        if self.is_left_down:
            self.left_up()
        self._send_input(flags=MOUSEEVENTF_LEFTUP)
        self._send_input(flags=MOUSEEVENTF_RIGHTUP)
        self._send_input(flags=MOUSEEVENTF_MIDDLEUP)
        self.is_left_down = False

    def get_active_process_name(self) -> Optional[str]:
        """Inspects the currently focused foreground window on Windows."""
        if not self.is_windows or not self.user32:
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

    def get_active_window_title(self) -> str:
        """Returns the title of the currently focused foreground window."""
        if not self.is_windows or not self.user32:
            return ""

        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                self.user32.GetWindowTextW(hwnd, buff, length + 1)
                return buff.value
        except Exception:
            pass
        return ""

    def is_fullscreen_app_active(self) -> bool:
        """Determines if the foreground application is running in borderless fullscreen."""
        if not self.is_windows or not self.user32:
            return False

        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return False

            rect = RECT()
            if self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                # Check against all monitor dimensions
                for mx, my, mw, mh in self.monitors:
                    if abs(w - mw) <= 2 and abs(h - mh) <= 2 and abs(rect.left - mx) <= 2 and abs(rect.top - my) <= 2:
                        return True
        except Exception:
            pass
        return False
