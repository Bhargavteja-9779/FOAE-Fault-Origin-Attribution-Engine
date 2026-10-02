"""Falsification tests for Claim 1 — the Tier-1 confounder gate.

Claim 1 was promoted to lead because it was untouched by the falsifications
that demoted UTP. Untested is not the same as strong. This file tests it.

Four propositions, any of which would sink it:

  F1  Tier-1 wear must actually degrade Tier-2 attribution. If attribution is
      robust to transport wear, there is nothing to gate and the claim is void.
  F2  assess_tier1_confound must detect wear THROUGH CW-AI observation noise.
      The stub is deliberately noisy so this is not circular.
  F3  Gating must reduce the misattribution rate among committed decisions at
      an acceptable coverage cost.
  F4  THE KILLER. Tier-1 information must add something a Tier-2-only
      heuristic cannot get for free. If simply abstaining when no hypothesis
      explains the observed footprint achieves the same reduction, then the
      Tier-1 mechanism is unnecessary and Claim 1 is obvious.

Scope: this models Tier-1 wear at the level of its diagnostic consequence —
common-mode corruption causing spurious anomalies across all PIDs — rather than
simulating waveforms. That is the mechanism by which transport wear confounds
attribution; the abstraction is disclosed, not hidden.
"""

from __future__ import annotations

import numpy as np
import pytest

from foae import config
from foae.evidence import cwai_stub
from foae.evidence.confound import GateAction, assess_tier1_confound, gate
from tests.test_generalization import TOPO_B, Topology
from tests.test_hybrid_claim4 import footprint_only

# Sample size: sets the precision of the rates below, not the outcome.
N_SESSIONS = 1500


def _auc(a: np.ndarray, b: np.ndarray) -> float:
    v = np.concatenate([a, b])
    r = v.argsort().argsort().astype(float) + 1.0
    u = r[: len(a)].sum() - len(a) * (len(a) + 1) / 2.0
    val = u / (len(a) * len(b))
    return max(val, 1.0 - val)


def make_sessions(topo: Topology, n: int, seed: int = 0):
    """Each session: a true Tier-2 fault plus a Tier-1 wear level."""
    rng = np.random.default_rng(seed)
    hyps = sorted(topo.hypotheses().items())
    out = []
    for _ in range(n):
        hyp_id, expected = hyps[rng.integers(len(hyps))]

        if topo.is_rail(hyp_id):
            members = sorted(expected)
            mask = rng.random(len(members)) < config.RAIL_MANIFEST_PROB
            if not mask.any():
                mask[rng.integers(len(members))] = True
            manifest = {m for m, k in zip(members, mask) if k}
        else:
            manifest = set(expected)

        wear = float(rng.random())
        # Two competing consequences of transport wear (see config.py):
        #   SPURIOUS  adds unrelated sensors -> usually breaks footprint
        #             consistency -> the free Tier-2 rule catches it
        #   SILENT    attenuates a genuine anomaly -> footprint stays
        #             consistent -> only Tier-1 information can catch it
        spurious = {
            s for s in topo.sensors
            if s not in manifest
            and rng.random() < wear * config.TIER1_SPURIOUS_ANOMALY_GAIN
        }
        masked = {
            s for s in manifest
            if rng.random() < wear * config.TIER1_SILENT_MASK_GAIN
        }
        if len(masked) == len(manifest) and manifest:
            masked.discard(sorted(masked)[0])
        observed = frozenset((manifest - masked) | spurious)

        cw = cwai_stub.generate(wear, rng)
        out.append({
            "truth": hyp_id,
            "observed": observed,
            "wear": wear,
            "confound": assess_tier1_confound(cw),
            "corrupted": len(spurious) > 0,
        })
    return out


@pytest.fixture(scope="module")
def sessions():
    return make_sessions(TOPO_B, N_SESSIONS, seed=11)


def _predict(s):
    return footprint_only(TOPO_B, s["observed"])


# ---------------------------------------------------------------------------


def test_F1_tier1_wear_degrades_attribution(sessions):
    """If attribution survives Tier-1 wear, there is nothing to gate."""
    lo = [s for s in sessions if s["wear"] < 0.25]
    hi = [s for s in sessions if s["wear"] > 0.75]
    acc_lo = np.mean([_predict(s) == s["truth"] for s in lo])
    acc_hi = np.mean([_predict(s) == s["truth"] for s in hi])
    assert acc_hi < acc_lo - 0.10, (
        f"Tier-1 wear does not meaningfully degrade attribution "
        f"(low-wear {acc_lo:.3f} vs high-wear {acc_hi:.3f}) — Claim 1 has no target"
    )


def test_F2_confound_score_detects_wear_through_noise(sessions):
    clean = np.array([s["confound"] for s in sessions if s["wear"] < 0.25])
    worn = np.array([s["confound"] for s in sessions if s["wear"] > 0.75])
    assert _auc(clean, worn) > 0.90, "confound score cannot detect Tier-1 wear"


def test_F3_gating_reduces_misattribution(sessions):
    """Among decisions actually committed, the gate must be more accurate."""
    ungated = np.mean([_predict(s) != s["truth"] for s in sessions])
    committed = [s for s in sessions if gate(s["confound"]) is not GateAction.ABSTAIN]
    gated = np.mean([_predict(s) != s["truth"] for s in committed])
    assert gated < ungated, f"gating did not reduce misattribution ({gated:.3f} vs {ungated:.3f})"


def test_F4_tier1_gate_beats_tier2_only_heuristic(sessions):
    """THE KILLER. A Tier-2-only abstention rule needs no CW-AI input at all.

    If it matches the Tier-1 gate at equal coverage, Claim 1's mechanism is
    unnecessary and an examiner will say so.
    """
    def stats(keep):
        c = [s for s in sessions if keep(s)]
        if not c:
            return 1.0, 0.0
        return float(np.mean([_predict(s) != s["truth"] for s in c])), len(c) / len(sessions)

    t1_err, t1_cov = stats(lambda s: gate(s["confound"]) is not GateAction.ABSTAIN)
    # Tier-2-only: abstain when no hypothesis explains the observation.
    t2_err, t2_cov = stats(lambda s: _predict(s) is not None)

    assert t1_err < t2_err, (
        f"Tier-2-only heuristic matches the Tier-1 gate "
        f"(err {t2_err:.3f} @ cov {t2_cov:.3f} vs Tier-1 {t1_err:.3f} @ cov {t1_cov:.3f}) "
        "— Claim 1's mechanism adds nothing"
    )
