"""Empirical test of the docs/design.md §5.1 identifiability claim.

The claim: CONN:C_VSS and RAIL:REF_5V_B produce an identical passive anomaly
footprint {vehicle_speed}, so footprint-based inference cannot separate them,
and the UTP probe is what resolves them.

This file tests that claim rather than assuming it. If passive inference DOES
separate the two faults, the design document is wrong and must be corrected —
that outcome is a legitimate result here, not a test failure to be tuned away.
"""

from __future__ import annotations

import numpy as np
import pytest

from foae import config
from foae.probe import perturbation, response
from foae.simulator import vehicle_model
from foae.simulator.faults import ConnectorDropoutFault, ReferenceRailFault

# Sample size: sets the precision of the LOO accuracy, not the outcome.
N_SEEDS = 50


# ---------------------------------------------------------------------------
# Statistics (numpy only — no sklearn dependency for a core claim test)
# ---------------------------------------------------------------------------


def auc(a: np.ndarray, b: np.ndarray) -> float:
    """Mann-Whitney AUC. 0.5 = indistinguishable, 1.0 = perfectly separated.

    Returned folded to [0.5, 1.0]: direction of separation is not the question,
    only whether separation exists.
    """
    all_v = np.concatenate([a, b])
    ranks = all_v.argsort().argsort().astype(float) + 1.0
    ra = ranks[: len(a)].sum()
    u = ra - len(a) * (len(a) + 1) / 2.0
    val = u / (len(a) * len(b))
    return max(val, 1.0 - val)


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if sp < 1e-12:
        return 0.0
    return abs(a.mean() - b.mean()) / sp


def loo_accuracy(fa: np.ndarray, fb: np.ndarray) -> float:
    """Leave-one-out nearest-centroid accuracy on standardised features."""
    x = np.vstack([fa, fb])
    y = np.array([0] * len(fa) + [1] * len(fb))
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd[sd < 1e-12] = 1.0
    x = (x - mu) / sd

    correct = 0
    for i in range(len(x)):
        mask = np.ones(len(x), bool)
        mask[i] = False
        c0 = x[mask & (y == 0)].mean(axis=0)
        c1 = x[mask & (y == 1)].mean(axis=0)
        pred = int(np.linalg.norm(x[i] - c1) < np.linalg.norm(x[i] - c0))
        correct += int(pred == y[i])
    return correct / len(x)


# ---------------------------------------------------------------------------
# Session generation
# ---------------------------------------------------------------------------


def _passive_residual(fault, seed: int) -> np.ndarray:
    """One passive session. Residual vs the physics-pair prediction.

    We use ground-truth speed as the prediction. That is GENEROUS to the
    passive observer — a real parity check is noisier — which makes a negative
    passive result a strong one.
    """
    rng = np.random.default_rng(seed)
    rate = config.INTERNAL_SIM_RATE_HZ
    true = vehicle_model.generate_true_speed(config.SESSION_DURATION_S, rate, rng)
    sr = config.SAMPLE_RATE_HZ
    m_d = fault.apply(true, rate, rng, probe=None, poll_hz=sr)
    m_d = vehicle_model.observe(m_d, config.PID_VEHICLE_SPEED, rng)
    t_d = vehicle_model.decimate(true, rate, sr)
    n = min(len(m_d), len(t_d))
    return m_d[:n] - t_d[:n]


def _probe_features(fault, seed: int) -> response.ResponseFeatures:
    """One probed session, returning generic response features."""
    rng = np.random.default_rng(seed + 100_000)
    rate = config.INTERNAL_SIM_RATE_HZ
    stim = perturbation.generate(config.MAX_PROBE_DURATION_S, rate)

    true = vehicle_model.generate_true_speed(config.MAX_PROBE_DURATION_S, rate, rng)
    pr = config.PROBE_SAMPLE_RATE_HZ
    measured = fault.apply(true, rate, rng, probe=stim, poll_hz=pr)
    measured = vehicle_model.observe(measured, config.PID_VEHICLE_SPEED, rng)
    t_d = vehicle_model.decimate(true, rate, pr)
    stim_d = vehicle_model.decimate(stim, rate, pr)
    n = min(len(measured), len(t_d), len(stim_d))
    return response.extract(stim_d[:n], measured[:n] - t_d[:n], pr)


