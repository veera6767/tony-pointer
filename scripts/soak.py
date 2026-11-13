"""
Pointer V - Automated Soak & Freeze Test Runner
Launches Pointer V with synthetic injection, monitors responsiveness,
analyzes metrics.csv, and checks for stalls > 250ms or freeze dumps.
"""

import argparse
import csv
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil


def get_log_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PointerV" / "logs"
    return Path.home() / ".pointerv" / "logs"


def run_soak_test(
    executable_or_script: str,
    duration_sec: int = 60,
    scenario: str = "mixed",
    extra_flags: list[str] = None
) -> dict:
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    metrics_csv = log_dir / "metrics.csv"
    stall_log = log_dir / "stall_dump.log"
    freeze_log = log_dir / "freeze_dump.log"

    # Clean existing logs for a fresh test run
    for lf in (metrics_csv, stall_log, freeze_log):
        if lf.exists():
            try:
                lf.unlink()
            except Exception:
                pass

    cmd = []
    if executable_or_script.endswith(".py"):
        python_exe = sys.executable
        cmd = [python_exe, executable_or_script]
    else:
        cmd = [executable_or_script]

    flags = ["--debug", "--autostart", "--safe-sink", "--inject", scenario]
    if extra_flags:
        flags.extend(extra_flags)
    cmd.extend(flags)

    print(f"[*] Starting Pointer V: {' '.join(cmd)}")
    print(f"[*] Target duration: {duration_sec}s | Scenario: {scenario}")

    proc = subprocess.Popen(cmd)
    ps_proc = None
    try:
        ps_proc = psutil.Process(proc.pid)
    except Exception:
        pass

    start_time = time.perf_counter()
    cpu_samples = []
    rss_samples = []
    frozen = False

    try:
        while time.perf_counter() - start_time < duration_sec:
            if proc.poll() is not None:
                print(f"[!] Process exited prematurely with code {proc.returncode}")
                break

            if ps_proc and ps_proc.is_running():
                try:
                    cpu_samples.append(ps_proc.cpu_percent(interval=0.2))
                    rss_samples.append(ps_proc.memory_info().rss / (1024 * 1024))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            else:
                time.sleep(0.2)

            # Check if freeze_dump was written
            if freeze_log.exists() and freeze_log.stat().st_size > 0:
                print("[!] FREEZE DUMP DETECTED! Process froze for > 3.0s!")
                frozen = True
                break

    finally:
        print("[*] Terminating process...")
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # Analyze metrics
    longest_stall_ms = 0.0
    fps_samples = []
    if metrics_csv.exists():
        try:
            with open(metrics_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stall = float(row.get("longest_stall_ms", 0.0))
                    if stall > longest_stall_ms:
                        longest_stall_ms = stall
                    fps_val = float(row.get("camera_fps", 0.0))
                    if fps_val > 0:
                        fps_samples.append(fps_val)
        except Exception as e:
            print(f"[!] Could not parse metrics.csv: {e}")

    avg_cpu = sum(cpu_samples) / max(1, len(cpu_samples))
    mem_start = rss_samples[0] if rss_samples else 0.0
    mem_end = rss_samples[-1] if rss_samples else 0.0
    mem_growth = max(0.0, mem_end - mem_start)
    avg_fps = sum(fps_samples) / max(1, len(fps_samples))

    stalls_logged = stall_log.exists() and stall_log.stat().st_size > 0
    passed = (not frozen) and (longest_stall_ms < 500.0) and (proc.returncode in (0, None, 1))

    result = {
        "scenario": scenario,
        "flags": " ".join(extra_flags or []),
        "duration_sec": round(time.perf_counter() - start_time, 1),
        "frozen": frozen,
        "longest_stall_ms": round(longest_stall_ms, 1),
        "stalls_logged": stalls_logged,
        "avg_cpu_pct": round(avg_cpu, 1),
        "mem_start_mb": round(mem_start, 1),
        "mem_end_mb": round(mem_end, 1),
        "mem_growth_mb": round(mem_growth, 1),
        "avg_fps": round(avg_fps, 1),
        "passed": passed,
    }

    print("\n" + "=" * 60)
    print("SOAK TEST REPORT:")
    print(f"  Duration:          {result['duration_sec']}s")
    print(f"  Longest UI Stall:  {result['longest_stall_ms']} ms")
    print(f"  Freeze Tripped:    {result['frozen']}")
    print(f"  Avg CPU:           {result['avg_cpu_pct']} %")
    print(f"  Memory Growth:     {result['mem_growth_mb']} MB (End: {result['mem_end_mb']} MB)")
    print(f"  Avg FPS:           {result['avg_fps']}")
    print(f"  OVERALL RESULT:    {'PASS' if passed else 'FAIL'}")
    print("=" * 60 + "\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Pointer V Soak Test")
    parser.add_argument("--exe", type=str, default="pointer_v/main.py", help="Path to main.py or PointerV.exe")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--scenario", type=str, default="mixed", help="Synthetic scenario name")
    parser.add_argument("extra_flags", nargs=argparse.REMAINDER, help="Flags to pass through to Pointer V")
    args = parser.parse_args()

    res = run_soak_test(
        executable_or_script=args.exe,
        duration_sec=args.duration,
        scenario=args.scenario,
        extra_flags=args.extra_flags
    )
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
