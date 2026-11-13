"""
Pointer V - Diagnostic Stack Dumper via py-spy
Dumps thread stacks of running Pointer V process.
"""

import argparse
import os
import subprocess
import sys
import psutil


def find_pointer_v_pid() -> int | None:
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            cmdline = " ".join(proc.info["cmdline"] or []).lower()
            if "pointerv.exe" in name:
                return proc.info["pid"]
            if "python" in name and ("pointer_v" in cmdline or "main.py" in cmdline):
                if proc.info["pid"] != os.getpid():
                    return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="Dump stacks of Pointer V using py-spy")
    parser.add_argument("--pid", type=int, default=None, help="Target process PID")
    args = parser.parse_args()

    pid = args.pid or find_pointer_v_pid()
    if not pid:
        print("[ERROR] No running Pointer V process found.")
        sys.exit(1)

    print(f"[*] Dumping thread stacks for PID {pid}...")
    try:
        # Locate py-spy binary in environment or PATH
        cmd = ["py-spy", "dump", "--pid", str(pid)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(res.stdout)
        else:
            print(f"[ERROR] py-spy failed (code {res.returncode}):\n{res.stderr}")
    except Exception as e:
        print(f"[ERROR] Failed to run py-spy: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
