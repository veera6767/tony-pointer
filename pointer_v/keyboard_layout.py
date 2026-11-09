"""
Pointer V - Keyboard Layout & 4-Key Window Geometry
Defines the EXACT 6-row Main Laptop Keyboard and the 6-row Symbols Panel.
Implements the 4-key window partitioner, visual order finger-to-key mapping,
and seamless inter-zone navigation.
"""

import enum
from dataclasses import dataclass
from typing import List, Optional


class Zone(enum.Enum):
    MAIN = "MAIN"
    SYMBOLS = "SYMBOLS"


@dataclass
class KeyDef:
    """Definition of a single key on the air keyboard."""
    label: str                   # Primary display label (e.g. 'A', 'Esc', 'Space')
    code: str                    # Key identifier / scan identifier
    display_label: Optional[str] = None # Secondary label (e.g. shifted character)
    is_modifier: bool = False    # True if Shift, Ctrl, Alt, Win, CapsLock
    needs_shift: bool = False    # True if literal symbol requires shift (e.g. '!')
    width_ratio: float = 1.0     # Relative visual width (1.0 = standard square, 2.0 = wide)
    char_to_send: Optional[str] = None # Literal character for typing

    @property
    def display(self) -> str:
        return self.display_label if self.display_label else self.label


@dataclass
class KeyboardWindow:
    """A locked 4-key window under the user's 4 fingers."""
    zone: Zone
    row: int
    window_idx: int
    keys: List[KeyDef]       # Always exactly 4 keys
    start_key_idx: int


# ============================================================================
# EXACT 6-ROW MAIN KEYBOARD (Laptop-style layout without numpad)
# ============================================================================
# 10 + 9 + 7 = 26 letters total across Rows 3, 4, 5.
# Row 1: Esc, F1-F12, Del (14 keys)
# Row 2: ` 1 2 3 4 5 6 7 8 9 0 - = Backspace (14 keys)
# Row 3: Tab, Q W E R T Y U I O P (10 keys), [ ] \ (14 keys)
# Row 4: Caps Lock, A S D F G H J K L (9 keys), ; ' Enter (13 keys)
# Row 5: Shift, Z X C V B N M (7 keys), , . / Shift (12 keys)
# Row 6: Ctrl, Win, Alt, SPACE (wide), Alt, Ctrl, Left, Up, Down, Right (10 keys)
# ============================================================================

