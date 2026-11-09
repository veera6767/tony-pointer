import os
import sys

# Ensure pointer_v is always in sys.path for test execution
PV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v"))
if PV_DIR not in sys.path:
    sys.path.insert(0, PV_DIR)

