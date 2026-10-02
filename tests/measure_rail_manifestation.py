"""MEASUREMENT, not a test. Run it; it prints numbers and asserts nothing.

Deliberately named ``measure_*`` so pytest does not collect it. It must not
change the 12 passed / 7 failed tally, and a measurement that can "fail" invites
tuning until it passes.

Answers three questions raised by the S1 finding (validation.md §12):

  1. How does attribution accuracy vary with how many of a shared rail's sensors
     clear anomaly detection?
  2. What fraction of rail faults partially manifest under RAIL_MANIFEST_PROB?
  3. What does the ABSTAIN_ON_NESTED_FOOTPRINT prototype do to all of it?

Run:  python tests/measure_rail_manifestation.py
"""

from __future__ import annotations

import dataclasses
import sys
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foae import config  # noqa: E402
from foae.attribution.footprint import (  # noqa: E402
    REASON_NESTED_FOOTPRINT,
    Tier1Assessment,
    attribute,
)
from foae.epdg.graph import build_epdg  # noqa: E402
from foae.pipeline import SCENARIOS, run_scenario  # noqa: E402
from foae.simulator import faults  # noqa: E402

SEVERITIES = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Rails carrying more than one sensor. A single-sensor rail cannot partially
# manifest, and REF_5V_B is the S4 collision case rather than a manifestation
# case, so the interesting rails are these.
RAILS = (
    (config.RAIL_REF_5V_A, "SEG_RAIL_REF_5V_A"),
    (config.RAIL_SENSOR_GND_A, "SEG_RAIL_GND_A"),
    (config.RAIL_SENSOR_GND_B, "SEG_RAIL_GND_B"),
)


def _rail_members(rail_id: str) -> tuple[str, ...]:
    return tuple(config.SHARED_RAILS[rail_id]["sensors"])  # type: ignore[arg-type]


def sweep_severity(flag: bool = False, graded: bool = False) -> list[dict[str, object]]:
    """Run each rail at each severity and record what came out."""
    original = config.ABSTAIN_ON_NESTED_FOOTPRINT
    original_graded = config.USE_GRADED_EVIDENCE
    config.ABSTAIN_ON_NESTED_FOOTPRINT = flag
    config.USE_GRADED_EVIDENCE = graded
    try:
        base = next(s for s in SCENARIOS if s.id == "S1_shared_rail")
        epdg = build_epdg()
        rows: list[dict[str, object]] = []
        for (rail_id, segment_id), sev in product(RAILS, SEVERITIES):
            members = _rail_members(rail_id)
            spec = dataclasses.replace(
                base,
                id=f"{segment_id}@{sev}",
                fault=faults.ReferenceRailFault(
                    rail_id=rail_id, segment_id=segment_id, severity=sev
                ),
                affected=members,
                truth_segment=segment_id,
                severity=sev,
            )
            r = run_scenario(spec, epdg)
            cleared = [p for p in members if p in r.observed_anomalous]
            a = r.attribution
            rows.append(
                {
                    "segment": segment_id,
                    "m": len(members),
                    "severity": sev,
                    "n_clear": len(cleared),
                    "abstained": a.abstained,
                    "reason": a.reason,
                    "named": a.segment_id,
                    "correct": (not a.abstained) and a.segment_id == segment_id,
                }
            )
        return rows
    finally:
        config.ABSTAIN_ON_NESTED_FOOTPRINT = original
        config.USE_GRADED_EVIDENCE = original_graded


def accuracy_by_n_clear(rows: list[dict[str, object]]) -> None:
    print("  n_clear/m   trials   named-correct   abstained   wrong-segment")
    keys = sorted({(r["n_clear"], r["m"]) for r in rows})
    for n_clear, m in keys:
        sub = [r for r in rows if r["n_clear"] == n_clear and r["m"] == m]
        ok = sum(1 for r in sub if r["correct"])
        ab = sum(1 for r in sub if r["abstained"])
        wrong = len(sub) - ok - ab
        print(
            "  %d/%d         %-8d %-15s %-11s %s"
            % (n_clear, m, len(sub), f"{ok} ({ok/len(sub):.2f})", ab, wrong)
        )


def manifestation_fractions(trials: int = 200_000) -> None:
    """How often does a rail fault partially manifest at RAIL_MANIFEST_PROB?"""
    p = config.RAIL_MANIFEST_PROB
    rng = np.random.default_rng(config.RANDOM_SEED)
    print(f"  RAIL_MANIFEST_PROB = {p}")
    print("  rail                 m   P(none)  P(partial)  P(all)  P(partial|>=1)")
    for rail_id, segment_id in RAILS:
        m = len(_rail_members(rail_id))
        draws = rng.random((trials, m)) < p
        k = draws.sum(axis=1)
        p_none = float((k == 0).mean())
        p_all = float((k == m).mean())
        p_part = float(((k > 0) & (k < m)).mean())
        cond = p_part / (1 - p_none) if p_none < 1 else float("nan")
        print(
            "  %-20s %d   %.3f    %.3f       %.3f   %.3f"
            % (segment_id, m, p_none, p_part, p_all, cond)
        )
    print()
    print("  Note: tests/test_generalization.py forces at least one sensor to")
    print("  manifest, so P(partial|>=1) is the rate that experiment samples.")


