"""Physics-based trace generation.

Minimal implementation: enough to support the §5.1 identifiability experiment.
Generates a healthy drive-cycle trace at INTERNAL_SIM_RATE_HZ, from which the
fault models in faults.py derive their observations.
"""

from __future__ import annotations

import numpy as np

from foae import config


def _smooth_drive_cycle(n: int, rate_hz: float, rng: np.random.Generator) -> np.ndarray:
    """A plausible speed profile: low-frequency random walk, smoothed."""
    steps = rng.normal(0.0, 1.0, size=n)
    # Integrate then low-pass by moving average over a window of ~4 s. The
    # window must stay shorter than the trace: np.convolve(mode="same") returns
    # the LONGER of its two inputs, so an oversized kernel silently changes the
    # output length. Short probe traces (2 s) hit exactly that case.
    win = max(1, min(int(rate_hz * 4.0), n // 2))
    walk = np.cumsum(steps)
    kernel = np.ones(win) / win
    smooth = np.convolve(walk, kernel, mode="same")
    lo, hi = config.PID_NOMINAL_RANGES[config.PID_VEHICLE_SPEED]
    span = smooth.max() - smooth.min()
    if span < 1e-9:
        return np.full(n, (lo + hi) / 2.0)
    norm = (smooth - smooth.min()) / span
    # Keep to a mid-range cruise band; full 0..160 swings are not representative.
    return lo + norm * (hi - lo) * 0.6 + 20.0


def generate_true_speed(
    duration_s: float,
    rate_hz: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Ground-truth vehicle speed at `rate_hz`, before any sensor effects."""
    n = int(duration_s * rate_hz)
    return _smooth_drive_cycle(n, rate_hz, rng)


def generate_true_maf(
    true_speed: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """MAF trace physically coupled to speed, per config.PHYSICS_PAIRS.

    Needed because MAF current draw is what loads a shared ground rail.
    """
    lo, hi = config.PID_NOMINAL_RANGES[config.PID_MAF_RATE]
    s = (true_speed - true_speed.min()) / (np.ptp(true_speed) + 1e-9)
    target_r = dict(
        ((a, b), r) for a, b, r in config.PHYSICS_PAIRS
    )[(config.PID_VEHICLE_SPEED, config.PID_MAF_RATE)]
    indep = rng.normal(0.0, 1.0, size=len(s))
    indep = (indep - indep.min()) / (np.ptp(indep) + 1e-9)
    mixed = target_r * s + (1.0 - target_r) * indep
    return lo + mixed * (hi - lo) * 0.5


def normalised_current_draw(signal: np.ndarray) -> np.ndarray:
    """Map a sensor trace to its instantaneous current draw in [0, 1]."""
    span = np.ptp(signal)
    if span < 1e-9:
        return np.zeros_like(signal)
    return (signal - signal.min()) / span


def observe(
    true_signal: np.ndarray,
    pid: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply healthy sensor measurement noise."""
    return true_signal + rng.normal(0.0, config.SENSOR_NOISE_STD[pid], size=len(true_signal))


def decimate(signal: np.ndarray, from_hz: float, to_hz: float) -> np.ndarray:
    """Sample-and-hold decimation, as a real tester polls a PID.

    Deliberately NOT anti-alias filtered: a tester reading a PID at 10 Hz does
    not low-pass the underlying electrical behaviour first, so contact bounce
    above Nyquist aliases down. That aliasing is part of what the passive
    observer actually sees.
    """
    factor = from_hz / to_hz
    if factor < 1.0:
        raise ValueError("decimate() cannot upsample")
    idx = (np.arange(int(len(signal) / factor)) * factor).astype(int)
    return signal[idx]
