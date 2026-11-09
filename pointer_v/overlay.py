"""
Pointer V - Blue Neon Gaming Cursor & Holographic Overlay
Draws a custom, high-precision neon-blue gaming pointer with:
- Sharp angular arrowhead polygon (gradient #2F7BFF -> #5BA0FF)
- White hotspot dot at exact tip
- 18px reticle ring with 4 corner ticks
- 8-step fading comet trail
- Soft radial glow
- Click ripples and air-tap contraction
- Dwell progress and hold-to-action radial arcs
- Non-intrusive mode transition chip
- Win32 click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
"""

import collections
import ctypes
import math
import sys
import time
from typing import Deque, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPen,
    QPolygonF, QRadialGradient
)
from PySide6.QtWidgets import QWidget

from theme import (
    AMBER, BLUE, BLUE_BRIGHT, BLUE_DEEP, CYAN, RED, TEXT_DISABLED, TEXT_PRIMARY, VIOLET, get_mono_font
)

# Win32 Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SPI_SETCURSORS = 0x0057


def set_click_through(hwnd: int):
    """Configures HWND so mouse clicks pass straight through without stealing focus."""
    if not sys.platform.startswith("win"):
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
    except Exception as e:
        print(f"[Overlay] Warning: Failed to set click-through on HWND {hwnd}: {e}")


