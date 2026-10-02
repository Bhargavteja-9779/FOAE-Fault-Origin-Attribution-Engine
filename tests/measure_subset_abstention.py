"""MEASUREMENT, not a test. Cost-asymmetric re-evaluation of the strict-subset
abstention rule (validation.md §13.3, rejected there on raw accuracy).

Named ``measure_*`` so pytest does not collect it. It asserts nothing.

§13.3 judged the rule on accuracy and rejected it: 0.67 -> 0.57. But accuracy
weights a wrong answer and a decline equally, and in a workshop they are not
equal — a misattribution sends someone to replace a good part while the real
fault stays in the car, and a decline sends them to look harder. This re-runs
the same rule at large n against the number that actually matters:
MISATTRIBUTION RATE.

Design notes:

* Manifestation is GENERATIVE here. Each rail trial draws a manifest mask over
  the rail's members at ``RAIL_MANIFEST_PROB`` (forcing at least one, matching
  tests/test_generalization.py) and the fault kernel is applied only to those
  sensors. In the shipped pipeline partial manifestation emerges from detection
  physics alone; making it explicit is what allows RAIL_MANIFEST_PROB to be
  swept as a real generative parameter rather than a scoring constant.

* Simulation is cached. Residual ratios do not depend on ANOMALY_DETECT_STD, so
  each simulation pass is reused across every detection threshold. Only
  RAIL_MANIFEST_PROB forces a fresh pass.

* All fault physics still routes through simulator/faults.py. This file only
  chooses which sensors receive the fault.

Run:  python tests/measure_subset_abstention.py
"""

from __future__ import annotations

import dataclasses
import sys
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foae import config  # noqa: E402
from foae.attribution.footprint import (  # noqa: E402
    GATE_PASS,
    Tier1Assessment,
    attribute,
)
from foae.epdg.graph import build_epdg  # noqa: E402
from foae.pipeline import SCENARIOS, run_scenario  # noqa: E402
from foae.simulator import faults  # noqa: E402

SEVERITIES = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
GRID_SEVERITIES = (0.4, 0.6, 0.8, 1.0)
N_SEEDS = 20
GRID_SEEDS = 5

CLEAN_TIER1 = Tier1Assessment(gate=GATE_PASS, confound_score=0.10)


# ---------------------------------------------------------------------------
# Trial generation
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Trial:
    truth_segment: str
    kind: str                      # "rail" | "connector"
    footprint: frozenset[str]      # the truth segment's full footprint
    manifested: frozenset[str]     # sensors the fault actually reached
    ratios: dict[str, float]
    severity: float
    seed: int


def _rails() -> list[tuple[str, str, tuple[str, ...]]]:
    out = []
    for rail_id, rail in config.SHARED_RAILS.items():
        members = tuple(rail["sensors"])  # type: ignore[arg-type]
        seg = "SEG_RAIL_" + (
            rail_id[len("SENSOR_"):] if rail_id.startswith("SENSOR_") else rail_id
        )
        out.append((rail_id, seg, members))
    return out


def _connectors() -> list[tuple[str, str, str]]:
    out = []
    for pid, spec in config.SENSOR_CONNECTOR_MAP.items():
        cid = spec.get("connector_id")
        if cid is None:
            continue
        out.append((pid, str(cid), "SEG_CONN_" + str(cid)[len("C_"):]))
    return out


def simulate(manifest_prob: float, severities, n_seeds: int) -> list[Trial]:
    """One simulation pass. Returns residual ratios per trial."""
    epdg = build_epdg()
    base = next(s for s in SCENARIOS if s.id == "S1_shared_rail")
    trials: list[Trial] = []

    for rail_id, seg, members in _rails():
        for sev in severities:
            for seed in range(n_seeds):
                # zlib.crc32, NOT hash(): Python salts string hashing per
                # process, so hash() would make the manifest masks - and every
                # number in this file - different on every run.
                rng = np.random.default_rng(
                    zlib.crc32(f"{seg}|{sev}|{seed}".encode("utf-8"))
                )
                mask = rng.random(len(members)) < manifest_prob
                if not mask.any():
                    mask[rng.integers(len(members))] = True
                manifested = tuple(m for m, k in zip(members, mask) if k)

                spec = dataclasses.replace(
                    base,
                    id=f"{seg}|{sev}|{seed}",
                    fault=faults.ReferenceRailFault(
                        rail_id=rail_id, segment_id=seg, severity=sev
                    ),
                    affected=manifested,
                    truth_segment=seg,
                    severity=sev,
                )
                r = run_scenario(spec, epdg, seed=config.RANDOM_SEED + seed)
                trials.append(
                    Trial(seg, "rail", frozenset(members), frozenset(manifested),
                          dict(r.residual_ratio), sev, seed)
                )

    for pid, cid, seg in _connectors():
        for sev in severities:
            for seed in range(n_seeds):
                spec = dataclasses.replace(
                    base,
                    id=f"{seg}|{sev}|{seed}",
                    fault=faults.ConnectorDropoutFault(
                        sensor=pid, connector_id=cid, segment_id=seg, severity=sev
                    ),
                    affected=(pid,),
                    truth_segment=seg,
                    severity=sev,
                )
                r = run_scenario(spec, epdg, seed=config.RANDOM_SEED + seed)
                trials.append(
                    Trial(seg, "connector", frozenset({pid}), frozenset({pid}),
                          dict(r.residual_ratio), sev, seed)
                )
    return trials


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Outcome:
    trial: Trial
    n_clear: int
    named: str | None
    abstained: bool
    reason: str | None
    correct: bool
    wrong: bool


