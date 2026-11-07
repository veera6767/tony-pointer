"""
Pointer V - Interactive Calibration Wizard Page
Step-by-step active-region corner calibration wizard with progress bar,
large readable instructions, live coordinate display, and Skip button.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG,
    GREEN, RADIUS_CONTROL, RADIUS_PANEL, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)


class CalibrationPage(QWidget):
    """Guided step-by-step corner calibration wizard."""

    calibration_completed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.current_hand = None
        self.current_step = 0
        self.samples = []

        self.steps = [
            ("Step 1 of 4: Top-Left Corner", "Point comfortably towards the TOP-LEFT corner of your primary screen area."),
            ("Step 2 of 4: Top-Right Corner", "Point comfortably towards the TOP-RIGHT corner of your primary screen area."),
            ("Step 3 of 4: Bottom-Right Corner", "Point comfortably towards the BOTTOM-RIGHT corner of your primary screen area."),
            ("Step 4 of 4: Bottom-Left Corner", "Point comfortably towards the BOTTOM-LEFT corner of your primary screen area."),
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Screen Active-Region Calibration Wizard")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 4)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        c_layout.addWidget(self.progress_bar)

        self.step_title = QLabel(self.steps[0][0])
        self.step_title.setFont(get_ui_font(14, bold=True))
        self.step_title.setStyleSheet(f"color: {BLUE};")
        c_layout.addWidget(self.step_title)

        self.step_desc = QLabel(self.steps[0][1])
        self.step_desc.setFont(get_ui_font(12))
        self.step_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        self.step_desc.setWordWrap(True)
        c_layout.addWidget(self.step_desc)

        # Coordinate box
        coord_box = QFrame()
        coord_box.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS_CONTROL}px;")
        coord_layout = QVBoxLayout(coord_box)
        coord_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_norm_pos = QLabel("Normalized Fingertip: Searching for index finger...")
        self.lbl_norm_pos.setFont(get_mono_font(11))
        self.lbl_norm_pos.setStyleSheet(f"color: {TEXT_PRIMARY};")
        coord_layout.addWidget(self.lbl_norm_pos)

        self.lbl_status = QLabel("Position hand comfortably within webcam view")
        self.lbl_status.setFont(get_ui_font(10))
        self.lbl_status.setStyleSheet(f"color: {TEXT_DISABLED};")
        coord_layout.addWidget(self.lbl_status)

        c_layout.addWidget(coord_box)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_capture = QPushButton("Capture Current Point")
        self.btn_capture.setObjectName("PrimaryButton")
        self.btn_capture.setFixedHeight(36)
        self.btn_capture.clicked.connect(self._capture_point)
        btn_row.addWidget(self.btn_capture)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setFixedHeight(36)
        self.btn_reset.clicked.connect(self._reset_wizard)
        btn_row.addWidget(self.btn_reset)

        btn_row.addStretch()

        self.btn_skip = QPushButton("Skip Calibration")
        self.btn_skip.setFixedHeight(36)
        self.btn_skip.clicked.connect(self._skip_wizard)
        btn_row.addWidget(self.btn_skip)

        c_layout.addLayout(btn_row)
        layout.addWidget(card)
        layout.addStretch()

    def update_hand(self, hand):
        self.current_hand = hand
        if hand:
            tip = hand.get(8)
            self.lbl_norm_pos.setText(f"Normalized Fingertip: X: {tip.x:.3f}, Y: {tip.y:.3f}")
            self.lbl_status.setText("Hand detected. Hold still and press Capture.")
            self.lbl_status.setStyleSheet(f"color: {GREEN};")
        else:
            self.lbl_norm_pos.setText("Normalized Fingertip: Hand not detected")
            self.lbl_status.setText("Position hand comfortably within webcam view")
            self.lbl_status.setStyleSheet(f"color: {AMBER};")

    def _capture_point(self):
        if not self.current_hand:
            QMessageBox.warning(self, "No Hand Detected", "Please keep your index finger in view of the webcam.")
            return

        tip = self.current_hand.get(8)
        self.samples.append((tip.x, tip.y))
        self.current_step += 1
        self.progress_bar.setValue(self.current_step)

        if self.current_step < 4:
            self.step_title.setText(self.steps[self.current_step][0])
            self.step_desc.setText(self.steps[self.current_step][1])
        else:
            xs = [pt[0] for pt in self.samples]
            ys = [pt[1] for pt in self.samples]

            x_min = max(0.05, min(xs))
            x_max = min(0.95, max(xs))
            y_min = max(0.05, min(ys))
            y_max = min(0.95, max(ys))

            self.settings.active_region.x_min = round(x_min, 3)
            self.settings.active_region.x_max = round(x_max, 3)
            self.settings.active_region.y_min = round(y_min, 3)
            self.settings.active_region.y_max = round(y_max, 3)

            QMessageBox.information(
                self,
                "Calibration Complete",
                f"Active Region successfully calibrated!\nX: [{x_min:.2f} .. {x_max:.2f}], Y: [{y_min:.2f} .. {y_max:.2f}]",
            )
            self.calibration_completed.emit()
            self._reset_wizard()

    def _reset_wizard(self):
        self.current_step = 0
        self.samples = []
        self.progress_bar.setValue(0)
        self.step_title.setText(self.steps[0][0])
        self.step_desc.setText(self.steps[0][1])

    def _skip_wizard(self):
        self.calibration_completed.emit()