MAIN_ROWS_RAW: List[List[KeyDef]] = [
    # Row 1 (14 keys)
    [
        KeyDef("Esc", "esc", width_ratio=1.2),
        KeyDef("F1", "f1"), KeyDef("F2", "f2"), KeyDef("F3", "f3"), KeyDef("F4", "f4"),
        KeyDef("F5", "f5"), KeyDef("F6", "f6"), KeyDef("F7", "f7"), KeyDef("F8", "f8"),
        KeyDef("F9", "f9"), KeyDef("F10", "f10"), KeyDef("F11", "f11"), KeyDef("F12", "f12"),
        KeyDef("Del", "del", width_ratio=1.2),
    ],
    # Row 2 (14 keys)
    [
        KeyDef("`", "`", char_to_send="`"),
        KeyDef("1", "1", char_to_send="1"), KeyDef("2", "2", char_to_send="2"),
        KeyDef("3", "3", char_to_send="3"), KeyDef("4", "4", char_to_send="4"),
        KeyDef("5", "5", char_to_send="5"), KeyDef("6", "6", char_to_send="6"),
        KeyDef("7", "7", char_to_send="7"), KeyDef("8", "8", char_to_send="8"),
        KeyDef("9", "9", char_to_send="9"), KeyDef("0", "0", char_to_send="0"),
        KeyDef("-", "-", char_to_send="-"), KeyDef("=", "=", char_to_send="="),
        KeyDef("Backspace", "backspace", width_ratio=1.6),
    ],
    # Row 3 (14 keys: Tab, 10 letters, [ ] \)
    [
        KeyDef("Tab", "tab", width_ratio=1.3),
        KeyDef("Q", "q", char_to_send="q"), KeyDef("W", "w", char_to_send="w"),
        KeyDef("E", "e", char_to_send="e"), KeyDef("R", "r", char_to_send="r"),
        KeyDef("T", "t", char_to_send="t"), KeyDef("Y", "y", char_to_send="y"),
        KeyDef("U", "u", char_to_send="u"), KeyDef("I", "i", char_to_send="i"),
        KeyDef("O", "o", char_to_send="o"), KeyDef("P", "p", char_to_send="p"),
        KeyDef("[", "[", char_to_send="["), KeyDef("]", "]", char_to_send="]"),
        KeyDef("\\", "\\", char_to_send="\\"),
    ],
    # Row 4 (13 keys: Caps Lock, 9 letters, ; ' Enter)
    [
        KeyDef("Caps", "capslock", is_modifier=True, width_ratio=1.5),
        KeyDef("A", "a", char_to_send="a"), KeyDef("S", "s", char_to_send="s"),
        KeyDef("D", "d", char_to_send="d"), KeyDef("F", "f", char_to_send="f"),
        KeyDef("G", "g", char_to_send="g"), KeyDef("H", "h", char_to_send="h"),
        KeyDef("J", "j", char_to_send="j"), KeyDef("K", "k", char_to_send="k"),
        KeyDef("L", "l", char_to_send="l"),
        KeyDef(";", ";", char_to_send=";"), KeyDef("'", "'", char_to_send="'"),
        KeyDef("Enter", "enter", width_ratio=1.6),
    ],
    # Row 5 (12 keys: Shift, 7 letters, , . / Shift)
    [
        KeyDef("Shift", "shift_l", is_modifier=True, width_ratio=1.7),
        KeyDef("Z", "z", char_to_send="z"), KeyDef("X", "x", char_to_send="x"),
        KeyDef("C", "c", char_to_send="c"), KeyDef("V", "v", char_to_send="v"),
        KeyDef("B", "b", char_to_send="b"), KeyDef("N", "n", char_to_send="n"),
        KeyDef("M", "m", char_to_send="m"),
        KeyDef(",", ",", char_to_send=","), KeyDef(".", ".", char_to_send="."),
        KeyDef("/", "/", char_to_send="/"),
        KeyDef("Shift", "shift_r", is_modifier=True, width_ratio=1.7),
    ],
    # Row 6 (10 keys: Ctrl, Win, Alt, SPACE (wide), Alt, Ctrl, arrows)
    [
        KeyDef("Ctrl", "ctrl_l", is_modifier=True, width_ratio=1.2),
        KeyDef("Win", "win", is_modifier=True, width_ratio=1.1),
        KeyDef("Alt", "alt_l", is_modifier=True, width_ratio=1.1),
        KeyDef("Space", "space", char_to_send=" ", width_ratio=3.8),
        KeyDef("Alt", "alt_r", is_modifier=True, width_ratio=1.1),
        KeyDef("Ctrl", "ctrl_r", is_modifier=True, width_ratio=1.2),
        KeyDef("Left", "left", width_ratio=1.0),
        KeyDef("Up", "up", width_ratio=1.0),
        KeyDef("Down", "down", width_ratio=1.0),
        KeyDef("Right", "right", width_ratio=1.0),
    ],
]


# ============================================================================
# SYMBOLS PANEL (Right side, separate 6 rows matching horizontal alignment)
# ============================================================================
# Row 1 (navigation): [Home End PgUp PgDn] [PrtSc Ins Pause ScrLk] (8 keys)
# Row 2 (shifted number symbols): [! @ # $] [% ^ & *] [( ) _ +] (12 keys)
# Row 3 (math/operators): [+ - * /] [= < > ~] (8 keys)
# Row 4 (brackets/quotes): [{ } [ ]] [( ) " '] (8 keys)
# Row 5 (punctuation): [: ; ? |] [\ / , .] (8 keys)
# Row 6 (editing): [Backspace Enter Tab Del] (4 keys)
# ============================================================================