def evaluate(trials, detect_std: float, subset_rule: bool) -> list[Outcome]:
    epdg = build_epdg()
    sensors = {n.id for n in epdg.nodes_of_kind(__import__(
        "foae.epdg.graph", fromlist=["NodeKind"]).NodeKind.SENSOR)}
    original = config.ABSTAIN_ON_NESTED_FOOTPRINT
    config.ABSTAIN_ON_NESTED_FOOTPRINT = subset_rule
    try:
        out = []
        for t in trials:
            observed = {
                pid for pid, r in t.ratios.items()
                if pid in sensors and r > detect_std
            }
            a = attribute(observed, epdg, CLEAN_TIER1)
            correct = (not a.abstained) and a.segment_id == t.truth_segment
            wrong = (not a.abstained) and a.segment_id != t.truth_segment
            out.append(
                Outcome(t, len(observed & t.footprint), a.segment_id,
                        a.abstained, a.reason, correct, wrong)
            )
        return out
    finally:
        config.ABSTAIN_ON_NESTED_FOOTPRINT = original


def rates(outcomes) -> tuple[float, float, float, int]:
    n = len(outcomes)
    if n == 0:
        return 0.0, 0.0, 0.0, 0
    ok = sum(1 for o in outcomes if o.correct)
    ab = sum(1 for o in outcomes if o.abstained)
    wr = sum(1 for o in outcomes if o.wrong)
    return ok / n, ab / n, wr / n, n


def _line(tag, outcomes) -> None:
    ok, ab, wr, n = rates(outcomes)
    print("  %-22s n=%-5d correct=%.4f  abstain=%.4f  MISATTRIB=%.4f (%d)"
          % (tag, n, ok, ab, wr, sum(1 for o in outcomes if o.wrong)))


def report(trials, detect_std: float) -> None:
    for subset in (False, True):
        name = "BINARY + STRICT-SUBSET" if subset else "BINARY ONLY"
        res = evaluate(trials, detect_std, subset)
        print("\n  --- %s ---" % name)
        _line("ALL", res)
        _line("connector faults", [o for o in res if o.trial.kind == "connector"])
        _line("rail faults", [o for o in res if o.trial.kind == "rail"])
        print("   by sensors clearing detection (of the truth footprint):")
        for key in sorted({(o.n_clear, len(o.trial.footprint)) for o in res}):
            sub = [o for o in res
                   if (o.n_clear, len(o.trial.footprint)) == key]
            _line("   %d of %d" % key, sub)

        wrongs = [o for o in res if o.wrong]
        if subset:
            if not wrongs:
                print("   >>> ZERO misattributions at n=%d" % len(res))
            else:
                print("   >>> %d MISATTRIBUTIONS - the claim is broken:"
                      % len(wrongs))
                for o in wrongs[:8]:
                    print("       truth=%-18s named=%-18s sev=%.1f seed=%d"
                          % (o.trial.truth_segment, o.named,
                             o.trial.severity, o.trial.seed))
                    print("         manifested=%s  observed_clearing=%d"
                          % (sorted(o.trial.manifested), o.n_clear))
                    print("         ratios=%s" % {
                        k: round(v, 3) for k, v in sorted(o.trial.ratios.items())
                    })
                if len(wrongs) > 8:
                    print("       ... and %d more" % (len(wrongs) - 8))


