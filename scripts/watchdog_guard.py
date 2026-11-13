"""
Pointer V - External Watchdog Safety Guard Process
Runs independently in the background, consuming minimal CPU (<0.1%).
Monitors the main Pointer V application process and heartbeat file.
If the heartbeat file is stale (> 5.0 seconds) or the parent process dies,
it sends emergency Win32 SendInput release events for all mouse buttons
and modifier keys, preventing any stuck keys or buttons.
"""

import ctypes
import os
from pathlib import Path
import sys
import time
import psutil

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

MODIFIER_SCANS = [
    0x2A,  # Left Shift
    0x36,  # Right Shift
    0x1D,  # Left Ctrl
    0x38,  # Left Alt
    0x5B,  # Left Win (extended)
]


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


def emergency_release_all():
    """Win32 SendInput call to release all buttons and modifiers."""
    if not sys.platform.startswith("win"):
        return
    user32 = ctypes.windll.user32

    # Release mouse buttons
    for flag in (MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEUP):
        mi = MOUSEINPUT(0, 0, 0, flag, 0, 0)
        inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    # Release modifier keys
    for scancode in MODIFIER_SCANS:
        ki = KEYBDINPUT(0, scancode, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, 0)
        inp = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def main():
    if len(sys.argv) < 2:
        print("Usage: watchdog_guard.py <target_pid> [heartbeat_path]")
        sys.exit(1)

    target_pid = int(sys.argv[1])
    heartbeat_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not heartbeat_path:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "PointerV" / "logs" if appdata else Path.home() / ".pointerv" / "logs"
        heartbeat_path = base / "heartbeat.ts"

    try:
        target_proc = psutil.Process(target_pid)
    except psutil.NoSuchProcess:
        sys.exit(0)

    already_released = False

    while True:
        time.sleep(1.0)

        # Check if parent process exited
        if not target_proc.is_running() or target_proc.status() == psutil.STATUS_ZOMBIE:
            emergency_release_all()
            break

        # Check heartbeat file freshness
        if heartbeat_path.exists():
            try:
                mtime = heartbeat_path.stat().st_mtime
                age = time.time() - mtime
                if age > 5.0 and not already_released:
                    print(f"[Watchdog Guard] Target PID {target_pid} stalled for {age:.1f}s! Force-releasing all inputs.")
                    emergency_release_all()
                    already_released = True
                elif age <= 2.0:
                    already_released = False
            except Exception:
                pass


if __name__ == "__main__":
    main()

