"""End-to-end run: simulator -> anomaly detection -> Tier-1 gate -> attribution.

docs/enablement_spec.md §3. Produces the §4 JSON export that the review
dashboard reads.

Two rules govern this module.

**All fault physics routes through ``simulator/faults.py``.** No local physics
here, not even "just a sag". A duplicated physics path is what made
``SHARED_GROUND_COUPLING`` unread for an entire investigation (handoff.md §6),
and the duplicate was correct at the default value and wrong everywhere else —
which is why it read as a flat line rather than an obvious bug. The fault
classes are used as physics kernels, instantiated with the identity of whatever
segment the scenario is about.

**``validation.experiments`` is measured, never transcribed.** Every figure in
that block is computed from the run that produced the file. An earlier revision
of the spec carried hardcoded rows that disagreed with the suite by a wide
margin. Numbers that are not measured by this run do not appear here at all —
see ``measure_experiments``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

import numpy as np

from foae import config
from foae.attribution.footprint import (
    REASON_FOOTPRINT_COLLISION,
    REASON_TIER1_CONFOUND,
    Attribution,
    Tier1Assessment,
    attribute,
    label_for_segment,
)
from foae.epdg.graph import (
    EPDG,
    PidName,
    SegmentId,
    build_epdg,
    connector_segment_id,
    rail_segment_id,
)
from foae.evidence import cwai_stub
from foae.evidence.confound import assess_tier1_confound, gate
from foae.simulator import faults, vehicle_model
from foae.types import FaultLayer

EXPORT_DIR = Path("data/runs")

# Claim status text. handoff.md §2 is the source of truth for this wording — it
# is not derived from anything this run measures, so it is quoted, not computed.
CLAIM_STATUS: tuple[dict[str, str], ...] = (
    {
        "id": "C1",
        "title": "Tier-1 confounder gate + abstention",
        "status": "UNDETERMINED",
        "note": "one bench measurement decides it",
    },
    {
        "id": "C2",
        "title": "Tier-2 footprint attribution over EPDG",
        "status": "NOT FILEABLE AS CONCEIVED",
        "note": (
            "correct for fully manifested rail faults and connector faults; "
            "a partially manifested rail fault is misattributed to a connector "
            "segment at full confidence (validation.md §12-§15)"
        ),
    },
    {
        "id": "C3",
        "title": "Diagnostic protocol as actuation channel",
        "status": "DISCRIMINATION ROBUSTLY FALSIFIED",
        "note": "only the no-extra-hardware argument survives",
    },
    {
        "id": "C4",
        "title": "Hybrid type-prior over topology",
        "status": "NOT FILEABLE",
        "note": "needs field data no bench can produce",
    },
)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioSpec:
    """One scenario. ``fault`` is a physics kernel from ``simulator/faults.py``.

    ``affected`` is which PIDs the fault physically touches — ground truth, not
    an observation. What the pipeline actually observes is whatever anomaly
    detection flags, which is allowed to disagree.
    """

    id: str
    label: str
    fault: object
    affected: tuple[PidName, ...]
    truth_segment: Optional[SegmentId]
    fault_type: str
    severity: float
    tier1_wear: float
    expect_abstain: bool
    expect_reason: Optional[str]
    # Tier-1 wear is common-mode: it degrades the transport every PID shares, so
    # the kernel is applied to all of them rather than to `affected`.
    common_mode: bool = False


def _scenarios() -> tuple[ScenarioSpec, ...]:
    return (
        ScenarioSpec(
            id="S1_shared_rail",
            label="Shared 5V rail degradation",
            fault=faults.ReferenceRailFault(
                rail_id=config.RAIL_REF_5V_A,
                segment_id="SEG_RAIL_REF_5V_A",
                severity=0.6,
            ),
            affected=(config.PID_ENGINE_RPM, config.PID_INTAKE_MAP),
            truth_segment="SEG_RAIL_REF_5V_A",
            fault_type="rail_resistance",
            severity=0.6,
            tier1_wear=0.05,
            expect_abstain=False,
            expect_reason=None,
        ),
        ScenarioSpec(
            id="S2_single_connector",
            label="Single sensor harness connector",
            fault=faults.ConnectorDropoutFault(
                sensor=config.PID_COOLANT_TEMP,
                connector_id="C_ECT",
                segment_id="SEG_CONN_ECT",
                severity=1.0,
            ),
            affected=(config.PID_COOLANT_TEMP,),
            truth_segment="SEG_CONN_ECT",
            fault_type="connector_dropout",
            severity=1.0,
            tier1_wear=0.05,
            expect_abstain=False,
            expect_reason=None,
        ),
        ScenarioSpec(
            id="S3_tier1_confound",
            label="OBD-II connector wear - common mode",
            fault=faults.ConnectorDropoutFault(
                sensor="", connector_id="J1962", segment_id="SEG_OBD_CAN_PAIR",
                severity=1.0,
            ),
            affected=config.PID_NAMES,
            truth_segment=None,
            fault_type="tier1_transport_wear",
            severity=1.0,
            tier1_wear=0.75,
            expect_abstain=True,
            expect_reason="tier1_confound",
            common_mode=True,
        ),
        # S5 sits BESIDE S1, it does not replace it. Same rail, same fault
        # kernel, severity raised until both of REF_5V_A's sensors clear
        # detection (intake_map's residual ratio crosses ANOMALY_DETECT_STD
        # between severity 0.8 and 0.9). S1 is the partially-manifested case and
        # S5 the fully-manifested one; the pair is the honest picture of what
        # footprint attribution does and does not deliver on a shared rail.
        ScenarioSpec(
            id="S5_rail_full_manifest",
            label="Shared 5V rail - fully manifested",
            fault=faults.ReferenceRailFault(
                rail_id=config.RAIL_REF_5V_A,
                segment_id="SEG_RAIL_REF_5V_A",
                severity=0.9,
            ),
            affected=(config.PID_ENGINE_RPM, config.PID_INTAKE_MAP),
            truth_segment="SEG_RAIL_REF_5V_A",
            fault_type="rail_resistance",
            severity=0.9,
            tier1_wear=0.05,
            expect_abstain=False,
            expect_reason=None,
        ),
        ScenarioSpec(
            id="S4_footprint_collision",
            label="Footprint collision - C_VSS vs REF_5V_B",
            fault=faults.ReferenceRailFault(
                rail_id=config.RAIL_REF_5V_B,
                segment_id="SEG_RAIL_REF_5V_B",
                severity=0.6,
            ),
            affected=(config.PID_VEHICLE_SPEED,),
            truth_segment="SEG_RAIL_REF_5V_B",
            fault_type="rail_resistance",
            severity=0.6,
            tier1_wear=0.05,
            expect_abstain=True,
            expect_reason="footprint_collision",
        ),
    )


SCENARIOS: tuple[ScenarioSpec, ...] = _scenarios()


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    spec: ScenarioSpec
    t_s: np.ndarray
    traces: dict[PidName, np.ndarray]
    residual_ratio: dict[PidName, float]
    onset_index: dict[PidName, Optional[int]]
    observed_anomalous: set[PidName]
    tier1: Tier1Assessment
    attribution: Attribution

    @property
    def outcome_as_expected(self) -> bool:
        a, s = self.attribution, self.spec
        if s.expect_abstain:
            return a.abstained and a.reason == s.expect_reason
        return not a.abstained and a.segment_id == s.truth_segment


# ---------------------------------------------------------------------------
# Trace generation
# ---------------------------------------------------------------------------


def _true_trace(
    pid: PidName, duration_s: float, rng: np.random.Generator
) -> np.ndarray:
    """Ground-truth trace for one PID at the internal simulation rate.

    Reuses ``vehicle_model``'s drive-cycle generator and maps it into the PID's
    nominal band. LIMITATION: every PID therefore shares one profile shape, so
    the export carries no genuine cross-PID physics beyond that. Attribution
    reads only the anomalous SET, so this does not affect any verdict here — but
    it means the traces are illustrative, not a physics claim.
    """
    base = vehicle_model.generate_true_speed(
        duration_s, config.INTERNAL_SIM_RATE_HZ, rng
    )
    lo, hi = config.PID_NOMINAL_RANGES[pid]
    span = np.ptp(base)
    if span < 1e-9:
        return np.full(len(base), (lo + hi) / 2.0)
    norm = (base - base.min()) / span
    return lo + norm * (hi - lo) * 0.6 + (hi - lo) * 0.2


def _detect(
    measured: np.ndarray, truth: np.ndarray, pid: PidName
) -> tuple[float, bool, Optional[int]]:
    """Flag a PID anomalous when its residual exceeds the noise floor.

    Returns (residual ratio, anomalous, onset index). The ratio is residual
    standard deviation in units of that PID's sensor noise, so the threshold is
    ``config.ANOMALY_DETECT_STD`` directly.
    """
    n = min(len(measured), len(truth))
    resid = measured[:n] - truth[:n]
    floor = config.SENSOR_NOISE_STD[pid]
    ratio = float(np.std(resid) / floor) if floor > 0 else 0.0
    anomalous = ratio > config.ANOMALY_DETECT_STD

    onset: Optional[int] = None
    if anomalous:
        over = np.abs(resid) > config.ANOMALY_DETECT_STD * floor
        idx = np.flatnonzero(over)
        onset = int(idx[0]) if idx.size else None
    return ratio, anomalous, onset


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: ScenarioSpec,
    epdg: Optional[EPDG] = None,
    seed: int = config.RANDOM_SEED,
) -> ScenarioResult:
    """Simulate, detect, gate, attribute. One scenario end to end."""
    if epdg is None:
        epdg = build_epdg()
    rng = np.random.default_rng(seed)

    internal = config.INTERNAL_SIM_RATE_HZ
    poll = config.SAMPLE_RATE_HZ
    duration = config.SESSION_DURATION_S

    faulted = set(scenario.affected)
    traces: dict[PidName, np.ndarray] = {}
    ratios: dict[PidName, float] = {}
    onsets: dict[PidName, Optional[int]] = {}
    observed: set[PidName] = set()

    # Co-resident current draw, for shared-ground kernels that need a load.
    load_source = _true_trace(config.PID_MAF_RATE, duration, rng)
    rail_load = vehicle_model.normalised_current_draw(load_source)

    for pid in config.PID_NAMES:
        truth = _true_trace(pid, duration, rng)
        truth_polled = vehicle_model.decimate(truth, internal, poll)

        if pid in faulted:
            measured = scenario.fault.apply(  # type: ignore[attr-defined]
                truth, internal, rng, rail_load=rail_load, poll_hz=poll
            )
        else:
            measured = truth_polled
        measured = vehicle_model.observe(measured, pid, rng)

        ratio, anomalous, onset = _detect(measured, truth_polled, pid)
        traces[pid] = measured
        ratios[pid] = ratio
        onsets[pid] = onset
        if anomalous:
            observed.add(pid)

    # Tier-1 evidence, through the real confound path.
    cwai = cwai_stub.generate(scenario.tier1_wear, rng)
    score = assess_tier1_confound(cwai)
    tier1 = Tier1Assessment.from_gate_action(
        gate(score),
        confound_score=score,
        cmv_anomalous=config.PID_CONTROL_MODULE_VOLTAGE in observed,
    )

    n = min(len(v) for v in traces.values())
    t_s = np.arange(n) / poll

    return ScenarioResult(
        spec=scenario,
        t_s=t_s,
        traces={k: v[:n] for k, v in traces.items()},
        residual_ratio=ratios,
        onset_index=onsets,
        observed_anomalous=observed,
        tier1=tier1,
        # Ratios are passed regardless of which path is active; attribute()
        # ignores them unless config.USE_GRADED_EVIDENCE is on. Thresholding
        # before attribution is what §12 identified as the failure, so the
        # unthresholded evidence is kept available all the way through.
        attribution=attribute(observed, epdg, tier1, residual_ratios=ratios),
    )


def run_all(
    epdg: Optional[EPDG] = None, seed: int = config.RANDOM_SEED
) -> list[ScenarioResult]:
    if epdg is None:
        epdg = build_epdg()
    return [run_scenario(s, epdg, seed) for s in SCENARIOS]


# ---------------------------------------------------------------------------
# Measured validation figures
# ---------------------------------------------------------------------------


def measure_experiments(
    results: list[ScenarioResult], epdg: Optional[EPDG] = None
) -> list[dict[str, object]]:
    """Compute every ``validation.experiments`` row from THIS run.

    Nothing here is quoted from a document. Experiments this pipeline does not
    actually perform — the identifiability pairs, the cross-harness transfer —
    are absent rather than transcribed: they live in the test suite, and a
    number this run did not measure is a number this run cannot defend.
    """
    if epdg is None:
        epdg = build_epdg()

    n_segments = len(epdg.segments())
    chance = 1.0 / n_segments if n_segments else 0.0

    attributed = [r for r in results if not r.attribution.abstained]
    correct = [
        r for r in attributed
        if r.attribution.segment_id == r.spec.truth_segment
    ]
    abstained = [r for r in results if r.attribution.abstained]
    as_expected = [r for r in results if r.outcome_as_expected]

    rows: list[dict[str, object]] = [
        {
            "name": "Footprint attribution accuracy vs chance",
            "measured": (len(correct) / len(attributed)) if attributed else None,
            "baseline": round(chance, 4),
            "n": len(attributed),
            "note": (
                f"{len(correct)}/{len(attributed)} non-abstaining scenarios "
                f"named the ground-truth segment; chance is 1/{n_segments} over "
                "the topology-derived hypothesis space"
            ),
        },
        {
            "name": "Outcome matches expectation (incl. abstentions)",
            "measured": len(as_expected) / len(results) if results else None,
            "baseline": None,
            "n": len(results),
            "note": (
                f"{len(as_expected)}/{len(results)} scenarios produced the "
                "expected verdict, counting a correct abstention as correct"
            ),
        },
        {
            "name": "Abstention rate",
            "measured": len(abstained) / len(results) if results else None,
            "baseline": None,
            "n": len(results),
            "note": "; ".join(
                f"{r.spec.id}:{r.attribution.reason}" for r in abstained
            ) or "no abstentions",
        },
    ]

    gate_row = _measure_gate_contrast(results, epdg)
    if gate_row is not None:
        rows.append(gate_row)
    return rows


def _measure_gate_contrast(
    results: list[ScenarioResult], epdg: EPDG
) -> Optional[dict[str, object]]:
    """What the Tier-1 gate prevented, measured by re-running without it.

    Recorded in validation.md §11. This is the only Claim 1 figure that does not
    rest on TIER1_SPURIOUS_ANOMALY_GAIN, which currently sits ~14x above its
    break-even range.
    """
    tripped = [r for r in results if r.tier1.tripped]
    if not tripped:
        return None
    r = tripped[0]

    ungated = attribute(
        r.observed_anomalous,
        epdg,
        Tier1Assessment(gate="PASS", confound_score=r.tier1.confound_score),
    )
    margin = None
    if len(ungated.candidates) >= 2:
        margin = round(
            ungated.candidates[0].match_score - ungated.candidates[1].match_score, 4
        )
    return {
        "name": f"Tier-1 gate contrast ({r.spec.id})",
        "measured": ungated.confidence,
        "baseline": None,
        "n": 1,
        "note": (
            f"with the gate disabled the attributor names "
            f"{ungated.segment_id} at {ungated.confidence}, top-2 margin "
            f"{margin} (> TIER2_AMBIGUOUS_MARGIN {config.TIER2_AMBIGUOUS_MARGIN}, "
            "so the collision abstention does not fire either); gated outcome "
            f"is ABSTAIN/{r.attribution.reason}"
        ),
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _config_hash() -> str:
    data = Path(config.__file__).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _git_commit() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _topology_json(epdg: EPDG) -> dict[str, object]:
    return {
        "nodes": [
            {"id": n.id, "label": n.label, "kind": n.kind.value} for n in epdg.nodes
        ],
        "edges": [
            {"from": e.source, "to": e.target, "rail": e.rail} for e in epdg.edges
        ],
    }


def _scenario_json(r: ScenarioResult) -> dict[str, object]:
    a, s = r.attribution, r.spec
    return {
        "id": s.id,
        "label": s.label,
        "ground_truth": {
            "origin_layer": FaultLayer.PHYSICAL.value,
            "segment_id": s.truth_segment,
            "fault_type": s.fault_type,
            "severity": s.severity,
        },
        "traces": {
            "t_s": [round(float(t), 3) for t in r.t_s],
            "pids": {
                pid: {
                    "values": [round(float(v), 3) for v in vals],
                    "nominal": list(config.PID_NOMINAL_RANGES[pid]),
                    "anomalous_from_index": r.onset_index[pid],
                }
                for pid, vals in r.traces.items()
            },
        },
        "tier1": {
            "confound_score": round(r.tier1.confound_score, 4),
            "threshold": r.tier1.threshold,
            "gate": r.tier1.gate,
            "cmv_anomalous": r.tier1.cmv_anomalous,
        },
        "observed_anomalous": sorted(r.observed_anomalous),
        "candidates": [
            {
                "segment_id": c.segment_id,
                "label": c.label,
                "match_score": round(c.match_score, 4),
                "footprint": sorted(c.footprint),
            }
            for c in a.candidates
        ],
        "verdict": {
            "origin_layer": a.origin_layer,
            "segment_id": a.segment_id,
            "confidence": None if a.confidence is None else round(a.confidence, 4),
            "abstained": a.abstained,
            "reason": a.reason,
            "correct": None if a.abstained else a.segment_id == s.truth_segment,
        },
    }


def build_export(
    results: list[ScenarioResult],
    epdg: Optional[EPDG] = None,
    seed: int = config.RANDOM_SEED,
    run_id: Optional[str] = None,
) -> dict[str, object]:
    if epdg is None:
        epdg = build_epdg()
    now = datetime.now(timezone.utc)
    run_id = run_id or f"foae-{now:%Y-%m-%d}-{seed}"

    return {
        "meta": {
            "run_id": run_id,
            "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "harness_id": epdg.topology.name,
            "evidence_basis": "simulation",
            "hardware_validated": False,
            "seed": seed,
            "config_hash": _config_hash(),
            "commit": _git_commit(),
        },
        "topology": _topology_json(epdg),
        "scenarios": [_scenario_json(r) for r in results],
        "validation": {
            "claims": [dict(c) for c in CLAIM_STATUS],
            "experiments": measure_experiments(results, epdg),
            "experiments_note": (
                "Every row above was measured by the run that produced this "
                "file. Identifiability, nesting and cross-harness transfer "
                "figures are NOT here: this pipeline does not perform those "
                "experiments, they live in the test suite, and transcribing "
                "them would put undefended numbers in an export."
            ),
        },
    }


def export_run(
    results: list[ScenarioResult],
    path: str | Path,
    payload: Optional[dict[str, object]] = None,
) -> None:
    """Serialise to the §4 JSON contract. UTF-8, always.

    ``payload`` lets a caller that has ALREADY built the export hand it in, so
    the bytes on disk and anything derived from the payload — a filename, a
    logged run_id — come from one object.

    Without it this function rebuilt the export from scratch, stamping a second
    ``generated_utc`` and, across a midnight boundary, a second ``run_id``. The
    caller in ``main`` derives the filename from its own payload, so a file
    could be named for one run and contain another. Nothing downstream checked
    the two agreed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = build_export(results)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Randomised demo runs (docs/demo/foae_live_demo.html)
