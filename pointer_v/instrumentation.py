"""
Pointer V - Performance Instrumentation, Watchdog, and Freeze Metrics
Provides high-precision monitoring for UI thread responsiveness:
- 50 ms UI heartbeat timer + independent watchdog background thread.
- Logs thread stacks (sys._current_frames()) whenever UI stall > 250 ms.
- Re-arms faulthandler 3.0s timer to dump to freeze_dump.log if UI freezes.
- Writes per-second metrics to metrics.csv (CPU, RAM, latency, queue depths, stall durations).
- Optional tracemalloc memory snapshot diffing every 30s.
"""

import csv
import faulthandler
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import tracemalloc
from typing import Any, Callable, Dict, Optional
import psutil

from PySide6.QtCore import QObject, QTimer


def get_log_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        log_dir = Path(appdata) / "PointerV" / "logs"
    else:
        log_dir = Path.home() / ".pointerv" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


_ACTIVE_COLLECTOR: Optional["MetricsCollector"] = None


def get_collector() -> Optional["MetricsCollector"]:
    return _ACTIVE_COLLECTOR


def set_collector(collector: Optional["MetricsCollector"]):
    global _ACTIVE_COLLECTOR
    _ACTIVE_COLLECTOR = collector


def record_paint_timing(name: str, duration_ms: float):
    if _ACTIVE_COLLECTOR:
        _ACTIVE_COLLECTOR.record_paint_timing(name, duration_ms)


