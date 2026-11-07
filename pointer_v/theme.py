"""
Pointer V - Central Theme & Design Token Architecture
Single source of truth for all UI colors, font configurations, geometry metrics,
and global QSS styling across the entire application.
No hardcoded colors elsewhere.
"""

from pathlib import Path
from PySide6.QtGui import QColor, QFont, QFontDatabase


# ============================================================================
# DESIGN TOKENS
# ============================================================================

# Backgrounds (Dark, slightly cool, never pure black)
BG0_WINDOW = "#0B0E13"      # Main window background
BG1_PANELS = "#11151C"      # Sidebar, toolbars, cards
BG2_CARDS = "#171C25"       # Inputs, cards, key fills
BG3_HOVER = "#1E2430"       # Active state, hover highlight

# Lines & Borders (1px clean precision)
BORDER = "#232A36"
BORDER_STRONG = "#2F3948"
ACCENT_LINE = "rgba(47, 123, 255, 0.40)"

# Typography Colors
TEXT_PRIMARY = "#E6EAF2"
TEXT_SECONDARY = "#9AA4B5"
TEXT_DISABLED = "#5B6575"

# Accent Colors
BLUE = "#2F7BFF"            # Primary accent
BLUE_BRIGHT = "#5BA0FF"     # Hover, locked-key glow
BLUE_DEEP = "#1B4FB8"       # Pressed state

# Functional Status Colors
CYAN = "#22D3EE"            # Cursor reticle, normal tracking
VIOLET = "#8B7CFF"          # Symbols panel, secondary focus
AMBER = "#F5A524"           # Sticky modifiers, warnings
GREEN = "#34D399"           # Ready, success
RED = "#F0506E"             # Errors, brush locked, emergency

# Mode Representation Colors
MODE_COLORS = {
    "POINTER": BLUE,
    "KEYBOARD": VIOLET,
    "PAINT": AMBER,
}

# Typography Families & Sizes
FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"

SIZE_PAGE_TITLE = 18
SIZE_SECTION_TITLE = 14
SIZE_BODY = 12
SIZE_SECONDARY = 11
SIZE_SMALL = 10

RADIUS_CONTROL = 6
RADIUS_PANEL = 8
RADIUS_WINDOW = 10


def init_fonts():
    """Loads bundled Inter and JetBrains Mono fonts into QFontDatabase."""
    fonts_dir = Path(__file__).resolve().parent / "assets" / "fonts"
    for font_file in fonts_dir.glob("*.ttf"):
        try:
            QFontDatabase.addApplicationFont(str(font_file))
        except Exception as e:
            print(f"[Theme] Warning: Could not register font {font_file}: {e}")


def get_ui_font(size: int = SIZE_BODY, bold: bool = False, weight: int = 500) -> QFont:
    """Returns the standard application typography font."""
    font = QFont(FONT_UI, size)
    font.setStyleHint(QFont.SansSerif)
    font.setWeight(QFont.Weight(weight if not bold else 600))
    return font


def get_mono_font(size: int = SIZE_BODY, bold: bool = False) -> QFont:
    """Returns the JetBrains Mono font strictly for numbers, metrics, and timestamps."""
    font = QFont(FONT_MONO, size)
    font.setStyleHint(QFont.Monospace)
    font.setWeight(QFont.DemiBold if bold else QFont.Normal)
    return font


def get_global_stylesheet() -> str:
    """Generates the master professional stylesheet for Pointer V."""
    return f"""
/* Master Window & Widget Defaults */
QWidget {{
    background-color: {BG0_WINDOW};
    color: {TEXT_PRIMARY};
    font-family: '{FONT_UI}', -apple-system, 'Segoe UI', sans-serif;
    font-size: {SIZE_BODY}px;
    selection-background-color: {BLUE};
    selection-color: #FFFFFF;
}}

/* Containers & Panels */
QFrame#PanelFrame, QFrame#CardFrame {{
    background-color: {BG1_PANELS};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_PANEL}px;
}}

QFrame#InnerCard {{
    background-color: {BG2_CARDS};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
}}

/* Push Buttons */
QPushButton {{
    background-color: {BG2_CARDS};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    color: {TEXT_PRIMARY};
    padding: 7px 16px;
    font-size: {SIZE_BODY}px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG3_HOVER};
    border: 1px solid {BORDER_STRONG};
    color: #FFFFFF;
}}

QPushButton:pressed {{
    background-color: {BLUE_DEEP};
    border: 1px solid {BLUE};
}}

QPushButton:disabled {{
    background-color: {BG1_PANELS};
    border: 1px solid {BORDER};
    color: {TEXT_DISABLED};
}}

QPushButton#PrimaryButton {{
    background-color: {BLUE};
    border: 1px solid {BLUE};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {BLUE_BRIGHT};
    border: 1px solid {BLUE_BRIGHT};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: {BLUE_DEEP};
}}

QPushButton#DangerButton {{
    background-color: rgba(240, 80, 110, 0.12);
    border: 1px solid rgba(240, 80, 110, 0.40);
    color: {RED};
}}

QPushButton#DangerButton:hover {{
    background-color: {RED};
    color: #FFFFFF;
}}

/* Form Inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG2_CARDS};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    color: {TEXT_PRIMARY};
    padding: 6px 10px;
    font-size: {SIZE_BODY}px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {BLUE};
    background-color: {BG3_HOVER};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG1_PANELS};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_CONTROL}px;
    color: {TEXT_PRIMARY};
    selection-background-color: {BG3_HOVER};
    selection-color: {TEXT_PRIMARY};
    padding: 4px;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER_STRONG};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {BLUE};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 1px solid {BORDER_STRONG};
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: {BLUE_BRIGHT};
    border: 1px solid {BLUE};
}}

/* Progress Bars */
QProgressBar {{
    background-color: {BG2_CARDS};
    border: 1px solid {BORDER};
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {BLUE};
    border-radius: 2px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0 2px 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_DISABLED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Tooltips */
QToolTip {{
    background-color: {BG1_PANELS};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 6px 10px;
    font-size: {SIZE_SECONDARY}px;
}}
"""