def restore_system_cursor():
    """Restores standard Windows cursor icons if hidden."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
        except Exception:
            pass


COLOR_PRESETS = {
    "Blue": (QColor(BLUE), QColor(BLUE_BRIGHT), QColor(BLUE_DEEP)),
    "Cyan": (QColor("#06B6D4"), QColor(CYAN), QColor("#0891B2")),
    "Violet": (QColor("#7C3AED"), QColor(VIOLET), QColor("#5B21B6")),
    "Red": (QColor("#DC2626"), QColor(RED), QColor("#991B1B")),
}


class CursorOverlayWindow(QWidget):
    """
    Transparent, click-through, always-on-top angular gaming cursor reticle.
    Accurately places the arrowhead tip over the physical Windows cursor position.
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.box_size = 128
        self.resize(self.box_size, self.box_size)

        self.cursor_x = 0
        self.cursor_y = 0
        self.state = "NORMAL"  # "NORMAL", "CLICK", "DOUBLE_CLICK", "BRUSH_LOCKED", "LOST", "PAUSED"
        self.dwell_progress = 0.0
        self.hold_progress = 0.0
        self.hold_color = QColor(AMBER)

        # Comet trail: last 8 global screen coordinates
        self.trail: Deque[Tuple[float, float, float]] = collections.deque(maxlen=8)

        # Dynamic animations
        self.ripple_radius = 0.0
        self.ripple_opacity = 0.0
        self.tap_ring_contract = 0.0

        # Mode chip indicator
        self.last_mode = "POINTER"
        self.mode_chip_text = ""
        self.mode_chip_opacity = 0.0
        self.mode_chip_start_time = 0.0

        # Test animation
        self.test_timer: Optional[QTimer] = None
        self.test_start_time = 0.0

        # High frequency repaint timer (capped at 60 Hz)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(16)

    def showEvent(self, event):
        super().showEvent(event)
        set_click_through(int(self.winId()))

    def set_mode_chip(self, mode_name: str):
        """Displays temporary fading chip near cursor when mode changes."""
        if mode_name != self.last_mode:
            self.last_mode = mode_name
            self.mode_chip_text = mode_name
            self.mode_chip_opacity = 1.0
            self.mode_chip_start_time = time.perf_counter()

    def update_position(
        self,
        x: int,
        y: int,
        state: str,
        dwell: float = 0.0,
        hold_prog: float = 0.0,
        hold_kind: str = ""
    ):
        """Called on frame updates with mapped screen coordinates."""
        self.cursor_x = x
        self.cursor_y = y
        self.dwell_progress = dwell
        self.hold_progress = hold_prog

        if hold_kind == "KEYBOARD":
            self.hold_color = QColor(VIOLET)
        elif hold_kind == "PAUSE":
            self.hold_color = QColor(AMBER)
        elif hold_kind == "RIGHT_CLICK":
            self.hold_color = QColor(CYAN)
        else:
            self.hold_color = QColor(AMBER)

        # Record comet trail
        now = time.perf_counter()
        if getattr(self.settings.overlay, "cursor_trail", True):
            self.trail.append((float(x), float(y), now))

        if state != self.state:
            if state in ("CLICK", "DOUBLE_CLICK"):
                self.ripple_radius = 8.0
                self.ripple_opacity = 1.0
                self.tap_ring_contract = 1.0
            self.state = state

        # Center the overlay window so the hotspot (center of box) is exactly at (x, y)
        half = self.box_size // 2
        self.move(x - half, y - half)
        self.update()

    def trigger_click_anim(self, double: bool = False):
        self.state = "DOUBLE_CLICK" if double else "CLICK"
        self.ripple_radius = 8.0
        self.ripple_opacity = 1.0
        self.tap_ring_contract = 1.0
        self.update()

    def start_test_animation(self, duration_s: float = 4.0):
        """Self-test: Animates cursor in a smooth figure-8 pattern across screen."""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        cx = geo.x() + geo.width() // 2
        cy = geo.y() + geo.height() // 2
        rx = geo.width() * 0.25
        ry = geo.height() * 0.20

        self.show()
        self.set_mode_chip("TEST CURSOR")
        self.test_start_time = time.perf_counter()

        def _step():
            elapsed = time.perf_counter() - self.test_start_time
            if elapsed > duration_s:
                if self.test_timer:
                    self.test_timer.stop()
                    self.test_timer = None
                self.update_position(int(cx), int(cy), "NORMAL")
                return

            t = elapsed * 2.0 * math.pi / 2.0
            nx = cx + rx * math.sin(t)
            ny = cy + ry * math.sin(2 * t) / 2.0
            dwell = (math.sin(elapsed * 4) + 1) * 0.4 if elapsed > 2.0 else 0.0
            st = "CLICK" if (int(elapsed * 2) % 2 == 1 and elapsed < 2.0) else "NORMAL"
            self.update_position(int(nx), int(ny), st, dwell=dwell)

        if self.test_timer is None:
            self.test_timer = QTimer(self)
            self.test_timer.timeout.connect(_step)
            self.test_timer.start(16)

    def _animate_step(self):
        need_repaint = False

        # Ripple fade-out
        if self.ripple_opacity > 0.0:
            self.ripple_radius += 3.0
            self.ripple_opacity = max(0.0, self.ripple_opacity - 0.08)
            if self.ripple_opacity <= 0.0 and self.state in ("CLICK", "DOUBLE_CLICK"):
                self.state = "NORMAL"
            need_repaint = True

        # Air tap contraction
        if self.tap_ring_contract > 0.0:
            self.tap_ring_contract = max(0.0, self.tap_ring_contract - 0.12)
            need_repaint = True

        # Mode chip fade-out
        if self.mode_chip_opacity > 0.0:
            elapsed = time.perf_counter() - self.mode_chip_start_time
            if elapsed > 1.2:
                self.mode_chip_opacity = max(0.0, 1.0 - (elapsed - 1.2) * 2.5)
            need_repaint = True

        # Trail cleanup
        if self.trail:
            need_repaint = True

        if need_repaint:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx = self.box_size / 2.0
        cy = self.box_size / 2.0

        scale = getattr(self.settings.overlay, "cursor_size", 1.0)
        scale = max(0.75, min(2.0, scale))

        color_name = getattr(self.settings.overlay, "cursor_color", "Blue")
        pri_col, bgt_col, deep_col = COLOR_PRESETS.get(color_name, COLOR_PRESETS["Blue"])

        if self.state == "BRUSH_LOCKED":
            pri_col = QColor(RED)
            bgt_col = QColor("#FF7A90")
            deep_col = QColor("#B91C1C")
        elif self.state == "LOST":
            pri_col = QColor(TEXT_DISABLED)
            bgt_col = QColor(TEXT_PRIMARY)
            deep_col = QColor("#334155")
        elif self.state == "PAUSED":
            pri_col = QColor(AMBER)
            bgt_col = QColor("#FBBF24")
            deep_col = QColor("#78350F")
        elif self.state == "YIELDING":
            pri_col = QColor(AMBER)
            bgt_col = QColor("#FBBF24")
            deep_col = QColor("#78350F")

        # 1. Comet Trail (last 8 positions fading behind cursor)
        if getattr(self.settings.overlay, "cursor_trail", True) and len(self.trail) > 1:
            trail_list = list(self.trail)
            for i in range(len(trail_list) - 1):
                tx, ty, _ = trail_list[i]
                # Map global coordinates into local widget space
                lx = cx + (tx - self.cursor_x)
                ly = cy + (ty - self.cursor_y)
                alpha = int(40.0 * (i + 1) / len(trail_list))
                t_color = QColor(pri_col.red(), pri_col.green(), pri_col.blue(), alpha)
                r_trail = (2.0 + 3.0 * (i / len(trail_list))) * scale
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(t_color))
                painter.drawEllipse(QPointF(lx, ly), r_trail, r_trail)

        # 2. Soft Ambient Glow
        if getattr(self.settings.overlay, "cursor_glow", True) and self.state != "LOST":
            glow_rad = 36.0 * scale
            glow_grad = QRadialGradient(cx, cy, glow_rad)
            glow_grad.setColorAt(0.0, QColor(pri_col.red(), pri_col.green(), pri_col.blue(), 75))
            glow_grad.setColorAt(0.5, QColor(pri_col.red(), pri_col.green(), pri_col.blue(), 25))
            glow_grad.setColorAt(1.0, QColor(pri_col.red(), pri_col.green(), pri_col.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_grad))
            painter.drawEllipse(QPointF(cx, cy), glow_rad, glow_rad)

        # 3. Click Ripple Ring
        if self.ripple_opacity > 0.0:
            r_col = QColor(bgt_col)
            r_col.setAlphaF(self.ripple_opacity)
            painter.setPen(QPen(r_col, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), self.ripple_radius * scale, self.ripple_radius * scale)

        # 4. Outer Gaming Reticle Ring with 4 Corner Ticks
        base_ring_r = 18.0 * scale
        if self.tap_ring_contract > 0.0:
            base_ring_r -= (4.0 * self.tap_ring_contract * scale)

        ring_pen = QPen(QColor(pri_col.red(), pri_col.green(), pri_col.blue(), 140), 1.2)
        if self.state == "LOST":
            ring_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), base_ring_r, base_ring_r)

        # 4 Corner Ticks on the outer ring (0, 90, 180, 270 deg)
        tick_len = 4.0 * scale
        painter.setPen(QPen(bgt_col, 1.5))
        for angle_deg in (0, 90, 180, 270):
            rad = math.radians(angle_deg)
            r_in = base_ring_r - tick_len / 2.0
            r_out = base_ring_r + tick_len / 2.0
            p1 = QPointF(cx + r_in * math.cos(rad), cy + r_in * math.sin(rad))
            p2 = QPointF(cx + r_out * math.cos(rad), cy + r_out * math.sin(rad))
            painter.drawLine(p1, p2)

        # 5. Dwell Progress Thin Arc
        if self.dwell_progress > 0.0 and self.state != "BRUSH_LOCKED":
            painter.setPen(QPen(QColor(AMBER), 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r_dwell = (base_ring_r + 5.0 * scale)
            rect_dwell = QRectF(cx - r_dwell, cy - r_dwell, r_dwell * 2, r_dwell * 2)
            span_angle = int(self.dwell_progress * 360 * 16)
            painter.drawArc(rect_dwell, 90 * 16, -span_angle)

        # 6. Hold Progress Radial Arc (Open Palm or Fist hold)
        if self.hold_progress > 0.0:
            painter.setPen(QPen(self.hold_color, 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r_hold = (base_ring_r + 9.0 * scale)
            rect_hold = QRectF(cx - r_hold, cy - r_hold, r_hold * 2, r_hold * 2)
            span_angle = int(self.hold_progress * 360 * 16)
            painter.drawArc(rect_hold, 90 * 16, -span_angle)

        # 7. Sharp Angular Neon Pointer Arrow (Gaming Style)
        # Hotspot tip is exactly at (cx, cy)
        pointer = QPolygonF([
            QPointF(cx, cy),                                   # Tip (hotspot)
            QPointF(cx - 5.0 * scale, cy + 18.0 * scale),      # Left corner
            QPointF(cx - 1.0 * scale, cy + 14.0 * scale),      # Center bottom notch
            QPointF(cx + 14.0 * scale, cy + 15.0 * scale),     # Right flare
        ])

        grad = QLinearGradient(cx, cy, cx + 10.0 * scale, cy + 18.0 * scale)
        grad.setColorAt(0.0, bgt_col)
        grad.setColorAt(1.0, deep_col)

        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
        painter.drawPolygon(pointer)

        # 8. White Hotspot Dot at Tip
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QPointF(cx, cy), 2.0 * scale, 2.0 * scale)

        # 9. Mode Indicator Chip (temporary fading pill)
        if self.mode_chip_opacity > 0.0:
            chip_alpha = int(self.mode_chip_opacity * 230)
            chip_bg = QColor(17, 21, 28, chip_alpha)
            chip_border = QColor(pri_col.red(), pri_col.green(), pri_col.blue(), chip_alpha)
            text_color = QColor(255, 255, 255, chip_alpha)

            chip_w = 64.0
            chip_h = 18.0
            chip_x = cx + 12.0 * scale
            chip_y = cy + 12.0 * scale

            painter.setBrush(QBrush(chip_bg))
            painter.setPen(QPen(chip_border, 1.0))
            painter.drawRoundedRect(QRectF(chip_x, chip_y, chip_w, chip_h), 4, 4)

            painter.setFont(get_mono_font(8, bold=True))
            painter.setPen(QPen(text_color))
            painter.drawText(QRectF(chip_x, chip_y, chip_w, chip_h), Qt.AlignmentFlag.AlignCenter, self.mode_chip_text)
