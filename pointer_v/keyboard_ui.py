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
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from keyboard_layout import KeyDef, KeyboardLayoutManager, Zone
from keyboard_out import ModifierState
from theme import (
    AMBER, BLUE, BLUE_BRIGHT, BORDER, RADIUS_CONTROL,
    TEXT_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY, VIOLET,
    get_mono_font, get_ui_font
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
    Air Keyboard and Symbols Panel docked in a screen corner.
    """

    def __init__(self, settings, layout_manager: KeyboardLayoutManager):
        super().__init__()
        self.settings = settings
        self.layout_manager = layout_manager

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

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

        # Phase D feedback
        self.swipe_progress: float = 0.0
        self.swipe_direction: str = ""
        self.finger_curls: Dict[str, float] = {}

        # Animation state for slide-and-fade
        self.is_animating: bool = False
        self.anim_progress: float = 1.0
        self.anim_start_pos = QPoint()
        self.anim_target_pos = QPoint()
        self.anim_start_opacity: float = 0.0
        self.anim_target_opacity: float = 0.94
        self.is_opening: bool = False

        # Drag tracking
        self.is_dragging: bool = False
        self.drag_position = QPoint()

        # Keyboard Dimensions & Layout scaling
        self.key_size = 40
        self.key_gap = 4
        self.margin_x = 16
        self.margin_y = 38
        self.divider_width = 24

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_animate)
        # Start at 200ms (slow tick) while keyboard is hidden to save UI-thread time.
        # animate_show() resets it to 16ms for smooth slide-in.
        self.anim_timer.start(200)

        self._recalculate_window_size()

        # Listen to screen topology updates
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):
            app.screenAdded.connect(lambda _: self._reposition_to_corner())
            app.screenRemoved.connect(lambda _: self._reposition_to_corner())
            app.primaryScreenChanged.connect(lambda _: self._reposition_to_corner())

    def _get_target_screen(self):
        """Resolves target screen according to monitor_mode setting."""
        from PySide6.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        if not screens:
            return None

        mode = getattr(self.settings.keyboard, "monitor_mode", "active_window")
        if mode == "specific":
            idx = getattr(self.settings.keyboard, "chosen_monitor", 0)
            if 0 <= idx < len(screens):
                return screens[idx]

        if mode == "active_window" and sys.platform.startswith("win"):
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd and hwnd != int(self.winId()):
                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    rc = RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                        from PySide6.QtCore import QPoint
                        center = QPoint((rc.left + rc.right) // 2, (rc.top + rc.bottom) // 2)
                        for s in screens:
                            if s.geometry().contains(center):
                                return s
            except Exception:
                pass

        # Fallback to primary screen
        return QGuiApplication.primaryScreen() or screens[0]

    def calculate_corner_position(self, corner_name: Optional[str] = None, screen=None) -> QPoint:
        """Computes docked QPoint in monitor work area for the given corner."""
        if screen is None:
            screen = self._get_target_screen()
        if screen is None:
            return QPoint(100, 100)

        work = screen.availableGeometry()
        margin = getattr(self.settings.keyboard, "margin", 16)
        w = self.width()
        h = self.height()

        if not corner_name:
            corner_name = getattr(self.settings.keyboard, "corner", "bottom-right") or "bottom-right"
        corner_name = str(corner_name).lower()

        # Dodge active window if setting enabled
        if getattr(self.settings.keyboard, "avoid_active_window", True) and sys.platform.startswith("win"):
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd and hwnd != int(self.winId()):
                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    rc = RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                        # If active window is in bottom-right quadrant, flip to bottom-left
                        if "right" in corner_name and (rc.right > work.center().x() and rc.bottom > work.center().y()):
                            corner_name = corner_name.replace("right", "left")
            except Exception:
                pass

        if corner_name == "top-left":
            return QPoint(work.left() + margin, work.top() + margin)
        elif corner_name == "top-right":
            return QPoint(work.right() - w - margin, work.top() + margin)
        elif corner_name == "bottom-left":
            return QPoint(work.left() + margin, work.bottom() - h - margin)
        elif corner_name == "bottom-center":
            return QPoint(work.left() + (work.width() - w) // 2, work.bottom() - h - margin)
        else: # "bottom-right" (default)
            return QPoint(work.right() - w - margin, work.bottom() - h - margin)

    def _reposition_to_corner(self):
        self._recalculate_window_size()
        pos = self.calculate_corner_position()
        self.move(pos)

    def _ensure_on_screen(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QGuiApplication
        target_rect = QRect(self.pos(), self.size())
        is_visible = any(s.geometry().intersects(target_rect) for s in QGuiApplication.screens())
        if not is_visible:
            self._reposition_to_corner()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked in header strip drag area (top 34 px)
            if event.position().y() <= 34:
                self.is_dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.is_dragging:
            self.is_dragging = False
            if getattr(self.settings.keyboard, "snap_to_corner", True):
                self._snap_to_nearest_corner()
            event.accept()

    def _snap_to_nearest_corner(self):
        """Finds closest corner among the 5 docks and smoothly snaps there."""
        screen = self._get_target_screen()
        if not screen:
            return

        corners = ["bottom-right", "bottom-left", "bottom-center", "top-right", "top-left"]
        best_corner = "bottom-right"
        min_dist = float("inf")
        cur_pos = self.pos()

        for c in corners:
            pt = self.calculate_corner_position(c, screen=screen)
            dist = math.hypot(cur_pos.x() - pt.x(), cur_pos.y() - pt.y())
            if dist < min_dist:
                min_dist = dist
                best_corner = c

        self.settings.keyboard.corner = best_corner
        target_pos = self.calculate_corner_position(best_corner, screen=screen)
        self.move(target_pos)
        return best_corner

    def animate_show(self):
        """Slides and fades keyboard in from corner edge over ~150 ms."""
        self._recalculate_window_size()
        screen = self._get_target_screen()
        self.anim_target_pos = self.calculate_corner_position(screen=screen)
        corner = getattr(self.settings.keyboard, "corner", "bottom-right")

        # Start offset slightly shifted towards the corner boundary
        offset_x = 40 if "right" in corner else (-40 if "left" in corner else 0)
        offset_y = 40 if "bottom" in corner else -40
        self.anim_start_pos = QPoint(self.anim_target_pos.x() + offset_x, self.anim_target_pos.y() + offset_y)

        self.move(self.anim_start_pos)
        self.anim_start_opacity = 0.0
        self.anim_target_opacity = getattr(self.settings.keyboard, "opacity", 0.94)
        self.setWindowOpacity(0.0)

        self.is_opening = True
        self.is_animating = True
        self.anim_progress = 0.0
        # Speed the animation timer back to 16ms for smooth slide-in.
        # (It may have been slowed to 200ms while hidden to save UI thread time.)
        self.anim_timer.setInterval(16)
        self.show()
        # showEvent applies NOACTIVATE; no need to call it again here.

    def showEvent(self, event):
        super().showEvent(event)
        try:
            apply_noactivate_style(int(self.winId()))
            self._ensure_on_screen()
        except Exception:
            pass

    def animate_hide(self):
        """Slides and fades out over ~150 ms."""
        if getattr(self.settings.keyboard, "keep_visible_dimmed", False):
            # Dim instead of hiding
            self.setWindowOpacity(0.18)
            return

        corner = getattr(self.settings.keyboard, "corner", "bottom-right")
        offset_x = 40 if "right" in corner else (-40 if "left" in corner else 0)
        offset_y = 40 if "bottom" in corner else -40

        self.anim_start_pos = self.pos()
        self.anim_target_pos = QPoint(self.anim_start_pos.x() + offset_x, self.anim_start_pos.y() + offset_y)
        self.anim_start_opacity = self.windowOpacity()
        self.anim_target_opacity = 0.0

        self.is_opening = False
        self.is_animating = True
        self.anim_progress = 0.0
        # Keep timer at 16ms during hide animation; _on_animate slows it to 200ms once hidden.

    def _recalculate_window_size(self):
        """Scales keyboard between 720 and 1100 px (about 40% of screen width)."""
        screen = self._get_target_screen()
        work_w = screen.availableGeometry().width() if screen else 1920
        target_pct = getattr(self.settings.keyboard, "width_percent", 0.40)
        desired_w = int(work_w * target_pct)
        clamped_w = max(720, min(1100, desired_w))

        # Dynamically scale key size to fit clamped width perfectly
        # 14 keys main + divider + 8 keys symbols = ~23 key units
        symbols_enabled = getattr(self.settings.keyboard, "symbols_panel_enabled", True)
        total_units = 14.5 + (9.0 if symbols_enabled else 0.0)
        avail_for_keys = clamped_w - (self.margin_x * 2) - (self.divider_width if symbols_enabled else 0)
        calc_key_size = int(avail_for_keys / total_units)
        self.key_size = max(34, min(48, calc_key_size))
        self.key_gap = max(3, int(self.key_size * 0.11))

        main_w = int(14.5 * (self.key_size + self.key_gap))
        symbols_w = int(8.5 * (self.key_size + self.key_gap)) if symbols_enabled else 0
        total_w = self.margin_x * 2 + main_w + (self.divider_width + symbols_w if symbols_w > 0 else 0)
        total_h = self.margin_y + 6 * (self.key_size + self.key_gap) + 16
        self.resize(int(total_w), int(total_h))

    def update_state(
        self,
        zone: Zone,
        row_idx: int,
        window_idx: int,
        modifiers: Dict[str, ModifierState],
        bounce: bool = False,
        swipe_progress: float = 0.0,
        swipe_dir: str = "",
        curls: Optional[Dict[str, float]] = None,
    ):
        self.active_zone = zone
        self.current_row = row_idx
        self.current_window_idx = window_idx
        self.modifiers = modifiers
        self.swipe_progress = swipe_progress
        self.swipe_direction = swipe_dir
        if curls:
            self.finger_curls = curls

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

        # Slide-and-fade animation step (~150 ms at 60 FPS is ~9-10 steps)
        if self.is_animating:
            self.anim_progress += 0.11
            if self.anim_progress >= 1.0:
                self.anim_progress = 1.0
                self.is_animating = False
                self.move(self.anim_target_pos)
                self.setWindowOpacity(self.anim_target_opacity)
                if not self.is_opening:
                    self.hide()
                # Slow the timer down when hidden — no need to keep painting at 62 Hz
                self.anim_timer.setInterval(200)
            else:
                # OutCubic easing
                t = self.anim_progress - 1.0
                ease = t * t * t + 1.0
                cur_x = int(self.anim_start_pos.x() + (self.anim_target_pos.x() - self.anim_start_pos.x()) * ease)
                cur_y = int(self.anim_start_pos.y() + (self.anim_target_pos.y() - self.anim_start_pos.y()) * ease)
                cur_op = self.anim_start_opacity + (self.anim_target_opacity - self.anim_start_opacity) * ease
                self.move(cur_x, cur_y)
                self.setWindowOpacity(cur_op)

        # Only trigger a repaint when the widget is actually visible — avoids
        # ~62 Hz paintEvent overhead on the UI thread while keyboard is hidden.
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        t0 = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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

        from instrumentation import record_paint_timing
        record_paint_timing("keyboard_ms", (time.perf_counter() - t0) * 1000.0)

    def _paint_header(self, painter: QPainter):
        # Swipe Progress Meter (Top Strip) or Drag Handle
        if getattr(self.settings.keyboard, "show_swipe_meter", True) and self.swipe_progress > 0.15:
            meter_w = 140
            meter_h = 16
            meter_x = (self.width() - meter_w) / 2
            meter_y = 4
            meter_rect = QRectF(meter_x, meter_y, meter_w, meter_h)

            painter.setBrush(QColor(23, 28, 37, 230))
            painter.setPen(QPen(QColor(BORDER), 1.0))
            painter.drawRoundedRect(meter_rect, 4, 4)

            fill_w = max(4.0, (meter_w - 4) * min(1.0, self.swipe_progress))
            fill_color = QColor(BLUE_BRIGHT if self.swipe_progress < 0.90 else AMBER)
            painter.setBrush(fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(meter_x + 2, meter_y + 2, fill_w, meter_h - 4), 3, 3)

            dir_arrow = {"UP": "▲ UP", "DOWN": "▼ DOWN", "LEFT": "◀ LEFT", "RIGHT": "▶ RIGHT"}.get(self.swipe_direction, self.swipe_direction)
            painter.setFont(get_ui_font(8, bold=True))
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.drawText(meter_rect, Qt.AlignmentFlag.AlignCenter, f"{dir_arrow} {int(self.swipe_progress * 100)}%")
        else:
            # Center Drag Handle & Title
            painter.setFont(get_ui_font(9, bold=True))
            painter.setPen(QColor(TEXT_DISABLED))
            handle_rect = QRectF(0, 4, self.width(), 16)
            painter.drawText(handle_rect, Qt.AlignmentFlag.AlignCenter, "⋮⋮ Pointer V Air Keyboard")

        # Header Info Chip: Zone and Row
        painter.setFont(get_ui_font(10, bold=True))
        zone_color = QColor(BLUE if self.active_zone == Zone.MAIN else VIOLET)
        painter.setPen(zone_color)
        painter.drawText(20, 24, f"{self.active_zone.value} · ROW {self.current_row + 1}")

        # Last Typed Strip (respecting privacy)
        if not getattr(self.settings.privacy, "hide_last_typed", False):
            painter.setFont(get_ui_font(10))
            painter.setPen(QColor(TEXT_SECONDARY))
            painter.drawText(140, 26, "Typed:")

            painter.setFont(get_mono_font(10, bold=True))
            painter.setPen(QColor(TEXT_PRIMARY))
            history_str = " ".join(self.last_typed_history[-5:])
            painter.drawText(184, 26, history_str)

        # Micro Finger Curl Bars (T, I, M, R, P)
        if getattr(self.settings.keyboard, "show_finger_bars", True):
            bars_x = self.width() - 325
            bars_y = 15
            finger_items = [("T", "thumb"), ("I", "index"), ("M", "middle"), ("R", "ring"), ("P", "pinky")]
            for idx, (label, fname) in enumerate(finger_items):
                curl = self.finger_curls.get(fname, 0.0)
                bx = bars_x + idx * 13
                # Background track 9x16
                painter.setBrush(QColor(23, 28, 37))
                painter.setPen(QPen(QColor(BORDER), 0.8))
                painter.drawRoundedRect(QRectF(bx, bars_y, 9, 16), 2, 2)
                # Fill level from bottom up
                fh = max(0.0, min(14.0, curl * 14.0))
                if fh > 0.5:
                    c_fill = QColor(BLUE_BRIGHT) if curl > 0.35 else QColor(70, 95, 130)
                    painter.setBrush(c_fill)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(QRectF(bx + 1.5, bars_y + 15.0 - fh, 6.0, fh))

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
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
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

                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key.display)
                curr_x += kw + self.key_gap

            curr_y += self.key_size + self.key_gap
