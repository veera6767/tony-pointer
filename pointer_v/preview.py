"""
Pointer V - Draggable Picture-in-Picture Webcam HUD Preview
Floating borderless preview with 8px rounded corners, subtle 1px blue corner brackets,
FPS telemetry chip, draggable handle, and configurable opacity.
"""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from theme import (
    BLUE, BORDER, RADIUS_PANEL, TEXT_PRIMARY, get_mono_font
)


class CameraPreviewOverlay(QWidget):
    """
    Draggable, semi-transparent, always-on-top picture-in-picture preview window.
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.drag_position = QPoint()
        self.fps_display: float = 0.0

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
        self._restore_position(w, h)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.display_label = QLabel(self)
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.display_label)

    def _restore_position(self, w: int, h: int):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QGuiApplication
        px = self.settings.overlay.preview_pos_x
        py = self.settings.overlay.preview_pos_y

        target_rect = QRect(px, py, w, h)
        is_visible = any(s.geometry().intersects(target_rect) for s in QGuiApplication.screens())
        if is_visible and px >= -500 and py >= -500:
            self.move(px, py)
        else:
            primary = QGuiApplication.primaryScreen()
            if primary:
                geo = primary.availableGeometry()
                self.move(geo.x() + geo.width() - w - 24, geo.y() + 24)
            else:
                self.move(100, 100)

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

    def update_frame(self, frame_bgr, fps: float = 0.0):
        """Converts BGR OpenCV frame to QPixmap and paints preview overlay."""
        target_w = max(100, self.width())
        target_h = max(70, self.height())

        final_pix = QPixmap(target_w, target_h)
        final_pix.fill(Qt.transparent)
        painter = QPainter(final_pix)
        painter.setRenderHint(QPainter.Antialiasing, True)

        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, target_w, target_h, RADIUS_PANEL, RADIUS_PANEL)
        painter.setClipPath(path)

        if frame_bgr is None:
            # Draw offline/reconnecting banner
            painter.fillRect(0, 0, target_w, target_h, QColor("#11151C"))
            painter.setPen(QPen(QColor(BORDER), 1.0))
            painter.drawRoundedRect(0, 0, target_w - 1, target_h - 1, RADIUS_PANEL, RADIUS_PANEL)

            painter.setPen(QColor("#F0506E"))
            painter.setFont(get_mono_font(10, bold=True))
            painter.drawText(0, target_h // 2 - 8, target_w, 20, Qt.AlignCenter, "⚠ Camera Offline")
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.setFont(get_mono_font(8))
            painter.drawText(0, target_h // 2 + 10, target_w, 16, Qt.AlignCenter, "Retrying every 2s...")
            painter.end()
            self.display_label.setPixmap(final_pix)
            return

        self.fps_display = fps
        h, w, ch = frame_bgr.shape
        bytes_per_line = ch * w
        rgb_frame = frame_bgr[:, :, ::-1].copy()
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

        pix = QPixmap.fromImage(q_img).scaled(
            target_w, target_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        painter.drawPixmap(0, 0, pix)

        # 1px border
        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(0, 0, target_w - 1, target_h - 1, RADIUS_PANEL, RADIUS_PANEL)

        # Corner brackets (40% blue, 1px)
        c_len = 12
        bracket_pen = QPen(QColor(47, 123, 255, 120), 1.5)
        painter.setPen(bracket_pen)
        # Top-left
        painter.drawLine(3, 3, 3 + c_len, 3)
        painter.drawLine(3, 3, 3, 3 + c_len)
        # Top-right
        painter.drawLine(target_w - 3, 3, target_w - 3 - c_len, 3)
        painter.drawLine(target_w - 3, 3, target_w - 3, 3 + c_len)
        # Bottom-left
        painter.drawLine(3, target_h - 3, 3 + c_len, target_h - 3)
        painter.drawLine(3, target_h - 3, 3, target_h - 3 - c_len)
        # Bottom-right
        painter.drawLine(target_w - 3, target_h - 3, target_w - 3 - c_len, target_h - 3)
        painter.drawLine(target_w - 3, target_h - 3, target_w - 3, target_h - 3 - c_len)

        # Small FPS chip at bottom right
        if self.fps_display > 0:
            painter.setFont(get_mono_font(9, bold=True))
            painter.setPen(QColor(TEXT_PRIMARY))
            fps_str = f"{self.fps_display:.0f} FPS"
            painter.drawText(target_w - 48, target_h - 8, fps_str)

        painter.end()
        self.display_label.setPixmap(final_pix)

