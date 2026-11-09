"""
Pointer V - Settings & Configuration Manager
Handles JSON-backed persistence for active region, One Euro filter parameters,
multi-monitor mapping, gesture thresholds, privacy preferences, camera settings,
and application profiles. Supports automatic migration from legacy TonyPointer settings.
"""

import copy
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from version import APP_NAME, APPDATA_DIR_NAME, OLD_APPDATA_DIR_NAME


@dataclass
class ActiveRegion:
    x_min: float = 0.15
    y_min: float = 0.15
    x_max: float = 0.85
    y_max: float = 0.85


@dataclass
class OneEuroSettings:
    min_cutoff: float = 1.0       # Minimum cutoff frequency (Hz)
    beta: float = 0.007           # Speed coefficient
    d_cutoff: float = 1.0         # Derivative cutoff frequency (Hz)


@dataclass
class PaintModeSettings:
    stabilizer: float = 0.85      # Visual smoothing strength (0.0 to 1.0)
    min_cutoff: float = 0.25      # Heavier smoothing for line work
    beta: float = 0.001
    auto_detect: bool = True
    active_apps: List[str] = field(
        default_factory=lambda: [
            "mspaint.exe",
            "krita.exe",
            "photoshop.exe",
            "clipstudio.exe",
            "gimp.exe",
            "paint.exe",
            "affinitydesigner.exe",
            "illustrator.exe",
            "figma.exe"
        ]
    )


@dataclass
class GestureSettings:
    double_tap_window_ms: float = 500.0   # Window for two taps to register as double-click
    tap_curl_threshold: float = 0.045     # Forward flexion depth/angle change for air tap
    tap_cooldown_ms: float = 220.0        # Anti-repeat cooldown
    neighbor_lockout_ms: float = 160.0    # Lockout across all fingers when any finger taps
    single_click_enabled: bool = True     # Toggle single air tap as left click
    dwell_lock_time_s: float = 0.60       # Index finger stationary time to lock brush
    dwell_radius_px: float = 16.0         # Allowed jitter radius for dwell
    pinch_threshold: float = 0.045        # Normalized 3D distance between thumb & index tip
    right_click_hold_s: float = 0.45      # Duration to hold 2 fingers for right click
    scroll_sensitivity: float = 2.4       # Multiplier for 2-finger scroll
    hand_timeout_ms: float = 300.0        # Freeze cursor if hand lost longer than this
    safety_release_timeout_s: float = 1.0 # Auto release mouse lock if lost
    dominant_hand: str = "auto"           # "auto", "right", "left"
    fist_pause_hold_s: float = 1.50       # Closed fist held 1.5s in POINTER mode to pause
    auto_pause_timeout_s: float = 10.0    # Auto pause if no hand is seen for N seconds
    pointing_sensitivity: float = 1.0     # Tolerance for relaxed pointing pose (0.5-2.0)
    click_mode: str = "left_only"         # "off", "left_only", "all"
    yield_duration_s: float = 1.5         # Pause cursor movement when physical mouse/touchpad moves
    yield_distance_px: int = 6            # Pixels difference from last set position to detect physical move
    max_brush_lock_s: float = 30.0        # Max duration in seconds to hold button locked
    circuit_breaker_enabled: bool = True  # Auto-pause on rapid click burst
    game_mode_enabled: bool = False       # Auto pause output when fullscreen game is focused
    game_mode_exclusions: List[str] = field(
        default_factory=lambda: ["steam.exe", "epicgames.exe"]
    )


@dataclass
class OverlaySettings:
    cursor_shape: str = "gaming"         # "gaming" neon blue arrowhead pointer
    cursor_color: str = "Blue"           # "Blue", "Cyan", "Violet", "Red"
    cursor_size: float = 1.0             # Scale 0.75x to 2.0x
    cursor_trail: bool = True            # 8-point fading comet trail
    cursor_glow: bool = True             # Soft ambient blue glow
    hide_system_cursor: bool = False     # Hide standard Windows arrow while active
    brush_lock_color: str = "#F0506E"    # Red brush locked
    preview_width: int = 320
    preview_height: int = 240
    preview_opacity: float = 0.90        # 90% opacity (not too transparent)
    preview_visible: bool = True
    preview_border: bool = True
    preview_pos_x: int = -1              # -1 defaults to top-right safe position
    preview_pos_y: int = -1


