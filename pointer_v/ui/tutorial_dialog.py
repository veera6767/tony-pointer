"""
Pointer V - First-Run Interactive Tutorial Dialog
6-8 step interactive onboarding checking each gesture live with automatic advance,
clear line hints, and 'Don't show on startup' preference saving.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QVBoxLayout
)

from theme import (
    AMBER, BG0_WINDOW, BG1_PANELS, BLUE, BORDER,
    GREEN, RADIUS_PANEL, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)

TUTORIAL_STEPS = [
    {
        "title": "Step 1 of 7: Pointing & Cursor Motion",
        "instruction": "Extend only your index finger with other fingers curled into a loose fist. Move your hand to guide the cursor.",
        "target_pose": "POINTING",
    },
    {
        "title": "Step 2 of 7: Air Double-Tap",
        "instruction": "Flex and release your index finger twice quickly (within 500ms) to trigger an air double-click.",
        "target_action": "DOUBLE_CLICK",
    },
    {
        "title": "Step 3 of 7: Engage Air Keyboard",
        "instruction": "Raise your open hand (all fingers extended, palm facing camera) and hold steady for 0.5 seconds.",
        "target_pose": "OPEN_PALM",
    },
    {
        "title": "Step 4 of 7: Sliding Door Row Swipe",
        "instruction": "While the Air Keyboard is open, swipe your whole open hand UP or DOWN to jump between rows.",
        "target_action": "SWIPE_ROW",
    },
    {
        "title": "Step 5 of 7: Hop 4-Key Windows",
        "instruction": "Swipe your whole hand LEFT or RIGHT to glide the electric-blue 4-key window along the row.",
        "target_action": "SWIPE_WINDOW",
    },
    {
        "title": "Step 6 of 7: Independent Finger Air-Tap",
        "instruction": "Curl any of your four typing fingers (Index, Middle, Ring, Pinky) to type the blue-glowing key under it.",
        "target_action": "KEY_TYPED",
    },
    {
        "title": "Step 7 of 7: Brush Lock (Paint Mode)",
        "instruction": "Pinch your thumb tip and index fingertip together, or dwell still for 0.6s to lock the left click down.",
        "target_pose": "PINCH",
    },
]


class TutorialDialog(QDialog):
    """Guided onboarding dialog that monitors gestures in real time."""

    def __init__(self, settings, get_telemetry_fn, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.get_telemetry = get_telemetry_fn
        self.current_step = 0

        self.setWindowTitle("Pointer V - Welcome & Quick Tutorial")
        self.setFixedSize(620, 420)
        self.setStyleSheet(f"background-color: {BG0_WINDOW}; color: {TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, len(TUTORIAL_STEPS))
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(14)

        self.title_lbl = QLabel(TUTORIAL_STEPS[0]["title"])
        self.title_lbl.setFont(get_ui_font(15, bold=True))
        self.title_lbl.setStyleSheet(f"color: {BLUE};")
        c_layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(TUTORIAL_STEPS[0]["instruction"])
        self.desc_lbl.setFont(get_ui_font(12))
        self.desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        self.desc_lbl.setWordWrap(True)
        c_layout.addWidget(self.desc_lbl)

        # Telemetry chip
        self.status_chip = QLabel("Waiting for gesture...")
        self.status_chip.setFont(get_mono_font(11))
        self.status_chip.setStyleSheet(f"color: {AMBER};")
        c_layout.addWidget(self.status_chip)

        layout.addWidget(card)

        # Bottom Bar: Checkbox + Skip + Next
        bot_row = QHBoxLayout()
        self.chk_dont_show = QCheckBox("Don't show tutorial on startup")
        self.chk_dont_show.setChecked(not getattr(self.settings, "show_tutorial_on_startup", True))
        self.chk_dont_show.toggled.connect(self._on_dont_show_toggled)
        bot_row.addWidget(self.chk_dont_show)

        bot_row.addStretch()

        self.btn_next = QPushButton("Next Step")
        self.btn_next.clicked.connect(self._advance_step)
        bot_row.addWidget(self.btn_next)

        self.btn_skip = QPushButton("Skip Tutorial")
        self.btn_skip.clicked.connect(self.accept)
        bot_row.addWidget(self.btn_skip)

        layout.addLayout(bot_row)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._check_gesture_match)
        self.poll_timer.start(50)

    def _check_gesture_match(self):
        telem = self.get_telemetry()
        pose = telem.get("pose", "")
        action = telem.get("action", "")

        step_data = TUTORIAL_STEPS[self.current_step]
        matched = False

        if "target_pose" in step_data and step_data["target_pose"] == pose:
            matched = True
        elif "target_action" in step_data and step_data["target_action"] == action:
            matched = True

        if matched:
            self.status_chip.setText(f"Gesture detected! ({pose or action})")
            self.status_chip.setStyleSheet(f"color: {GREEN};")
            # Auto-advance after small pause
            QTimer.singleShot(600, self._advance_step)
        else:
            self.status_chip.setText(f"Current Pose: {pose} · Action: {action}")
            self.status_chip.setStyleSheet(f"color: {TEXT_DISABLED};")

    def _advance_step(self):
        self.current_step += 1
        self.progress.setValue(self.current_step)
        if self.current_step >= len(TUTORIAL_STEPS):
            self.settings.tutorial_completed = True
            self.accept()
            return

        data = TUTORIAL_STEPS[self.current_step]
        self.title_lbl.setText(data["title"])
        self.desc_lbl.setText(data["instruction"])

    def _on_dont_show_toggled(self, checked: bool):
        self.settings.show_tutorial_on_startup = not checked

