"""Falsification tests for candidate Claim 4 — the hybrid attributor.

Claim 4: a transferred fault-type prior applied over a topology-derived
hypothesis space. Measured on configuration B at 0.877 overall / 0.900 on rail
faults, up from 0.425 footprint-alone, with zero target-harness training data.

Three ways this could be an artefact rather than a mechanism:

  T1  It only works on the A->B pair. A third structurally different
      configuration C should show the same gain if the mechanism is real.
  T2  It depends on the type prior being accurate. If a degraded prior makes
      the hybrid WORSE than footprint alone, the mechanism is fragile and
      unclaimable — a diagnostic system cannot rely on an input that harms it
      when wrong.
  T3  The gain is an artefact of one tuned weighting. A real mechanism should
      show gain across a broad range of prior strengths.

T2 is the most likely to break it and is the one that matters operationally.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.test_generalization import (
    CONNECTOR_PRIOR,
    MANIFEST_PROB,
    RAIL_PRIOR,
    N_TRIALS,
    generate_trials,
    predict_type,
    train_type_classifier,
)

# Topologies live in tests/topologies.py, under the config audit. C is defined
# there beside A and B so all three structural comparisons in this module's
# docstring can be checked in one place.
from tests.topologies import TOPO_A, TOPO_B, TOPO_C, Topology  # noqa: F401


def hybrid_attribute(
    topo: Topology,
    observed: frozenset[str],
    p_rail: float,
    weight: float = 0.99,
) -> str | None:
    """Footprint posterior re-weighted by a fault-type prior.

    `p_rail` in [0, 1] is P(fault is a shared-rail fault). `weight` controls how
    strongly the type prior is applied: 0.5 ignores it entirely, 1.0 makes it a
    hard restriction.
    """
    hyps = topo.hypotheses()
    n_conn = sum(1 for h in hyps if not topo.is_rail(h))
    n_rail = max(1, sum(1 for h in hyps if topo.is_rail(h)))

    best, best_p = None, -1.0
    for hyp_id, expected in hyps.items():
        if not observed <= expected:
            continue
        is_rail = topo.is_rail(hyp_id)
        prior = RAIL_PRIOR / n_rail if is_rail else CONNECTOR_PRIOR / n_conn
        k, m = len(observed), len(expected)
        lik = (MANIFEST_PROB**k) * ((1 - MANIFEST_PROB) ** (m - k))

        agree = p_rail if is_rail else (1.0 - p_rail)
        type_factor = (1.0 - weight) + (2.0 * weight - 1.0) * agree

        p = prior * lik * max(type_factor, 1e-9)
        if p > best_p:
            best, best_p = hyp_id, p
    return best


def footprint_only(topo: Topology, observed: frozenset[str]) -> str | None:
    return hybrid_attribute(topo, observed, p_rail=0.5, weight=0.5)


def _score(topo, trials, fn) -> tuple[float, float]:
    """Returns (overall accuracy, rail-trial accuracy)."""
    ok = [fn(h, o, f) == h for h, o, f in trials]
    rail = [
        fn(h, o, f) == h for h, o, f in trials if topo.is_rail(h)
    ]
    return float(np.mean(ok)), float(np.mean(rail)) if rail else float("nan")


@pytest.fixture(scope="module")
def setup():
    a = generate_trials(TOPO_A, N_TRIALS, seed0=0)
    c = generate_trials(TOPO_C, N_TRIALS, seed0=900_000)
    model = train_type_classifier(a, TOPO_A)
    return a, c, model


# ---------------------------------------------------------------------------
# T1 — does the gain reproduce on a third configuration?
# ---------------------------------------------------------------------------


def test_hybrid_gain_reproduces_on_config_C(setup):
    a, c, model = setup
    fp, fp_rail = _score(TOPO_C, c, lambda h, o, f: footprint_only(TOPO_C, o))
    hy, hy_rail = _score(
        TOPO_C, c,
        lambda h, o, f: hybrid_attribute(TOPO_C, o, float(predict_type(model, f))),
    )
    assert hy_rail > fp_rail, (
        f"no rail-fault gain on config C: footprint {fp_rail:.3f} -> hybrid {hy_rail:.3f}"
    )


# ---------------------------------------------------------------------------
# T2 — does a degraded prior make it WORSE than footprint alone?
# ---------------------------------------------------------------------------


def test_hybrid_not_worse_than_footprint_at_realistic_prior_error(setup):
    """A 20% wrong type prior is realistic. The hybrid must not underperform
    footprint-alone there, or it cannot be relied on."""
    a, c, model = setup
    rng = np.random.default_rng(0)
    fp, _ = _score(TOPO_C, c, lambda h, o, f: footprint_only(TOPO_C, o))

    def noisy(h, o, f):
        true_rail = float(TOPO_C.is_rail(h))
        p = 1.0 - true_rail if rng.random() < 0.20 else true_rail
        return hybrid_attribute(TOPO_C, o, p)

    hy, _ = _score(TOPO_C, c, noisy)
    assert hy >= fp, f"hybrid ({hy:.3f}) worse than footprint alone ({fp:.3f}) at 20% prior error"


# ---------------------------------------------------------------------------
# T3 — is the gain an artefact of one tuned weight?
# ---------------------------------------------------------------------------


def test_hybrid_gain_robust_across_prior_weights(setup):
    a, c, model = setup
    fp_rail = _score(TOPO_C, c, lambda h, o, f: footprint_only(TOPO_C, o))[1]
    gains = []
    for w in (0.6, 0.7, 0.8, 0.9, 0.99):
        r = _score(
            TOPO_C, c,
            lambda h, o, f, w=w: hybrid_attribute(
                TOPO_C, o, float(predict_type(model, f)), weight=w
            ),
        )[1]
        gains.append(r > fp_rail)
    assert all(gains), f"gain not robust across weights: {gains}"
