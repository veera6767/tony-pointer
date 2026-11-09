"""
Pointer V - Practice & Typing Sandbox Page
Interactive sandbox with live gesture confidence readouts and a built-in
typing test input box for practicing air-typing without switching windows.
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from theme import (
    BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG,
    RADIUS_CONTROL, RADIUS_PANEL, TEXT_DISABLED, TEXT_PRIMARY,
    TEXT_SECONDARY, get_mono_font, get_ui_font
)


class PracticePage(QWidget):
    """Practice typing and gesture confidence playground."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.start_typing_time = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Gesture Practice & Typing Sandbox")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left: Live Confidence Telemetry Card
        conf_card = QFrame()
        conf_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        c_layout = QVBoxLayout(conf_card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(10)

        c_title = QLabel("Live Gesture Confidence")
        c_title.setFont(get_ui_font(13, bold=True))
        c_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        c_layout.addWidget(c_title)

        self.lbl_pose = QLabel("Pose: Unknown")
        self.lbl_action = QLabel("Action: None")
        self.lbl_dwell = QLabel("Dwell Lock Charge: 0%")
        self.lbl_palm = QLabel("Open Palm Charge: 0%")
        self.lbl_fist = QLabel("Fist Hold Charge: 0%")

        for lbl in (self.lbl_pose, self.lbl_action, self.lbl_dwell, self.lbl_palm, self.lbl_fist):
            lbl.setFont(get_mono_font(11))
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            c_layout.addWidget(lbl)

        c_layout.addStretch()

        help_box = QLabel(
            "Instructions:\n"
            "1. Focus cursor inside the test typing box on the right.\n"
            "2. Raise open palm to engage Air Keyboard.\n"
            "3. Flex any finger to type characters directly into this box!\n"
            "4. Hold closed fist for 0.5s to exit keyboard."
        )
        help_box.setFont(get_ui_font(11))
        help_box.setStyleSheet(f"color: {TEXT_DISABLED};")
        c_layout.addWidget(help_box)

        split_layout.addWidget(conf_card, stretch=1)

        # Right: Interactive In-App Typing Box
        typing_card = QFrame()
        typing_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        t_layout = QVBoxLayout(typing_card)
        t_layout.setContentsMargins(16, 16, 16, 16)
        t_layout.setSpacing(10)

        t_header = QHBoxLayout()
        t_title = QLabel("In-App Typing Test Box")
        t_title.setFont(get_ui_font(13, bold=True))
        t_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        t_header.addWidget(t_title)

        t_header.addStretch()

        self.lbl_stats = QLabel("Chars: 0 · Words: 0")
        self.lbl_stats.setFont(get_mono_font(10))
        self.lbl_stats.setStyleSheet(f"color: {TEXT_SECONDARY};")
        t_header.addWidget(self.lbl_stats)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedSize(60, 24)
        self.btn_clear.clicked.connect(self._clear_text)
        t_header.addWidget(self.btn_clear)
        t_layout.addLayout(t_header)

        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Click here to test air keyboard typing directly inside Pointer V...")
        self.text_editor.setFont(get_ui_font(13))
        self.text_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG2_CARDS};
                border: 1px solid {BORDER_STRONG};
                border-radius: {RADIUS_CONTROL}px;
                color: {TEXT_PRIMARY};
                padding: 12px;
            }}
            QTextEdit:focus {{
                border: 1px solid {BLUE};
            }}
        """)
        self.text_editor.textChanged.connect(self._on_text_changed)
        t_layout.addWidget(self.text_editor)

        split_layout.addWidget(typing_card, stretch=2)
        layout.addLayout(split_layout)

    def _on_text_changed(self):
        text = self.text_editor.toPlainText()
        chars = len(text)
        words = len(text.split())
        self.lbl_stats.setText(f"Chars: {chars} · Words: {words}")

    def _clear_text(self):
        self.text_editor.clear()

    def update_telemetry(self, telemetry: dict):
        pose = telemetry.get("pose", "UNKNOWN")
        action = telemetry.get("status_text", "NONE")
        dwell = int(telemetry.get("dwell_progress", 0.0) * 100)
        palm = int(telemetry.get("open_palm_progress", 0.0) * 100)
        fist = int(telemetry.get("fist_progress", 0.0) * 100)

        self.lbl_pose.setText(f"Pose: {pose}")
        self.lbl_action.setText(f"Action: {action}")
        self.lbl_dwell.setText(f"Dwell Lock Charge: {dwell}%")
        self.lbl_palm.setText(f"Open Palm Charge: {palm}%")
        self.lbl_fist.setText(f"Fist Hold Charge: {fist}%")

