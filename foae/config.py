"""Single source of truth for every constant, threshold, and hyperparameter.

No magic numbers may appear anywhere else in the codebase. If a module needs a
number, it is defined here and imported.

Group order follows FOAE_Project_Structure.md section 7.

Values marked ``PROVISIONAL`` were not recoverable from any spec document and
are placeholders chosen to be physically plausible. They must be reviewed
against docs/design.md before any validation run whose numbers reach the IDF.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Vehicle model
# ---------------------------------------------------------------------------

SAMPLE_RATE_HZ: Final[float] = 10.0
SESSION_DURATION_S: Final[float] = 120.0
NUM_PIDS: Final[int] = 6

SAMPLES_PER_SESSION: Final[int] = int(SAMPLE_RATE_HZ * SESSION_DURATION_S)

# Internal simulation rate. Contact bounce at INTERMITTENT_CONTACT_BOUNCE_HZ
# (15 Hz) is above the Nyquist limit of the 10 Hz logging rate, so the physics
# is simulated here and decimated. The resulting aliasing is real — a real
# tester sampling at 10 Hz sees bounce folded down as low-frequency noise.
INTERNAL_SIM_RATE_HZ: Final[float] = 200.0

# During an active probe the tester focuses on the target PID and polls it far
# faster than the background logging rate. This sets the lag resolution
# available to response.compute(). PROVISIONAL.
PROBE_SAMPLE_RATE_HZ: Final[float] = 100.0

# The six OBD-II PIDs the simulator emits, in column order. 0x42 is required by
# the bench ECU simulator (see FOAE_Project_Structure.md, bench/firmware).
PID_ENGINE_RPM: Final[str] = "engine_rpm"                          # 0x0C
PID_VEHICLE_SPEED: Final[str] = "vehicle_speed"                    # 0x0D
PID_COOLANT_TEMP: Final[str] = "coolant_temp"                      # 0x05
PID_INTAKE_MAP: Final[str] = "intake_map"                          # 0x0B
PID_MAF_RATE: Final[str] = "maf_rate"                              # 0x10
PID_CONTROL_MODULE_VOLTAGE: Final[str] = "control_module_voltage"  # 0x42

PID_NAMES: Final[tuple[str, ...]] = (
    PID_ENGINE_RPM,
    PID_VEHICLE_SPEED,
    PID_COOLANT_TEMP,
    PID_INTAKE_MAP,
    PID_MAF_RATE,
    PID_CONTROL_MODULE_VOLTAGE,
)

PID_CODES: Final[dict[str, int]] = {
    PID_ENGINE_RPM: 0x0C,
    PID_VEHICLE_SPEED: 0x0D,
    PID_COOLANT_TEMP: 0x05,
    PID_INTAKE_MAP: 0x0B,
    PID_MAF_RATE: 0x10,
    PID_CONTROL_MODULE_VOLTAGE: 0x42,
}

# Nominal operating ranges, used by the simulator to bound generated traces and
# by plausibility.py to flag out-of-range values. PROVISIONAL.
PID_NOMINAL_RANGES: Final[dict[str, tuple[float, float]]] = {
    PID_ENGINE_RPM: (600.0, 6000.0),
    PID_VEHICLE_SPEED: (0.0, 160.0),
    PID_COOLANT_TEMP: (-40.0, 120.0),
    PID_INTAKE_MAP: (20.0, 255.0),
    PID_MAF_RATE: (0.0, 300.0),
    PID_CONTROL_MODULE_VOLTAGE: (11.0, 14.8),
}

# PROVISIONAL: per-PID Gaussian measurement noise, in each PID's native units.
SENSOR_NOISE_STD: Final[dict[str, float]] = {
    PID_ENGINE_RPM: 12.0,
    PID_VEHICLE_SPEED: 0.3,
    PID_COOLANT_TEMP: 0.15,
    PID_INTAKE_MAP: 1.2,
    PID_MAF_RATE: 0.8,
    PID_CONTROL_MODULE_VOLTAGE: 0.02,
}

# ---------------------------------------------------------------------------
# Pin assignments — TIER 1: SAE J1962 OBD-II connector
# ---------------------------------------------------------------------------
#
# Tier 1 is the diagnostic transport. Every PID reaches the tester over the same
# CAN pair, so wear at this connector degrades ALL PIDs together and carries no
# per-sensor attribution signal. This is CW-AI's domain.

NUM_PINS: Final[int] = 16  # fixes CWAIOutput.per_pin_error_vector shape (16,)

PIN_CHASSIS_GROUND: Final[int] = 4
PIN_SIGNAL_GROUND: Final[int] = 5
PIN_CAN_HIGH: Final[int] = 6
PIN_CAN_LOW: Final[int] = 14
PIN_BATTERY_POWER: Final[int] = 16

PIN_ASSIGNMENTS: Final[dict[int, str]] = {
    1: "manufacturer_discretionary",
    2: "j1850_bus_positive",
    3: "manufacturer_discretionary",
    PIN_CHASSIS_GROUND: "chassis_ground",
    PIN_SIGNAL_GROUND: "signal_ground",
    PIN_CAN_HIGH: "can_high",
    7: "iso9141_k_line",
    8: "manufacturer_discretionary",
    9: "manufacturer_discretionary",
    10: "j1850_bus_negative",
    11: "manufacturer_discretionary",
    12: "manufacturer_discretionary",
    13: "manufacturer_discretionary",
    PIN_CAN_LOW: "can_low",
    15: "iso9141_l_line",
    PIN_BATTERY_POWER: "battery_power",
}

# ---------------------------------------------------------------------------
# Harness topology — two tiers
# ---------------------------------------------------------------------------
#
# TIER 1 (SENSOR_PIN_MAP): the J1962 diagnostic transport. All PIDs traverse the
#   same CAN pair, so wear here is common-mode — it degrades every PID at once.
#   Diagnostically it answers "is the OBD-II link healthy", not "which sensor".
#
# TIER 2 (SENSOR_CONNECTOR_MAP): the in-vehicle sensor harness. Each sensor has
#   its own connector with its own signal / ground / reference pins. Wear here
#   is specific to one sensor's signal path — this is what carries attribution
#   signal, and it is what FOAE's EPDG primarily operates on.
#
# SHARED_RAILS couples the tiers' Tier-2 half: several sensors share one sensor
# ground or one 5V reference, so a degraded rail moves a GROUP of sensors
# together while leaving others untouched. That contrast — coupled group vs.
# independent sensor — is the discriminating structure the EPDG exploits.
#
# Both maps are PROVISIONAL pending bench-rig confirmation (docs/bench_setup.md).

# --- Tier 1 -----------------------------------------------------------------

# Which J1962 pins each PID's transport path depends on. Identical for every
# PID by construction: they share the bus. PROVISIONAL.
_OBD_TRANSPORT_PINS: Final[tuple[int, ...]] = (
    PIN_CHASSIS_GROUND,
    PIN_SIGNAL_GROUND,
    PIN_CAN_HIGH,
    PIN_CAN_LOW,
    PIN_BATTERY_POWER,
)

SENSOR_PIN_MAP: Final[dict[str, tuple[int, ...]]] = {
    pid: _OBD_TRANSPORT_PINS for pid in PID_NAMES
}

# --- Tier 2 -----------------------------------------------------------------

# Rail identifiers. Sensors sharing a rail are electrically coupled.
RAIL_REF_5V_A: Final[str] = "REF_5V_A"
RAIL_REF_5V_B: Final[str] = "REF_5V_B"
RAIL_SENSOR_GND_A: Final[str] = "SENSOR_GND_A"
RAIL_SENSOR_GND_B: Final[str] = "SENSOR_GND_B"

RAIL_KIND_REFERENCE: Final[str] = "reference"
RAIL_KIND_GROUND: Final[str] = "ground"

# Per-sensor harness connectors. Pin numbers are local to each connector, not
# J1962 pins. `reference_pin`/`reference_rail` are None for sensors that carry
# no 5V reference (2-wire thermistors, battery-powered hot-wire MAF).
#
# PROVISIONAL — pin counts and rail grouping must be confirmed against the
# bench rig. The coupling structure is the part that matters: MAP+CKP share
# REF_5V_A, MAP+ECT+CKP share SENSOR_GND_A, VSS+MAF share SENSOR_GND_B, and
# MAF is reference-independent. So a REF_5V_A fault moves exactly two sensors
# and a SENSOR_GND_B fault moves a different, disjoint two.
SENSOR_CONNECTOR_MAP: Final[dict[str, dict[str, object]]] = {
    PID_ENGINE_RPM: {
        "connector_id": "C_CKP",            # crankshaft position, 3-wire Hall
        "pin_count": 3,
        "signal_pin": 1,
        "ground_pin": 2,
        "reference_pin": 3,
        "ground_rail": RAIL_SENSOR_GND_A,
        "reference_rail": RAIL_REF_5V_A,
    },
    PID_INTAKE_MAP: {
        "connector_id": "C_MAP",            # manifold absolute pressure, 3-wire
        "pin_count": 3,
        "signal_pin": 2,
        "ground_pin": 1,
        "reference_pin": 3,
        "ground_rail": RAIL_SENSOR_GND_A,
        "reference_rail": RAIL_REF_5V_A,
    },
    PID_COOLANT_TEMP: {
        "connector_id": "C_ECT",            # 2-wire thermistor, ECU pull-up
        "pin_count": 2,
        "signal_pin": 1,
        "ground_pin": 2,
        "reference_pin": None,
        "ground_rail": RAIL_SENSOR_GND_A,
        "reference_rail": None,
    },
    PID_VEHICLE_SPEED: {
        "connector_id": "C_VSS",            # vehicle speed, 3-wire Hall
        "pin_count": 3,
        "signal_pin": 1,
        "ground_pin": 2,
        "reference_pin": 3,
        "ground_rail": RAIL_SENSOR_GND_B,
        "reference_rail": RAIL_REF_5V_B,
    },
    PID_MAF_RATE: {
        "connector_id": "C_MAF",            # hot-wire MAF, battery-fed
        "pin_count": 4,
        "signal_pin": 3,
        "ground_pin": 1,
        "reference_pin": None,
        "ground_rail": RAIL_SENSOR_GND_B,
        "reference_rail": None,
    },
    # control_module_voltage is the ECU's own supply measurement, not a sensor
    # on the harness. It has no Tier-2 connector: it is observable only through
    # the Tier-1 power path, which makes it the PID that discriminates an
    # OBD-II/power fault from any sensor-harness fault.
    PID_CONTROL_MODULE_VOLTAGE: {
        "connector_id": None,
        "pin_count": 0,
        "signal_pin": None,
        "ground_pin": None,
        "reference_pin": None,
        "ground_rail": None,
        "reference_rail": None,
    },
}

# Rail membership. PROVISIONAL.
SHARED_RAILS: Final[dict[str, dict[str, object]]] = {
    RAIL_REF_5V_A: {
        "kind": RAIL_KIND_REFERENCE,
        "nominal_v": 5.0,
        "sensors": (PID_ENGINE_RPM, PID_INTAKE_MAP),
    },
    RAIL_REF_5V_B: {
        "kind": RAIL_KIND_REFERENCE,
        "nominal_v": 5.0,
        "sensors": (PID_VEHICLE_SPEED,),
    },
    RAIL_SENSOR_GND_A: {
        "kind": RAIL_KIND_GROUND,
        "nominal_v": 0.0,
        "sensors": (PID_ENGINE_RPM, PID_INTAKE_MAP, PID_COOLANT_TEMP),
    },
    RAIL_SENSOR_GND_B: {
        "kind": RAIL_KIND_GROUND,
        "nominal_v": 0.0,
        "sensors": (PID_VEHICLE_SPEED, PID_MAF_RATE),
    },
}

# Named harness segments, used as ProbeSignature.segment_id values. Segments
# now span both tiers: SEG_OBD_* are Tier 1, SEG_CONN_*/SEG_RAIL_* are Tier 2.
HARNESS_SEGMENTS: Final[dict[str, tuple[str, ...]]] = {
    # Tier 1 — common-mode, affects all PIDs
    "SEG_OBD_CAN_PAIR": PID_NAMES,
    "SEG_OBD_PWR": PID_NAMES,
    "SEG_OBD_GND": PID_NAMES,
    # Tier 2 — per-connector, affects one sensor
    "SEG_CONN_CKP": (PID_ENGINE_RPM,),
    "SEG_CONN_MAP": (PID_INTAKE_MAP,),
    "SEG_CONN_ECT": (PID_COOLANT_TEMP,),
    "SEG_CONN_VSS": (PID_VEHICLE_SPEED,),
    "SEG_CONN_MAF": (PID_MAF_RATE,),
    # Tier 2 — per-rail, affects a coupled group
    "SEG_RAIL_REF_5V_A": (PID_ENGINE_RPM, PID_INTAKE_MAP),
    "SEG_RAIL_REF_5V_B": (PID_VEHICLE_SPEED,),
    "SEG_RAIL_GND_A": (PID_ENGINE_RPM, PID_INTAKE_MAP, PID_COOLANT_TEMP),
    "SEG_RAIL_GND_B": (PID_VEHICLE_SPEED, PID_MAF_RATE),
}

# Derived: sensor -> the other sensors it is electrically coupled to via any
# shared rail. Computed here so the coupling has exactly one definition.
SENSOR_RAIL_COUPLING: Final[dict[str, frozenset[str]]] = {
    pid: frozenset(
        other
        for rail in SHARED_RAILS.values()
        if pid in rail["sensors"]  # type: ignore[operator]
        for other in rail["sensors"]  # type: ignore[union-attr]
        if other != pid
    )
    for pid in PID_NAMES
}

# ---------------------------------------------------------------------------
# Physics pairs
# ---------------------------------------------------------------------------

# Pairs whose correlation must hold in a healthy session (test_simulator.py):
# (pid_a, pid_b, expected_pearson_r). PROVISIONAL correlation targets.
PHYSICS_PAIRS: Final[tuple[tuple[str, str, float], ...]] = (
    (PID_ENGINE_RPM, PID_VEHICLE_SPEED, 0.92),
    (PID_ENGINE_RPM, PID_MAF_RATE, 0.88),
    (PID_INTAKE_MAP, PID_MAF_RATE, 0.85),
    (PID_ENGINE_RPM, PID_INTAKE_MAP, 0.70),
    (PID_VEHICLE_SPEED, PID_MAF_RATE, 0.75),
)

# Deviation from the above before plausibility.py calls a relationship anomalous.
PHYSICS_PAIR_TOLERANCE: Final[float] = 0.20

# ---------------------------------------------------------------------------
# Fault injection
# ---------------------------------------------------------------------------

COMPONENT_DRIFT_RATE: Final[float] = 0.015                           # range-fraction per minute
SENSOR_BIAS_RANGE: Final[tuple[float, float]] = (0.05, 0.35)         # fraction of range
PHYSICAL_RESISTANCE_RANGE: Final[tuple[float, float]] = (0.5, 12.0)  # ohms

# Intermittent-contact regime. This is where probe sensitivity lives: the
# intermittent regime must be perturbation-responsive while a fixed-resistance
# fault is not (test_intermittent.py).
INTERMITTENT_CONTACT_BOUNCE_HZ: Final[float] = 15.0
INTERMITTENT_DUTY_CYCLE: Final[float] = 0.3
INTERMITTENT_RESISTANCE_SPIKE_MULTIPLIER: Final[float] = 8.0

FAULT_ONSET_FRACTION: Final[float] = 0.25  # fault begins 25% into the session

# --- Contact dynamics (moved here from simulator/intermittent.py) -----------
#
# Relocated per the handoff.md §5 Rule 1 corollary: any constant that can change
# an experimental outcome belongs in this file. Both of these change the probe
# signature directly, and both were outside the config audit.

# Mechanical/thermal response lag of a fretted contact to a change in current
# loading. This is the physical basis of the lag-dominant probe signature.
# PROVISIONAL — must be measured on the bench rig against real fretted pins.
CONTACT_RESPONSE_LAG_MS: Final[float] = 80.0

# How strongly probe-induced load raises the dropout probability. PROVISIONAL.
CONTACT_LOAD_SENSITIVITY: Final[float] = 1.8

# --- Rail coupling (moved here from simulator/faults.py) --------------------
#
# SHARED_GROUND_COUPLING is the constant named in handoff.md §6 as having been
# read by NOTHING for the entire Claim 2 / Claim 4 investigation, because
# test_generalization.py duplicated the contact physics locally instead of
# calling faults.py. Sweeping it measured nothing. The physics path has since
# been unified; the constant is relocated here so it cannot fall out of the
# audit again.
#
# A fretted contact on a SHARED ground rail carries return current for every
# sensor on that rail, so VSS dropouts track MAF's current draw. A fault in the
# VSS connector itself carries VSS current only and has no such coupling. That
# asymmetry is the whole physical distinction between the two hypotheses, and
# it is what a probe interrogates by modulating MAF polling.
#
# Bench Experiment C (docs/bench_setup.md §5, threshold in handoff.md §3)
# measures this: coupling ≥ 0.25 or the mechanism does not exist at all. The
# current value 1.0 is FOUR TIMES the threshold that would merely establish
# existence — it is not a measured number. PROVISIONAL.
SHARED_GROUND_COUPLING: Final[float] = 1.0

# A connector-local fault still sees a little common-mode bus activity, so it is
# not perfectly probe-inert. Keeps the discrimination non-trivial. PROVISIONAL.
CONNECTOR_COMMON_MODE_COUPLING: Final[float] = 0.15

# --- REF_5V_B rail fault parameters (moved here from simulator/faults.py) ---
#
# A degraded 5V reference forms a resistive divider. Quiescent sag, plus extra
# sag proportional to instantaneous load. Assumes a NON-ratiometric ADC
# reference — if the ECU's ADC referenced the same 5V rail the error would
# cancel. PROVISIONAL: confirm against the bench ECU.
#
# Both feed ReferenceRailFault.apply and both change an experimental outcome, so
# they are audited here under the same handoff.md §5 Rule 1 corollary as the
# five constants relocated before them.
RAIL_QUIESCENT_SAG: Final[float] = 0.06        # 6% low at rest
RAIL_LOAD_SENSITIVITY: Final[float] = 0.10     # additional sag at full probe load

# ---------------------------------------------------------------------------
# EPDG
# ---------------------------------------------------------------------------

CONTACT_R_SENSITIVITY_DEFAULT: Final[float] = 0.08  # evidence per ohm
EPDG_PROPAGATION_DECAY: Final[float] = 0.6          # per graph hop. PROVISIONAL.
EPDG_MIN_EVIDENCE: Final[float] = 1e-3              # below this, treat as zero

# ---------------------------------------------------------------------------
# Tier-1 confounder gate  (see docs/design.md section 3)
# ---------------------------------------------------------------------------

# Above this confound score, Tier-1 (OBD-II) wear is severe enough that every
# PID is suspect and Tier-2 attribution is not trustworthy for that session.
# The pipeline abstains rather than attributing. PROVISIONAL.
TIER1_CONFOUND_THRESHOLD: Final[float] = 0.50

# Below this, Tier-1 is treated as clean and no de-weighting is applied.
TIER1_CONFOUND_CLEAN_FLOOR: Final[float] = 0.15

# Weighting of the two Tier-1 confound inputs: normalised per-pin error energy
# and contact resistance. Must sum to 1.0. PROVISIONAL.
TIER1_CONFOUND_W_PIN_ERROR: Final[float] = 0.6
TIER1_CONFOUND_W_RESISTANCE: Final[float] = 0.4

# Contact resistance at which a single J1962 pin is considered fully degraded,
# used to normalise the resistance term into [0, 1]. PROVISIONAL.
TIER1_FULL_DEGRADE_OHM: Final[float] = 10.0

# Observation noise of the CW-AI detector stub (moved here from
# evidence/cwai_stub.py). If CWAIOutput were a noiseless readout of true wear,
# any test of `assess_tier1_confound` would be circular — this constant is what
# keeps the Claim 1 gate test honest, so it belongs in the audit.
# PROVISIONAL — must be replaced with the real CW-AI detector's characterised
# error. Chosen non-trivially large so confound detection is not circular.
CWAI_NOISE: Final[float] = 0.15

# Whether an anomalous control_module_voltage on its own forces abstention,
# independently of the confound score.
#
# BE PRECISE ABOUT WHY. control_module_voltage is the ECU's own supply
# measurement and has no Tier-2 harness connector, so it is observable only
# through the Tier-1 path. But it can move for reasons that have nothing to do
# with connector wear at all — a failing alternator, a weak battery, a bad
# charging regulator. So the justification for abstaining is NOT "Tier 1 is
# degraded": that would assert a cause we have not established.
#
# The correct statement is: A COMMON-MODE EXPLANATION EXISTS THAT A TIER-2
# VERDICT WOULD IGNORE. Something is moving every PID at once, we do not know
# what, and naming a harness segment would silently discard that possibility.
# Same abstention either way — but the reason on the record is the one we can
# actually defend.
#
# Exposed as a constant so Rule 1 can sweep it: setting this False must change
# S3's outcome. If it does not, the CMV path is not doing what we think it is.
CMV_ANOMALY_FORCES_ABSTAIN: Final[bool] = True

# How Tier-1 wear corrupts a session. These two govern the Claim 1 result and
# were previously buried in test files, escaping the config audit.
#
# SPURIOUS: transport wear makes unrelated sensors look anomalous. This ADDS
#   sensors to the observed footprint, which usually makes it explainable by no
#   hypothesis at all — so a Tier-2 consistency rule detects it for free.
# SILENT_MASK: transport wear ATTENUATES a genuine anomaly, removing a sensor
#   from the observed footprint. The result stays consistent with a smaller
#   hypothesis, so the Tier-2 rule accepts it and attributes confidently to the
#   wrong segment.
#
# Claim 1 lives or dies on the ratio between these. Bench Experiment A
# (docs/bench_setup.md §5) exists to measure the real ratio.

# ===========================================================================
# READ THIS BEFORE RERUNNING ANY CLAIM 1 EXPERIMENT
# ===========================================================================
#
# TIER1_SPURIOUS_ANOMALY_GAIN — current value 0.5.
#
# This is THE constant that flipped Claim 1 from DEAD to UNDETERMINED during
# the audit. It is not a measured quantity and never has been.
#
#   Pre-registered break-even range (Experiment A, handoff.md §3):
#       spurious rate < 0.035  -> Claim 1 works, file it
#       spurious rate > 0.10   -> withdraw Claim 1
#       between                -> report both, re-run the sweep with measured
#                                 values
#
#   Current value 0.5 sits roughly 14x ABOVE the top of that break-even range
#   (0.5 / 0.035 ≈ 14).
#
# CONSEQUENCE, STATED PLAINLY: a cold rerun at 0.5 will wrongly conclude that
# Claim 1 is dead. That is exactly what happened before the audit. The verdict
# was an artefact of this placeholder, not a property of the mechanism.
#
# Do not read a Claim 1 result off a run at this value and do not treat such a
# run as a falsification. Sweep across 0.035–0.10 — or better, wait for the
# Experiment A measurement, which is the only thing that settles it.
# PROVISIONAL.
TIER1_SPURIOUS_ANOMALY_GAIN: Final[float] = 0.5

# ===========================================================================
# TIER1_SILENT_MASK_GAIN — current value 0.0, i.e. SWITCHED OFF.
# ===========================================================================
#
# This constant models the EXACT mechanism Claim 1 exists to defend against:
# Tier-1 transport wear silently ATTENUATING a genuine anomaly so that a sensor
# drops out of the observed footprint. The truncated footprint stays internally
# consistent with a smaller hypothesis, so the Tier-2 consistency rule accepts
# it and attributes confidently to the WRONG segment. Unlike the spurious case,
# nothing downstream detects this — that silent failure is the entire argument
# for declining to answer.
#
# At 0.0 the mechanism is disabled. Any run at this value measures a world in
# which the thing Claim 1 protects against cannot happen, and will therefore
# find no value in the gate. Claim 1 was originally falsified under exactly
# this setting.
#
# A non-zero value must come from Experiment A, not from tuning.
# PROVISIONAL.
TIER1_SILENT_MASK_GAIN: Final[float] = 0.0

# ---------------------------------------------------------------------------
# Tier-2 inverse inference  (see docs/design.md section 4)
# ---------------------------------------------------------------------------

# Probability that a shared-rail fault has propagated to each of its sensors at
# the time of observation. Drives all partial-manifestation ambiguity, which is
# what Claims 2 and 4 exist to resolve. PROVISIONAL — needs field data on fault
# progression rates.
RAIL_MANIFEST_PROB: Final[float] = 0.6

# Residual standard deviation above which a sensor counts as anomalous.
# PROVISIONAL — must be set from real per-PID noise floors.
ANOMALY_DETECT_STD: Final[float] = 2.0

# Footprint-match score below which a hypothesis is discarded outright.
FOOTPRINT_MATCH_FLOOR: Final[float] = 0.30

# If the top two hypotheses are within this margin, the result is AMBIGUOUS and
# a probe is required to separate them. Sized to catch the known
# C_VSS / REF_5V_B footprint collision. PROVISIONAL.
TIER2_AMBIGUOUS_MARGIN: Final[float] = 0.10

# PROTOTYPE, DEFAULT OFF. Score candidates on graded per-sensor evidence instead
# of a thresholded anomalous set.
#
# The binary path throws away the residual magnitude at the threshold, and §12
# showed that is where the S1 failure comes from: intake_map at ratio 1.605 is
# plainly elevated above its noise floor, but a hard cut at ANOMALY_DETECT_STD
# discards that and truncates the footprint. Graded scoring keeps the ratio and
# lets a sub-threshold elevation still support a larger hypothesis.
#
# Both paths stay runnable. This is the last untried mechanism after the probe
# (Claim 3) and the type prior (Claim 4) were closed.
USE_GRADED_EVIDENCE: Final[bool] = False

# Width of the logistic that converts a residual ratio into soft membership.
# The MIDPOINT is ANOMALY_DETECT_STD, deliberately: graded scoring is then a
# strict softening of the existing decision boundary rather than a different
# boundary chosen to be favourable. Only the sharpness is free.
#
# PROVISIONAL and invented. Rule 1 applies: it must be swept, because a width
# small enough reproduces the binary path exactly and a width large enough makes
# every sensor half-anomalous. See tests/measure_rail_manifestation.py.
GRADED_EVIDENCE_WIDTH: Final[float] = 0.5

# PROTOTYPE, DEFAULT OFF. Abstain when the winning segment's footprint is a
# strict subset of another viable candidate's and the difference is explainable
# by non-manifestation.
#
# Motivation: a partially manifested rail fault truncates the observed footprint
# to a subset that a connector segment explains perfectly, so attribution names
# the connector with full confidence and nothing flags it (validation.md §12).
# Because connector footprints are singletons nested inside every rail footprint
# they belong to, this is structural, not incidental.
#
# It is OFF because the cure may be worse than the disease: the same nesting
# means a FULLY manifested rail fault also sits inside a larger rail's
# footprint, so the rule can abstain on the cases Claim 2 exists to win. Measure
# before enabling — tests/measure_rail_manifestation.py reports what it does to
# S1, S5 and the severity sweep.
ABSTAIN_ON_NESTED_FOOTPRINT: Final[bool] = False

# Prior mass on a single-connector fault vs a shared-rail fault. Connector
# faults are the more common failure mode in field data, and this prior is what
# breaks the strict-subset nesting when a probe is unavailable. PROVISIONAL.
PRIOR_CONNECTOR_FAULT: Final[float] = 0.7
PRIOR_RAIL_FAULT: Final[float] = 0.3

# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

ANOMALY_THRESHOLD: Final[float] = 0.55
UNCERTAINTY_PROBE_THRESHOLD: Final[float] = 0.30  # the UTP trigger, theta
PROVENANCE_CONFIRM_THRESHOLD: Final[float] = 0.70

# ---------------------------------------------------------------------------
# Probe safety
# ---------------------------------------------------------------------------

MAX_PROBE_DURATION_S: Final[float] = 2.0

# Probe stimulus frequency (moved here from probe/perturbation.py).
#
# Chosen well below contact-bounce frequency so the two are separable in the
# response, and low enough to fit whole cycles inside MAX_PROBE_DURATION_S —
# which is why it lives beside that constant. PROVISIONAL.
#
# Relocated per the handoff.md §5 Rule 1 corollary: any constant that can change
# an experimental outcome belongs in this file. This one sets the frequency the
# probe response is cross-correlated against, so it changes every Claim 3
# signature, and it was outside the config audit. Value unchanged: 2.0.
PROBE_STIMULUS_HZ: Final[float] = 2.0

MAX_BUS_UTIL_DELTA: Final[float] = 0.05  # +5 percentage points, absolute
WATCHDOG_TIMEOUT_S: Final[float] = 3.0
PROBE_COOLDOWN_S: Final[float] = 30.0

# Vehicle states in which a probe must be denied outright. Values must match
# VehicleState member values in types.py; test_safety.py asserts they do.
EXCLUDED_VEHICLE_STATES: Final[tuple[str, ...]] = (
    "cranking",
    "wide_open_throttle",
    "limp_home",
    "airbag_deployed",
    "dtc_active_safety_critical",
)

PROBE_PERTURBATION_AMPLITUDE: Final[float] = 0.15    # fraction of nominal cadence
PROBE_MIN_RESPONSE_CORRELATION: Final[float] = 0.35  # below this, no response
PROBE_MAX_RESPONSE_LAG_MS: Final[float] = 250.0

# ---------------------------------------------------------------------------
# DTC gate
# ---------------------------------------------------------------------------

T_CONFIRM_SESSIONS: Final[int] = 3  # hysteresis: consecutive sessions to confirm

# ---------------------------------------------------------------------------
# ML
# ---------------------------------------------------------------------------

XGBOOST_PARAMS: Final[dict[str, object]] = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "reg:squarederror",
    "random_state": 42,
}

BNN_HIDDEN_LAYERS: Final[tuple[int, ...]] = (128, 64, 32)
BNN_MC_PASSES: Final[int] = 50
BNN_DROPOUT_RATE: Final[float] = 0.2
BNN_LEARNING_RATE: Final[float] = 1e-3
BNN_EPOCHS: Final[int] = 100
BNN_BATCH_SIZE: Final[int] = 64

RANDOM_SEED: Final[int] = 42

# ---------------------------------------------------------------------------
# Conformal
# ---------------------------------------------------------------------------

CONFORMAL_ALPHA: Final[float] = 0.1  # target coverage = 1 - alpha = 90%
CALIB_SPLIT_FRACTION: Final[float] = 0.2
