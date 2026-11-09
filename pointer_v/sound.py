"""
Pointer V - Audio Feedback Manager
Provides crisp, non-blocking audio cues for air clicks, modifier locks, and mode transitions
with global mute, volume thresholds, and Windows native WAV dispatch.
"""

from pathlib import Path
import sys

try:
    import winsound
    HAS_WINSOUND = True
except Exception:
    HAS_WINSOUND = False


class SoundManager:
    """Dispatches subtle sound cues asynchronously without stalling vision threads."""

    def __init__(self, settings):
        self.settings = settings
        base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
        if (base / "pointer_v" / "assets" / "sounds").exists():
            self.sounds_dir = base / "pointer_v" / "assets" / "sounds"
        elif (base / "assets" / "sounds").exists():
            self.sounds_dir = base / "assets" / "sounds"
        else:
            self.sounds_dir = Path(__file__).resolve().parent / "assets" / "sounds"

    def play(self, sound_name: str, freq_fallback: int = 800, dur_fallback: int = 40):
        if not getattr(self.settings.sound, "enabled", True):
            return
        if getattr(self.settings.sound, "muted", False):
            return
        if getattr(self.settings.sound, "volume", 80) <= 0:
            return

        if not HAS_WINSOUND:
            return

        wav_path = self.sounds_dir / f"{sound_name}.wav"
        if wav_path.exists():
            try:
                flags = winsound.SND_ASYNC | winsound.SND_FILENAME | winsound.SND_NODEFAULT
                winsound.PlaySound(str(wav_path), flags)
                return
            except Exception:
                pass

        try:
            winsound.Beep(freq_fallback, dur_fallback)
        except Exception:
            pass

    def key_click(self):
        self.play("click", 1200, 20)

    def key_repeat(self):
        self.play("click", 1400, 15)

    def double_click(self):
        self.play("double_click", 1600, 35)

    def lock(self):
        self.play("lock", 1100, 40)

    def unlock(self):
        self.play("unlock", 600, 40)

    def mode_change(self):
        self.play("mode_change", 1000, 50)

    def warning(self):
        self.play("warning", 400, 80)