SYMBOL_ROWS_RAW: List[List[KeyDef]] = [
    # Row 1 (Navigation - 8 keys)
    [
        KeyDef("Home", "home"), KeyDef("End", "end"),
        KeyDef("PgUp", "pgup"), KeyDef("PgDn", "pgdn"),
        KeyDef("PrtSc", "prtsc"), KeyDef("Ins", "ins"),
        KeyDef("Pause", "pause"), KeyDef("ScrLk", "scrlk"),
    ],
    # Row 2 (Shifted number symbols - 12 keys)
    [
        KeyDef("!", "exclamation", needs_shift=True, char_to_send="!"),
        KeyDef("@", "at", needs_shift=True, char_to_send="@"),
        KeyDef("#", "hash", needs_shift=True, char_to_send="#"),
        KeyDef("$", "dollar", needs_shift=True, char_to_send="$"),
        KeyDef("%", "percent", needs_shift=True, char_to_send="%"),
        KeyDef("^", "caret", needs_shift=True, char_to_send="^"),
        KeyDef("&", "ampersand", needs_shift=True, char_to_send="&"),
        KeyDef("*", "asterisk", needs_shift=True, char_to_send="*"),
        KeyDef("(", "lparen", needs_shift=True, char_to_send="("),
        KeyDef(")", "rparen", needs_shift=True, char_to_send=")"),
        KeyDef("_", "underscore", needs_shift=True, char_to_send="_"),
        KeyDef("+", "plus", needs_shift=True, char_to_send="+"),
    ],
    # Row 3 (Math/Operators - 8 keys)
    [
        KeyDef("+", "sym_plus", needs_shift=True, char_to_send="+"),
        KeyDef("-", "sym_minus", needs_shift=False, char_to_send="-"),
        KeyDef("*", "sym_asterisk", needs_shift=True, char_to_send="*"),
        KeyDef("/", "sym_slash", needs_shift=False, char_to_send="/"),
        KeyDef("=", "sym_equals", needs_shift=False, char_to_send="="),
        KeyDef("<", "sym_less", needs_shift=True, char_to_send="<"),
        KeyDef(">", "sym_greater", needs_shift=True, char_to_send=">"),
        KeyDef("~", "sym_tilde", needs_shift=True, char_to_send="~"),
    ],
    # Row 4 (Brackets & Quotes - 8 keys)
    [
        KeyDef("{", "sym_lbrace", needs_shift=True, char_to_send="{"),
        KeyDef("}", "sym_rbrace", needs_shift=True, char_to_send="}"),
        KeyDef("[", "sym_lbracket", needs_shift=False, char_to_send="["),
        KeyDef("]", "sym_rbracket", needs_shift=False, char_to_send="]"),
        KeyDef("(", "sym_lparen2", needs_shift=True, char_to_send="("),
        KeyDef(")", "sym_rparen2", needs_shift=True, char_to_send=")"),
        KeyDef('"', "sym_dquote", needs_shift=True, char_to_send='"'),
        KeyDef("'", "sym_squote", needs_shift=False, char_to_send="'"),
    ],
    # Row 5 (Punctuation - 8 keys)
    [
        KeyDef(":", "sym_colon", needs_shift=True, char_to_send=":"),
        KeyDef(";", "sym_semicolon", needs_shift=False, char_to_send=";"),
        KeyDef("?", "sym_question", needs_shift=True, char_to_send="?"),
        KeyDef("|", "sym_pipe", needs_shift=True, char_to_send="|"),
        KeyDef("\\", "sym_backslash", needs_shift=False, char_to_send="\\"),
        KeyDef("/", "sym_slash2", needs_shift=False, char_to_send="/"),
        KeyDef(",", "sym_comma", needs_shift=False, char_to_send=","),
        KeyDef(".", "sym_dot", needs_shift=False, char_to_send="."),
    ],
    # Row 6 (Editing - 4 keys)
    [
        KeyDef("Backspace", "backspace", width_ratio=1.4),
        KeyDef("Enter", "enter", width_ratio=1.4),
        KeyDef("Tab", "tab", width_ratio=1.2),
        KeyDef("Del", "del", width_ratio=1.2),
    ],
]


