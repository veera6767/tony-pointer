"""
Pointer V - Air Keyboard Settings & Layout Page
Floating Air Keyboard HUD geometry, Symbols panel toggles, dominant hand mapping,
and hold-to-repeat rate/delay configurations.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QFormLayout, QHBoxLayout,
    QLabel, QSlider, QSpinBox, QVBoxLayout, QWidget
)

from theme import (
    BG1_PANELS, BG2_CARDS, BORDER, RADIUS_CONTROL, RADIUS_PANEL, TEXT_PRIMARY,
    TEXT_SECONDARY, get_ui_font
)


class KeyboardPage(QWidget):
    """Air Keyboard configuration and layout inspection."""

    settings_changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Air Keyboard Configuration")
        title.setFont(get_ui_font(16, bold=True))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left Column: Panels & Behavior
        card_left = QFrame()
        card_left.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        l_form = QFormLayout(card_left)
        l_form.setContentsMargins(16, 16, 16, 16)
        l_form.setSpacing(12)

        l_title = QLabel("HUD Panels & Navigation")
        l_title.setFont(get_ui_font(13, bold=True))
        l_title.setStyleSheet(f"color: {TEXT_PRIMARY}; margin-bottom: 4px;")
        l_form.addRow(l_title)

        self.chk_symbols = QCheckBox("Enable Docked Symbols Panel")
        self.chk_symbols.setChecked(self.settings.keyboard.symbols_panel_enabled)
        self.chk_symbols.toggled.connect(self._save_settings)
        l_form.addRow("Symbols Panel:", self.chk_symbols)

        self.chk_dim = QCheckBox("Dim Inactive Panel to 40% Opacity")
        self.chk_dim.setChecked(self.settings.keyboard.dim_inactive_panel)
        self.chk_dim.toggled.connect(self._save_settings)
        l_form.addRow("Zone Dimming:", self.chk_dim)

        self.chk_thumb = QCheckBox("Thumb Air-Tap Emits Space Bar")
        self.chk_thumb.setChecked(self.settings.keyboard.thumb_is_space)
        self.chk_thumb.toggled.connect(self._save_settings)
        l_form.addRow("Thumb Action:", self.chk_thumb)

        self.spin_opacity = QSlider(Qt.Horizontal)
        self.spin_opacity.setRange(40, 100)
        self.spin_opacity.setValue(int(self.settings.keyboard.opacity * 100))
        self.spin_opacity.valueChanged.connect(self._save_settings)
        l_form.addRow("HUD Glass Opacity:", self.spin_opacity)

        self.spin_swipe = QDoubleSpinBox()
        self.spin_swipe.setRange(0.15, 0.60)
        self.spin_swipe.setSingleStep(0.02)
        self.spin_swipe.setValue(self.settings.keyboard.swipe_threshold)
        self.spin_swipe.valueChanged.connect(self._save_settings)
        l_form.addRow("Swipe Threshold (Hand Normalized):", self.spin_swipe)

        split_layout.addWidget(card_left)

        # Right Column: Finger Mapping & Key Repeat Rate
        card_right = QFrame()
        card_right.setStyleSheet(f"background-color: {BG1_PANELS}; border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px;")
        r_form = QFormLayout(card_right)
        r_form.setContentsMargins(16, 16, 16, 16)
        r_form.setSpacing(12)

        r_title = QLabel("Typing & Hold-to-Repeat")
        r_title.setFont(get_ui_font(13, bold=True))
        r_title.setStyleSheet(f"color: {TEXT_PRIMARY}; margin-bottom: 4px;")
        r_form.addRow(r_title)

        self.combo_hand = QComboBox()
        self.combo_hand.addItems(["Auto-Detect (MediaPipe)", "Right Hand", "Left Hand"])
        hand_setting = getattr(self.settings.gestures, "dominant_hand", "auto").lower()
        hand_idx = 0 if hand_setting == "auto" else (1 if hand_setting == "right" else 2)
        self.combo_hand.setCurrentIndex(hand_idx)
        self.combo_hand.currentIndexChanged.connect(self._save_settings)
        r_form.addRow("Dominant Hand:", self.combo_hand)

        self.combo_mapping = QComboBox()
        self.combo_mapping.addItems(["Visual Order (Left-to-Right)", "Reversed Order"])
        self.combo_mapping.setCurrentIndex(0 if self.settings.keyboard.finger_mapping == "visual" else 1)
        self.combo_mapping.currentIndexChanged.connect(self._save_settings)
        r_form.addRow("Finger-to-Key Order:", self.combo_mapping)

        self.spin_repeat_delay = QSpinBox()
        self.spin_repeat_delay.setRange(200, 1000)
        self.spin_repeat_delay.setSingleStep(50)
        self.spin_repeat_delay.setValue(int(self.settings.keyboard.key_repeat_delay_s * 1000))
        self.spin_repeat_delay.valueChanged.connect(self._save_settings)
        r_form.addRow("Key Repeat Initial Delay (ms):", self.spin_repeat_delay)

        self.spin_repeat_rate = QDoubleSpinBox()
        self.spin_repeat_rate.setRange(2.0, 30.0)
        self.spin_repeat_rate.setSingleStep(1.0)
        self.spin_repeat_rate.setValue(getattr(self.settings.keyboard, "key_repeat_rate_cps", 15.0))
        self.spin_repeat_rate.valueChanged.connect(self._save_settings)
        r_form.addRow("Key Repeat Rate (chars/sec):", self.spin_repeat_rate)

        split_layout.addWidget(card_right)
        layout.addLayout(split_layout)

        # Informational Note
        note_card = QFrame()
        note_card.setStyleSheet(f"background-color: {BG2_CARDS}; border: 1px solid {BORDER}; border-radius: {RADIUS_CONTROL}px;")
        n_box = QVBoxLayout(note_card)
        n_box.setContentsMargins(14, 12, 14, 12)
        n_lbl = QLabel(
            "Navigation Tips:\n"
            "· Swipe hand UP / DOWN to switch rows (Rows 1–6)\n"
            "· Swipe hand LEFT / RIGHT to hop 4-key windows\n"
            "· Swipe RIGHT from the last window of Main to cross into Symbols; swipe LEFT from Symbols to return\n"
            "· Hold any finger curled >500ms to repeat typing (Backspace, arrows, or characters)"
        )
        n_lbl.setFont(get_ui_font(11))
        n_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.4;")
        n_box.addWidget(n_lbl)
        layout.addWidget(note_card)

        layout.addStretch()

    def _save_settings(self):
        self.settings.keyboard.symbols_panel_enabled = self.chk_symbols.isChecked()
        self.settings.keyboard.dim_inactive_panel = self.chk_dim.isChecked()
        self.settings.keyboard.thumb_is_space = self.chk_thumb.isChecked()
        self.settings.keyboard.opacity = self.spin_opacity.value() / 100.0
        self.settings.keyboard.swipe_threshold = self.spin_swipe.value()

        hand_map = ["auto", "right", "left"]
        self.settings.gestures.dominant_hand = hand_map[self.combo_hand.currentIndex()]
        self.settings.keyboard.finger_mapping = "visual" if self.combo_mapping.currentIndex() == 0 else "reversed"

        self.settings.keyboard.key_repeat_delay_s = self.spin_repeat_delay.value() / 1000.0
        self.settings.keyboard.key_repeat_rate_cps = self.spin_repeat_rate.value()

        self.settings_changed.emit()