# ---------------------------------------------------------------------------
#
# The browser demo replays REAL engine output. Every verdict in demo_runs.json
# is produced by run_scenario() -> attribute() exactly as the main export is;
# the HTML only renders. Nothing about attribution is reimplemented in JS,
# because a second implementation would drift from this one and nothing would
# tell us (handoff.md §6).

DEMO_OUT = Path("docs/demo/demo_runs.json")

# Trace points kept per PID in the demo file. A full session is 1200 samples
# per PID; at ~24 scenarios that inlines to several MB of HTML for a sparkline
# 180px wide. Values are real, just decimated for transport.
DEMO_TRACE_POINTS: Final[int] = 120


def _demo_fault_pool() -> tuple[dict[str, object], ...]:
    """Every fault location the demo can inject, built from config topology.

    Locations are derived from SHARED_RAILS and SENSOR_CONNECTOR_MAP rather
    than listed by hand, so a topology change reaches the demo automatically
    instead of silently leaving it describing the old harness.
    """
    pool: list[dict[str, object]] = []

    for rail_id, rail in config.SHARED_RAILS.items():
        members = tuple(rail["sensors"])  # type: ignore[arg-type]
        seg = rail_segment_id(rail_id)
        is_reference = rail["kind"] == config.RAIL_KIND_REFERENCE
        # A reference rail is a resistive divider; a sensor ground fretting is
        # intermittent. Both kernels come from simulator/faults.py - no local
        # physics here, ever (handoff.md §6).
        if is_reference:
            def make(sev: float, _r: str = rail_id, _s: str = seg) -> object:
                return faults.ReferenceRailFault(
                    rail_id=_r, segment_id=_s, severity=sev
                )
        else:
            def make(sev: float, _r: str = rail_id, _s: str = seg) -> object:
                return faults.SharedGroundIntermittentFault(
                    rail_id=_r, segment_id=_s, severity=sev
                )
        pool.append({
            "kind": "rail",
            "segment_id": seg,
            "label": f"{label_for_segment(seg)} degradation",
            "affected": members,
            "fault_type": "rail_resistance" if is_reference else "rail_intermittent",
            "make": make,
        })

    for pid in config.PID_NAMES:
        spec = config.SENSOR_CONNECTOR_MAP.get(pid)
        if spec is None or spec.get("connector_id") is None:
            continue
        conn = str(spec["connector_id"])
        seg = connector_segment_id(conn)

        def make_conn(
            sev: float, _p: str = pid, _c: str = conn, _s: str = seg
        ) -> object:
            return faults.ConnectorDropoutFault(
                sensor=_p, connector_id=_c, segment_id=_s, severity=sev
            )

        pool.append({
            "kind": "connector",
            "segment_id": seg,
            "label": f"{label_for_segment(seg)} fretting",
            "affected": (pid,),
            "fault_type": "connector_dropout",
            "make": make_conn,
        })

    # Tier 1. Common-mode transport wear: every PID moves, including
    # control_module_voltage, which has no Tier-2 connector. The gate trips and
    # the system declines. That is the Claim 1 story and it stays in the demo.
    def make_tier1(sev: float) -> object:
        return faults.ConnectorDropoutFault(
            sensor="", connector_id="J1962", segment_id="SEG_OBD_CAN_PAIR",
            severity=sev,
        )

    pool.append({
        "kind": "tier1",
        "segment_id": None,
        "label": "OBD-II transport wear - common mode",
        "affected": config.PID_NAMES,
        "fault_type": "tier1_transport_wear",
        "make": make_tier1,
    })
    return tuple(pool)


