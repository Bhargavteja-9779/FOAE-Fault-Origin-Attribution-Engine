"""Intermittent-contact regime.

This is where probe sensitivity lives. A fretted connector contact does not sit
at a fixed elevated resistance — it chatters, opening and closing at contact-
bounce frequencies. Increased current draw (which an active probe causes)
raises the dropout rate, but the contact responds with mechanical/thermal
inertia, so the rate change LAGS the stimulus.

Contrast with a rail-reference fault, which is a resistive divider: it responds
to load instantaneously.
"""

from __future__ import annotations

import numpy as np

from foae import config

# CONTACT_RESPONSE_LAG_MS and CONTACT_LOAD_SENSITIVITY now live in config.py
# (handoff.md §5 Rule 1 corollary: any constant that can change an experimental
# outcome belongs there). Values are unchanged: 80.0 ms and 1.8.


def contact_gate(
    n: int,
    rate_hz: float,
    rng: np.random.Generator,
    load_modulation: np.ndarray | None = None,
) -> np.ndarray:
    """Boolean array: True where the contact is OPEN (dropout in progress).

    `load_modulation` in [0, 1] raises dropout probability, applied with
    config.CONTACT_RESPONSE_LAG_MS of delay.
    """
    t = np.arange(n) / rate_hz

    # Bounce carrier: contact is mechanically susceptible during part of each
    # bounce cycle. Squared sine gives a smooth susceptibility window.
    carrier = np.sin(2.0 * np.pi * config.INTERMITTENT_CONTACT_BOUNCE_HZ * t) ** 2

    p = np.full(n, config.INTERMITTENT_DUTY_CYCLE)
    if load_modulation is not None:
        lag_samples = int(config.CONTACT_RESPONSE_LAG_MS * 1e-3 * rate_hz)
        delayed = np.concatenate([np.zeros(lag_samples), load_modulation])[:n]
        p = p * (1.0 + config.CONTACT_LOAD_SENSITIVITY * delayed)

    p = np.clip(p * carrier, 0.0, 1.0)
    return rng.random(n) < p


def apply_dropout_polled(
    signal: np.ndarray,
    gate: np.ndarray,
    from_hz: float,
    poll_hz: float,
) -> np.ndarray:
    """Dropout at POLL granularity — the physically correct coupling.

    A tester reads a PID once per poll interval. If contact chatter corrupts
    any part of that interval the poll fails, and the ECU reports the last
    successfully polled value for the whole interval.

    Holding at the internal simulation rate instead (see `apply_dropout`)
    understates the fault by orders of magnitude: a 5 ms hold on a smooth trace
    produces an error far below sensor noise, making the fault undetectable by
    construction rather than by physics.

    Returns an array already at `poll_hz`.
    """
    factor = from_hz / poll_hz
    n_out = int(len(signal) / factor)
    out = np.empty(n_out)
    last_good = signal[0]
    for i in range(n_out):
        lo, hi = int(i * factor), min(int((i + 1) * factor), len(signal))
        if hi <= lo:
            out[i] = last_good
            continue
        if gate[lo:hi].any():
            out[i] = last_good          # stale: poll corrupted
        else:
            last_good = signal[hi - 1]
            out[i] = last_good
    return out


def apply_dropout(signal: np.ndarray, gate: np.ndarray) -> np.ndarray:
    """Sample-and-hold through dropouts: the ECU keeps the last good reading.

    The error introduced is the difference between the held value and the
    signal's true current value, so its SIGN depends on whether the signal
    happened to be rising or falling at dropout onset. That is the physical
    origin of the unstable polarity — it is not injected noise.
    """
    out = signal.copy()
    last_good = signal[0]
    for i in range(len(signal)):
        if gate[i]:
            out[i] = last_good
        else:
            last_good = signal[i]
    return out
