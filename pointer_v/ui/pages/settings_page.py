"""
Pointer V - Settings Management Page
Grouped sections: Pointer, Clicks, Paint, Keyboard, Hand & Camera, Privacy, Sound, Hotkeys, Startup.
Form rows with label on left, control on right, helper text underneath.
Export/Import settings JSON and per-section reset to defaults.
"""

from dataclasses import asdict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QSlider, QSpinBox, QVBoxLayout, QWidget, QLineEdit
)

from settings import AppConfig
from theme import (
    BG1_PANELS, BG2_CARDS, BLUE, BORDER, BORDER_STRONG,
    RADIUS_CONTROL, RADIUS_PANEL, RED, TEXT_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, get_mono_font, get_ui_font
)


class SettingsPage(QWidget):
    """Full settings inspector and configuration coordinator."""

    settings_changed = Signal()

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings = settings_manager.config

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(14)

        # Header with Title + Export/Import Buttons
        header = QHBoxLayout()
        title = QLabel("Application Settings")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)

        header.addStretch()

        btn_export = QPushButton("Export Settings...")
        btn_export.clicked.connect(self._export_settings)
        header.addWidget(btn_export)

        btn_import = QPushButton("Import Settings...")
        btn_import.clicked.connect(self._import_settings)
        header.addWidget(btn_import)
        main_layout.addLayout(header)

        # Scroll Area for grouped forms
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }}")

        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setSpacing(18)

        # 1. Pointer & Smoothing Section
        form_layout.addWidget(self._build_pointer_section())

        # 2. Clicks & Gestures Section
        form_layout.addWidget(self._build_clicks_section())

        # 3. Paint Mode Section
        form_layout.addWidget(self._build_paint_section())

        # 4. Keyboard Section
        form_layout.addWidget(self._build_keyboard_section())

        # 5. Hand & Camera Section
        form_layout.addWidget(self._build_camera_section())

        # 6. Privacy Section
        form_layout.addWidget(self._build_privacy_section())

        # 7. Sound Section
        form_layout.addWidget(self._build_sound_section())

        # 8. Hotkeys & Startup Section
        form_layout.addWidget(self._build_hotkeys_startup_section())

        form_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_section_card(self, title_text: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        t_lbl = QLabel(title_text)
        t_lbl.setFont(get_ui_font(13, bold=True))
        t_lbl.setStyleSheet(f"color: {BLUE}; margin-bottom: 4px;")
        layout.addWidget(t_lbl)
        return card, layout

    def _build_pointer_section(self) -> QWidget:
        card, box = self._create_section_card("1. Pointer Sensitivity & One Euro Smoothing")
        form = QFormLayout()
        form.setSpacing(10)

        self.spin_sens = QDoubleSpinBox()
        self.spin_sens.setRange(0.2, 5.0)
        self.spin_sens.setSingleStep(0.1)
        self.spin_sens.setValue(self.settings.sensitivity)
        self.spin_sens.valueChanged.connect(self._save)
        form.addRow("Pointer Speed Multiplier:", self.spin_sens)

        self.spin_min_cutoff = QDoubleSpinBox()
        self.spin_min_cutoff.setRange(0.1, 5.0)
        self.spin_min_cutoff.setSingleStep(0.1)
        self.spin_min_cutoff.setValue(self.settings.one_euro.min_cutoff)
        self.spin_min_cutoff.valueChanged.connect(self._save)
        form.addRow("One Euro Min Cutoff (Rest Jitter Suppression Hz):", self.spin_min_cutoff)

        self.spin_beta = QDoubleSpinBox()
        self.spin_beta.setRange(0.0005, 0.05)
        self.spin_beta.setDecimals(4)
        self.spin_beta.setSingleStep(0.001)
        self.spin_beta.setValue(self.settings.one_euro.beta)
        self.spin_beta.valueChanged.connect(self._save)
        form.addRow("One Euro Beta (High-Speed Lag Adaptation):", self.spin_beta)

        box.addLayout(form)
        return card

    def _build_clicks_section(self) -> QWidget:
        card, box = self._create_section_card("2. Click Gestures & Dwell Parameters")
        form = QFormLayout()
        form.setSpacing(10)

        self.spin_double_tap = QSpinBox()
        self.spin_double_tap.setRange(200, 800)
        self.spin_double_tap.setSingleStep(25)
        self.spin_double_tap.setValue(int(self.settings.gestures.double_tap_window_ms))
        self.spin_double_tap.valueChanged.connect(self._save)
        form.addRow("Air Double-Tap Window (ms):", self.spin_double_tap)

        self.chk_single_click = QCheckBox("Enable Single Air Tap as Left Click")
        self.chk_single_click.setChecked(self.settings.gestures.single_click_enabled)
        self.chk_single_click.toggled.connect(self._save)
        form.addRow("Single Click:", self.chk_single_click)

        self.spin_dwell = QDoubleSpinBox()
        self.spin_dwell.setRange(0.3, 1.5)
        self.spin_dwell.setSingleStep(0.05)
        self.spin_dwell.setValue(self.settings.gestures.dwell_lock_time_s)
        self.spin_dwell.valueChanged.connect(self._save)
        form.addRow("Dwell Brush Lock Hold Duration (seconds):", self.spin_dwell)

        self.spin_right = QDoubleSpinBox()
        self.spin_right.setRange(0.2, 1.2)
        self.spin_right.setSingleStep(0.05)
        self.spin_right.setValue(self.settings.gestures.right_click_hold_s)
        self.spin_right.valueChanged.connect(self._save)
        form.addRow("Two-Finger Right Click Hold Duration (seconds):", self.spin_right)

        box.addLayout(form)
        return card

    def _build_paint_section(self) -> QWidget:
        card, box = self._create_section_card("3. Paint & Creative Suite Mode")
        form = QFormLayout()
        form.setSpacing(10)

        self.chk_auto_paint = QCheckBox("Auto-Detect Creative Apps and Apply Heavy Brush Stabilizer")
        self.chk_auto_paint.setChecked(self.settings.paint.auto_detect)
        self.chk_auto_paint.toggled.connect(self._save)
        form.addRow("Auto-Detection:", self.chk_auto_paint)

        self.txt_paint_apps = QLineEdit(", ".join(self.settings.paint.active_apps))
        self.txt_paint_apps.editingFinished.connect(self._save)
        form.addRow("Active Target Processes:", self.txt_paint_apps)

        box.addLayout(form)
        return card

    def _build_keyboard_section(self) -> QWidget:
        card, box = self._create_section_card("4. Air Keyboard HUD & Key Repeat")
        form = QFormLayout()
        form.setSpacing(10)

        self.chk_symbols_enabled = QCheckBox("Enable Separate Symbols Panel on Right")
        self.chk_symbols_enabled.setChecked(self.settings.keyboard.symbols_panel_enabled)
        self.chk_symbols_enabled.toggled.connect(self._save)
        form.addRow("Symbols Panel:", self.chk_symbols_enabled)

        self.chk_dim_inactive = QCheckBox("Dim Inactive Panel to 40% Opacity")
        self.chk_dim_inactive.setChecked(self.settings.keyboard.dim_inactive_panel)
        self.chk_dim_inactive.toggled.connect(self._save)
        form.addRow("Zone Focus:", self.chk_dim_inactive)

        self.chk_thumb_space = QCheckBox("Thumb Air-Tap Emits Space Bar")
        self.chk_thumb_space.setChecked(self.settings.keyboard.thumb_is_space)
        self.chk_thumb_space.toggled.connect(self._save)
        form.addRow("Thumb Shortcut:", self.chk_thumb_space)

        self.spin_repeat_delay = QSpinBox()
        self.spin_repeat_delay.setRange(200, 1000)
        self.spin_repeat_delay.setSingleStep(50)
        self.spin_repeat_delay.setValue(int(self.settings.keyboard.key_repeat_delay_s * 1000))
        self.spin_repeat_delay.valueChanged.connect(self._save)
        form.addRow("Key Repeat Initial Delay (ms):", self.spin_repeat_delay)

        self.spin_repeat_rate = QDoubleSpinBox()
        self.spin_repeat_rate.setRange(2.0, 30.0)
        self.spin_repeat_rate.setSingleStep(1.0)
        self.spin_repeat_rate.setValue(getattr(self.settings.keyboard, "key_repeat_rate_cps", 15.0))
        self.spin_repeat_rate.valueChanged.connect(self._save)
        form.addRow("Key Repeat Rate (chars/sec):", self.spin_repeat_rate)

        box.addLayout(form)
        return card

    def _build_camera_section(self) -> QWidget:
        card, box = self._create_section_card("5. Hand & Camera Hardware")
        form = QFormLayout()
        form.setSpacing(10)

        self.combo_hand = QComboBox()
        self.combo_hand.addItems(["Auto-Detect (MediaPipe)", "Right Hand", "Left Hand"])
        h = getattr(self.settings.gestures, "dominant_hand", "auto").lower()
        self.combo_hand.setCurrentIndex(0 if h == "auto" else (1 if h == "right" else 2))
        self.combo_hand.currentIndexChanged.connect(self._save)
        form.addRow("Dominant Hand:", self.combo_hand)

        self.spin_auto_pause = QSpinBox()
        self.spin_auto_pause.setRange(3, 60)
        self.spin_auto_pause.setValue(int(getattr(self.settings.gestures, "auto_pause_timeout_s", 10.0)))
        self.spin_auto_pause.valueChanged.connect(self._save)
        form.addRow("Auto-Pause Timeout (seconds with no hand seen):", self.spin_auto_pause)

        box.addLayout(form)
        return card

    def _build_privacy_section(self) -> QWidget:
        card, box = self._create_section_card("6. Privacy & Security")
        form = QFormLayout()
        form.setSpacing(10)

        self.chk_hide_typed = QCheckBox("Hide 'Last Typed' Text Strip Everywhere")
        self.chk_hide_typed.setChecked(getattr(self.settings.privacy, "hide_last_typed", False))
        self.chk_hide_typed.toggled.connect(self._save)
        form.addRow("Mask Typing History:", self.chk_hide_typed)

        self.chk_hide_passwords = QCheckBox("Auto-Hide Typing History When Window Suggests Password Field")
        self.chk_hide_passwords.setChecked(getattr(self.settings.privacy, "auto_hide_passwords", True))
        self.chk_hide_passwords.toggled.connect(self._save)
        form.addRow("Password Shield:", self.chk_hide_passwords)

        note = QLabel("Privacy Guarantee: Pointer V runs strictly in-memory locally. No frames or keystrokes are ever sent to network or stored.")
        note.setFont(get_ui_font(10))
        note.setStyleSheet(f"color: {TEXT_DISABLED};")
        note.setWordWrap(True)
        form.addRow(note)

        box.addLayout(form)
        return card

    def _build_sound_section(self) -> QWidget:
        card, box = self._create_section_card("7. Sound Cues & Volume")
        form = QFormLayout()
        form.setSpacing(10)

        self.chk_sound_enabled = QCheckBox("Enable Audio Feedback for Clicks, Locks, and Mode Switches")
        self.chk_sound_enabled.setChecked(self.settings.sound.enabled)
        self.chk_sound_enabled.toggled.connect(self._save)
        form.addRow("Sound Feedback:", self.chk_sound_enabled)

        self.chk_mute = QCheckBox("Global Audio Mute")
        self.chk_mute.setChecked(self.settings.sound.muted)
        self.chk_mute.toggled.connect(self._save)
        form.addRow("Mute:", self.chk_mute)

        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(self.settings.sound.volume)
        self.slider_volume.valueChanged.connect(self._save)
        form.addRow("Master Volume:", self.slider_volume)

        box.addLayout(form)
        return card

    def _build_hotkeys_startup_section(self) -> QWidget:
        card, box = self._create_section_card("8. Global Hotkeys & Startup")
        form = QFormLayout()
        form.setSpacing(10)

        self.chk_startup_min = QCheckBox("Start Minimized to System Tray")
        self.chk_startup_min.setChecked(self.settings.start_minimized)
        self.chk_startup_min.toggled.connect(self._save)
        form.addRow("System Startup:", self.chk_startup_min)

        self.chk_dev_mode = QCheckBox("Enable Hidden Developer Tools Page")
        self.chk_dev_mode.setChecked(self.settings.developer_mode_enabled)
        self.chk_dev_mode.toggled.connect(self._save)
        form.addRow("Developer Mode:", self.chk_dev_mode)

        hotkey_desc = QLabel(
            "Active Hotkeys:\n"
            "· Ctrl + Alt + T: Toggle Pointer V ON / OFF\n"
            "· Ctrl + Alt + K: Toggle Air Keyboard HUD\n"
            "· Ctrl + Alt + S: Toggle Keyboard Zone (Main ↔ Symbols)\n"
            "· Ctrl + Alt + P: Toggle Paint Mode Profile\n"
            "· Ctrl + Alt + Space: Pause / Resume Tracking Output\n"
            "· Esc: Emergency Safety Release (Releases all buttons and modifiers)"
        )
        hotkey_desc.setFont(get_mono_font(10))
        hotkey_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        form.addRow("Hotkeys Reference:", hotkey_desc)

        box.addLayout(form)
        return card

    def _save(self):
        self.settings.sensitivity = self.spin_sens.value()
        self.settings.one_euro.min_cutoff = self.spin_min_cutoff.value()
        self.settings.one_euro.beta = self.spin_beta.value()

        self.settings.gestures.double_tap_window_ms = float(self.spin_double_tap.value())
        self.settings.gestures.single_click_enabled = self.chk_single_click.isChecked()
        self.settings.gestures.dwell_lock_time_s = self.spin_dwell.value()
        self.settings.gestures.right_click_hold_s = self.spin_right.value()
        self.settings.gestures.auto_pause_timeout_s = float(self.spin_auto_pause.value())

        hand_map = ["auto", "right", "left"]
        self.settings.gestures.dominant_hand = hand_map[self.combo_hand.currentIndex()]

        self.settings.paint.auto_detect = self.chk_auto_paint.isChecked()
        apps = [x.strip().lower() for x in self.txt_paint_apps.text().split(",") if x.strip()]
        self.settings.paint.active_apps = apps

        self.settings.keyboard.symbols_panel_enabled = self.chk_symbols_enabled.isChecked()
        self.settings.keyboard.dim_inactive_panel = self.chk_dim_inactive.isChecked()
        self.settings.keyboard.thumb_is_space = self.chk_thumb_space.isChecked()
        self.settings.keyboard.key_repeat_delay_s = self.spin_repeat_delay.value() / 1000.0
        self.settings.keyboard.key_repeat_rate_cps = self.spin_repeat_rate.value()

        self.settings.privacy.hide_last_typed = self.chk_hide_typed.isChecked()
        self.settings.privacy.auto_hide_passwords = self.chk_hide_passwords.isChecked()

        self.settings.sound.enabled = self.chk_sound_enabled.isChecked()
        self.settings.sound.muted = self.chk_mute.isChecked()
        self.settings.sound.volume = self.slider_volume.value()

        self.settings.start_minimized = self.chk_startup_min.isChecked()
        self.settings.developer_mode_enabled = self.chk_dev_mode.isChecked()

        self.settings_manager.save()
        self.settings_changed.emit()

    def _export_settings(self):
        dest, _ = QFileDialog.getSaveFileName(self, "Export Pointer V Settings", "pointer_v_settings.json", "JSON Files (*.json)")
        if dest:
            if self.settings_manager.export_to_file(dest):
                QMessageBox.information(self, "Export Success", f"Settings successfully exported to:\n{dest}")
            else:
                QMessageBox.critical(self, "Export Failed", "Could not write settings file.")

    def _import_settings(self):
        src, _ = QFileDialog.getOpenFileName(self, "Import Pointer V Settings", "", "JSON Files (*.json)")
        if src:
            if self.settings_manager.import_from_file(src):
                self.settings = self.settings_manager.config
                QMessageBox.information(self, "Import Success", "Settings imported successfully!")
                self.settings_changed.emit()
            else:
                QMessageBox.critical(self, "Import Failed", "Failed to parse imported settings JSON.")
