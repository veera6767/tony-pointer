"""
Pointer V - Synthetic Sound Cue Generator
Generates clean, subtle WAV audio cues for key click, brush lock/unlock, and mode switches.
"""

import math
from pathlib import Path
import struct
import wave

def generate_wave(filename: str, duration_s: float, freqs: list, volume: float = 0.3):
    sample_rate = 44100
    n_samples = int(duration_s * sample_rate)

    out = []
    for i in range(n_samples):
        t = i / sample_rate
        # Envelope to avoid click at edges (fade in and out)
        fade_len = min(0.005, duration_s / 3.0)
        env = 1.0
        if t < fade_len:
            env = t / fade_len
        elif t > duration_s - fade_len:
            env = (duration_s - t) / fade_len

        val = 0.0
        for f, weight in freqs:
            val += math.sin(2.0 * math.pi * f * t) * weight

        sample = int(val * env * volume * 32767.0)
        sample = max(-32768, min(32767, sample))
        out.append(sample)

    p = Path(filename)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        raw_bytes = struct.pack(f"<{len(out)}h", *out)
        wav.writeframes(raw_bytes)

def generate_all_sounds():
    base_dir = Path(__file__).resolve().parent / "assets" / "sounds"
    generate_wave(str(base_dir / "click.wav"), 0.015, [(1800, 0.8), (2400, 0.2)], volume=0.25)
    generate_wave(str(base_dir / "double_click.wav"), 0.045, [(1600, 0.6), (2200, 0.4)], volume=0.28)
    generate_wave(str(base_dir / "lock.wav"), 0.05, [(800, 0.5), (1400, 0.5)], volume=0.25)
    generate_wave(str(base_dir / "unlock.wav"), 0.05, [(1400, 0.5), (800, 0.5)], volume=0.25)
    generate_wave(str(base_dir / "mode_change.wav"), 0.06, [(900, 0.4), (1200, 0.6)], volume=0.25)
    generate_wave(str(base_dir / "warning.wav"), 0.08, [(350, 0.7), (450, 0.3)], volume=0.3)
    print("All audio cues generated successfully.")

if __name__ == "__main__":
    generate_all_sounds()