class KeyboardLayoutManager:
    """
    Builds and manages 4-key windows across both MAIN and SYMBOLS zones.
    Ensures every key in every row is reachable through progressive sliding windows,
    clamping the final window to the row's last 4 keys if length is not a multiple of 4.
    """

    def __init__(self, main_rows: Optional[List[List[KeyDef]]] = None, symbol_rows: Optional[List[List[KeyDef]]] = None):
        self.main_rows = main_rows or MAIN_ROWS_RAW
        self.symbol_rows = symbol_rows or SYMBOL_ROWS_RAW

        # Precompute 4-key windows for each row in both zones
        self.main_windows: List[List[KeyboardWindow]] = self._build_windows(self.main_rows, Zone.MAIN)
        self.symbol_windows: List[List[KeyboardWindow]] = self._build_windows(self.symbol_rows, Zone.SYMBOLS)

    def _build_windows(self, rows: List[List[KeyDef]], zone: Zone) -> List[List[KeyboardWindow]]:
        row_windows: List[List[KeyboardWindow]] = []

        for row_idx, keys in enumerate(rows):
            n = len(keys)
            windows: List[KeyboardWindow] = []

            if n <= 4:
                # 4 or fewer keys: single window (padded with trailing keys if < 4)
                win_keys = keys if n == 4 else keys + [keys[-1]] * (4 - n)
                windows.append(KeyboardWindow(zone=zone, row=row_idx, window_idx=0, keys=win_keys, start_key_idx=0))
            else:
                # Progressive 4-key step windows
                start_indices = []
                idx = 0
                while idx + 4 <= n:
                    start_indices.append(idx)
                    idx += 4

                # Clamp final window to exact last 4 keys so no keys are missed
                last_start = n - 4
                if last_start not in start_indices:
                    start_indices.append(last_start)

                start_indices.sort()

                for w_idx, s_idx in enumerate(start_indices):
                    win_keys = keys[s_idx : s_idx + 4]
                    windows.append(
                        KeyboardWindow(
                            zone=zone,
                            row=row_idx,
                            window_idx=w_idx,
                            keys=win_keys,
                            start_key_idx=s_idx,
                        )
                    )

            row_windows.append(windows)

        return row_windows

    def get_window(self, zone: Zone, row_idx: int, window_idx: int) -> KeyboardWindow:
        """Retrieves the clamped 4-key window for the given zone, row, and window index."""
        row_idx = max(0, min(5, row_idx))
        target_table = self.main_windows if zone == Zone.MAIN else self.symbol_windows
        row_wins = target_table[row_idx]
        w_idx = max(0, min(len(row_wins) - 1, window_idx))
        return row_wins[w_idx]

    def get_max_window_idx(self, zone: Zone, row_idx: int) -> int:
        """Returns the last valid window index in the specified row."""
        row_idx = max(0, min(5, row_idx))
        target_table = self.main_windows if zone == Zone.MAIN else self.symbol_windows
        return len(target_table[row_idx]) - 1

    def is_last_window_of_row(self, zone: Zone, row_idx: int, window_idx: int) -> bool:
        return window_idx >= self.get_max_window_idx(zone, row_idx)

    def is_first_window_of_row(self, zone: Zone, row_idx: int, window_idx: int) -> bool:
        return window_idx <= 0