def scenario_effect(flag: bool = False, graded: bool = False) -> None:
    original = config.ABSTAIN_ON_NESTED_FOOTPRINT
    original_graded = config.USE_GRADED_EVIDENCE
    config.ABSTAIN_ON_NESTED_FOOTPRINT = flag
    config.USE_GRADED_EVIDENCE = graded
    try:
        epdg = build_epdg()
        for s in SCENARIOS:
            r = run_scenario(s, epdg)
            a = r.attribution
            mark = "   " if a.abstained else (
                "ok " if a.segment_id == s.truth_segment else "BAD"
            )
            print(
                "  %s %-24s abstained=%-5s reason=%-20s named=%-20s conf=%s"
                % (
                    mark,
                    s.id,
                    a.abstained,
                    a.reason,
                    a.segment_id,
                    None if a.confidence is None else round(a.confidence, 4),
                )
            )
    finally:
        config.ABSTAIN_ON_NESTED_FOOTPRINT = original
        config.USE_GRADED_EVIDENCE = original_graded


def _tally(rows: list[dict[str, object]]) -> tuple[int, int, int]:
    ok = sum(1 for r in rows if r["correct"])
    ab = sum(1 for r in rows if r["abstained"])
    return ok, ab, len(rows) - ok - ab


def binary_vs_graded() -> None:
    """The §13.1 sweep, run both ways, broken out by sensors clearing."""
    b = sweep_severity(graded=False)
    g = sweep_severity(graded=True)
    print("  n_clear/m  trials |  BINARY ok/abst/wrong |  GRADED ok/abst/wrong")
    keys = sorted({(r["n_clear"], r["m"]) for r in b})
    for n_clear, m in keys:
        bs = [r for r in b if r["n_clear"] == n_clear and r["m"] == m]
        gs = [r for r in g if r["n_clear"] == n_clear and r["m"] == m]
        bo, ba, bw = _tally(bs)
        go, ga, gw = _tally(gs)
        print(
            "  %d/%d        %-6d |  %d / %d / %-11d |  %d / %d / %d"
            % (n_clear, m, len(bs), bo, ba, bw, go, ga, gw)
        )
    bo, ba, bw = _tally(b)
    go, ga, gw = _tally(g)
    print("  " + "-" * 68)
    print(
        "  TOTAL      %-6d |  %d / %d / %-11d |  %d / %d / %d"
        % (len(b), bo, ba, bw, go, ga, gw)
    )
    print(
        "  accuracy                %.2f                   %.2f"
        % (bo / len(b), go / len(g))
    )

    print("\n  The 1-of-2 rows in detail (where binary loses 5 and abstains 2):")
    print("  segment              sev  BINARY                GRADED")
    for rb, rg in zip(b, g):
        if not (rb["n_clear"] == 1 and rb["m"] == 2):
            continue
        vb = f"ABSTAIN/{rb['reason']}" if rb["abstained"] else f"names {rb['named']}"
        vg = f"ABSTAIN/{rg['reason']}" if rg["abstained"] else f"names {rg['named']}"
        print("  %-20s %.1f  %-21s %s" % (rb["segment"], rb["severity"], vb, vg))


def prior_sweep() -> None:
    """Does graded evidence remove the dependence on PRIOR_CONNECTOR_FAULT?"""
    epdg = build_epdg()
    s1 = next(s for s in SCENARIOS if s.id == "S1_shared_rail")
    s5 = next(s for s in SCENARIOS if s.id == "S5_rail_full_manifest")
    orig_c, orig_r = config.PRIOR_CONNECTOR_FAULT, config.PRIOR_RAIL_FAULT
    orig_g = config.USE_GRADED_EVIDENCE
    try:
        for graded in (False, True):
            config.USE_GRADED_EVIDENCE = graded
            print("\n  %s evidence:" % ("GRADED" if graded else "BINARY"))
            print("   prior_conn  S1 verdict            S1 ok  "
                  "S5 verdict            S5 ok  sweep acc")
            for pc in (0.3, 0.5, 0.7, 0.9):
                config.PRIOR_CONNECTOR_FAULT = pc
                config.PRIOR_RAIL_FAULT = 1.0 - pc
                a1 = run_scenario(s1, epdg).attribution
                a5 = run_scenario(s5, epdg).attribution
                rows = sweep_severity(graded=graded)
                ok, _, _ = _tally(rows)
                v1 = "ABSTAIN" if a1.abstained else str(a1.segment_id)
                v5 = "ABSTAIN" if a5.abstained else str(a5.segment_id)
                print(
                    "   %.1f         %-21s %-6s %-21s %-6s %.2f"
                    % (
                        pc,
                        v1,
                        "yes" if a1.segment_id == s1.truth_segment else "NO",
                        v5,
                        "yes" if a5.segment_id == s5.truth_segment else "NO",
                        ok / len(rows),
                    )
                )
    finally:
        config.PRIOR_CONNECTOR_FAULT, config.PRIOR_RAIL_FAULT = orig_c, orig_r
        config.USE_GRADED_EVIDENCE = orig_g


