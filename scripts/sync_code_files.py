"""
Script to synchronize src/data/codeFiles.ts from the real pointer_v python files.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POINTER_V = ROOT / "pointer_v"
CODE_FILES_TS = ROOT / "src" / "data" / "codeFiles.ts"

DESCRIPTIONS = {
    "main.py": "Pointer V - Main Application Entrypoint & System Coordinator",
    "theme.py": "Pointer V - Centralized Design Tokens, Palette & Theme QSS Generator",
    "version.py": "Pointer V - Version, Metadata & Product Constants",
    "settings.py": "Pointer V - JSON Settings Persistence & Legacy Migration Manager",
    "filters.py": "Pointer V - Mathematical Filters (One Euro Filter 2D & History Buffer)",
    "mouse.py": "Pointer V - Win32 High-Resolution Multi-Monitor Mouse Controller",
    "tracker.py": "Pointer V - MediaPipe Hand Landmarks & 3D Vector Geometry Tracker",
    "gestures.py": "Pointer V - Gesture State Machine & Hysteresis Classification Engine",
    "camera.py": "Pointer V - Threaded OpenCV Capture Stream & HUD Visualizer",
    "keyboard_layout.py": "Pointer V - 4-Key Progressive Sliding Window Keyboard Layout Engine",
    "keyboard_out.py": "Pointer V - Win32 Virtual Keyboard Output & Sticky Modifier Dispatcher",
    "keyboard_ui.py": "Pointer V - Floating Corner Air Keyboard Widget & HUD",
    "finger_taps.py": "Pointer V - Independent 5-Finger Flexion & Neighbor Lockout Detector",
    "mode_manager.py": "Pointer V - Multi-Modal Navigation & Sliding Door Gesture Coordinator",
    "overlay.py": "Pointer V - Frameless Windows Click-Through Cursor Reticle Overlay",
    "preview.py": "Pointer V - Draggable Live Webcam Preview PiP Overlay",
    "recorder.py": "Pointer V - Raw 21-Point Landmark Session Recorder & Replayer",
    "sound.py": "Pointer V - Low-Latency Audio Feedback & Synthetic Cues Dispatcher",
    "logger.py": "Pointer V - Privacy-Preserving Rotating Logger",
    "hotkeys.py": "Pointer V - Native Win32 RegisterHotKey Global Hotkey Dispatcher",
    "instrumentation.py": "Pointer V - UI Watchdog & Performance Metrics Collector",
    "scenario_generator.py": "Pointer V - Synthetic Gesture Landmark Scenario Generator",
}

def sync():
    files = []
    for py_file in sorted(POINTER_V.glob("*.py")):
        name = py_file.name
        content = py_file.read_text(encoding="utf-8")
        desc = DESCRIPTIONS.get(name, f"Pointer V - {name}")
        files.append({
            "name": name,
            "path": f"pointer_v/{name}",
            "description": desc,
            "content": content,
            "language": "python"
        })

    # Generate TypeScript content
    ts_content = [
        "// Code Files Database for Pointer V Desktop & Web Studio",
        "// Automatically generated from real repository files",
        "",
        "export interface CodeFile {",
        "  name: string;",
        "  path: string;",
        "  description: string;",
        "  content: string;",
        "  language: string;",
        "}",
        "",
        "export const POINTER_V_FILES: CodeFile[] = " + json.dumps(files, indent=2) + ";\n"
    ]

    CODE_FILES_TS.write_text("\n".join(ts_content), encoding="utf-8")
    print(f"Synced {len(files)} files to {CODE_FILES_TS}")

if __name__ == "__main__":
    sync()