# Severities tried per location, strongest first. A rail fault must be severe
# enough that EVERY sensor on the rail clears detection - a partially
# manifested rail is the validation.md section 12 failure, and the demo
# excludes it BY MEASUREMENT below rather than by assuming a severity suffices.
_DEMO_SEVERITIES: Final[tuple[float, ...]] = (1.0, 0.95, 0.9)


def _demo_spec(entry: dict[str, object], severity: float) -> ScenarioSpec:
    is_tier1 = entry["kind"] == "tier1"
    seg = entry["segment_id"]
    return ScenarioSpec(
        id=str(seg or "SEG_OBD_CAN_PAIR"),
        label=str(entry["label"]),
        fault=entry["make"](severity),  # type: ignore[operator]
        affected=tuple(entry["affected"]),  # type: ignore[arg-type]
        truth_segment=None if is_tier1 else str(seg),
        fault_type=str(entry["fault_type"]),
        severity=severity,
        tier1_wear=0.75 if is_tier1 else 0.05,
        expect_abstain=is_tier1,
        expect_reason=REASON_TIER1_CONFOUND if is_tier1 else None,
        common_mode=is_tier1,
    )


def _demo_acceptable(r: ScenarioResult, entry: dict[str, object]) -> bool:
    """Is this sample fit for a CLEAN demo?

    Accepted:
      * a correct named segment;
      * ABSTAIN/tier1_confound on a Tier-1 fault - the system declining;
      * ABSTAIN/footprint_collision - a property of the WIRING (REF_5V_B
        carries only vehicle_speed, so a fault on that rail and a fault in the
        VSS connector are indistinguishable). Not a mistake, and worth showing.

    Rejected: a wrong named segment. In this harness that means a partially
    manifested rail (validation.md section 12). Excluding it is a demo-staging
    decision, recorded in meta.selection of the generated file so the exclusion
    travels with the data instead of living only in this docstring.
    """
    a = r.attribution
    if entry["kind"] == "tier1":
        return a.abstained and a.reason == REASON_TIER1_CONFOUND
    if a.abstained:
        return a.reason == REASON_FOOTPRINT_COLLISION
    return a.segment_id == r.spec.truth_segment


