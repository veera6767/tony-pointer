"""
Static Code Quality & Undefined Name Tests
Ensures zero undefined names (F821), syntax errors, or broken imports across pointer_v.
"""

import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
POINTER_V_DIR = REPO_ROOT / "pointer_v"


def test_ruff_no_undefined_names():
    """Verifies with ruff that pointer_v contains zero undefined names (F821)."""
    cmd = [sys.executable, "-m", "ruff", "check", str(POINTER_V_DIR), "--select", "F821,E9"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert res.returncode == 0, f"Ruff found undefined names or syntax errors:\n{res.stdout}\n{res.stderr}"


def test_pyflakes_pointer_v():
    """Verifies with pyflakes that no syntax or undefined names exist in pointer_v source."""
    py_files = []
    for root, _, files in os.walk(str(POINTER_V_DIR)):
        if any(ignored in root for ignored in ["dist", "build", "_backups", "__pycache__"]):
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    cmd = [sys.executable, "-m", "pyflakes"] + py_files
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    
    # Filter for fatal errors: undefined names or syntax errors
    fatal_lines = [
        line for line in (res.stdout + res.stderr).splitlines()
        if "undefined name" in line.lower() or "syntaxerror" in line.lower()
    ]
    assert len(fatal_lines) == 0, f"Pyflakes found fatal issues:\n" + "\n".join(fatal_lines)
