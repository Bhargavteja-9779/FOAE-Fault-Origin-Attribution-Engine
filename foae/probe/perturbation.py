"""Diagnostic-schedule perturbation primitives.

The probe modulates diagnostic request cadence, which modulates electrical load
on the sensor harness. It is a load stimulus, not a signal injection — nothing
is written to the sensor.
"""

from __future__ import annotations

import numpy as np

from foae import config

# --- Stimulus frequency ------------------------------------------------------
# PROBE_STIMULUS_HZ now lives in config.py (handoff.md §5 Rule 1 corollary).
# Value is unchanged: 2.0.


def generate(
    duration_s: float = config.MAX_PROBE_DURATION_S,
    rate_hz: float = config.INTERNAL_SIM_RATE_HZ,
) -> np.ndarray:
    """Square-wave load stimulus in [0, 1].

    Deterministic by design: the stimulus must be exactly known in order to
    cross-correlate the response against it.
    """
    n = int(duration_s * rate_hz)
    t = np.arange(n) / rate_hz
    return (np.sin(2.0 * np.pi * config.PROBE_STIMULUS_HZ * t) > 0).astype(float)
