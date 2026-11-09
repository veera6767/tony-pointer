"""
Pointer V - Hardware-Level Mouse Emulation via Win32 SendInput
Uses ctypes to invoke user32.dll SendInput with MOUSEEVENTF_ABSOLUTE and
MOUSEEVENTF_VIRTUALDESK. Sets Per-Monitor DPI Awareness V2 so coordinates
line up perfectly with physical pixels across mixed-DPI multi-monitor setups.
"""

import ctypes
from ctypes import wintypes
import math
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

# Ctypes Structures for Win32 SendInput (aligned to Windows SDK x64 40-byte tagINPUT)
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
        self.left_down_time: float = 0.0
        self.last_pos = (0, 0)
        self.last_set_pos: Optional[Tuple[int, int]] = None
        self.yielding_until: float = 0.0
        self.click_history: List[Tuple[float, bool, int, int]] = []
        self.send_hook = send_hook
        self.monitors: List[Tuple[int, int, int, int]] = []
        self.last_sendinput_ret: int = 1
        self.last_sendinput_err: int = 0
        self.last_action: str = "IDLE"

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

    def _send_input(self, flags: int, data: int = 0, dx: int = 0, dy: int = 0, action_name: str = "MOUSE"):
        self.last_action = action_name
        if self.send_hook:
            self.send_hook(flags, data, dx, dy)
            return

        if not self.is_windows or not self.user32:
            return

        mi = MOUSEINPUT(
            dx=dx,
            dy=dy,
            mouseData=data,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
        ret = self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.last_sendinput_ret = ret
        if ret == 0:
            self.last_sendinput_err = ctypes.windll.kernel32.GetLastError()
        else:
            self.last_sendinput_err = 0

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Queries physical cursor coordinates via Win32 GetCursorPos."""
        if not self.is_windows or not self.user32:
            return self.last_pos
        pt = wintypes.POINT()
        if self.user32.GetCursorPos(ctypes.byref(pt)):
            return (int(pt.x), int(pt.y))
        return self.last_pos

    def check_physical_move(self, threshold_px: int = 6, yield_duration_s: float = 1.5) -> bool:
        """
        Input arbitration: Detects if user moved the physical touchpad or mouse.
        Returns True if physical input is active and Pointer V must yield.
        """
        now = time.perf_counter()
        if now < self.yielding_until:
            return True

        if self.last_set_pos is None:
            return False

        cx, cy = self.get_cursor_pos()
        dist = math.hypot(cx - self.last_set_pos[0], cy - self.last_set_pos[1])
        if dist > threshold_px:
            self.yielding_until = now + yield_duration_s
            self.emergency_release()
            return True
        return False

    @property
    def is_yielding(self) -> bool:
        """Returns True if Pointer V is actively yielding to physical mouse/touchpad."""
        return time.perf_counter() < self.yielding_until

    def move_to(self, screen_x: int, screen_y: int):
        """
        Move cursor to absolute desktop coordinates via SendInput.
        Applies a 2px dead zone to prevent fighting with sub-pixel jitter.
        """
        if self.is_yielding:
            return

        dx = screen_x - self.last_pos[0]
        dy = screen_y - self.last_pos[1]
        if (dx * dx + dy * dy) < 4.0:  # 2 px threshold
            return

        self.last_pos = (screen_x, screen_y)
        self.last_set_pos = (screen_x, screen_y)
        norm_x, norm_y = self.normalize_to_virtual_desktop(screen_x, screen_y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(flags=flags, dx=norm_x, dy=norm_y, action_name="MOVE")

    def record_click_and_check_breaker(self, is_right: bool, x: int, y: int) -> bool:
        """
        Circuit breaker: Checks for unintended rapid click loops.
        Returns True if circuit breaker tripped.
        - > 4 clicks within 2.0 s
        - > 2 right clicks within 5.0 s at same screen position (< 15 px)
        """
        now = time.perf_counter()
        self.click_history.append((now, is_right, x, y))
        self.click_history = [c for c in self.click_history if now - c[0] <= 6.0]

        clicks_2s = [c for c in self.click_history if now - c[0] <= 2.0]
        if len(clicks_2s) > 4:
            self.emergency_release()
            return True

        if is_right:
            rc_5s = [c for c in self.click_history if c[1] and now - c[0] <= 5.0]
            close_rc = [c for c in rc_5s if math.hypot(c[2] - x, c[3] - y) <= 15.0]
            if len(close_rc) > 2:
                self.emergency_release()
                return True

        return False

    def check_brush_lock_timeout(self, max_duration_s: float = 30.0) -> bool:
        """Auto-releases brush lock if held longer than max_duration_s."""
        if self.is_left_down:
            if (time.perf_counter() - self.left_down_time) >= max_duration_s:
                self.left_up()
                return True
        return False

    def left_down(self):
        """Press and hold left mouse button down."""
        if self.is_yielding:
            return
        if not self.is_left_down:
            self._send_input(flags=MOUSEEVENTF_LEFTDOWN, action_name="LEFT_DOWN")
            self.is_left_down = True
            self.left_down_time = time.perf_counter()

    def left_up(self):
        """Release left mouse button."""
        if self.is_left_down:
            self._send_input(flags=MOUSEEVENTF_LEFTUP, action_name="LEFT_UP")
            self.is_left_down = False
            self.left_down_time = 0.0

    def click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Standard left click (Down then Up)."""
        if self.is_yielding:
            return
        if x is not None and y is not None:
            self.move_to(x, y)
        self._send_input(flags=MOUSEEVENTF_LEFTDOWN, action_name="CLICK_DOWN")
        time.sleep(0.015)
        self._send_input(flags=MOUSEEVENTF_LEFTUP, action_name="CLICK_UP")

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Rapid double left click."""
        if self.is_yielding:
            return
        if x is not None and y is not None:
            self.move_to(x, y)
        self.click()
        time.sleep(0.045)
        self.click()

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Right click for context menus."""
        if self.is_yielding:
            return
        if x is not None and y is not None:
            self.move_to(x, y)
        self._send_input(flags=MOUSEEVENTF_RIGHTDOWN, action_name="RIGHT_DOWN")
        time.sleep(0.02)
        self._send_input(flags=MOUSEEVENTF_RIGHTUP, action_name="RIGHT_UP")

    def scroll(self, amount: int):
        """Scroll mouse wheel."""
        if self.is_yielding:
            return
        delta = int(amount * 120)
        self._send_input(flags=MOUSEEVENTF_WHEEL, data=delta, action_name="SCROLL")

    def emergency_release(self):
        """Guarantees all mouse buttons (left, right, middle) are released safely."""
        if self.is_left_down:
            self.left_up()
        self._send_input(flags=MOUSEEVENTF_LEFTUP)
        self._send_input(flags=MOUSEEVENTF_RIGHTUP)
        self._send_input(flags=MOUSEEVENTF_MIDDLEUP)
        self.is_left_down = False
        self.left_down_time = 0.0
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

            # Never treat explorer or Pointer V windows as game mode
            proc_name = self.get_active_process_name().lower()
            if proc_name in ("explorer.exe", "pointerv.exe", "python.exe", "taskmgr.exe", "desktop"):
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
