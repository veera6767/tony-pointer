"""
Pointer V - Core Custom Widgets
Includes ToggleSwitch, ModeChip, CustomTitleBar, SidebarRail, and StatusBarWidget.
Adheres strictly to theme tokens without hardcoded colors.
"""

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG0_WINDOW, BG1_PANELS, BG2_CARDS, BG3_HOVER, BLUE, BLUE_BRIGHT,
    BORDER, BORDER_STRONG, CYAN, GREEN, MODE_COLORS, RADIUS_CONTROL, RADIUS_PANEL,
    RED, TEXT_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY, VIOLET,
    get_mono_font, get_ui_font
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
        self.setFixedHeight(26)
        self.setMinimumWidth(80)

    def set_status(self, mode: str, is_paused: bool = False):
        self.mode = mode
        self.is_paused = is_paused
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.is_paused:
            color = QColor(TEXT_DISABLED)
            text = "PAUSED"
        else:
            color_hex = MODE_COLORS.get(self.mode, BLUE)
            color = QColor(color_hex)
            text = self.mode

        w = self.width()
        h = self.height()

        # Pill background
        bg = QColor(color.red(), color.green(), color.blue(), 28)
        painter.setBrush(bg)
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), h / 2, h / 2)

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

        # Navigation items
        self.nav_items = [
            ("Dashboard", "D"),
            ("Camera", "C"),
            ("Gestures", "G"),
            ("Keyboard", "K"),
            ("Practice", "P"),
            ("Settings", "S"),
            ("Calibration", "W"),
            ("About", "A"),
        ]

        for idx, (label, icon_char) in enumerate(self.nav_items):
            btn = QPushButton(f"  {icon_char}   {label}")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self._on_btn_click(i))
            self.buttons.append((btn, label, icon_char))
            self.layout.addWidget(btn)

        self.layout.addStretch()

        # Hidden developer page button
        self.dev_btn = QPushButton("  *   Developer")
        self.dev_btn.setFixedHeight(36)
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
        for idx, (btn, label, icon_char) in enumerate(self.buttons):
            is_active = (idx == self.active_index)
            btn_text = f"  {icon_char}   {label}" if self.is_expanded else f"  {icon_char}"
            btn.setText(btn_text)
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
                        padding-left: 12px;
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
                        padding-left: 14px;
                    }}
                    QPushButton:hover {{
                        background-color: {BG2_CARDS};
                        color: {TEXT_PRIMARY};
                    }}
                """)


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

