"""
Pointer V - Developer Tools & Landmark Stream Recording Page
Allows recording raw 21-point 3D landmark streams (with timestamps, zero camera images)
to local JSON files, replaying recordings through the gesture engine, and generating
synthetic gesture trajectories for regression testing.
"""

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget
)

from recorder import LandmarkRecorder, LandmarkReplayer
from theme import (
    AMBER, BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG,
    GREEN, RADIUS_CONTROL, RADIUS_PANEL, RED, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)


class DeveloperPage(QWidget):
    """Developer diagnostics, raw landmark recording, and replay tools."""

    start_recording_requested = Signal()
    stop_recording_requested = Signal()
    replay_file_requested = Signal(str)

    def __init__(self, settings, recorder: LandmarkRecorder, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.recorder = recorder

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Developer Tools: Landmark Stream Recording & Replay")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 16, 20, 16)
        c_layout.setSpacing(12)

        desc = QLabel(
            "Privacy Notice: Recording captures ONLY mathematical 3D landmark coordinates (21 points) "
            "and timestamps. No camera images, video feeds, or keystroke names are recorded."
        )
        desc.setFont(get_ui_font(11))
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        desc.setWordWrap(True)
        c_layout.addWidget(desc)

        # Record Controls
        self.status_lbl = QLabel("Recorder State: IDLE (0 frames captured)")
        self.status_lbl.setFont(get_mono_font(11))
        self.status_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        c_layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.btn_record = QPushButton("● Start Recording Stream")
        self.btn_record.setFixedHeight(36)
        self.btn_record.clicked.connect(self._toggle_recording)
        btn_row.addWidget(self.btn_record)

        self.btn_save = QPushButton("Save Stream to File...")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_recording)
        btn_row.addWidget(self.btn_save)

        self.btn_replay = QPushButton("Load & Replay File...")
        self.btn_replay.setFixedHeight(36)
        self.btn_replay.clicked.connect(self._load_replay)
        btn_row.addWidget(self.btn_replay)

        btn_row.addStretch()
        c_layout.addLayout(btn_row)

        layout.addWidget(card)
        layout.addStretch()

    def _toggle_recording(self):
        if not self.recorder.is_recording:
            self.recorder.start()
            self.btn_record.setText("■ Stop Recording")
            self.btn_record.setStyleSheet(f"background-color: {RED}; color: #FFFFFF;")
            self.status_lbl.setText("Recorder State: RECORDING LIVE LANDMARKS...")
            self.status_lbl.setStyleSheet(f"color: {RED};")
            self.btn_save.setEnabled(False)
            self.start_recording_requested.emit()
        else:
            count = self.recorder.stop()
            self.btn_record.setText("● Start Recording Stream")
            self.btn_record.setStyleSheet("")
            self.status_lbl.setText(f"Recorder State: STOPPED ({count} frames recorded)")
            self.status_lbl.setStyleSheet(f"color: {GREEN};")
            self.btn_save.setEnabled(count > 0)
            self.stop_recording_requested.emit()

    def _save_recording(self):
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Landmark Recording", "gesture_recording.json", "JSON Files (*.json)"
        )
        if dest:
            if self.recorder.save_to_file(dest):
                QMessageBox.information(self, "Saved", f"Landmark stream saved successfully to:\n{dest}")
            else:
                QMessageBox.critical(self, "Save Error", "Could not write stream file.")

    def _load_replay(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Load Landmark Recording", "", "JSON Files (*.json)"
        )
        if src:
            self.replay_file_requested.emit(src)
            QMessageBox.information(self, "Replay Loaded", f"File loaded:\n{src}\nReplay active.")