def _reject_reason(r: ScenarioResult) -> str:
    a = r.attribution
    if a.abstained:
        return f"abstain/{a.reason}"
    return f"named {a.segment_id} (truth {r.spec.truth_segment})"


def _decimate_scenario_traces(sc: dict[str, object], points: int) -> None:
    """Thin traces in place. Real values, fewer of them."""
    traces = sc["traces"]  # type: ignore[index]
    t = traces["t_s"]  # type: ignore[index]
    n = len(t)
    if n <= points:
        return
    step = n / points
    keep = sorted({min(n - 1, int(i * step)) for i in range(points)})
    index = {k: i for i, k in enumerate(keep)}
    traces["t_s"] = [t[i] for i in keep]  # type: ignore[index]
    for _pid, block in traces["pids"].items():  # type: ignore[index]
        block["values"] = [block["values"][i] for i in keep]
        onset = block.get("anomalous_from_index")
        if onset is None:
            block["anomalous_from_index"] = None
        else:
            # Map to the nearest kept sample at or after the original onset.
            after = [k for k in keep if k >= onset]
            block["anomalous_from_index"] = index[after[0]] if after else None


def generate_demo_runs(
    count: int = 24, seed: int = config.RANDOM_SEED
) -> dict[str, object]:
    """Run `count` randomly chosen faults through the real engine.

    Locations are sampled without replacement within each pass over the pool,
    so a small count still covers a spread of segments rather than repeating
    one. Every entry that survives ``_demo_acceptable`` is real engine output.
    """
    epdg = build_epdg()
    pool = _demo_fault_pool()
    rng = np.random.default_rng(seed)

    accepted: list[ScenarioResult] = []
    rejected: list[tuple[str, str]] = []
    attempts = 0
    max_attempts = count * 12
    order: list[int] = []

    while len(accepted) < count and attempts < max_attempts:
        if not order:
            order = [int(i) for i in rng.permutation(len(pool))]
        entry = pool[order.pop()]

        for severity in _DEMO_SEVERITIES:
            attempts += 1
            spec = _demo_spec(entry, severity)
            run_seed = int(rng.integers(1, 2 ** 31 - 1))
            r = run_scenario(spec, epdg, seed=run_seed)
            if _demo_acceptable(r, entry):
                accepted.append(r)
                break
            rejected.append((spec.id, _reject_reason(r)))

    payload = build_export(accepted, epdg, seed=seed, run_id=f"foae-demo-{seed}")
    for sc in payload["scenarios"]:  # type: ignore[index]
        _decimate_scenario_traces(sc, DEMO_TRACE_POINTS)

    meta = payload["meta"]  # type: ignore[index]
    meta["kind"] = "randomised-demo"
    meta["scenario_count"] = len(accepted)
    meta["trace_points"] = DEMO_TRACE_POINTS
    meta["trace_note"] = (
        f"Traces are decimated to {DEMO_TRACE_POINTS} points for transport. "
        "Values are real engine output; every verdict was computed on the "
        "full-rate traces before decimation."
    )
    meta["selection"] = (
        "CLEAN DEMO SET. Faults were sampled at random from the config "
        "topology and run through the real simulator and attributor. Samples "
        "whose verdict named the WRONG segment were discarded and resampled at "
        "a higher severity; in this harness those are partially manifested "
        "rail faults, the open failure recorded in validation.md sections "
        "12-15. Abstentions are NOT filtered: Tier-1 gate trips and footprint "
        "collisions are kept, because a system that declines when it cannot "
        "answer is part of what this demonstrates. This file therefore shows "
        "the engine working as designed, NOT a representative error rate."
    )
    meta["rejected_samples"] = len(rejected)
    return payload


