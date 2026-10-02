"""Stimulus-response cross-correlation.

Fault-agnostic by construction. This module knows nothing about which fault
might be present; it extracts the same feature set regardless. That matters for
the identifiability experiment — a discriminator that inspected fault-specific
parameters would make the result circular.

Two response channels are computed, because a load stimulus can couple into a
signal two physically distinct ways:

  ADDITIVE   the stimulus shifts the signal value directly
             -> visible as correlation with the SIGNED residual
  MODULATING the stimulus changes the ENERGY of a disturbance without a
             consistent sign
             -> visible as correlation with the residual ENVELOPE

Computing both is standard practice for separating additive from multiplicative
coupling; it is not tailored to either fault.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foae import config


@dataclass(frozen=True)
class ResponseFeatures:
    """Generic probe-response descriptor for one sensor."""

    signed_lag_ms: float
    signed_polarity: int
    signed_magnitude: float
    envelope_lag_ms: float
    envelope_magnitude: float


def _best_lag(
    stimulus: np.ndarray,
    response: np.ndarray,
    rate_hz: float,
    max_lag_ms: float,
) -> tuple[float, float]:
    """Return (lag_ms, signed correlation at that lag) maximising |corr|."""
    s = stimulus - stimulus.mean()
    r = response - response.mean()
    s_norm = np.linalg.norm(s)
    r_norm = np.linalg.norm(r)
    if s_norm < 1e-12 or r_norm < 1e-12:
        return 0.0, 0.0

    max_lag = int(max_lag_ms * 1e-3 * rate_hz)
    best_lag, best_corr = 0, 0.0
    for lag in range(max_lag + 1):
        if lag >= len(s):
            break
        a = s[: len(s) - lag]
        b = r[lag:]
        c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
        if abs(c) > abs(best_corr):
            best_lag, best_corr = lag, c
    return best_lag / rate_hz * 1000.0, best_corr


def extract(
    stimulus: np.ndarray,
    residual: np.ndarray,
    rate_hz: float = config.PROBE_SAMPLE_RATE_HZ,
    max_lag_ms: float = config.PROBE_MAX_RESPONSE_LAG_MS,
) -> ResponseFeatures:
    """Extract generic response features from one stimulus/residual pair."""
    lag_s, corr_s = _best_lag(stimulus, residual, rate_hz, max_lag_ms)

    envelope = np.abs(residual - residual.mean())
    lag_e, corr_e = _best_lag(stimulus, envelope, rate_hz, max_lag_ms)

    return ResponseFeatures(
        signed_lag_ms=lag_s,
        signed_polarity=int(np.sign(corr_s)),
        signed_magnitude=abs(corr_s),
        envelope_lag_ms=lag_e,
        envelope_magnitude=abs(corr_e),
    )
