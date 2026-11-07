"""
Pointer V - Holographic Cursor Reticle Overlay
Draws a precise, non-intrusive cursor reticle centered on the pointing finger:
- Thin 1.5px ring (cyan normal, red when brush locked, grey when tracking lost)
- Short expanding ripple on click
- Thin arc for dwell progress
- Full click-through transparent input styles via Win32 API
"""

import ctypes
import sys
from typing import Optional

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from theme import CYAN, RED, TEXT_DISABLED, AMBER

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080


def set_click_through(hwnd: int):
    """Configures HWND so mouse clicks pass straight through to underlying windows."""
    if not sys.platform.startswith("win"):
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
    except Exception as e:
        print(f"[Overlay] Note: Could not set click-through on HWND {hwnd}: {e}")


class CursorOverlayWindow(QWidget):
    """
    Transparent, click-through, always-on-top cursor reticle.
    Follows index finger coordinates across all monitors.
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.box_size = 96
        self.resize(self.box_size, self.box_size)

        self.cursor_x = 0
        self.cursor_y = 0
        self.state = "NORMAL"  # "NORMAL", "CLICK", "DOUBLE_CLICK", "BRUSH_LOCKED", "LOST"
        self.dwell_progress = 0.0

        # Click ripple animation
        self.ripple_radius = 0.0
        self.ripple_opacity = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(16)

    def showEvent(self, event):
        super().showEvent(event)
        set_click_through(int(self.winId()))

    def update_position(self, x: int, y: int, state: str, dwell: float = 0.0):
        self.cursor_x = x
        self.cursor_y = y
        self.dwell_progress = dwell

        if state != self.state:
            if state in ("CLICK", "DOUBLE_CLICK"):
                self.ripple_radius = 12.0
                self.ripple_opacity = 1.0
            self.state = state

        half = self.box_size // 2
        self.move(x - half, y - half)

    def trigger_click_anim(self, double: bool = False):
        self.state = "DOUBLE_CLICK" if double else "CLICK"
        self.ripple_radius = 12.0
        self.ripple_opacity = 1.0
        self.update()

    def _animate_step(self):
        if self.ripple_opacity > 0.0:
            self.ripple_radius += 2.0
            self.ripple_opacity = max(0.0, self.ripple_opacity - 0.09)
            if self.ripple_opacity <= 0.0 and self.state in ("CLICK", "DOUBLE_CLICK"):
                self.state = "NORMAL"
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx = self.box_size / 2.0
        cy = self.box_size / 2.0

        if self.state == "BRUSH_LOCKED":
            color = QColor(RED)
            ring_pen = QPen(color, 2.0)
            fill_brush = QBrush(QColor(240, 80, 110, 60))
        elif self.state == "LOST":
            color = QColor(TEXT_DISABLED)
            ring_pen = QPen(color, 1.5, Qt.DashLine)
            fill_brush = QBrush(Qt.NoBrush)
        else:
            color = QColor(CYAN)
            ring_pen = QPen(color, 1.5)
            fill_brush = QBrush(QColor(34, 211, 238, 20))

        # 1. Click Ripple (subtle short expanding ring)
        if self.ripple_opacity > 0.0:
            r_col = QColor(color)
            r_col.setAlphaF(self.ripple_opacity)
            painter.setPen(QPen(r_col, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(self.ripple_radius), int(self.ripple_radius))

        # 2. Main 1.5px Ring
        r_inner = 10.0
        rect_inner = QRectF(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)
        painter.setPen(ring_pen)
        painter.setBrush(fill_brush)
        painter.drawEllipse(rect_inner)

        # Center dot
        painter.setPen(QPen(color, 1.5))
        painter.drawPoint(QPoint(int(cx), int(cy)))

        # 3. Dwell progress thin arc
        if self.dwell_progress > 0.0 and self.state != "BRUSH_LOCKED":
            painter.setPen(QPen(QColor(AMBER), 2.0))
            painter.setBrush(Qt.NoBrush)
            r_dwell = 14.0
            rect_dwell = QRectF(cx - r_dwell, cy - r_dwell, r_dwell * 2, r_dwell * 2)
            span_angle = int(self.dwell_progress * 360 * 16)
            painter.drawArc(rect_dwell, 90 * 16, -span_angle)
