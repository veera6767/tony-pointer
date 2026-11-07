"""
Pointer V - Signal Filters & Mathematical Smoothing
Implements the 1 Euro Filter (Casiez, Roussel, & Vogel, 2012) for jitter-free,
ultra-responsive 2D cursor mapping, plus a historical position ring buffer to
anchor clicks during the micro-impulse of air taps.
"""

import collections
import math
import time
from typing import Optional, Tuple


class LowPassFilter:
    """Standard 1st-order exponential low-pass filter."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.s: Optional[float] = None

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha

        if self.s is None:
            self.s = value
        else:
            self.s = self.alpha * value + (1.0 - self.alpha) * self.s
        return self.s

    def reset(self):
        self.s = None


class OneEuroFilter:
    """
    One Euro Filter (Casiez, Roussel, Vogel, CHI 2012).
    Dynamically adjusts low-pass cutoff frequency based on movement speed:
    - Slow movements: low cutoff -> suppresses human hand tremor & optical noise.
    - Fast movements: high cutoff -> zero perceptible latency or trailing lag.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filt = LowPassFilter()
        self.dx_filt = LowPassFilter()
        self.last_time: Optional[float] = None
        self.last_x: Optional[float] = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if timestamp is None:
            timestamp = time.perf_counter()

        if self.last_time is None:
            self.last_time = timestamp
            self.last_x = x
            return self.x_filt.filter(x, 1.0)

        dt = timestamp - self.last_time
        if dt <= 1e-6:
            # Duplicate or very close frame
            return self.x_filt.s if self.x_filt.s is not None else x

        # Estimate derivative (speed)
        dx = (x - self.last_x) / dt
        edx = self.dx_filt.filter(dx, self._alpha(self.d_cutoff, dt))

        # Calculate dynamic cutoff based on speed
        cutoff = self.min_cutoff + self.beta * abs(edx)

        # Filter the position
        res = self.x_filt.filter(x, self._alpha(cutoff, dt))

        self.last_time = timestamp
        self.last_x = x
        return res

    def reset(self):
        self.x_filt.reset()
        self.dx_filt.reset()
        self.last_time = None
        self.last_x = None


class OneEuroFilter2D:
    """Dual-axis One Euro Filter for 2D screen coordinates."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.x_filter = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.y_filter = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def update_params(self, min_cutoff: float, beta: float):
        self.x_filter.min_cutoff = min_cutoff
        self.x_filter.beta = beta
        self.y_filter.min_cutoff = min_cutoff
        self.y_filter.beta = beta

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if timestamp is None:
            timestamp = time.perf_counter()
        fx = self.x_filter.filter(x, timestamp)
        fy = self.y_filter.filter(y, timestamp)
        return fx, fy

    def reset(self):
        self.x_filter.reset()
        self.y_filter.reset()


class PositionHistoryBuffer:
    """
    Stores timestamped cursor positions for the past N milliseconds.
    When a user initiates an air-tap gesture, the physical curl of the index
    finger naturally introduces a downward/backward impulse.
    By querying this buffer at (current_time - lookback_ms), Pointer V freezes
    the cursor at the exact intent target where the finger rested before the tap!
    """

    def __init__(self, max_duration_s: float = 0.5):
        self.max_duration_s = max_duration_s
        self.history = collections.deque()  # Stores (timestamp, x, y)

    def append(self, x: float, y: float, timestamp: Optional[float] = None):
        if timestamp is None:
            timestamp = time.perf_counter()
        self.history.append((timestamp, x, y))

        # Evict old entries
        cutoff = timestamp - self.max_duration_s
        while self.history and self.history[0][0] < cutoff:
            self.history.popleft()

    def get_position_at_lookback(self, lookback_ms: float = 150.0) -> Optional[Tuple[float, float]]:
        if not self.history:
            return None

        current_time = self.history[-1][0]
        target_time = current_time - (lookback_ms / 1000.0)

        # Find closest sample to target_time
        best_diff = float("inf")
        best_coord = (self.history[-1][1], self.history[-1][2])

        for t, x, y in reversed(self.history):
            diff = abs(t - target_time)
            if diff < best_diff:
                best_diff = diff
                best_coord = (x, y)
            else:
                # Difference starting to grow because entries are chronological
                break

        return best_coord

    def clear(self):
        self.history.clear()


def apply_acceleration(delta_x: float, delta_y: float, sensitivity: float, accel_exp: float = 1.15) -> Tuple[float, float]:
    """
    Subtle power curve acceleration: allows fine sub-pixel micro-adjustments
    when moving slowly, yet flings the cursor across dual 4K monitors on swift flicks.
    """
    speed = math.hypot(delta_x, delta_y)
    if speed <= 1e-5:
        return 0.0, 0.0

    multiplier = (speed ** (accel_exp - 1.0)) * sensitivity
    return delta_x * multiplier, delta_y * multiplier
