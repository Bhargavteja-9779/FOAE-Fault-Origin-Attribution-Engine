"""§5.2 nesting pair: early-stage RAIL:SENSOR_GND_B vs CONN:C_VSS.

Replacement candidate for the falsified §5.1 pair. Same protocol as
tests/test_identifiability.py, same four discriminators.

Both faults are intermittent-dropout on vehicle_speed with identical footprint
{vehicle_speed}. They differ only in what modulates the dropout rate: a shared
ground rail carries the co-resident sensor's (MAF) return current, a connector
fault does not.

The passive observer is given the SAME information the probe exploits — the MAF
trace is fully observable — so passive is not handicapped. The question is not
whether passive CAN separate them but how much observation it needs.

This pair is to be falsified as readily as the last one.
"""

from __future__ import annotations

import numpy as np
import pytest

from foae import config
from foae.probe import perturbation, response
from foae.simulator import vehicle_model
from foae.simulator.faults import ConnectorDropoutFault, SharedGroundIntermittentFault

from tests.test_identifiability import auc, cohens_d, loo_accuracy  # noqa: F401

# Sample size: sets the precision of the LOO accuracy, not the outcome.
N_SEEDS = 50


def _passive_session(fault, seed: int, duration_s: float | None = None):
    """Returns (vss_residual, observed_maf) at logging rate."""
    duration_s = duration_s or config.SESSION_DURATION_S
    rng = np.random.default_rng(seed)
    rate = config.INTERNAL_SIM_RATE_HZ

    true_v = vehicle_model.generate_true_speed(duration_s, rate, rng)
    true_m = vehicle_model.generate_true_maf(true_v, rng)
    rail_load = vehicle_model.normalised_current_draw(true_m)

    sr = config.SAMPLE_RATE_HZ
    meas = fault.apply(true_v, rate, rng, probe=None, rail_load=rail_load, poll_hz=sr)
    meas = vehicle_model.observe(meas, config.PID_VEHICLE_SPEED, rng)
    obs_m = vehicle_model.observe(true_m, config.PID_MAF_RATE, rng)

    t_d = vehicle_model.decimate(true_v, rate, sr)
    maf_d = vehicle_model.decimate(obs_m, rate, sr)
    n = min(len(meas), len(t_d), len(maf_d))
    return meas[:n] - t_d[:n], maf_d[:n]


def _probe_features(fault, seed: int) -> response.ResponseFeatures:
    rng = np.random.default_rng(seed + 100_000)
    rate = config.INTERNAL_SIM_RATE_HZ
    stim = perturbation.generate(config.MAX_PROBE_DURATION_S, rate)

    true_v = vehicle_model.generate_true_speed(config.MAX_PROBE_DURATION_S, rate, rng)
    true_m = vehicle_model.generate_true_maf(true_v, rng)
    rail_load = vehicle_model.normalised_current_draw(true_m)

    pr = config.PROBE_SAMPLE_RATE_HZ
    meas = fault.apply(true_v, rate, rng, probe=stim, rail_load=rail_load, poll_hz=pr)
    meas = vehicle_model.observe(meas, config.PID_VEHICLE_SPEED, rng)
    t_d = vehicle_model.decimate(true_v, rate, pr)
    stim_d = vehicle_model.decimate(stim, rate, pr)
    n = min(len(meas), len(t_d), len(stim_d))
    return response.extract(stim_d[:n], meas[:n] - t_d[:n], pr)


def passive_features(resid: np.ndarray, maf: np.ndarray) -> list[float]:
    """Marginal waveform stats PLUS the rail-coupling statistic.

    The coupling term — correlation between co-resident current draw and
    dropout energy — is the passive route to the same physics the probe
    interrogates. Including it is what makes this a fair comparison.
    """
    r = resid - resid.mean()
    sd = r.std()
    kurt = float((r**4).mean() / (sd**4 + 1e-12)) if sd > 1e-12 else 0.0
    ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 2 and sd > 1e-12 else 0.0
    hf = float(np.abs(np.diff(r)).mean() / (sd + 1e-12))

    env = np.abs(r)
    m = maf[: len(env)]
    coup = 0.0
    if env.std() > 1e-12 and m.std() > 1e-12:
        coup = float(np.corrcoef(env, m)[0, 1])
    return [float(sd), kurt, ac1, hf, coup]


@pytest.fixture(scope="module")
def trials():
    conn, gnd = ConnectorDropoutFault(), SharedGroundIntermittentFault()
    return {
        "passive_conn": [_passive_session(conn, s) for s in range(N_SEEDS)],
        "passive_gnd": [_passive_session(gnd, s) for s in range(N_SEEDS)],
        "probe_conn": [_probe_features(conn, s) for s in range(N_SEEDS)],
        "probe_gnd": [_probe_features(gnd, s) for s in range(N_SEEDS)],
    }


def test_footprints_are_identical():
    assert {ConnectorDropoutFault().sensor} == {SharedGroundIntermittentFault().sensor}


def test_marginal_waveform_does_not_separate(trials):
    """Same mechanism => marginal stats should NOT separate them.

    If this fails the pair is as weak as the §5.1 pair and must be abandoned.
    """
    fa = np.array([passive_features(r, m)[:4] for r, m in trials["passive_conn"]])
    fb = np.array([passive_features(r, m)[:4] for r, m in trials["passive_gnd"]])
    acc = loo_accuracy(fa, fb)
    assert acc < 0.75, f"marginal waveform separates the pair ({acc:.3f}) — pair is weak"


def test_probe_separates_the_pair(trials):
    fa = np.array([[f.signed_magnitude, f.envelope_magnitude] for f in trials["probe_conn"]])
    fb = np.array([[f.signed_magnitude, f.envelope_magnitude] for f in trials["probe_gnd"]])
    acc = loo_accuracy(fa, fb)
    assert acc >= 0.90, f"probe separation insufficient: {acc:.3f}"
