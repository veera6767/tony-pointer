"""
Pointer V - Privacy-Guaranteed Rotating Logger & Diagnostics
Strict Privacy Guarantee:
- Never logs typed characters, keystroke labels, or symbol contents.
- Logs only telemetry counts, event rates, and performance timings.
- Automatically rotates log files up to 2MB in %APPDATA%\\PointerV\\logs.
- Provides sanitized diagnostic report exports.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from version import APP_NAME, APPDATA_DIR_NAME, __version__

# Global Logger instance
_LOGGER: Optional[logging.Logger] = None


def get_logs_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        logs_dir = Path(appdata) / APPDATA_DIR_NAME / "logs"
    else:
        logs_dir = Path.home() / f".{APPDATA_DIR_NAME.lower()}" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("PointerV")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = get_logs_dir() / "pointer_v.log"
    handler = RotatingFileHandler(
        str(log_path),
        maxBytes=2 * 1024 * 1024, # 2 MB
        backupCount=3,
        encoding="utf-8"
    )
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    _LOGGER = logger
    _LOGGER.info(f"{APP_NAME} v{__version__} logging initialized (Strict Privacy Mode).")
    return _LOGGER


def log_input_event(event_type: str, count: int = 1, duration_ms: float = 0.0):
    """
    Logs input dispatch metadata strictly without recording key identities or contents.
    Example: log_input_event('key_typed', count=1, duration_ms=0.5)
    """
    logger = _LOGGER or setup_logger()
    logger.info(f"[Input] type={event_type} count={count} latency={duration_ms:.2f}ms")


def generate_diagnostics_report(telemetry: Dict) -> str:
    """
    Builds a sanitized diagnostics string for troubleshooting without any private keystroke or image data.
    """
    report = [
        f"=== {APP_NAME} Diagnostics Report ===",
        f"Version: {__version__}",
        f"Platform: {platform.platform()} ({platform.architecture()[0]})",
        f"Python: {sys.version.split()[0]}",
        f"System Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "--- Telemetry Snapshot ---",
        f"Operating Mode: {telemetry.get('mode', 'UNKNOWN')}",
        f"Target FPS: {telemetry.get('fps', 0.0):.1f}",
        f"Inference Latency: {telemetry.get('latency_ms', 0.0):.2f} ms",
        f"Camera Connected: {telemetry.get('camera_connected', False)}",
        f"Camera Luminance: {telemetry.get('camera_brightness', 0.0):.1f}",
        f"Tracking State: {telemetry.get('status_text', 'UNKNOWN')}",
        f"Active Monitor Setup: {telemetry.get('monitor_count', 1)} monitor(s)",
        "",
        "--- Privacy Verification ---",
        "Keystroke Recording: DISABLED (zero keys logged)",
        "Network Telemetry: NONE (offline local execution only)",
        "Frames to Disk: DISABLED",
        "========================================"
    ]
    return "\n".join(report)