def break_attempt(trials, detect_std: float) -> None:
    """Try to produce a misattribution under the rule.

    Everything above assumes detection never produces a FALSE POSITIVE — no
    sensor outside the true footprint is ever flagged. That assumption is not
    safe: config.TIER1_SPURIOUS_ANOMALY_GAIN exists precisely because Tier-1
    wear "makes unrelated sensors look anomalous", and its comment says this
    ADDS sensors to the observed footprint.

    The rule only fires when ``observed <= top.footprint``. A stray sensor can
    break that containment, and then nothing declines. This injects one spurious
    sensor per trial and counts what gets through.
    """
    from foae.epdg.graph import NodeKind

    epdg = build_epdg()
    sensors = sorted({n.id for n in epdg.nodes_of_kind(NodeKind.SENSOR)})
    original = config.ABSTAIN_ON_NESTED_FOOTPRINT
    config.ABSTAIN_ON_NESTED_FOOTPRINT = True
    try:
        total = 0
        wrongs = []
        for t in trials:
            base = {
                pid for pid, r in t.ratios.items()
                if pid in sensors and r > detect_std
            }
            for spur in sensors:
                if spur in t.footprint or spur in base:
                    continue
                observed = base | {spur}
                a = attribute(observed, epdg, CLEAN_TIER1)
                total += 1
                if not a.abstained and a.segment_id != t.truth_segment:
                    wrongs.append((t, spur, observed, a))
        print("  injected one spurious anomalous sensor per trial-sensor pair")
        print("  evaluated %d perturbed observations" % total)
        if not wrongs:
            print("  >>> still ZERO misattributions - the rule survives this too")
            return
        print("  >>> %d MISATTRIBUTIONS (%.4f) - THE RULE IS BREAKABLE"
              % (len(wrongs), len(wrongs) / total))
        seen = set()
        shown = 0
        for t, spur, observed, a in wrongs:
            key = (t.truth_segment, a.segment_id, spur)
            if key in seen:
                continue
            seen.add(key)
            shown += 1
            if shown > 6:
                continue
            print("     truth=%-18s named=%-18s conf=%.3f" %
                  (t.truth_segment, a.segment_id, a.confidence))
            print("       spurious sensor injected: %s" % spur)
            print("       observed=%s  (manifested=%s, sev=%.1f seed=%d)"
                  % (sorted(observed), sorted(t.manifested), t.severity, t.seed))
        print("     ... %d distinct (truth, named, spurious) combinations"
              % len(seen))
    finally:
        config.ABSTAIN_ON_NESTED_FOOTPRINT = original


def nameable_share(trials) -> None:
    epdg = build_epdg()
    fp = epdg.footprint_matrix()
    maximal = [s for s, f in fp.items()
               if not any(o != s and f < of for o, of in fp.items())]
    print("  Segments still nameable under the rule (maximal footprints):")
    for s in sorted(maximal):
        print("    %-20s footprint=%s" % (s, sorted(fp[s])))
    print("  -> %d of %d segments" % (len(maximal), len(fp)))
    counts = Counter(t.truth_segment for t in trials)
    total = sum(counts.values())
    inset = sum(v for k, v in counts.items() if k in maximal)
    print("  Share of trials whose true segment is nameable: %d/%d = %.3f"
          % (inset, total, inset / total))
    print("  (all other faults can only ever be declined, never named)")


# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 78)
    print("LARGE-N RE-EVALUATION OF THE STRICT-SUBSET ABSTENTION RULE")
    print("=" * 78)
    print("RAIL_MANIFEST_PROB=%s  ANOMALY_DETECT_STD=%s  seeds=%d  severities=%d"
          % (config.RAIL_MANIFEST_PROB, config.ANOMALY_DETECT_STD,
             N_SEEDS, len(SEVERITIES)))

    trials = simulate(config.RAIL_MANIFEST_PROB, SEVERITIES, N_SEEDS)
    n_rail = sum(1 for t in trials if t.kind == "rail")
    print("trials: %d rail + %d connector = %d total"
          % (n_rail, len(trials) - n_rail, len(trials)))

    print("\n" + "=" * 78)
    print("1-2. RATES AT THE CONFIGURED VALUES")
    print("=" * 78)
    report(trials, config.ANOMALY_DETECT_STD)

    print("\n" + "=" * 78)
    print("2b. BREAK ATTEMPT: SPURIOUS DETECTION")
    print("=" * 78)
    break_attempt(trials, config.ANOMALY_DETECT_STD)

    print("\n" + "=" * 78)
    print("3. WHAT REMAINS NAMEABLE")
    print("=" * 78)
    nameable_share(trials)

    print("\n" + "=" * 78)
    print("4. GRID: RAIL_MANIFEST_PROB x ANOMALY_DETECT_STD (strict-subset ON)")
    print("=" * 78)
    print("  manifest_p  detect_std   n      correct   abstain   MISATTRIB")
    for mp in (0.4, 0.6, 0.8):
        grid_trials = simulate(mp, GRID_SEVERITIES, GRID_SEEDS)
        for ds in (1.5, 2.0, 3.0):
            res = evaluate(grid_trials, ds, subset_rule=True)
            ok, ab, wr, n = rates(res)
            flag = "" if wr == 0 else "   <-- NON-ZERO"
            print("  %-11.1f %-12.1f %-6d %.4f    %.4f    %.4f%s"
                  % (mp, ds, n, ok, ab, wr, flag))


if __name__ == "__main__":
    main()
