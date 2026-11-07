"""
Tony Pointer - PySide6 Floating Air Keyboard HUD & Symbols Panel
Renders the 6-row Laptop Keyboard on the left and the docked 6-row Symbols Panel on the right.
Features electric blue neon 4-key window glow, active/inactive zone dimming,
pulsing divider crossing indicators, sticky modifier tags, and a live 'last typed' strip.
"""

import math
import sys
import time
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from keyboard_layout import KeyDef, KeyboardLayoutManager, KeyboardWindow, Zone
from keyboard_out import ModifierState


class FloatingAirKeyboardWidget(QWidget):
    """
    Transparent, non-activating floating HUD window displaying the
    Iron-Man holographic Air Keyboard and Symbols Panel.
    """

    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        super().__init__()
        self.settings = settings
        self.layout_manager = layout_manager

        # Non-activating, always-on-top transparent tool window
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Keyboard Dimensions
        self.key_size = 46
        self.key_gap = 6
        self.margin_x = 24
        self.margin_y = 48  # Space for 'last typed' strip
        self.divider_width = 32

        # Dynamic state
        self.active_zone = Zone.MAIN
        self.current_row = 3
        self.current_window_idx = 0
        self.locked_keys: Set[str] = set()

        # Modifier states
        self.modifiers: Dict[str, ModifierState] = {
            "shift": ModifierState.INACTIVE,
            "ctrl": ModifierState.INACTIVE,
            "alt": ModifierState.INACTIVE,
            "win": ModifierState.INACTIVE,
            "caps": ModifierState.INACTIVE,
        }

        # Feedback animations
        self.flash_key_code: Optional[str] = None
        self.flash_opacity: float = 0.0
        self.last_typed_history: List[str] = ["Tony", "Pointer", "Ready"]
        self.pulse_phase: float = 0.0
        self.bounce_offset: float = 0.0

        # Animation Loop (60 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_animate)
        self.anim_timer.start(16)

        self._recalculate_window_size()

    def _recalculate_window_size(self):
        # 14 standard keys wide for main keyboard
        main_w = 14 * (self.key_size + self.key_gap) + 80
        # Symbols panel width (8 keys wide)
        symbols_w = 8 * (self.key_size + self.key_gap) + 40 if self.settings.keyboard.symbols_panel_enabled else 0
        total_w = self.margin_x * 2 + main_w + (self.divider_width + symbols_w if symbols_w > 0 else 0)
        total_h = self.margin_y + 6 * (self.key_size + self.key_gap) + 32
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

        # Identify the 4 locked keys
        active_window = self.layout_manager.get_window(zone, row_idx, window_idx)
        self.locked_keys = {k.code for k in active_window.keys}

        if bounce:
            self.bounce_offset = 12.0

        self.update()

    def trigger_key_flash(self, key_code: str, label: str):
        self.flash_key_code = key_code
        self.flash_opacity = 1.0
        self.last_typed_history.append(label)
        if len(self.last_typed_history) > 12:
            self.last_typed_history.pop(0)
        self.update()

    def _on_animate(self):
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)

        if self.flash_opacity > 0.0:
            self.flash_opacity = max(0.0, self.flash_opacity - 0.08)

        if self.bounce_offset > 0.0:
            self.bounce_offset = max(0.0, self.bounce_offset - 1.5)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # 1. Subtle Frosted Obsidian Backdrop
        bg_color = QColor(7, 11, 20, int(255 * self.settings.keyboard.opacity))
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor(0, 229, 255, 60), 1.5))
        painter.drawRoundedRect(QRectF(8, 8, w - 16, h - 16), 10, 10)

        # 2. Last Typed History Strip & Active Mode Header
        self._paint_header_strip(painter)

        # 3. Main Keyboard Geometry
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
            accent_color=QColor(0, 229, 255),
        )

        # 4. Docked Symbols Panel (if enabled)
        if self.settings.keyboard.symbols_panel_enabled:
            # Main keyboard width estimation (14 units wide)
            main_block_w = 14 * (self.key_size + self.key_gap) + 80
            divider_x = main_x + main_block_w + (self.divider_width // 2)

            # Paint Glowing Vertical Divider
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
                accent_color=QColor(168, 85, 247), # Violet/Teal distinction
            )

    def _paint_header_strip(self, painter: QPainter):
        # 'Last Typed' Text preview
        painter.setFont(QFont("JetBrains Mono", 10, QFont.Bold))
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(24, 32, "LAST TYPED:")

        history_str = " ".join(self.last_typed_history[-6:])
        painter.setPen(QColor(0, 229, 255))
        painter.drawText(118, 32, history_str)

        # Sticky Modifiers Indicators
        mod_x = self.width() - 320
        mods_to_show = [("SHIFT", "shift"), ("CTRL", "ctrl"), ("ALT", "alt"), ("CAPS", "caps")]

        for name, code in mods_to_show:
            state = self.modifiers.get(code, ModifierState.INACTIVE)
            if state == ModifierState.LOCKED:
                bg = QColor(255, 179, 0) # Solid amber
                fg = QColor(10, 15, 25)
            elif state == ModifierState.LATCHED:
                bg = QColor(255, 100, 0, 180) # Orange glow
                fg = QColor(255, 255, 255)
            else:
                bg = QColor(15, 23, 42, 100)
                fg = QColor(100, 116, 139)

            painter.setBrush(bg)
            painter.setPen(QPen(fg, 1))
            rect = QRectF(mod_x, 18, 52, 20)
            painter.drawRoundedRect(rect, 3, 3)

            painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
            painter.setPen(fg)
            painter.drawText(rect, Qt.AlignCenter, name)
            mod_x += 60

    def _paint_divider(self, painter: QPainter, div_x: float, start_y: float):
        total_h = 6 * (self.key_size + self.key_gap)

        # Glowing vertical line
        glow = math.sin(self.pulse_phase) * 0.3 + 0.7
        painter.setPen(QPen(QColor(0, 229, 255, int(180 * glow)), 2))
        painter.drawLine(int(div_x), int(start_y), int(div_x), int(start_y + total_h))

        # Header Label: SYMBOLS
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor(168, 85, 247))
        painter.drawText(int(div_x + 12), int(start_y - 8), "SYMBOLS")

        # Pulsing Arrow towards Symbols when on the last window of MAIN
        is_on_last_main = (
            self.active_zone == Zone.MAIN
            and self.layout_manager.is_last_window_of_row(Zone.MAIN, self.current_row, self.current_window_idx)
        )
        if is_on_last_main:
            arrow_y = start_y + self.current_row * (self.key_size + self.key_gap) + (self.key_size / 2.0)
            painter.setPen(QPen(QColor(0, 229, 255), 2.5))
            # Draw right-pointing chevron: >
            cx = div_x
            painter.drawLine(int(cx - 6), int(arrow_y - 6), int(cx + 6), int(arrow_y))
            painter.drawLine(int(cx + 6), int(arrow_y), int(cx - 6), int(arrow_y + 6))

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

            # Check if this row holds the locked window
            is_active_row = (zone == self.active_zone and row_idx == self.current_row)

            for key in key_list:
                kw = int(self.key_size * key.width_ratio)
                kh = self.key_size

                is_locked = is_active_row and (key.code in self.locked_keys)
                is_flashing = (self.flash_key_code == key.code and self.flash_opacity > 0.0)

                # Key Geometry Rect
                rect = QRectF(curr_x, curr_y, kw, kh)

                # Visual Styling based on 4-key window lock
                if is_flashing:
                    # White-blue impact flash
                    painter.setBrush(QColor(255, 255, 255, 240))
                    painter.setPen(QPen(QColor(0, 229, 255), 3.0))
                elif is_locked:
                    # Strong Electric BLUE Neon Glow under user's fingers!
                    painter.setBrush(QColor(0, 180, 255, int(130 * opacity)))
                    painter.setPen(QPen(QColor(0, 229, 255, int(255 * opacity)), 2.5))
                else:
                    # Dim unselected key
                    base_fill = QColor(15, 23, 42, int(150 * opacity))
                    painter.setBrush(base_fill)
                    border_color = QColor(accent_color.red(), accent_color.green(), accent_color.blue(), int(80 * opacity))
                    painter.setPen(QPen(border_color, 1.0))

                painter.drawRoundedRect(rect, 4, 4)

                # Key Label Text
                painter.setFont(QFont("JetBrains Mono", 9 if len(key.label) <= 2 else 7, QFont.Bold))

                if is_flashing:
                    painter.setPen(QColor(10, 15, 25))
                elif is_locked:
                    painter.setPen(QColor(255, 255, 255))
                else:
                    text_color = QColor(203, 213, 225, int(220 * opacity))
                    painter.setPen(text_color)

                painter.drawText(rect, Qt.AlignCenter, key.display)

                curr_x += kw + self.key_gap

            curr_y += self.key_size + self.key_gap
