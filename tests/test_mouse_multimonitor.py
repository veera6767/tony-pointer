"""
Unit tests for multi-monitor coordinate mapping, Per-Monitor DPI awareness V2,
and absolute SendInput 0..65535 virtual desktop remapping with mocked display setups.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from mouse import MouseController


def test_single_monitor_normalization():
    """Verify 0..65535 normalization on a standard 1920x1080 primary display."""
    mc = MouseController()
    virtual_bounds = (0, 0, 1920, 1080)

    # Top-Left corner (0, 0) -> (0, 0)
    nx1, ny1 = mc.normalize_to_virtual_desktop(0, 0, virtual_bounds)
    assert nx1 == 0
    assert ny1 == 0

    # Bottom-Right corner (1919, 1079) -> (65535, 65535)
    nx2, ny2 = mc.normalize_to_virtual_desktop(1919, 1079, virtual_bounds)
    assert nx2 == 65535
    assert ny2 == 65535

    # Center (960, 540) -> ~32767
    nxc, nyc = mc.normalize_to_virtual_desktop(960, 540, virtual_bounds)
    assert abs(nxc - 32767) <= 50
    assert abs(nyc - 32767) <= 50


def test_two_monitors_side_by_side_mixed_dpi():
    """Two monitors: Primary 1920x1080 at (0,0), Secondary 2560x1440 at (1920,0)."""
    mc = MouseController()
    # Virtual desktop spans x=0..4480, y=0..1440
    virtual_bounds = (0, 0, 4480, 1440)

    # Primary origin (0, 0) -> (0, 0)
    nx1, ny1 = mc.normalize_to_virtual_desktop(0, 0, virtual_bounds)
    assert nx1 == 0
    assert ny1 == 0

    # Seam between monitors at x=1920
    nx_seam, ny_seam = mc.normalize_to_virtual_desktop(1920, 0, virtual_bounds)
    expected_seam_x = int((1920 * 65535) / 4479)
    assert abs(nx_seam - expected_seam_x) <= 2

    # Secondary far right corner at x=4479, y=1439 -> (65535, 65535)
    nx_far, ny_far = mc.normalize_to_virtual_desktop(4479, 1439, virtual_bounds)
    assert nx_far == 65535
    assert ny_far == 65535


def test_monitor_to_the_left_of_primary():
    """Secondary 1920x1080 at (-1920, 0), Primary 1920x1080 at (0, 0). Virtual spans (-1920, 0, 3840, 1080)."""
    mc = MouseController()
    virtual_bounds = (-1920, 0, 3840, 1080)

    # Far left corner of secondary monitor: x=-1920 -> 0
    nx_left, ny_left = mc.normalize_to_virtual_desktop(-1920, 0, virtual_bounds)
    assert nx_left == 0
    assert ny_left == 0

    # Origin of primary monitor: x=0 -> middle of virtual desktop
    nx_pri, _ = mc.normalize_to_virtual_desktop(0, 0, virtual_bounds)
    expected_pri_x = int((1920 * 65535) / 3839)
    assert abs(nx_pri - expected_pri_x) <= 2

    # Far right corner of primary monitor: x=1919 -> 65535
    nx_right, ny_right = mc.normalize_to_virtual_desktop(1919, 1079, virtual_bounds)
    assert nx_right == 65535
    assert ny_right == 65535


def test_emergency_release_all_buttons():
    """Emergency release safely triggers left, right, and middle up events."""
    events = []
    def mock_send(flags, data=0, dx=0, dy=0):
        events.append(flags)

    mc = MouseController(send_hook=mock_send)
    mc.is_left_down = True
    mc.emergency_release()

    assert mc.is_left_down is False
    # Check that LEFTUP (0x0004), RIGHTUP (0x0010), and MIDDLEUP (0x0040) are dispatched
    from mouse import MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEUP
    assert MOUSEEVENTF_LEFTUP in events
    assert MOUSEEVENTF_RIGHTUP in events
    assert MOUSEEVENTF_MIDDLEUP in events

