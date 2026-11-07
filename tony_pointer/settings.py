"""
Tony Pointer - Settings & Configuration Manager
Handles JSON-backed persistence for active region, One Euro filter parameters,
gesture thresholds, camera settings, and paint application profiles.
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ActiveRegion:
    x_min: float = 0.15
    y_min: float = 0.15
    x_max: float = 0.85
    y_max: float = 0.85


@dataclass
class OneEuroSettings:
    min_cutoff: float = 1.0       # Minimum cutoff frequency (Hz)
    beta: float = 0.007           # Speed coefficient (higher = faster adaptation to high speeds)
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
    single_click_enabled: bool = True     # Toggle single air tap as left click
    dwell_lock_time_s: float = 0.60       # Index finger stationary time to lock brush
    dwell_radius_px: float = 16.0         # Allowed jitter radius for dwell
    pinch_threshold: float = 0.045        # Normalized 3D distance between thumb & index tip
    right_click_hold_s: float = 0.45      # Duration to hold 2 fingers for right click
    scroll_sensitivity: float = 2.4       # Multiplier for 2-finger scroll
    hand_timeout_ms: float = 300.0        # Freeze cursor if hand lost longer than this
    safety_release_timeout_s: float = 1.0 # Auto release mouse lock if lost


@dataclass
class OverlaySettings:
    cursor_color: str = "#00E5FF"        # Iron-Man Cyan
    brush_lock_color: str = "#FF5722"    # Arc Reactor Orange-Red
    cursor_size: int = 34
    preview_width: int = 320
    preview_height: int = 240
    preview_opacity: float = 0.85
    preview_visible: bool = True
    preview_pos_x: int = 40
    preview_pos_y: int = 40


@dataclass
class KeyboardSettings:
    enabled: bool = True
    symbols_panel_enabled: bool = True
    dim_inactive_panel: bool = True
    opacity: float = 0.88
    open_palm_hold_s: float = 0.50       # Hold open palm for ~0.5s to open keyboard
    fist_close_hold_s: float = 0.50      # Hold fist for ~0.5s to close keyboard
    swipe_threshold: float = 0.32        # Normalized by hand size
    swipe_cooldown_ms: float = 300.0     # Cooldown between row/window jumps
    tap_cooldown_ms: float = 200.0       # Per-finger debounce
    index_sensitivity: float = 1.0
    middle_sensitivity: float = 1.0
    ring_sensitivity: float = 1.25       # Calibrated for anatomically weaker ring finger
    pinky_sensitivity: float = 1.35      # Calibrated for pinky finger
    thumb_is_space: bool = True          # Thumb tap emits Space
    key_repeat_delay_s: float = 0.50     # Hold finger curled for >0.5s to repeat
    key_repeat_interval_s: float = 0.10  # 10 Hz repeat rate
    finger_mapping: str = "visual"       # "visual" (left-to-right) or "reversed"
    hotkey_keyboard: str = "ctrl+alt+k"
    hotkey_zone_toggle: str = "ctrl+alt+s"
    sound_enabled: bool = True


@dataclass
class AppConfig:
    version: str = "1.0.0"
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    target_fps: int = 60
    sensitivity: float = 1.0
    acceleration: float = 1.15
    active_region: ActiveRegion = field(default_factory=ActiveRegion)
    one_euro: OneEuroSettings = field(default_factory=OneEuroSettings)
    paint: PaintModeSettings = field(default_factory=PaintModeSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    keyboard: KeyboardSettings = field(default_factory=KeyboardSettings)
    hotkey_toggle: str = "ctrl+alt+t"
    hotkey_paint: str = "ctrl+alt+p"
    start_minimized: bool = False


class SettingsManager:
    """Manages loading, saving, and defaults for Tony Pointer configuration."""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Stored in user home ~/.tony_pointer/settings.json
            base_dir = Path.home() / ".tony_pointer"
        else:
            base_dir = Path(config_dir)

        base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = base_dir / "config.json"
        self.config: AppConfig = self.load()

    def load(self) -> AppConfig:
        """Load settings from JSON, filling in any missing fields with defaults."""
        if not self.filepath.exists():
            cfg = AppConfig()
            self.save(cfg)
            return cfg

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            active_region = ActiveRegion(**data.get("active_region", {}))
            one_euro = OneEuroSettings(**data.get("one_euro", {}))
            paint = PaintModeSettings(**data.get("paint", {}))
            gestures = GestureSettings(**data.get("gestures", {}))
            overlay = OverlaySettings(**data.get("overlay", {}))
            keyboard = KeyboardSettings(**data.get("keyboard", {}))

            cfg = AppConfig(
                version=data.get("version", "1.0.0"),
                camera_index=data.get("camera_index", 0),
                camera_width=data.get("camera_width", 1280),
                camera_height=data.get("camera_height", 720),
                target_fps=data.get("target_fps", 60),
                sensitivity=data.get("sensitivity", 1.0),
                acceleration=data.get("acceleration", 1.15),
                active_region=active_region,
                one_euro=one_euro,
                paint=paint,
                gestures=gestures,
                overlay=overlay,
                keyboard=keyboard,
                hotkey_toggle=data.get("hotkey_toggle", "ctrl+alt+t"),
                hotkey_paint=data.get("hotkey_paint", "ctrl+alt+p"),
                start_minimized=data.get("start_minimized", False),
            )
            return cfg
        except Exception as e:
            print(f"[TonyPointer] Warning: Failed to parse settings JSON ({e}). Using defaults.")
            cfg = AppConfig()
            self.save(cfg)
            return cfg

    def save(self, config: AppConfig = None) -> bool:
        """Persist settings to JSON file."""
        if config is not None:
            self.config = config

        try:
            data = asdict(self.config)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[TonyPointer] Error saving settings: {e}")
            return False
