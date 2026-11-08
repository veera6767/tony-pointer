"""
Pointer V - Floating Air Keyboard HUD & Symbols Panel
Renders the 6-row Laptop Keyboard and docked 6-row Symbols Panel in dark glass style.
Features blue-bright locked key glow, amber sticky modifier chips, and Win32
WS_EX_NOACTIVATE & WS_EX_TOOLWINDOW flags to guarantee focus is never stolen from active apps.
"""

import ctypes
import math
import sys
import time
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from keyboard_layout import KeyDef, KeyboardLayoutManager, KeyboardWindow, Zone
from keyboard_out import ModifierState
from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BG3_HOVER, BLUE, BLUE_BRIGHT,
    BORDER, BORDER_STRONG, RADIUS_CONTROL, RADIUS_PANEL, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_DISABLED, VIOLET, get_mono_font, get_ui_font
)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def apply_noactivate_style(hwnd: int):
    """Applies WS_EX_NOACTIVATE and WS_EX_TOOLWINDOW to prevent keyboard from stealing focus."""
    if not sys.platform.startswith("win"):
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except Exception as e:
        print(f"[KeyboardHUD] Note: Could not apply NOACTIVATE style: {e}")


class FloatingAirKeyboardWidget(QWidget):
    """
    Transparent, non-activating floating HUD window displaying the
    Air Keyboard and Symbols Panel.
    """

    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        super().__init__()
        self.settings = settings
        self.layout_manager = layout_manager

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Keyboard Dimensions
        self.key_size = 44
        self.key_gap = 5
        self.margin_x = 20
        self.margin_y = 44
        self.divider_width = 28

        # Dynamic state
        self.active_zone = Zone.MAIN
        self.current_row = 3
        self.current_window_idx = 0
        self.locked_keys: Set[str] = set()

        self.modifiers: Dict[str, ModifierState] = {
            "shift": ModifierState.INACTIVE,
            "ctrl": ModifierState.INACTIVE,
            "alt": ModifierState.INACTIVE,
            "win": ModifierState.INACTIVE,
            "caps": ModifierState.INACTIVE,
        }

        # Animations
        self.flash_key_code: Optional[str] = None
        self.flash_opacity: float = 0.0
        self.last_typed_history: List[str] = []
        self.glow_phase: float = 0.0

        # Drag tracking
        self.drag_position = QPoint()

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_animate)
        self.anim_timer.start(16)

        self._recalculate_window_size()

    def showEvent(self, event):
        super().showEvent(event)
        # Apply Win32 NOACTIVATE style after window is created
        apply_noactivate_style(int(self.winId()))
        self._ensure_on_screen()

    def _ensure_on_screen(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QGuiApplication
        target_rect = QRect(self.pos(), self.size())
        is_visible = any(s.geometry().intersects(target_rect) for s in QGuiApplication.screens())
        if not is_visible:
            primary = QGuiApplication.primaryScreen()
            if primary:
                geo = primary.availableGeometry()
                cx = geo.x() + max(0, (geo.width() - self.width()) // 2)
                cy = geo.y() + geo.height() - self.height() - 40
                self.move(cx, cy)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()

    def _recalculate_window_size(self):
        main_w = 14 * (self.key_size + self.key_gap) + 60
        symbols_w = 8 * (self.key_size + self.key_gap) + 30 if self.settings.keyboard.symbols_panel_enabled else 0
        total_w = self.margin_x * 2 + main_w + (self.divider_width + symbols_w if symbols_w > 0 else 0)
        total_h = self.margin_y + 6 * (self.key_size + self.key_gap) + 24
        self.resize(int(total_w), int(total_h))

    def update_state(
        self,
        zone: Zone,
        row_idx: int,
        window_idx: int,
        modifiers: Dict[str, ModifierState],
        bounce: bool = False
    ):
        self.active_zone = zone
        self.current_row = row_idx
        self.current_window_idx = window_idx
        self.modifiers = modifiers

        active_window = self.layout_manager.get_window(zone, row_idx, window_idx)
        self.locked_keys = {k.code for k in active_window.keys}
        self.update()

    def trigger_key_flash(self, key_code: str, label: str):
        self.flash_key_code = key_code
        self.flash_opacity = 1.0

        # Only add to history if privacy allows
        if not getattr(self.settings.privacy, "hide_last_typed", False):
            self.last_typed_history.append(label)
            if len(self.last_typed_history) > 10:
                self.last_typed_history.pop(0)

        self.update()

    def clear_last_typed(self):
        self.last_typed_history.clear()
        self.update()

    def _on_animate(self):
        self.glow_phase = (self.glow_phase + 0.06) % (2 * math.pi)
        if self.flash_opacity > 0.0:
            self.flash_opacity = max(0.0, self.flash_opacity - 0.10)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # 1. Dark Glass Backdrop (bg1 at ~88% opacity, 1px border, 10px radius)
        bg = QColor(17, 21, 28, int(255 * self.settings.keyboard.opacity))
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(35, 42, 54), 1.0))
        painter.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), 10, 10)

        # 2. Header Strip: Zone, Row, Last Typed, Modifiers
        self._paint_header(painter)

        # 3. Main Keyboard Zone
        main_x = self.margin_x
        main_y = self.margin_y
        main_opacity = 1.0 if self.active_zone == Zone.MAIN else 0.40

        self._paint_zone(
            painter=painter,
            rows=self.layout_manager.main_rows,
            start_x=main_x,
            start_y=main_y,
            zone=Zone.MAIN,
            opacity=main_opacity,
            accent_color=QColor(BLUE_BRIGHT)
        )

        # 4. Docked Symbols Panel
        if self.settings.keyboard.symbols_panel_enabled:
            main_block_w = 14 * (self.key_size + self.key_gap) + 60
            divider_x = main_x + main_block_w + (self.divider_width // 2)

            self._paint_divider(painter, divider_x, main_y)

            symbols_x = divider_x + (self.divider_width // 2)
            symbols_opacity = 1.0 if self.active_zone == Zone.SYMBOLS else (0.35 if self.settings.keyboard.dim_inactive_panel else 0.85)

            self._paint_zone(
                painter=painter,
                rows=self.layout_manager.symbol_rows,
                start_x=symbols_x,
                start_y=main_y,
                zone=Zone.SYMBOLS,
                opacity=symbols_opacity,
                accent_color=QColor(VIOLET)
            )

    def _paint_header(self, painter: QPainter):
        # Header Info Chip: Zone and Row
        painter.setFont(get_ui_font(10, bold=True))
        zone_color = QColor(BLUE if self.active_zone == Zone.MAIN else VIOLET)
        painter.setPen(zone_color)
        painter.drawText(20, 26, f"{self.active_zone.value} · ROW {self.current_row + 1}")

        # Last Typed Strip (respecting privacy)
        if not getattr(self.settings.privacy, "hide_last_typed", False):
            painter.setFont(get_ui_font(10))
            painter.setPen(QColor(TEXT_SECONDARY))
            painter.drawText(140, 26, "Typed:")

            painter.setFont(get_mono_font(10, bold=True))
            painter.setPen(QColor(TEXT_PRIMARY))
            history_str = " ".join(self.last_typed_history[-5:])
            painter.drawText(184, 26, history_str)

        # Modifiers on Right
        mod_x = self.width() - 250
        mods = [("Shift", "shift"), ("Ctrl", "ctrl"), ("Alt", "alt"), ("Caps", "caps")]

        for label, key in mods:
            state = self.modifiers.get(key, ModifierState.INACTIVE)
            rect = QRectF(mod_x, 14, 46, 18)

            if state == ModifierState.LOCKED:
                painter.setBrush(QColor(AMBER))
                painter.setPen(QPen(QColor(AMBER), 1.0))
                fg = QColor(11, 14, 19)
            elif state == ModifierState.LATCHED:
                painter.setBrush(QColor(23, 28, 37))
                painter.setPen(QPen(QColor(AMBER), 1.5))
                fg = QColor(AMBER)
            else:
                painter.setBrush(QColor(23, 28, 37))
                painter.setPen(QPen(QColor(BORDER), 1.0))
                fg = QColor(TEXT_DISABLED)

            painter.drawRoundedRect(rect, 4, 4)
            painter.setFont(get_ui_font(9, bold=True))
            painter.setPen(fg)
            painter.drawText(rect, Qt.AlignCenter, label)
            mod_x += 52

    def _paint_divider(self, painter: QPainter, div_x: float, start_y: float):
        total_h = 6 * (self.key_size + self.key_gap)

        # 1px vertical line with 40% opacity accent
        painter.setPen(QPen(QColor(47, 123, 255, 100), 1))
        painter.drawLine(int(div_x), int(start_y), int(div_x), int(start_y + total_h))

        painter.setFont(get_ui_font(8, bold=True))
        painter.setPen(QColor(VIOLET))
        painter.drawText(int(div_x + 8), int(start_y - 6), "SYMBOLS")

        # Indicator arrow when at crossing edge
        if self.active_zone == Zone.MAIN and self.layout_manager.is_last_window_of_row(Zone.MAIN, self.current_row, self.current_window_idx):
            arrow_y = start_y + self.current_row * (self.key_size + self.key_gap) + (self.key_size / 2.0)
            painter.setPen(QPen(QColor(BLUE_BRIGHT), 1.5))
            cx = div_x
            painter.drawLine(int(cx - 4), int(arrow_y - 4), int(cx + 4), int(arrow_y))
            painter.drawLine(int(cx + 4), int(arrow_y), int(cx - 4), int(arrow_y + 4))

    def _paint_zone(
        self,
        painter: QPainter,
        rows: List[List[KeyDef]],
        start_x: float,
        start_y: float,
        zone: Zone,
        opacity: float,
        accent_color: QColor,
    ):
        curr_y = start_y

        for row_idx, key_list in enumerate(rows):
            curr_x = start_x
            is_active_row = (zone == self.active_zone and row_idx == self.current_row)

            for key in key_list:
                kw = int(self.key_size * key.width_ratio)
                kh = self.key_size
                is_locked = is_active_row and (key.code in self.locked_keys)
                is_flashing = (self.flash_key_code == key.code and self.flash_opacity > 0.0)

                rect = QRectF(curr_x, curr_y, kw, kh)

                # Soft animated glow for locked keys
                glow_int = int((math.sin(self.glow_phase) * 0.15 + 0.85) * 255)

                if is_flashing:
                    # White-blue impact flash
                    painter.setBrush(QColor(230, 240, 255, 230))
                    painter.setPen(QPen(QColor(BLUE_BRIGHT), 2.0))
                elif is_locked:
                    # Blue-bright 1px border + soft blue glow + slightly lighter fill
                    painter.setBrush(QColor(30, 48, 80, int(200 * opacity)))
                    painter.setPen(QPen(QColor(91, 160, 255, int(glow_int * opacity)), 1.5))
                else:
                    painter.setBrush(QColor(23, 28, 37, int(200 * opacity)))
                    painter.setPen(QPen(QColor(35, 42, 54, int(220 * opacity)), 1.0))

                painter.drawRoundedRect(rect, RADIUS_CONTROL, RADIUS_CONTROL)

                # Key Label
                painter.setFont(get_ui_font(10 if len(key.label) <= 2 else 8, bold=is_locked))

                if is_flashing:
                    painter.setPen(QColor(11, 14, 19))
                elif is_locked:
                    painter.setPen(QColor(TEXT_PRIMARY))
                else:
                    painter.setPen(QColor(TEXT_SECONDARY))

                painter.drawText(rect, Qt.AlignCenter, key.display)
                curr_x += kw + self.key_gap

            curr_y += self.key_size + self.key_gap
