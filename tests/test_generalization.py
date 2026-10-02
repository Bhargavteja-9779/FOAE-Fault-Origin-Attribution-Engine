"""Does footprint matching generalise across harness configurations better
than a trained waveform discriminator?

This decides whether `epdg/` is justified at all (design.md Claim 2).

The claim under test: a waveform discriminator must be TRAINED on fault
examples from a specific harness, and does not transfer when the harness
changes. Footprint matching is CONSTRUCTED from harness design data, so it
transfers by definition — it needs no examples from the target harness.

As with the identifiability tests, this is written to be falsifiable. If the
waveform discriminator transfers well to configuration B, Claim 2 is wrong.
"""

from __future__ import annotations

import numpy as np
import pytest

from foae import config
from foae.simulator import vehicle_model
from foae.simulator.faults import ConnectorDropoutFault, SharedGroundIntermittentFault

# Topologies live in tests/topologies.py, under the config audit: they ARE the
# hypothesis space, so a change to one silently changes every figure here.
# Re-exported for callers that still import them from this module.
from tests.topologies import TOPO_A, TOPO_B, Topology  # noqa: F401

# Sample sizes. These set the PRECISION of the estimates below, not the outcome
# the experiment reports, so they stay here rather than in config.py.
N_TRIALS = 20
SESSION_S = 30.0

# Moved to config.py 2026-08-05 so they fall under the config audit � these
# govern experimental outcomes and must not live in test files.
ANOMALY_STD_THRESHOLD = config.ANOMALY_DETECT_STD
MANIFEST_PROB = config.RAIL_MANIFEST_PROB

CONNECTOR_PRIOR = config.PRIOR_CONNECTOR_FAULT
RAIL_PRIOR = config.PRIOR_RAIL_FAULT


# ---------------------------------------------------------------------------
# Trial generation
# ---------------------------------------------------------------------------


