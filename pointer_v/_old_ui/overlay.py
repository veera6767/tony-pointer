"""
Tony Pointer - PySide6 Holographic Cursor Reticle & Camera HUD Overlays
Draws an Iron-Man / JARVIS sci-fi cursor overlay that follows the finger position,
changes visual states (normal cyan ring, click ripples, solid brush lock, dim lost),
and stays click-through on Windows via Win32 extended window styles.
Also includes a floating, draggable, semi-transparent camera HUD window.
"""

import ctypes
import math
import sys
import time
from typing import Optional

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Win32 click-through styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080


def set_click_through(hwnd: int):
    """Configures a Win32 HWND so all mouse clicks pass straight through to windows beneath."""
    if not sys.platform.startswith("win"):
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
    except Exception as e:
        print(f"[TonyPointer] Note: Could not set click-through on HWND {hwnd}: {e}")


class CursorOverlayWindow(QWidget):
    """
    Transparent, click-through, always-on-top cursor reticle window.
    Positions itself centered at (target_x, target_y) and renders the Iron-Man HUD.
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        # Window flags for borderless, top-level overlay
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.box_size = 120  # Window dimension around cursor
        self.resize(self.box_size, self.box_size)

        # Reticle States
        self.cursor_x = 0
        self.cursor_y = 0
        self.state = "NORMAL"  # "NORMAL", "CLICK", "DOUBLE_CLICK", "BRUSH_LOCKED", "LOST"
        self.dwell_progress = 0.0

        # Animation parameters
        self.angle = 0.0
        self.ripple_radius = 0.0
        self.ripple_opacity = 0.0

        # Animation timer (60 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(16)

    def showEvent(self, event):
        super().showEvent(event)
        # Apply Win32 click-through after window handle exists
        set_click_through(int(self.winId()))

    def update_position(self, x: int, y: int, state: str, dwell: float = 0.0):
        self.cursor_x = x
        self.cursor_y = y
        self.dwell_progress = dwell

        if state != self.state:
            if state in ("CLICK", "DOUBLE_CLICK"):
                self.ripple_radius = 16.0
                self.ripple_opacity = 1.0
            self.state = state

        # Center window over cursor position
        half = self.box_size // 2
        self.move(x - half, y - half)

    def trigger_click_anim(self, double: bool = False):
        self.state = "DOUBLE_CLICK" if double else "CLICK"
        self.ripple_radius = 16.0
        self.ripple_opacity = 1.0
        self.update()

    def _animate_step(self):
        self.angle = (self.angle + 2.5) % 360.0

        # Animate ripple decay
        if self.ripple_opacity > 0.0:
            self.ripple_radius += 2.2
            self.ripple_opacity = max(0.0, self.ripple_opacity - 0.07)
            if self.ripple_opacity <= 0.0 and self.state in ("CLICK", "DOUBLE_CLICK"):
                self.state = "NORMAL"

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx = self.box_size / 2.0
        cy = self.box_size / 2.0

        # State color resolution
        if self.state == "BRUSH_LOCKED":
            main_color = QColor(255, 87, 34)   # Solid Arc Orange-Red
            ring_pen = QPen(main_color, 3.0)
            fill_brush = QBrush(QColor(255, 87, 34, 180))
        elif self.state == "LOST":
            main_color = QColor(100, 116, 139) # Dim Slate Grey
            ring_pen = QPen(main_color, 1.5, Qt.DashLine)
            fill_brush = QBrush(Qt.NoBrush)
        else:
            main_color = QColor(0, 229, 255)   # Iron-Man Laser Cyan
            ring_pen = QPen(main_color, 2.0)
            fill_brush = QBrush(QColor(0, 229, 255, 40))

        # 1. Ripple Animation on Click / Double Click
        if self.ripple_opacity > 0.0:
            ripple_color = QColor(main_color)
            ripple_color.setAlphaF(self.ripple_opacity)
            painter.setPen(QPen(ripple_color, 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(self.ripple_radius), int(self.ripple_radius))

            if self.state == "DOUBLE_CLICK":
                # Double concentric ripple
                painter.drawEllipse(QPoint(int(cx), int(cy)), int(self.ripple_radius * 0.7), int(self.ripple_radius * 0.7))

        # 2. Outer Rotating Sci-Fi Segments
        if self.state != "LOST":
            painter.setPen(QPen(QColor(main_color.red(), main_color.green(), main_color.blue(), 120), 1.5))
            painter.setBrush(Qt.NoBrush)
            r_outer = 24.0
            rect_outer = QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)

            # Draw 3 rotating HUD arcs
            for offset in (0, 120, 240):
                painter.drawArc(rect_outer, int((self.angle + offset) * 16), int(60 * 16))

        # 3. Main Center Ring / Solid Brush Lock Indicator
        r_inner = 14.0
        rect_inner = QRectF(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)
        painter.setPen(ring_pen)
        painter.setBrush(fill_brush)
        painter.drawEllipse(rect_inner)

        # Center Precision Dot / Crosshairs
        painter.setPen(QPen(main_color, 2.0))
        painter.drawPoint(QPoint(int(cx), int(cy)))
        painter.drawLine(int(cx - 3), int(cy), int(cx + 3), int(cy))
        painter.drawLine(int(cx), int(cy - 3), int(cx), int(cy + 3))

        # 4. Dwell Progress Radial Fill Arc
        if self.dwell_progress > 0.0 and self.state != "BRUSH_LOCKED":
            dwell_color = QColor(255, 179, 0)  # Amber charging arc
            painter.setPen(QPen(dwell_color, 3.5))
            painter.setBrush(Qt.NoBrush)
            r_dwell = 19.0
            rect_dwell = QRectF(cx - r_dwell, cy - r_dwell, r_dwell * 2, r_dwell * 2)
            span_angle = int(self.dwell_progress * 360 * 16)
            painter.drawArc(rect_dwell, 90 * 16, -span_angle)


class CameraPreviewOverlay(QWidget):
    """
    Draggable, semi-transparent, always-on-top HUD preview window.
    Shows mirrored live camera stream, hand skeleton, and active region box.
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.drag_position = QPoint()

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(self.settings.overlay.preview_opacity)

        w = self.settings.overlay.preview_width
        h = self.settings.overlay.preview_height
        self.resize(w, h)
        self.move(self.settings.overlay.preview_pos_x, self.settings.overlay.preview_pos_y)

        # Video frame display label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.display_label = QLabel(self)
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: #0b0f19; border: 1px solid #00e5ff; border-radius: 6px;")
        layout.addWidget(self.display_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            self.settings.overlay.preview_pos_x = new_pos.x()
            self.settings.overlay.preview_pos_y = new_pos.y()
            event.accept()

    def update_frame(self, frame_bgr):
        """Converts BGR OpenCV frame to QPixmap and updates label."""
        if frame_bgr is None:
            return

        h, w, ch = frame_bgr.shape
        bytes_per_line = ch * w
        # Convert BGR to RGB for Qt display
        rgb_frame = frame_bgr[:, :, ::-1].copy()
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(q_img).scaled(
            self.display_label.width(),
            self.display_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.display_label.setPixmap(pix)
