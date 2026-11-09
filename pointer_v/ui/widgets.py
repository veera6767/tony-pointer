"""
Pointer V - Core Custom Widgets
Includes ToggleSwitch, ModeChip, CustomTitleBar, SidebarRail, and StatusBarWidget.
Adheres strictly to theme tokens without hardcoded colors.
"""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BG3_HOVER, BLUE, BLUE_BRIGHT,
    BORDER, BORDER_STRONG, GREEN, RADIUS_CONTROL, RED, TEXT_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)


class ToggleSwitch(QWidget):
    """Clean, animated modern toggle switch without emojis or flashy neon."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Track background
        bg_color = QColor(BLUE) if self._checked else QColor(BORDER_STRONG)
        border_color = QColor(BLUE_BRIGHT) if self._checked else QColor(BORDER)

        track_rect = QRectF(1, 1, 42, 22)
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(track_rect, 11, 11)

        # Thumb
        thumb_x = 22.0 if self._checked else 2.0
        thumb_rect = QRectF(thumb_x, 2, 20, 20)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(thumb_rect)


class ModeChip(QWidget):
    """Pill badge showing current operating mode in its designated theme color."""

    def __init__(self, mode: str = "POINTER", is_paused: bool = False, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.is_paused = is_paused
        self.is_yielding = False
        self.hand_visible = True
        self.is_active = False
        self.setFixedHeight(26)
        self.setMinimumWidth(100)

    def set_status(
        self,
        mode: str,
        is_paused: bool = False,
        is_yielding: bool = False,
        hand_visible: bool = True,
        is_active: bool = True
    ):
        self.mode = mode
        self.is_paused = is_paused
        self.is_yielding = is_yielding
        self.hand_visible = hand_visible
        self.is_active = is_active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if not self.is_active:
            color = QColor(TEXT_DISABLED)
            text = "STANDBY"
        elif self.is_paused:
            color = QColor(RED)
            text = "PAUSED"
        elif self.is_yielding:
            color = QColor(AMBER)
            text = "YIELDING to touchpad"
        elif not self.hand_visible:
            color = QColor(TEXT_SECONDARY)
            text = "NO HAND"
        elif self.mode == "KEYBOARD":
            color = QColor(BLUE)
            text = "KEYBOARD MODE"
        else:
            color = QColor(GREEN)
            text = "OUTPUT ACTIVE"

        h = self.height()

        # Pill background
        bg = QColor(color.red(), color.green(), color.blue(), 28)
        painter.setBrush(bg)
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, h - 2), h / 2, h / 2)

        # Text
        painter.setFont(get_ui_font(10, bold=True))
        painter.setPen(color)
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class CustomTitleBar(QWidget):
    """Frameless custom title bar with window controls, app icon, and mode indicator."""

    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.drag_start = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)

        # App Icon & Title
        self.icon_label = QLabel()
        from pathlib import Path
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icons" / "pointer_v_32.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pix)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel("Pointer V")
        self.title_label.setFont(get_ui_font(12, bold=True))
        self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.title_label)

        # Mode Chip
        self.mode_chip = ModeChip("POINTER", parent=self)
        layout.addWidget(self.mode_chip)

        layout.addStretch()

        # Window Controls (Min, Max, Close)
        btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {TEXT_SECONDARY};
                font-size: 13px;
                width: 32px;
                height: 28px;
            }}
            QPushButton:hover {{
                background-color: {BG3_HOVER};
                color: {TEXT_PRIMARY};
            }}
        """

        self.btn_min = QPushButton("─")
        self.btn_min.setStyleSheet(btn_style)
        self.btn_min.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.btn_min)

        self.btn_max = QPushButton("□")
        self.btn_max.setStyleSheet(btn_style)
        self.btn_max.clicked.connect(self.maximize_clicked.emit)
        layout.addWidget(self.btn_max)

        self.btn_close = QPushButton("✕")
        self.btn_close.setStyleSheet(f"""
            {btn_style}
            QPushButton:hover {{
                background-color: {RED};
                color: #FFFFFF;
            }}
        """)
        self.btn_close.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_start and event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.drag_start
            self.window().move(self.window().pos() + delta)
            self.drag_start = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_start = None