@dataclass
class KeyboardSettings:
    enabled: bool = True
    symbols_panel_enabled: bool = True
    dim_inactive_panel: bool = True
    opacity: float = 0.94
    corner: str = "bottom-right"         # "top-left", "top-right", "bottom-left", "bottom-right", "bottom-center"
    monitor_mode: str = "active_window"  # "active_window", "primary", "specific"
    chosen_monitor: int = -1             # Specific monitor index if monitor_mode is "specific"
    margin: int = 16                     # Padding from monitor work area edges in px
    width_percent: float = 0.40          # 0.25 to 0.60 of screen work width
    snap_to_corner: bool = True          # Snap to nearest corner when released after drag
    avoid_active_window: bool = True     # Best-effort dodge if foreground window overlaps
    keep_visible_dimmed: bool = False    # Dim instead of hiding when closing keyboard
    open_palm_hold_s: float = 0.50       # Hold open palm for ~0.5s to open keyboard
    fist_close_hold_s: float = 0.50      # Hold fist for ~0.5s to close keyboard
    swipe_threshold: float = 0.32        # Normalized by hand size
    swipe_cooldown_ms: float = 300.0     # Cooldown between row/window jumps
    tap_cooldown_ms: float = 200.0       # Per-finger debounce
    neighbor_lockout_ms: float = 160.0   # Debounce across neighboring fingers
    index_sensitivity: float = 1.0
    middle_sensitivity: float = 1.0
    ring_sensitivity: float = 1.25       # Calibrated for anatomically weaker ring finger
    pinky_sensitivity: float = 1.35      # Calibrated for pinky finger
    thumb_is_space: bool = True          # Thumb tap emits Space
    key_repeat_delay_s: float = 0.50     # 500 ms initial hold delay before repeating
    key_repeat_rate_cps: float = 15.0    # 15 chars/sec repeat rate
    finger_mapping: str = "visual"       # "visual" (left-to-right) or "reversed"
    hotkey_keyboard: str = "ctrl+alt+k"
    hotkey_zone_toggle: str = "ctrl+alt+s"
    sound_enabled: bool = True

    @property
    def key_repeat_interval_s(self) -> float:
        rate = max(1.0, min(50.0, self.key_repeat_rate_cps))
        return 1.0 / rate


@dataclass
class PrivacySettings:
    hide_last_typed: bool = False
    auto_hide_passwords: bool = True
    camera_active_indicator: bool = True


@dataclass
class SoundSettings:
    enabled: bool = True
    volume: int = 80                     # 0-100
    muted: bool = False


@dataclass
class MultiMonitorSettings:
    monitor_index: int = -1              # -1 for Virtual Desktop (All Monitors), >= 0 for specific monitor