def _faulted_residual(
    seed: int,
    rail_coupled: bool,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """One faulted sensor trace. Returns (residual, co-resident load).

    Routed through foae.simulator.faults — the SINGLE physics implementation.

    This function previously called intermittent.contact_gate directly, which
    bypassed faults.py and meant SHARED_GROUND_COUPLING and
    CONNECTOR_COMMON_MODE_COUPLING were never read by any Claim 2 or Claim 4
    experiment. Setting either to zero changed nothing, so sensitivity sweeps
    over them silently measured nothing (docs/validation.md §10.4).

    Do not reintroduce a local physics path here. If a variation is needed, add
    it to faults.py so every experiment sees it.
    """
    rate = config.INTERNAL_SIM_RATE_HZ
    sr = config.SAMPLE_RATE_HZ
    true = vehicle_model.generate_true_speed(SESSION_S, rate, rng)
    co = vehicle_model.generate_true_speed(SESSION_S, rate, rng)
    load = vehicle_model.normalised_current_draw(co)

    fault = SharedGroundIntermittentFault() if rail_coupled else ConnectorDropoutFault()
    meas = fault.apply(true, rate, rng, probe=None, rail_load=load, poll_hz=sr)
    meas = vehicle_model.observe(meas, config.PID_VEHICLE_SPEED, rng)

    t_d = vehicle_model.decimate(true, rate, sr)
    load_d = vehicle_model.decimate(load, rate, sr)
    n = min(len(meas), len(t_d), len(load_d))
    return meas[:n] - t_d[:n], load_d[:n]


def _waveform_features(resid: np.ndarray, load: np.ndarray) -> list[float]:
    """Config-independent waveform statistics — the same five as §5.2."""
    r = resid - resid.mean()
    sd = r.std()
    kurt = float((r**4).mean() / (sd**4 + 1e-12)) if sd > 1e-12 else 0.0
    ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 2 and sd > 1e-12 else 0.0
    hf = float(np.abs(np.diff(r)).mean() / (sd + 1e-12))
    env = np.abs(r)
    coup = 0.0
    if env.std() > 1e-12 and load.std() > 1e-12:
        coup = float(np.corrcoef(env, load[: len(env)])[0, 1])
    return [float(sd), kurt, ac1, hf, coup]


def generate_trials(topo: Topology, n_trials: int, seed0: int = 0):
    """Returns list of (hyp_id, observed_footprint, waveform_features)."""
    out = []
    hyps = topo.hypotheses()
    for hi, (hyp_id, expected) in enumerate(sorted(hyps.items())):
        for k in range(n_trials):
            rng = np.random.default_rng(seed0 + hi * 1000 + k)
            rail = topo.is_rail(hyp_id)

            if rail:
                # Partial manifestation: the fault has reached only some of the
                # rail's sensors so far. This is what creates real ambiguity.
                members = sorted(expected)
                mask = rng.random(len(members)) < MANIFEST_PROB
                if not mask.any():
                    mask[rng.integers(len(members))] = True
                manifest = frozenset(m for m, k2 in zip(members, mask) if k2)
            else:
                manifest = expected

            feats = []
            for _ in manifest:
                resid, load = _faulted_residual(0, rail, rng)
                if resid.std() > ANOMALY_STD_THRESHOLD:
                    feats.append(_waveform_features(resid, load))
            if not feats:
                continue
            out.append((hyp_id, manifest, np.array(feats).mean(axis=0)))
    return out


# ---------------------------------------------------------------------------
# Method 1 — footprint attributor: TOPOLOGY ONLY, no training data
# ---------------------------------------------------------------------------


def footprint_attribute(topo: Topology, observed: frozenset[str]) -> str | None:
    """Posterior argmax over hypotheses built from design data alone."""
    hyps = topo.hypotheses()
    n_conn = sum(1 for h in hyps if not topo.is_rail(h))
    n_rail = max(1, sum(1 for h in hyps if topo.is_rail(h)))

    best, best_p = None, -1.0
    for hyp_id, expected in hyps.items():
        if not observed <= expected:
            continue  # cannot explain a sensor outside its footprint
        prior = RAIL_PRIOR / n_rail if topo.is_rail(hyp_id) else CONNECTOR_PRIOR / n_conn
        k, m = len(observed), len(expected)
        lik = (MANIFEST_PROB**k) * ((1 - MANIFEST_PROB) ** (m - k))
        p = prior * lik
        if p > best_p:
            best, best_p = hyp_id, p
    return best


# ---------------------------------------------------------------------------
# Method 2 — waveform discriminator: TRAINED, label space is config-specific
# ---------------------------------------------------------------------------


def train_type_classifier(trials, topo: Topology):
    """Nearest-centroid on standardised features -> connector vs rail.

    Type is the ONLY label shared between configurations, so this is the most
    favourable transfer task available to the waveform approach.
    """
    x = np.array([t[2] for t in trials])
    y = np.array([int(topo.is_rail(t[0])) for t in trials])
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd[sd < 1e-12] = 1.0
    xs = (x - mu) / sd
    return {"mu": mu, "sd": sd, "c0": xs[y == 0].mean(axis=0), "c1": xs[y == 1].mean(axis=0)}


def predict_type(model, feats: np.ndarray) -> int:
    z = (feats - model["mu"]) / model["sd"]
    return int(np.linalg.norm(z - model["c1"]) < np.linalg.norm(z - model["c0"]))


def type_accuracy(model, trials, topo: Topology) -> float:
    ok = sum(predict_type(model, t[2]) == int(topo.is_rail(t[0])) for t in trials)
    return ok / len(trials)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    a = generate_trials(TOPO_A, N_TRIALS, seed0=0)
    b = generate_trials(TOPO_B, N_TRIALS, seed0=500_000)
    return a, b


def test_topologies_are_structurally_different():
    """Configuration B must not be a relabelling of A."""
    a_sig = sorted(len(v) for v in TOPO_A.rails.values())
    b_sig = sorted(len(v) for v in TOPO_B.rails.values())
    assert a_sig != b_sig, "rail cardinality profiles are identical"
    assert len(TOPO_A.sensors) != len(TOPO_B.sensors), "same sensor count"
    assert len(TOPO_A.hypotheses()) != len(TOPO_B.hypotheses())


def test_footprint_beats_chance_on_B(data):
    """Topology must be doing real work, not guessing."""
    _, b = data
    n_hyp = len(TOPO_B.hypotheses())
    acc = sum(footprint_attribute(TOPO_B, obs) == hid for hid, obs, _ in b) / len(b)
    assert acc > 3.0 / n_hyp, f"footprint {acc:.3f} not meaningfully above chance {1/n_hyp:.3f}"


def test_waveform_does_not_transfer_better_than_footprint(data):
    """Claim 2's condition. Fails loudly if the waveform approach transfers."""
    a, b = data
    model = train_type_classifier(a, TOPO_A)
    wave_b = type_accuracy(model, b, TOPO_B)
    fp_b = sum(
        TOPO_B.is_rail(footprint_attribute(TOPO_B, obs) or "") == TOPO_B.is_rail(hid)
        for hid, obs, _ in b
    ) / len(b)
    assert fp_b >= wave_b, (
        f"waveform transfer ({wave_b:.3f}) matched or beat footprint ({fp_b:.3f}) "
        "— Claim 2 is not supported"
    )