def create_sidebar_icon(name: str, color_hex: str = TEXT_SECONDARY) -> QIcon:
    """Generates crisp 18x18 Lucide-style vector line QIcon for sidebar navigation."""
    pix = QPixmap(36, 36)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    pen = QPen(QColor(color_hex), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "Dashboard":
        # 2x2 grid squares
        painter.drawRoundedRect(QRectF(4, 4, 11, 11), 2, 2)
        painter.drawRoundedRect(QRectF(21, 4, 11, 11), 2, 2)
        painter.drawRoundedRect(QRectF(4, 21, 11, 11), 2, 2)
        painter.drawRoundedRect(QRectF(21, 21, 11, 11), 2, 2)

    elif name == "Camera":
        # Video camera body and lens
        painter.drawRoundedRect(QRectF(4, 8, 18, 20), 3, 3)
        path = QPainterPath()
        path.moveTo(22, 14)
        path.lineTo(31, 9)
        path.lineTo(31, 27)
        path.lineTo(22, 22)
        path.closeSubpath()
        painter.drawPath(path)

    elif name == "Gestures":
        # Hand icon: palm + 4 fingers + thumb
        path = QPainterPath()
        path.moveTo(10, 31)
        path.lineTo(10, 16)
        path.arcTo(QRectF(10, 12, 4, 8), 180, -180) # Index
        path.lineTo(14, 8)
        path.arcTo(QRectF(14, 4, 4, 8), 180, -180) # Middle
        path.lineTo(18, 10)
        path.arcTo(QRectF(18, 6, 4, 8), 180, -180) # Ring
        path.lineTo(22, 15)
        path.arcTo(QRectF(22, 12, 4, 8), 180, -180) # Pinky
        path.lineTo(26, 24)
        path.arcTo(QRectF(18, 20, 12, 12), 0, -90)
        path.lineTo(10, 31)
        painter.drawPath(path)

    elif name == "Keyboard":
        # Keyboard frame + space line + key rows
        painter.drawRoundedRect(QRectF(3, 8, 30, 20), 3, 3)
        painter.drawLine(10, 23, 26, 23)
        painter.drawLine(8, 14, 12, 14)
        painter.drawLine(16, 14, 20, 14)
        painter.drawLine(24, 14, 28, 14)

    elif name == "Practice":
        # Target / Bullseye
        painter.drawEllipse(QRectF(4, 4, 28, 28))
        painter.drawEllipse(QRectF(12, 12, 12, 12))
        painter.drawLine(18, 2, 18, 34)
        painter.drawLine(2, 18, 34, 18)

    elif name == "Settings":
        # Sliders / Controls
        painter.drawLine(6, 10, 30, 10)
        painter.drawEllipse(QRectF(10, 7, 6, 6))
        painter.drawLine(6, 18, 30, 18)
        painter.drawEllipse(QRectF(20, 15, 6, 6))
        painter.drawLine(6, 26, 30, 26)
        painter.drawEllipse(QRectF(14, 23, 6, 6))

    elif name == "Calibration":
        # Crosshair calibration corners
        painter.drawEllipse(QRectF(10, 10, 16, 16))
        painter.drawLine(5, 18, 10, 18)
        painter.drawLine(26, 18, 31, 18)
        painter.drawLine(18, 5, 18, 10)
        painter.drawLine(18, 26, 18, 31)

    elif name == "About":
        # Info circle
        painter.drawEllipse(QRectF(4, 4, 28, 28))
        painter.drawPoint(18, 11)
        painter.drawLine(18, 16, 18, 26)

    elif name == "Developer":
        # Terminal / Code brackets: < / >
        path = QPainterPath()
        path.moveTo(13, 11)
        path.lineTo(6, 18)
        path.lineTo(13, 25)
        path.moveTo(23, 11)
        path.lineTo(30, 18)
        path.lineTo(23, 25)
        painter.drawPath(path)
        painter.drawLine(20, 10, 16, 26)

    else:
        painter.drawEllipse(QRectF(10, 10, 16, 16))

    painter.end()
    return QIcon(pix)


class SidebarRail(QFrame):
    """
    Left navigation rail: 64px collapsed icon rail expanding to 200px.
    Active tab receives a 2px blue indicator bar on left edge and bg3 highlight.
    """

    page_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(64)
        self.is_expanded = False
        self.active_index = 0
        self.buttons = []

        self.setObjectName("PanelFrame")
        self.setStyleSheet(f"background-color: {BG1_PANELS}; border-right: 1px solid {BORDER};")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 12, 6, 12)
        self.layout.setSpacing(6)

        # Hamburger toggle button
        self.toggle_btn = QPushButton("≡")
        self.toggle_btn.setFixedHeight(36)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {BORDER};
                border-radius: {RADIUS_CONTROL}px;
                color: {TEXT_SECONDARY};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {BG3_HOVER};
                color: {TEXT_PRIMARY};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_expand)
        self.layout.addWidget(self.toggle_btn)

        self.layout.addSpacing(8)

        # Navigation items with dedicated vector line icons
        self.nav_items = [
            "Dashboard",
            "Camera",
            "Gestures",
            "Keyboard",
            "Practice",
            "Settings",
            "Calibration",
            "About",
        ]

        for idx, label in enumerate(self.nav_items):
            btn = QPushButton()
            btn.setFixedHeight(40)
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self._on_btn_click(i))
            self.buttons.append((btn, label))
            self.layout.addWidget(btn)

        self.layout.addStretch()

        # Hidden developer page button
        self.dev_btn = QPushButton()
        self.dev_btn.setFixedHeight(38)
        self.dev_btn.setIconSize(QSize(18, 18))
        self.dev_btn.setIcon(create_sidebar_icon("Developer", TEXT_SECONDARY))
        self.dev_btn.setCursor(Qt.PointingHandCursor)
        self.dev_btn.setVisible(False)
        self.dev_btn.clicked.connect(lambda: self._on_btn_click(len(self.nav_items)))
        self.layout.addWidget(self.dev_btn)

        self._refresh_styles()

    def set_developer_mode_visible(self, visible: bool):
        self.dev_btn.setVisible(visible)

    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        new_width = 200 if self.is_expanded else 64
        self.setFixedWidth(new_width)
        self._refresh_styles()

    def _on_btn_click(self, index: int):
        self.active_index = index
        self._refresh_styles()
        self.page_selected.emit(index)

    def _refresh_styles(self):
        for idx, (btn, label) in enumerate(self.buttons):
            is_active = (idx == self.active_index)
            icon_color = BLUE_BRIGHT if is_active else TEXT_SECONDARY
            btn.setIcon(create_sidebar_icon(label, icon_color))
            btn.setText(f"  {label}" if self.is_expanded else "")
            btn.setFont(get_ui_font(11, bold=is_active))

            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {BG3_HOVER};
                        border: none;
                        border-left: 2px solid {BLUE};
                        border-radius: {RADIUS_CONTROL}px;
                        color: {TEXT_PRIMARY};
                        text-align: left;
                        padding-left: {16 if self.is_expanded else 12}px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: {RADIUS_CONTROL}px;
                        color: {TEXT_SECONDARY};
                        text-align: left;
                        padding-left: {16 if self.is_expanded else 12}px;
                    }}
                    QPushButton:hover {{
                        background-color: {BG2_CARDS};
                        color: {TEXT_PRIMARY};
                    }}
                """)

        # Developer button styling
        is_dev_active = (self.active_index == len(self.nav_items))
        dev_color = BLUE_BRIGHT if is_dev_active else TEXT_SECONDARY
        self.dev_btn.setIcon(create_sidebar_icon("Developer", dev_color))
        self.dev_btn.setText("  Developer" if self.is_expanded else "")
        self.dev_btn.setFont(get_ui_font(11, bold=is_dev_active))
        if is_dev_active:
            self.dev_btn.setStyleSheet(f"QPushButton {{ background-color: {BG3_HOVER}; border: none; border-left: 2px solid {BLUE}; border-radius: {RADIUS_CONTROL}px; color: {TEXT_PRIMARY}; text-align: left; padding-left: {16 if self.is_expanded else 12}px; }}")
        else:
            self.dev_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; border-radius: {RADIUS_CONTROL}px; color: {TEXT_SECONDARY}; text-align: left; padding-left: {16 if self.is_expanded else 12}px; }} QPushButton:hover {{ background-color: {BG2_CARDS}; color: {TEXT_PRIMARY}; }}")


class StatusBarWidget(QFrame):
    """
    Bottom status bar showing:
    - Camera indicator with active green/amber dot
    - FPS and latency in JetBrains Mono
    - Active mode, paused state, and global hotkey hints
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet(f"background-color: {BG1_PANELS}; border-top: 1px solid {BORDER};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        # Camera indicator
        self.cam_dot = QLabel("●")
        self.cam_dot.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
        layout.addWidget(self.cam_dot)

        self.cam_status = QLabel("Camera Active")
        self.cam_status.setFont(get_ui_font(10))
        self.cam_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.cam_status)

        layout.addSpacing(8)

        # FPS & Latency (Strictly in JetBrains Mono)
        self.lbl_fps = QLabel("60.0 FPS")
        self.lbl_fps.setFont(get_mono_font(10))
        self.lbl_fps.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.lbl_fps)

        self.lbl_latency = QLabel("0.0 ms")
        self.lbl_latency.setFont(get_mono_font(10))
        self.lbl_latency.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.lbl_latency)

        layout.addStretch()

        # Hotkey Hints
        hints = QLabel("Ctrl+Alt+T Toggle · Ctrl+Alt+K Keyboard · Ctrl+Alt+Space Pause · Esc Stop")
        hints.setFont(get_ui_font(10))
        hints.setStyleSheet(f"color: {TEXT_DISABLED};")
        layout.addWidget(hints)

    def update_telemetry(self, fps: float, latency: float, camera_connected: bool, is_paused: bool):
        self.lbl_fps.setText(f"{fps:.1f} FPS")
        self.lbl_latency.setText(f"{latency:.1f} ms")

        if is_paused:
            self.cam_dot.setStyleSheet(f"color: {AMBER}; font-size: 12px;")
            self.cam_status.setText("Tracking Paused")
        elif camera_connected:
            self.cam_dot.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
            self.cam_status.setText("Camera Active")
        else:
            self.cam_dot.setStyleSheet(f"color: {RED}; font-size: 12px;")
            self.cam_status.setText("Camera Reconnecting...")