@dataclass
class AppConfig:
    version: str = "2.0.0"
    camera_index: int = 0
    camera_name: str = ""
    camera_width: int = 1280
    camera_height: int = 720
    target_fps: int = 60                 # 15, 30, 60
    battery_saver: bool = False          # Default OFF (throttles to 15 FPS only after 5s no hand)
    sensitivity: float = 1.0
    acceleration: float = 1.15
    active_region: ActiveRegion = field(default_factory=ActiveRegion)
    one_euro: OneEuroSettings = field(default_factory=OneEuroSettings)
    paint: PaintModeSettings = field(default_factory=PaintModeSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    keyboard: KeyboardSettings = field(default_factory=KeyboardSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    sound: SoundSettings = field(default_factory=SoundSettings)
    monitors: MultiMonitorSettings = field(default_factory=MultiMonitorSettings)
    hotkey_toggle: str = "ctrl+alt+t"
    hotkey_paint: str = "ctrl+alt+p"
    hotkey_pause: str = "ctrl+alt+space"
    start_minimized: bool = False
    close_to_tray: bool = False          # False = X button quits app; True = minimizes to tray
    tutorial_completed: bool = False
    show_tutorial_on_startup: bool = True
    developer_mode_enabled: bool = False
    window_geometry: Dict[str, List[int]] = field(
        default_factory=lambda: {
            "main": [100, 100, 1080, 700],
            "preview": [40, 40, 320, 240],
            "keyboard": [-1, -1, 0, 0],
        }
    )


def _deep_merge_dict(target: dict, source: dict) -> dict:
    """Recursively merges source dict into target dict."""
    for key, value in source.items():
        if key in target:
            if isinstance(target[key], dict) and isinstance(value, dict):
                _deep_merge_dict(target[key], value)
            else:
                target[key] = value
    return target


class SettingsManager:
    """Manages loading, saving, migration, and defaults for Pointer V configuration."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # Resolves %APPDATA%\PointerV on Windows
            appdata = os.environ.get("APPDATA")
            if appdata:
                base_dir = Path(appdata) / APPDATA_DIR_NAME
            else:
                base_dir = Path.home() / f".{APPDATA_DIR_NAME.lower()}"
        else:
            base_dir = Path(config_dir)

        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.base_dir / "settings.json"

        # Check for legacy TonyPointer settings to migrate once
        self._check_legacy_migration()

        self.config: AppConfig = self.load()

    def _check_legacy_migration(self):
        r"""
        One-time migration:
        If %APPDATA%\PointerV\settings.json does not exist, but old
        %APPDATA%\TonyPointer\settings.json (or config.json) or
        ~/.tony_pointer/config.json exists, copy its settings over once and leave old folder alone.
        """
        if self.filepath.exists():
            return

        legacy_candidates = []
        appdata = os.environ.get("APPDATA")
        if appdata:
            legacy_candidates.append(Path(appdata) / OLD_APPDATA_DIR_NAME / "settings.json")
            legacy_candidates.append(Path(appdata) / OLD_APPDATA_DIR_NAME / "config.json")
        legacy_candidates.append(Path.home() / ".tony_pointer" / "config.json")
        legacy_candidates.append(Path.home() / ".tony_pointer" / "settings.json")

        for cand in legacy_candidates:
            if cand.exists() and cand.is_file():
                try:
                    print(f"[{APP_NAME}] Found legacy configuration at {cand}. Migrating to {self.filepath}...")
                    shutil.copy2(cand, self.filepath)
                    return
                except Exception as e:
                    print(f"[{APP_NAME}] Migration notice: could not copy legacy config ({e})")

    def load(self) -> AppConfig:
        """Load settings from JSON, safely merging with defaults to handle corrupt or old versions."""
        default_cfg = AppConfig()
        default_dict = asdict(default_cfg)

        if not self.filepath.exists():
            self.save(default_cfg)
            return default_cfg

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise ValueError("Settings file is empty")
                user_data = json.loads(content)

            # Deep merge user_data on top of default_dict
            merged_dict = _deep_merge_dict(copy.deepcopy(default_dict), user_data)

            # Reconstruct dataclasses safely
            active_region = ActiveRegion(**merged_dict.get("active_region", {}))
            one_euro = OneEuroSettings(**merged_dict.get("one_euro", {}))
            paint = PaintModeSettings(**merged_dict.get("paint", {}))
            gestures = GestureSettings(**merged_dict.get("gestures", {}))
            overlay = OverlaySettings(**merged_dict.get("overlay", {}))
            keyboard = KeyboardSettings(**merged_dict.get("keyboard", {}))
            privacy = PrivacySettings(**merged_dict.get("privacy", {}))
            sound = SoundSettings(**merged_dict.get("sound", {}))
            monitors = MultiMonitorSettings(**merged_dict.get("monitors", {}))

            cfg = AppConfig(
                version=merged_dict.get("version", "2.0.0"),
                camera_index=merged_dict.get("camera_index", 0),
                camera_name=merged_dict.get("camera_name", ""),
                camera_width=merged_dict.get("camera_width", 1280),
                camera_height=merged_dict.get("camera_height", 720),
                target_fps=merged_dict.get("target_fps", 60),
                battery_saver=merged_dict.get("battery_saver", False),
                sensitivity=merged_dict.get("sensitivity", 1.0),
                acceleration=merged_dict.get("acceleration", 1.15),
                active_region=active_region,
                one_euro=one_euro,
                paint=paint,
                gestures=gestures,
                overlay=overlay,
                keyboard=keyboard,
                privacy=privacy,
                sound=sound,
                monitors=monitors,
                hotkey_toggle=merged_dict.get("hotkey_toggle", "ctrl+alt+t"),
                hotkey_paint=merged_dict.get("hotkey_paint", "ctrl+alt+p"),
                hotkey_pause=merged_dict.get("hotkey_pause", "ctrl+alt+space"),
                start_minimized=merged_dict.get("start_minimized", False),
                close_to_tray=merged_dict.get("close_to_tray", False),
                tutorial_completed=merged_dict.get("tutorial_completed", False),
                show_tutorial_on_startup=merged_dict.get("show_tutorial_on_startup", True),
                developer_mode_enabled=merged_dict.get("developer_mode_enabled", False),
                window_geometry=merged_dict.get("window_geometry", default_dict["window_geometry"]),
            )
            return cfg
        except Exception as e:
            print(f"[{APP_NAME}] Warning: Failed to parse settings JSON ({e}). Preserving defaults.")
            self.save(default_cfg)
            return default_cfg

    def save(self, config: Optional[AppConfig] = None) -> bool:
        """Persist settings to JSON file safely with backup."""
        if config is not None:
            self.config = config

        try:
            data = asdict(self.config)
            temp_path = self.filepath.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.filepath)
            return True
        except Exception as e:
            print(f"[{APP_NAME}] Error saving settings: {e}")
            return False

    def export_to_file(self, dest_path: str) -> bool:
        """Export configuration to an external JSON file."""
        try:
            data = asdict(self.config)
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[{APP_NAME}] Export settings error: {e}")
            return False

    def import_from_file(self, src_path: str) -> bool:
        """Import configuration from an external JSON file and merge."""
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_dict = asdict(AppConfig())
            merged = _deep_merge_dict(default_dict, data)

            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)

            self.config = self.load()
            return True
        except Exception as e:
            print(f"[{APP_NAME}] Import settings error: {e}")
            return False
