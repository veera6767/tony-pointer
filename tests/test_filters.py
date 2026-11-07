"""
Unit tests for One Euro Filter smoothing and anti-jitter buffer.
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pointer_v")))

from filters import OneEuroFilter, OneEuroFilter2D, PositionHistoryBuffer


def test_one_euro_filter_rest_suppression():
    """At rest with slight noise, the filter output should show heavy smoothing."""
    f = OneEuroFilter(min_cutoff=1.0, beta=0.007)
    t = 0.0
    val = 100.0
    outputs = []

    for i in range(30):
        t += 0.016
        # Small noise +/- 1.0 around 100.0
        jitter = 1.0 if (i % 2 == 0) else -1.0
        out = f.filter(val + jitter, t)
        outputs.append(out)

    # Output should stay tightly centered around 100.0 with less variance than raw jitter
    variance_raw = 1.0
    var_filt = sum((x - 100.0) ** 2 for x in outputs[5:]) / len(outputs[5:])
    assert var_filt < variance_raw


def test_one_euro_filter_fast_adaptation():
    """During rapid motion, filter adapts rapidly with low lag."""
    f = OneEuroFilter(min_cutoff=1.0, beta=0.007)
    t = 0.0
    # Step jump from 0 to 500
    f.filter(0.0, t)
    t += 0.016
    out = f.filter(500.0, t)
    # With high beta and speed, it should cover significant ground
    assert out > 100.0


def test_history_buffer_lookback():
    """Historical lookback correctly retrieves position 150ms in the past."""
    buf = PositionHistoryBuffer(max_duration_s=0.6)
    t = 1.0
    buf.append(100, 200, t)
    buf.append(120, 220, t + 0.05)
    buf.append(150, 250, t + 0.10)
    buf.append(200, 300, t + 0.15)
    buf.append(300, 400, t + 0.20)

    # Look back 150ms from t+0.20 -> roughly t+0.05 (120, 220)
    pos = buf.get_position_at_lookback(150.0)
    assert pos is not None
    assert abs(pos[0] - 120) <= 20
    assert abs(pos[1] - 220) <= 20