def width_sweep() -> None:
    """Rule 1 on GRADED_EVIDENCE_WIDTH: it is invented, so sweep it."""
    epdg = build_epdg()
    s1 = next(s for s in SCENARIOS if s.id == "S1_shared_rail")
    s5 = next(s for s in SCENARIOS if s.id == "S5_rail_full_manifest")
    orig_w, orig_g = config.GRADED_EVIDENCE_WIDTH, config.USE_GRADED_EVIDENCE
    try:
        config.USE_GRADED_EVIDENCE = True
        print("   width   S1 named               S5 named              sweep acc")
        for w in (0.1, 0.25, 0.5, 1.0, 2.0, 4.0):
            config.GRADED_EVIDENCE_WIDTH = w
            a1 = run_scenario(s1, epdg).attribution
            a5 = run_scenario(s5, epdg).attribution
            rows = sweep_severity(graded=True)
            ok, _, _ = _tally(rows)
            print(
                "   %-7.2f %-21s %-21s %.2f"
                % (
                    w,
                    "ABSTAIN" if a1.abstained else str(a1.segment_id),
                    "ABSTAIN" if a5.abstained else str(a5.segment_id),
                    ok / len(rows),
                )
            )
    finally:
        config.GRADED_EVIDENCE_WIDTH = orig_w
        config.USE_GRADED_EVIDENCE = orig_g


def main() -> None:
    print("=" * 78)
    print("1. ATTRIBUTION ACCURACY vs HOW MANY RAIL SENSORS CLEAR DETECTION")
    print("=" * 78)
    off = sweep_severity(flag=False)
    print("\n  ABSTAIN_ON_NESTED_FOOTPRINT = False (shipped default)")
    accuracy_by_n_clear(off)

    print("\n  Per-rail detail (severity -> sensors clearing -> verdict):")
    print("  segment              sev   n_clear  verdict")
    for r in off:
        verdict = (
            f"ABSTAIN/{r['reason']}" if r["abstained"] else f"names {r['named']}"
        )
        mark = "ok " if r["correct"] else ("-  " if r["abstained"] else "WRONG")
        print(
            "  %-20s %.1f   %d/%d      %s %s"
            % (r["segment"], r["severity"], r["n_clear"], r["m"], mark, verdict)
        )

    print()
    print("=" * 78)
    print("2. HOW OFTEN DOES A RAIL FAULT PARTIALLY MANIFEST?")
    print("=" * 78)
    manifestation_fractions()

    print()
    print("=" * 78)
    print("3. PROTOTYPE: ABSTAIN_ON_NESTED_FOOTPRINT")
    print("=" * 78)
    print("\n  Scenarios, flag OFF:")
    scenario_effect(flag=False)
    print("\n  Scenarios, flag ON:")
    scenario_effect(flag=True)

    on = sweep_severity(flag=True)
    print("\n  Sweep, flag ON:")
    accuracy_by_n_clear(on)

    n = len(off)
    ok_off = sum(1 for r in off if r["correct"])
    ok_on = sum(1 for r in on if r["correct"])
    ab_on = sum(1 for r in on if r["abstained"])
    nested = sum(1 for r in on if r["reason"] == REASON_NESTED_FOOTPRINT)
    print()
    print("  SUMMARY over %d rail trials:" % n)
    print("    flag OFF: %d correct (%.2f), %d abstained"
          % (ok_off, ok_off / n, sum(1 for r in off if r["abstained"])))
    print("    flag ON : %d correct (%.2f), %d abstained (%d nested_footprint)"
          % (ok_on, ok_on / n, ab_on, nested))

    print()
    print("=" * 78)
    print("4. SOFT EVIDENCE: BINARY vs GRADED (width=%s)" % config.GRADED_EVIDENCE_WIDTH)
    print("=" * 78)
    print("\n  Scenarios, BINARY:")
    scenario_effect(graded=False)
    print("\n  Scenarios, GRADED:")
    scenario_effect(graded=True)
    print()
    binary_vs_graded()

    print()
    print("=" * 78)
    print("5. DEPENDENCE ON PRIOR_CONNECTOR_FAULT")
    print("=" * 78)
    prior_sweep()

    print()
    print("=" * 78)
    print("6. RULE 1 SWEEP OF THE INVENTED GRADED_EVIDENCE_WIDTH")
    print("=" * 78)
    width_sweep()


if __name__ == "__main__":
    main()
