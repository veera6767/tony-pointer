"""
Pointer V - Gestures Reference & Live Sensor Debug
Displays clean list of all gestures with the live detected gesture highlighted,
plus per-finger curl meters for anatomical debugging.
"""

from typing import Dict
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget
)

from theme import (
    BG1_PANELS, BG2_CARDS, BG3_HOVER, BLUE, BORDER, RADIUS_CONTROL, RADIUS_PANEL, TEXT_DISABLED, TEXT_PRIMARY,
    TEXT_SECONDARY, get_mono_font, get_ui_font
)

GESTURES_INFO = [
    ("Move Cursor", "Pointing pose (Index extended, others curled)", "Moves cursor with One Euro smoothing"),
    ("Air Double-Tap", "Swift curl-and-release flexure of index twice within 500ms", "Double Left Click (opens apps/folders)"),
    ("Air Single-Tap", "Swift flexure of index finger", "Single Left Click (configurable)"),
    ("Open Air Keyboard", "Hold OPEN PALM towards camera for ~0.5s", "Launches Floating Air Keyboard HUD"),
    ("Close Air Keyboard", "Hold FIST ~0.5s or switch to Pointing", "Closes keyboard and resumes Pointer mode"),
    ("Pause Tracking", "Hold CLOSED FIST for 1.5s in Pointer mode", "Pauses tracking output; preview stays on"),
    ("Air Type Key", "Swift curl-and-release of any of the 4 typing fingers", "Types the locked key under that finger"),
    ("Thumb Space", "Swift curl-and-release of Thumb", "Types Space bar"),
    ("Slide Row (Up/Down)", "Move whole open hand up or down deliberately", "Jumps active 4-key window up or down one row"),
    ("Hop Window (Left/Right)", "Move whole open hand left or right deliberately", "Hops to next 4-key progressive window"),
    ("Cross into Symbols", "Swipe Right from last window of Main keyboard", "Crosses divider smoothly into Symbols panel"),
    ("Right Click", "Index + Middle fingers extended and held still for 0.45s", "Opens Windows Context Menu"),
    ("Two-Finger Scroll", "Index + Middle fingers extended, move up/down vertically", "Smoothly scrolls pages / documents"),
    ("Brush Lock (Pinch)", "Touch Thumb tip to Index fingertip", "Locks left mouse button DOWN for drawing/painting"),
    ("Brush Lock (Dwell)", "Hold index finger stationary for 0.6 seconds", "Locks left mouse button DOWN"),
    ("Emergency Release", "Press Esc or hand lost > 1.0s", "Releases all held buttons and keys instantly"),
]


class GesturesPage(QWidget):
    """Gestures catalogue and real-time curl sensor telemetry."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.gesture_rows: Dict[str, QFrame] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Gesture Detection & Finger Curl Sensors")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left: Clean Gesture Table
        table_card = QFrame()
        table_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(16, 16, 16, 16)
        t_layout.setSpacing(8)

        t_title = QLabel("Gesture Catalogue")
        t_title.setFont(get_ui_font(13, bold=True))
        t_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        t_layout.addWidget(t_title)

        for name, pose_desc, action_desc in GESTURES_INFO:
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER}; border-radius: {RADIUS_CONTROL}px;")
            r_box = QHBoxLayout(row_frame)
            r_box.setContentsMargins(12, 6, 12, 6)

            n_lbl = QLabel(name)
            n_lbl.setFont(get_ui_font(11, bold=True))
            n_lbl.setFixedWidth(160)
            n_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
            r_box.addWidget(n_lbl)

            p_lbl = QLabel(pose_desc)
            p_lbl.setFont(get_ui_font(11))
            p_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            r_box.addWidget(p_lbl)

            a_lbl = QLabel(action_desc)
            a_lbl.setFont(get_ui_font(11))
            a_lbl.setStyleSheet(f"color: {TEXT_DISABLED};")
            r_box.addWidget(a_lbl)

            t_layout.addWidget(row_frame)
            self.gesture_rows[name.lower()] = row_frame

        t_layout.addStretch()
        split_layout.addWidget(table_card, stretch=3)

        # Right: Per-Finger Curl Meters
        sensor_card = QFrame()
        sensor_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        s_layout = QVBoxLayout(sensor_card)
        s_layout.setContentsMargins(16, 16, 16, 16)
        s_layout.setSpacing(12)

        s_title = QLabel("Per-Finger Curl Telemetry")
        s_title.setFont(get_ui_font(13, bold=True))
        s_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        s_layout.addWidget(s_title)

        s_desc = QLabel("Real-time angular flexion sensor values (0% straight, 100% curled).")
        s_desc.setFont(get_ui_font(10))
        s_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        s_desc.setWordWrap(True)
        s_layout.addWidget(s_desc)

        self.curl_bars = {}
        for f in ("thumb", "index", "middle", "ring", "pinky"):
            f_box = QVBoxLayout()
            f_header = QHBoxLayout()
            lbl = QLabel(f.capitalize())
            lbl.setFont(get_ui_font(11, bold=True))
            lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
            val_lbl = QLabel("0%")
            val_lbl.setFont(get_mono_font(10))
            val_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            f_header.addWidget(lbl)
            f_header.addStretch()
            f_header.addWidget(val_lbl)
            f_box.addLayout(f_header)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(8)
            f_box.addWidget(bar)
            s_layout.addLayout(f_box)

            self.curl_bars[f] = (bar, val_lbl)

        s_layout.addStretch()
        split_layout.addWidget(sensor_card, stretch=1)

        layout.addLayout(split_layout)

    def update_telemetry(self, curls: dict, status_text: str):
        for f, (bar, val_lbl) in self.curl_bars.items():
            val = int(curls.get(f, 0.0) * 100)
            bar.setValue(val)
            val_lbl.setText(f"{val}%")

        # Highlight active gesture row
        st_lower = status_text.lower()
        for name, frame in self.gesture_rows.items():
            if name in st_lower or st_lower in name:
                frame.setStyleSheet(f"background-color: {BG3_HOVER}; border: 1px solid {BLUE}; border-radius: {RADIUS_CONTROL}px;")
            else:
                frame.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER}; border-radius: {RADIUS_CONTROL}px;")

