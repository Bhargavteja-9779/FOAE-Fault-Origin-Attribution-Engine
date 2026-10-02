"""Unit tests for the OCWD physics, parsing and features (no datasets needed)."""
import numpy as np
import pandas as pd

from ocwd import physics as ph
from ocwd.loaders import _parse_canmodes_ts, _session_bounds
from ocwd.features import coherence, passive_features, poisson_slope


def test_canmodes_unpadded_ms_and_stale_seconds():
    raw = pd.Series(["57.963", "57.990", "57.3", "57.17", "58.30"])
    t = _parse_canmodes_ts(raw)
    assert np.allclose(t, [57.963, 57.990, 58.003, 58.017, 58.030])


def test_canmodes_thousands_separators():
    t = _parse_canmodes_ts(pd.Series(["1.728.720.282.150", "1.728.720.282.164"]))
    assert np.allclose(t, [1728720282.150, 1728720282.164])


def test_session_split_on_gap_and_backstep():
    t = np.r_[np.arange(0, 200, 0.1), np.arange(300, 500, 0.1)]
    b = _session_bounds(t, max_gap=5, min_dur=60)
    assert len(b) == 2


def test_interruption_rate_monotone_in_R_and_vibration():
    p = ph.ContactParams()
    v = np.ones(3)
    r = [ph.interruption_rate(R, v, p)[0] for R in (0.3, 1.5, 6, 30)]
    assert all(a < b for a, b in zip(r, r[1:]))
    assert ph.interruption_rate(6, np.array([2.0]), p)[0] == 2 * ph.interruption_rate(6, np.array([1.0]), p)[0]


def test_interruption_count_matches_poisson_mean():
    p = ph.ContactParams()
    rng = np.random.default_rng(0)
    g = np.arange(0, 1000, 0.1)
    v = np.ones(len(g))
    it = ph.sample_interruptions(g, v, 6.0, p, rng)
    expected = ph.interruption_rate(6.0, np.ones(1), p)[0] * 1000
    assert abs(len(it.start) - expected) < 5 * np.sqrt(expected)


def test_dlc_loss_only_when_overlapping():
    t = np.array([1.0, 2.0, 3.0])
    it = ph.Interruptions(np.array([1.9999]), np.array([0.001]), np.array([False]), np.array([0.0]))
    keep = ph.apply_dlc_passive(t, np.full(3, 8), it, 0.0, np.random.default_rng(0))
    assert keep.tolist() == [True, False, True]


def test_brownout_reset_silences_tool():
    t = np.arange(0, 10, 0.01)
    it = ph.Interruptions(np.array([5.0]), np.array([0.003]), np.array([True]), np.array([1.0]))
    keep = ph.apply_dlc_passive(t, np.full(len(t), 8), it, 0.0, np.random.default_rng(0))
    lost = t[~keep]
    assert lost.min() >= 5.0 and lost.max() <= 6.01 and len(lost) > 90


def test_poll_timeout_shifts_loop():
    t = np.arange(0, 10, 0.1)
    lost = np.zeros(len(t), bool)
    lost[50] = True
    empty = ph.Interruptions(np.zeros(0), np.zeros(0), np.zeros(0, bool), np.zeros(0))
    t2, keep = ph.simulate_poll(t, empty, ph.ContactParams(), np.random.default_rng(0), 0.0, extra_lost=lost)
    assert (~keep).sum() == 1
    assert np.diff(t2).max() > 0.25          # gap = period + timeout - latency


def test_poisson_slope_recovers_sign():
    rng = np.random.default_rng(1)
    x = rng.uniform(0.2, 2, 2000)
    y = rng.poisson(0.5 * x ** 1.5)
    b, z = poisson_slope(y.astype(float), np.log(x))
    assert b > 0 and z > 10
    b0, z0 = poisson_slope(rng.poisson(0.5, 2000).astype(float), np.log(x))
    assert abs(z0) < 4


def test_coherence_detects_vibration_coupled_losses():
    rng = np.random.default_rng(2)
    v = np.exp(rng.normal(0, 0.5, 300))
    assert coherence(rng.poisson(0.3 * v), v)["coh_z"] > 3
    assert abs(coherence(rng.poisson(0.3, 300), v)["coh_z"]) < 3


def test_passive_features_count_missing_frames():
    t = np.arange(0, 60, 0.01)
    cid = np.zeros(len(t), int)
    keep = np.ones(len(t), bool)
    keep[[100, 2000, 4000]] = False
    f = passive_features(t[keep], cid[keep], 0.0, 60.0)
    assert f["miss_pm"] == 3 and f["gap_events_pm"] == 3


def test_markov_model_matches_first_order_statistics():
    """Cross-model test: same mean rate and duration, different structure."""
    g = np.arange(0, 2000, 0.1)
    v = np.ones(len(g))
    q = ph.ContactParams()
    m = ph.with_params(q, process="markov")
    a = ph.sample_interruptions(g, v, 6.0, q, np.random.default_rng(0))
    b = ph.sample_interruptions(g, v, 6.0, m, np.random.default_rng(1))
    assert abs(len(b.start) / len(a.start) - 1) < 0.15
    assert abs(b.dur.mean() / a.dur.mean() - 1) < 0.15
    # bursty: inter-arrival coefficient of variation well above the Poisson value of 1
    ia = np.diff(b.start)
    assert ia.std() / ia.mean() > 1.5


def test_markov_brownout_uses_cumulative_open_time():
    m = ph.with_params(ph.ContactParams(), process="markov", p_power=1.0, d0=1e-4, holdup=1e-3)
    it = ph.sample_interruptions(np.arange(0, 200, 0.1), np.ones(2000), 15.0, m, np.random.default_rng(2))
    r = it.reset_len > 0
    assert r.any()
    assert (it.dur[r] < m.holdup).mean() > 0.5   # resets triggered by accumulation, not one long gap


def test_transformer_baseline_shapes():
    from ocwd.models import SeqTransformer
    X = np.random.default_rng(0).random((64, 3, 300)).astype("float32")
    y = np.random.default_rng(1).integers(0, 5, 64)
    P = SeqTransformer(3, 5, epochs=1).fit(X, y).proba(X[:7])
    assert P.shape == (7, 5) and np.allclose(P.sum(1), 1, atol=1e-5)
