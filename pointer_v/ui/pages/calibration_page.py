"""
Pointer V - Interactive Calibration Wizard & Gesture Lab Page
Step-by-step active-region corner calibration wizard and guided
per-finger curl / sensitivity calibration with live feedback.
"""

from typing import Dict, List, Tuple
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QTabWidget, QVBoxLayout, QWidget
)

from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BLUE_BRIGHT, BORDER, BORDER_STRONG,
    CYAN, GREEN, RADIUS_CONTROL, RADIUS_PANEL, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)


class CalibrationPage(QWidget):
    """Guided step-by-step corner calibration wizard and Gesture Lab."""

    calibration_completed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.current_hand = None
        self.current_step = 0
        self.samples: List[Tuple[float, float]] = []

        # Gesture lab state
        self.gesture_lab_step = 0
        self.lab_straight_curls: Dict[str, float] = {}
        self.lab_curled_curls: Dict[str, float] = {}
        self.lab_pointing_curls: Dict[str, float] = {}

        self.steps = [
            ("Step 1 of 4: Top-Left Corner", "Point comfortably towards the TOP-LEFT corner of your primary screen area."),
            ("Step 2 of 4: Top-Right Corner", "Point comfortably towards the TOP-RIGHT corner of your primary screen area."),
            ("Step 3 of 4: Bottom-Right Corner", "Point comfortably towards the BOTTOM-RIGHT corner of your primary screen area."),
            ("Step 4 of 4: Bottom-Left Corner", "Point comfortably towards the BOTTOM-LEFT corner of your primary screen area."),
        ]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        title = QLabel("Calibration Center & Gesture Lab")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                border-radius: {RADIUS_PANEL}px;
                background-color: {BG1_PANELS};
            }}
            QTabBar::tab {{
                background-color: {BG2_CARDS};
                color: {TEXT_SECONDARY};
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {BG1_PANELS};
                color: {BLUE_BRIGHT};
                border-bottom: 2px solid {BLUE};
            }}
        """)

        # Tab 1: Screen Active Region
        tab_region = QWidget()
        self._build_region_tab(tab_region)
        self.tabs.addTab(tab_region, "Screen Active Region")

        # Tab 2: Gesture Lab
        tab_lab = QWidget()
        self._build_gesture_lab_tab(tab_lab)
        self.tabs.addTab(tab_lab, "Gesture Lab & Finger Calibration")

        main_layout.addWidget(self.tabs)

    def _build_region_tab(self, parent):
        c_layout = QVBoxLayout(parent)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(14)

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
        c_layout.addStretch()

    def _build_gesture_lab_tab(self, parent):
        l_layout = QVBoxLayout(parent)
        l_layout.setContentsMargins(20, 20, 20, 20)
        l_layout.setSpacing(12)

        header = QLabel("Guided Gesture & Finger Curl Calibration")
        header.setFont(get_ui_font(13, bold=True))
        header.setStyleSheet(f"color: {TEXT_PRIMARY};")
        l_layout.addWidget(header)

        desc = QLabel(
            "Calibrates your hand's relaxed vs curled geometry for reliable click air taps and pointing recognition."
        )
        desc.setFont(get_ui_font(11))
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        l_layout.addWidget(desc)

        # Live Curl Readouts
        box = QFrame()
        box.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS_CONTROL}px;")
        b_layout = QVBoxLayout(box)
        b_layout.setContentsMargins(14, 10, 14, 10)

        self.lbl_live_curls = QLabel("Live Curls: Thumb: 0% · Index: 0% · Middle: 0% · Ring: 0% · Pinky: 0%")
        self.lbl_live_curls.setFont(get_mono_font(10, bold=True))
        self.lbl_live_curls.setStyleSheet(f"color: {CYAN};")
        b_layout.addWidget(self.lbl_live_curls)

        self.lbl_lab_status = QLabel("Step 1: Hold hand flat with all fingers straight, then click 'Record Straight Hand'.")
        self.lbl_lab_status.setFont(get_ui_font(11))
        self.lbl_lab_status.setStyleSheet(f"color: {TEXT_PRIMARY};")
        b_layout.addWidget(self.lbl_lab_status)
        l_layout.addWidget(box)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_rec_straight = QPushButton("1. Record Straight Hand")
        self.btn_rec_straight.setFixedHeight(34)
        self.btn_rec_straight.clicked.connect(self._record_straight)
        btn_row.addWidget(self.btn_rec_straight)

        self.btn_rec_fist = QPushButton("2. Record Closed Fist")
        self.btn_rec_fist.setFixedHeight(34)
        self.btn_rec_fist.clicked.connect(self._record_fist)
        btn_row.addWidget(self.btn_rec_fist)

        self.btn_rec_point = QPushButton("3. Record Natural Pointing")
        self.btn_rec_point.setFixedHeight(34)
        self.btn_rec_point.clicked.connect(self._record_pointing)
        btn_row.addWidget(self.btn_rec_point)

        self.btn_apply_lab = QPushButton("Apply Calibration")
        self.btn_apply_lab.setObjectName("PrimaryButton")
        self.btn_apply_lab.setFixedHeight(34)
        self.btn_apply_lab.clicked.connect(self._apply_gesture_calibration)
        btn_row.addWidget(self.btn_apply_lab)

        l_layout.addLayout(btn_row)

        self.lbl_lab_results = QLabel("Results: Waiting for recording steps...")
        self.lbl_lab_results.setFont(get_mono_font(10))
        self.lbl_lab_results.setStyleSheet(f"color: {TEXT_SECONDARY};")
        l_layout.addWidget(self.lbl_lab_results)
        l_layout.addStretch()

    def update_hand(self, hand):
        self.current_hand = hand
        if hand:
            tip = hand.get(8)
            self.lbl_norm_pos.setText(f"Normalized Fingertip: X: {tip.x:.3f}, Y: {tip.y:.3f}")
            self.lbl_status.setText("Hand detected. Hold still and press Capture.")
            self.lbl_status.setStyleSheet(f"color: {GREEN};")

            # Update live curl readouts
            curls = self._measure_curls(hand)
            c_str = f"Live Curls: T:{curls['thumb']*100:.0f}% · I:{curls['index']*100:.0f}% · M:{curls['middle']*100:.0f}% · R:{curls['ring']*100:.0f}% · P:{curls['pinky']*100:.0f}%"
            self.lbl_live_curls.setText(c_str)
        else:
            self.lbl_norm_pos.setText("Normalized Fingertip: Hand not detected")
            self.lbl_status.setText("Position hand comfortably within webcam view")
            self.lbl_status.setStyleSheet(f"color: {AMBER};")

    def _measure_curls(self, hand) -> Dict[str, float]:
        fingers = [("index", 8, 6, 5), ("middle", 12, 10, 9), ("ring", 16, 14, 13), ("pinky", 20, 18, 17)]
        res = {}
        for f_name, tip_idx, pip_idx, mcp_idx in fingers:
            pip_angle = hand.angle_deg(mcp_idx, pip_idx, tip_idx)
            curl_metric = max(0.0, min(1.0, (170.0 - pip_angle) / 70.0))
            res[f_name] = curl_metric
        t_angle = hand.angle_deg(1, 2, 4)
        res["thumb"] = max(0.0, min(1.0, (160.0 - t_angle) / 55.0))
        return res

    def _record_straight(self):
        if not self.current_hand:
            QMessageBox.warning(self, "No Hand Detected", "Please place your hand in view of the webcam.")
            return
        self.lab_straight_curls = self._measure_curls(self.current_hand)
        self.lbl_lab_status.setText("Step 2: Close your hand into a gentle fist and click 'Record Closed Fist'.")
        self.lbl_lab_results.setText(f"Straight Baseline Recorded: Index curl = {self.lab_straight_curls['index']*100:.0f}%")

    def _record_fist(self):
        if not self.current_hand:
            QMessageBox.warning(self, "No Hand Detected", "Please place your hand in view of the webcam.")
            return
        self.lab_curled_curls = self._measure_curls(self.current_hand)
        self.lbl_lab_status.setText("Step 3: Extend your index finger naturally to point, then click 'Record Natural Pointing'.")
        self.lbl_lab_results.setText(f"Fist Baseline Recorded: Index curl = {self.lab_curled_curls['index']*100:.0f}%")

    def _record_pointing(self):
        if not self.current_hand:
            QMessageBox.warning(self, "No Hand Detected", "Please place your hand in view of the webcam.")
            return
        self.lab_pointing_curls = self._measure_curls(self.current_hand)
        self.lbl_lab_status.setText("Ready! Click 'Apply Calibration' to save your personalized settings.")
        self.lbl_lab_results.setText(
            f"Pointing Recorded: Index = {self.lab_pointing_curls['index']*100:.0f}%, Middle = {self.lab_pointing_curls['middle']*100:.0f}%"
        )

    def _apply_gesture_calibration(self):
        if not self.lab_straight_curls or not self.lab_pointing_curls:
            QMessageBox.information(self, "Notice", "Please record at least Straight Hand and Natural Pointing baselines first.")
            return

        # Personalize pointing sensitivity
        straight_idx = self.lab_straight_curls.get("index", 0.1)
        point_idx = self.lab_pointing_curls.get("index", 0.15)
        point_mid = self.lab_pointing_curls.get("middle", 0.7)

        # If natural pointing has slightly curled index or relaxed middle, bump pointing sensitivity
        calibrated_sens = 1.0
        if point_idx > 0.20 or point_mid < 0.65:
            calibrated_sens = 1.25

        self.settings.gestures.pointing_sensitivity = calibrated_sens
        self.lbl_lab_results.setText(f"Calibration Applied! Pointing Sensitivity set to {calibrated_sens:.2f}x.")
        QMessageBox.information(
            self,
            "Gesture Lab Calibrated",
            f"Personalized hand geometry calibrated successfully!\nPointing Sensitivity: {calibrated_sens:.2f}x"
        )
        self.calibration_completed.emit()

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