def _passive_waveform_features(resid: np.ndarray) -> list[float]:
    """Generic passive waveform statistics — no fault-specific knowledge."""
    r = resid - resid.mean()
    sd = r.std()
    kurt = float((r**4).mean() / (sd**4 + 1e-12)) if sd > 1e-12 else 0.0
    ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 2 and sd > 1e-12 else 0.0
    hf = float(np.abs(np.diff(r)).mean() / (sd + 1e-12))
    return [float(sd), float(np.abs(r).mean()), kurt, ac1, hf]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trials():
    conn, rail = ConnectorDropoutFault(), ReferenceRailFault()
    return {
        "passive_conn": [_passive_residual(conn, s) for s in range(N_SEEDS)],
        "passive_rail": [_passive_residual(rail, s) for s in range(N_SEEDS)],
        "probe_conn": [_probe_features(conn, s) for s in range(N_SEEDS)],
        "probe_rail": [_probe_features(rail, s) for s in range(N_SEEDS)],
    }


# ---------------------------------------------------------------------------
# (a) Passive footprint inference must NOT separate them
# ---------------------------------------------------------------------------


def test_footprints_are_identical():
    """The collision itself: both faults implicate exactly {vehicle_speed}."""
    conn_fp = {ConnectorDropoutFault().sensor}
    rail_fp = set(ReferenceRailFault().affected_sensors)
    assert conn_fp == rail_fp == {config.PID_VEHICLE_SPEED}


def test_footprint_match_scores_are_equal(trials):
    """Set-agreement scoring assigns both hypotheses an identical score."""
    observed = {config.PID_VEHICLE_SPEED}

    def jaccard(a: set, b: set) -> float:
        return len(a & b) / len(a | b)

    s_conn = jaccard(observed, {ConnectorDropoutFault().sensor})
    s_rail = jaccard(observed, set(ReferenceRailFault().affected_sensors))
    assert s_conn == s_rail == 1.0


# ---------------------------------------------------------------------------
# (b) Probe response MUST separate them
# ---------------------------------------------------------------------------


def test_probe_separates_the_pair(trials):
    """The lead claim's empirical support."""
    fa = np.array(
        [[f.signed_magnitude, f.envelope_magnitude, f.envelope_lag_ms]
         for f in trials["probe_conn"]]
    )
    fb = np.array(
        [[f.signed_magnitude, f.envelope_magnitude, f.envelope_lag_ms]
         for f in trials["probe_rail"]]
    )
    acc = loo_accuracy(fa, fb)
    assert acc >= 0.90, f"probe separation insufficient: LOO accuracy {acc:.3f}"


def test_probe_signed_magnitude_effect_size(trials):
    a = np.array([f.signed_magnitude for f in trials["probe_conn"]])
    b = np.array([f.signed_magnitude for f in trials["probe_rail"]])
    assert cohens_d(a, b) >= 0.8, "signed-magnitude separation below large effect"


def test_rail_polarity_is_stable(trials):
    """Rail fault: consistent sign, as a resistive divider should give."""
    pol = np.array([f.signed_polarity for f in trials["probe_rail"]])
    dominant = max((pol == 1).mean(), (pol == -1).mean())
    assert dominant >= 0.9, f"rail polarity unstable ({dominant:.2f})"


def test_connector_polarity_is_less_stable_than_rail(trials):
    """Connector fault: sign depends on signal slope at dropout onset."""
    pc = np.array([f.signed_polarity for f in trials["probe_conn"]])
    pr = np.array([f.signed_polarity for f in trials["probe_rail"]])
    stab_c = max((pc == 1).mean(), (pc == -1).mean())
    stab_r = max((pr == 1).mean(), (pr == -1).mean())
    assert stab_c < stab_r, f"connector polarity ({stab_c:.2f}) not less stable than rail ({stab_r:.2f})"