def write_demo_runs(
    count: int = 24, seed: int = config.RANDOM_SEED, out: Path = DEMO_OUT
) -> Path:
    payload = generate_demo_runs(count, seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> Path:
    """Default: the five-scenario export. ``demo``: randomised demo runs."""
    parser = argparse.ArgumentParser(prog="python -m foae.pipeline")
    sub = parser.add_subparsers(dest="command")

    d = sub.add_parser("demo", help="generate randomised runs for the browser demo")
    d.add_argument("-n", "--count", type=int, default=24,
                   help="scenarios to generate (default 24)")
    d.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                   help=f"master seed (default {config.RANDOM_SEED})")
    d.add_argument("-o", "--out", type=Path, default=DEMO_OUT,
                   help=f"output path (default {DEMO_OUT})")

    args = parser.parse_args(argv)

    if args.command == "demo":
        return write_demo_runs(args.count, args.seed, args.out)

    epdg = build_epdg()
    results = run_all(epdg)
    # Build ONCE. The filename and the file contents must come from the same
    # payload; see export_run's docstring for what happens when they do not.
    payload = build_export(results, epdg)
    out = EXPORT_DIR / f"{payload['meta']['run_id']}.json"  # type: ignore[index]
    export_run(results, out, payload=payload)
    return out


if __name__ == "__main__":
    print(main())