class MetricsCollector(QObject):
    """
    Orchestrates the 50ms UI heartbeat, watchdog thread, faulthandler,
    metrics CSV logging, and memory growth monitoring.
    """

    def __init__(
        self,
        is_debug: bool = False,
        get_telemetry_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        get_signal_counts_fn: Optional[Callable[[], Dict[str, int]]] = None,
    ):
        super().__init__()
        self.is_debug = is_debug
        self.get_telemetry_fn = get_telemetry_fn
        self.get_signal_counts_fn = get_signal_counts_fn

        self.log_dir = get_log_dir()
        self.stall_log_file = self.log_dir / "stall_dump.log"
        self.freeze_dump_file = self.log_dir / "freeze_dump.log"
        self.metrics_csv_file = self.log_dir / "metrics.csv"

        self.last_ui_heartbeat = time.perf_counter()
        self.longest_ui_stall_sec = 0.0
        self.longest_stall_this_second = 0.0
        self.running = False
        self.freeze_fp = None

        # Tracemalloc
        self.last_tracemalloc_snap = None
        self.last_tracemalloc_time = 0.0

        # Subsystem paint timings (updated by UI widgets)
        self.paint_timings = {
            "overlay_ms": 0.0,
            "preview_ms": 0.0,
            "keyboard_ms": 0.0,
        }

        # Initialize psutil process
        self.process = psutil.Process()

        # CSV initialization
        self.csv_file_handle = None
        self.csv_writer = None
        self._init_csv()

        # 1. 50ms UI Heartbeat Timer (strictly runs on UI thread)
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(50)
        self.ui_timer.timeout.connect(self._ui_heartbeat)

        # 2. Watchdog Thread (independent daemon OS thread)
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)

    def _init_csv(self):
        try:
            write_header = not self.metrics_csv_file.exists() or self.metrics_csv_file.stat().st_size == 0
            self.csv_file_handle = open(self.metrics_csv_file, "a", newline="", encoding="utf-8", buffering=1)
            self.csv_writer = csv.writer(self.csv_file_handle)
            if write_header:
                self.csv_writer.writerow([
                    "timestamp",
                    "process_cpu_pct",
                    "rss_mb",
                    "handles",
                    "longest_stall_ms",
                    "camera_fps",
                    "inference_ms",
                    "gesture_ms",
                    "output_ms",
                    "overlay_paint_ms",
                    "preview_paint_ms",
                    "keyboard_paint_ms",
                    "signals_per_sec",
                ])
        except Exception as e:
            print(f"[Metrics] CSV init error: {e}")

    def start(self):
        self.running = True
        self.last_ui_heartbeat = time.perf_counter()

        # Enable faulthandler with 3.0s watchdog dump
        try:
            self.freeze_fp = open(self.freeze_dump_file, "a", encoding="utf-8")
            faulthandler.enable(file=self.freeze_fp)
            faulthandler.dump_traceback_later(3, repeat=True, file=self.freeze_fp)
        except Exception as e:
            print(f"[Metrics] Faulthandler init failed: {e}")

        # Start tracemalloc if debug
        if self.is_debug:
            try:
                tracemalloc.start()
                self.last_tracemalloc_snap = tracemalloc.take_snapshot()
                self.last_tracemalloc_time = time.perf_counter()
            except Exception:
                pass

        self.ui_timer.start()
        self.watchdog_thread.start()

    def _ui_heartbeat(self):
        """Called every 50ms on Qt UI thread. Measures intervals and pets faulthandler."""
        now = time.perf_counter()
        stall = now - self.last_ui_heartbeat
        if stall > self.longest_stall_this_second:
            self.longest_stall_this_second = stall
        if stall > self.longest_ui_stall_sec:
            self.longest_ui_stall_sec = stall

        self.last_ui_heartbeat = now
        try:
            hb_file = self.log_dir / "heartbeat.ts"
            hb_file.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass

        # Re-arm faulthandler 3.0s timer
        if self.freeze_fp:
            try:
                faulthandler.dump_traceback_later(3, repeat=True, file=self.freeze_fp)
            except Exception:
                pass

    def record_paint_timing(self, name: str, duration_ms: float):
        self.paint_timings[name] = duration_ms

    def _watchdog_loop(self):
        """Independent monitor thread: checks for stalls > 250ms and writes CSV every 1s."""
        last_csv_write = time.perf_counter()
        last_logged_stall_time = 0.0

        while self.running:
            time.sleep(0.05)
            now = time.perf_counter()
            current_stall = now - self.last_ui_heartbeat

            # Check for UI Stall > 250 ms
            if current_stall > 0.250 and (now - last_logged_stall_time > 1.0):
                last_logged_stall_time = now
                self._dump_thread_stacks(current_stall)

            # Write metrics CSV every 1.0 second
            if now - last_csv_write >= 1.0:
                elapsed = now - last_csv_write
                last_csv_write = now
                self._write_csv_row(self.longest_stall_this_second * 1000.0)
                self.longest_stall_this_second = 0.0

                # Tracemalloc snapshot diff every 30s
                if self.is_debug and (now - self.last_tracemalloc_time >= 30.0):
                    self.last_tracemalloc_time = now
                    self._check_memory_growth()

    def _dump_thread_stacks(self, stall_sec: float):
        """Dumps all thread tracebacks when UI thread exceeds 250ms stall."""
        try:
            with open(self.stall_log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"UI THREAD STALL DETECTED: {stall_sec*1000.0:.1f} ms at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*70}\n")
                frames = sys._current_frames()
                for thread_id, frame in frames.items():
                    f.write(f"\n--- Thread ID: {thread_id} ---\n")
                    traceback.print_stack(frame, file=f)
        except Exception as e:
            print(f"[Watchdog] Failed to dump stall stacks: {e}")

    def _write_csv_row(self, max_stall_ms: float):
        if not self.csv_writer:
            return
        try:
            cpu_pct = self.process.cpu_percent(interval=None)
            mem_info = self.process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            num_handles = self.process.num_handles() if hasattr(self.process, "num_handles") else 0

            telem = self.get_telemetry_fn() if self.get_telemetry_fn else {}
            camera_fps = telem.get("fps", 0.0)
            perf = telem.get("perf", {})
            inf_ms = perf.get("inf_ms", telem.get("inference_ms", 0.0))
            gest_ms = perf.get("gest_ms", 0.0)
            out_ms = perf.get("output_ms", 0.0)

            signals_dict = self.get_signal_counts_fn() if self.get_signal_counts_fn else {}
            signals_str = ";".join(f"{k}={v}" for k, v in signals_dict.items())

            self.csv_writer.writerow([
                time.strftime("%H:%M:%S"),
                f"{cpu_pct:.1f}",
                f"{rss_mb:.1f}",
                num_handles,
                f"{max_stall_ms:.1f}",
                f"{camera_fps:.1f}",
                f"{inf_ms:.1f}",
                f"{gest_ms:.1f}",
                f"{out_ms:.1f}",
                f"{self.paint_timings.get('overlay_ms', 0.0):.2f}",
                f"{self.paint_timings.get('preview_ms', 0.0):.2f}",
                f"{self.paint_timings.get('keyboard_ms', 0.0):.2f}",
                signals_str,
            ])
        except Exception as e:
            print(f"[Metrics] CSV write error: {e}")

    def _check_memory_growth(self):
        try:
            current_snap = tracemalloc.take_snapshot()
            top_stats = current_snap.compare_to(self.last_tracemalloc_snap, "lineno")
            self.last_tracemalloc_snap = current_snap

            growth_log = self.log_dir / "memory_growth.log"
            with open(growth_log, "a", encoding="utf-8") as f:
                f.write(f"\n--- Tracemalloc 30s Snapshot Diff at {time.strftime('%H:%M:%S')} ---\n")
                for stat in top_stats[:10]:
                    f.write(f"{stat}\n")
        except Exception as e:
            print(f"[Metrics] Tracemalloc diff error: {e}")

    def stop(self):
        self.running = False
        try:
            self.ui_timer.stop()
        except Exception:
            pass
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        if self.freeze_fp:
            try:
                self.freeze_fp.close()
            except Exception:
                pass
            self.freeze_fp = None
        if self.csv_file_handle:
            try:
                self.csv_file_handle.close()
            except Exception:
                pass
            self.csv_file_handle = None
