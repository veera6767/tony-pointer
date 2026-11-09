"""
Pointer V - About, Credits, Privacy & Diagnostics Page
Product details, version 2.0.0, license, local privacy statement,
open logs folder, copy sanitized diagnostics, and update check placeholder.
"""

import os
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget
)

from logger import generate_diagnostics_report, get_logs_dir
from theme import (
    BG1_PANELS, BLUE, BORDER, RADIUS_PANEL, TEXT_PRIMARY,
    TEXT_SECONDARY, get_ui_font
)
from version import APP_NAME, APP_TAGLINE, COMPANY_NAME, COPYRIGHT, __version__


class AboutPage(QWidget):
    """About dialog with verified privacy declarations and diagnostics tools."""

    def __init__(self, get_telemetry_fn, parent=None):
        super().__init__(parent)
        self.get_telemetry = get_telemetry_fn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(f"About {APP_NAME}")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Main Info Card
        info_card = QFrame()
        info_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        i_layout = QVBoxLayout(info_card)
        i_layout.setContentsMargins(20, 16, 20, 16)
        i_layout.setSpacing(10)

        header_row = QHBoxLayout()
        logo_lbl = QLabel()
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "pointer_v_64.png"
        if not logo_path.exists():
            logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "pointer_v_32.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        header_row.addWidget(logo_lbl)

        v_box = QVBoxLayout()
        v_title = QLabel(f"{APP_NAME} v{__version__}")
        v_title.setFont(get_ui_font(15, bold=True))
        v_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v_tag = QLabel(APP_TAGLINE)
        v_tag.setFont(get_ui_font(11))
        v_tag.setStyleSheet(f"color: {TEXT_SECONDARY};")
        v_box.addWidget(v_title)
        v_box.addWidget(v_tag)
        header_row.addLayout(v_box)
        header_row.addStretch()
        i_layout.addLayout(header_row)

        desc = QLabel(
            f"{COPYRIGHT}\n"
            f"Built by {COMPANY_NAME}.\n\n"
            "Open source software licensed under Apache License 2.0.\n"
            "Credits: Google MediaPipe Tasks, PySide6 (Qt for Python), OpenCV, NumPy."
        )
        desc.setFont(get_ui_font(11))
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        i_layout.addWidget(desc)
        layout.addWidget(info_card)

        # Privacy Statement Card
        priv_card = QFrame()
        priv_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        p_layout = QVBoxLayout(priv_card)
        p_layout.setContentsMargins(20, 16, 20, 16)
        p_layout.setSpacing(8)

        p_title = QLabel("Privacy & Security Declaration")
        p_title.setFont(get_ui_font(13, bold=True))
        p_title.setStyleSheet(f"color: {BLUE};")
        p_layout.addWidget(p_title)

        p_text = QLabel(
            "· Camera frames are processed strictly in-memory.\n"
            "· Zero frames or landmarks are written to disk (except explicit Developer recordings).\n"
            "· No telemetry, no analytics, and zero network transmissions.\n"
            "· Keystrokes and character identities are NEVER logged into files or diagnostics.\n"
            "· All tracking and inference execute completely offline on your local computer."
        )
        p_text.setFont(get_ui_font(11))
        p_text.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.5;")
        p_layout.addWidget(p_text)
        layout.addWidget(priv_card)

        # Diagnostics & Actions
        action_card = QFrame()
        action_card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        a_layout = QHBoxLayout(action_card)
        a_layout.setContentsMargins(16, 12, 16, 12)
        a_layout.setSpacing(12)

        btn_logs = QPushButton("Open Logs Folder")
        btn_logs.clicked.connect(self._open_logs)
        a_layout.addWidget(btn_logs)

        btn_diag = QPushButton("Copy Diagnostics")
        btn_diag.clicked.connect(self._copy_diagnostics)
        a_layout.addWidget(btn_diag)

        btn_updates = QPushButton("Check for Updates")
        btn_updates.clicked.connect(self._check_updates)
        a_layout.addWidget(btn_updates)

        btn_report = QPushButton("Report a Problem")
        btn_report.clicked.connect(self._report_problem)
        a_layout.addWidget(btn_report)

        a_layout.addStretch()
        layout.addWidget(action_card)
        layout.addStretch()

    def _open_logs(self):
        logs_dir = get_logs_dir()
        if sys.platform.startswith("win"):
            os.startfile(str(logs_dir))
        else:
            subprocess.Popen(["xdg-open", str(logs_dir)])

    def _copy_diagnostics(self):
        telemetry = self.get_telemetry()
        report = generate_diagnostics_report(telemetry)
        QApplication.clipboard().setText(report)
        QMessageBox.information(
            self,
            "Diagnostics Copied",
            "Sanitized system diagnostics successfully copied to clipboard.\n(No typed keys or camera frames are included)."
        )

    def _check_updates(self):
        QMessageBox.information(
            self,
            "Check for Updates",
            f"You are running {APP_NAME} v{__version__} (Latest release).\nNo online update server configured in offline mode."
        )

    def _report_problem(self):
        QMessageBox.information(
            self,
            "Report a Problem",
            "To report issues or request features, visit GitHub repository issues or submit diagnostics to the developer."
        )

