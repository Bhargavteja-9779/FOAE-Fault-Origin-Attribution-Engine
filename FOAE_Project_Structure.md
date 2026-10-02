# FOAE — Project Structure

Complete repository layout, module responsibilities, data flow, and file-by-file
breakdown. Reflects the post-research revision (UTP is the lead claim, probe engine
built before EPDG, conformal UQ instead of bare MC-Dropout).

---

## 1. Repository tree

```
foae/
│
├── README.md                       # Project overview, setup, how to run
├── pyproject.toml                  # Dependencies, package config
├── .gitignore                      # data/, __pycache__, *.pkl, .venv
├── LICENSE                         # Decide with VIT IPR cell (likely restricted)
│
├── foae/                           # ── MAIN PACKAGE ──
│   ├── __init__.py
│   ├── config.py                   # ALL constants, thresholds, hyperparameters
│   ├── types.py                    # Shared dataclasses and enums
│   │
│   ├── simulator/                  # ── PHASE 1 ──
│   │   ├── __init__.py
│   │   ├── vehicle_model.py        # Physics-based PID trace generator
│   │   ├── harness.py              # Electrical topology (pin map, shared lines)
│   │   ├── faults.py               # ComponentFault, SensorFault, PhysicalFault
│   │   ├── intermittent.py         # Intermittent-contact regime model (NEW,
│   │   │                           #   from research: where probe-sensitivity lives)
│   │   ├── scenarios.py            # Session generator, seed control, batch datasets
│   │   └── probe_hook.py           # Perturbation injection interface
│   │
│   ├── probe/                      # ── PHASE 2 (moved up — LEAD CLAIM) ──
│   │   ├── __init__.py
│   │   ├── perturbation.py         # Diagnostic-schedule perturbation primitives
│   │   ├── response.py             # Stimulus-response cross-correlation
│   │   ├── safety.py               # Safety envelope enforcement + audit log
│   │   ├── signatures.py           # Perturbation-response signature library (NEW)
│   │   └── utp.py                  # Uncertainty-triggered probe scheduler
│   │
│   ├── evidence/                   # ── PHASE 3 ──
│   │   ├── __init__.py
│   │   ├── cwai_stub.py            # CW-AI output interface (filed patent = black box)
│   │   └── plausibility.py         # PID-relationship residual scorer
│   │
│   ├── epdg/                       # ── PHASE 3 ──
│   │   ├── __init__.py
│   │   ├── graph.py                # networkx DiGraph subclass + node/edge schema
│   │   ├── build.py                # Construct EPDG from harness topology
│   │   └── propagate.py            # Pin-wear evidence → per-sensor evidence
│   │
│   ├── attribution/                # ── PHASE 4 ──
│   │   ├── __init__.py
│   │   ├── twins.py                # Three counterfactual scorers
│   │   ├── attributor.py           # Combine scores → ProvenanceVector
│   │   ├── uncertainty.py          # MC-Dropout BNN
│   │   ├── conformal.py            # Split-conformal calibration wrapper (NEW)
│   │   └── features.py             # Feature vector assembly
│   │
│   ├── controller/                 # ── PHASE 5 ──
│   │   ├── __init__.py
│   │   ├── gate.py                 # DTC gate logic + T_confirm hysteresis
│   │   ├── dem_mock.py             # Mock Diagnostic Event Manager (ECU stand-in)
│   │   └── embodiments.py          # IntegratedEmbodiment, ServiceToolEmbodiment
│   │
│   ├── pipeline.py                 # End-to-end orchestration (the main loop)
│   │
│   ├── validation/                 # ── PHASE 6 ──
│   │   ├── __init__.py
│   │   ├── run_all.py              # Master validation entry point
│   │   ├── scenario_1_synthetic.py # Within-distribution
│   │   ├── scenario_2_empirical.py # HCRL / ROAD
│   │   ├── scenario_3_probe_lift.py# Passive vs ADP-assisted
│   │   ├── scenario_4_economy.py   # Probe economy / bus overhead
│   │   ├── scenario_5_falsepos.py  # False-suppression rate
│   │   ├── scenario_6_safety.py    # Safety envelope compliance
│   │   ├── metrics.py              # Confusion matrix, macro-F1, ECE, coverage
│   │   └── reports.py              # Generate IDF tables + plots
│   │
│   ├── bench/                      # ── PHASE 6 parallel track ──
│   │   ├── __init__.py
│   │   ├── firmware/               # ESP32/STM32 sketches
│   │   │   ├── ecu_simulator/      # Publishes OBD-II PIDs incl. 0x42
│   │   │   └── tester_node/        # UDS requests with controllable cadence
│   │   ├── capture.py              # Log real CAN traffic from the rig
│   │   └── analyze.py              # Run FOAE pipeline on bench captures
│   │
│   └── dashboard/                  # ── PHASE 7 ──
│       ├── __init__.py
│       ├── app.py                  # Streamlit entry point
│       └── views/
│           ├── provenance.py       # Provenance vector + confidence bars
│           ├── epdg_view.py        # EPDG graph with wear highlighting
│           └── gate_log.py         # DTC decisions + audit trail
│
├── tests/                          # Mirrors foae/ structure
│   ├── conftest.py                 # Shared fixtures (sessions, harness, epdg)
│   ├── test_simulator.py
│   ├── test_intermittent.py
│   ├── test_probe.py
│   ├── test_safety.py
│   ├── test_evidence.py
│   ├── test_epdg.py
│   ├── test_attribution.py
│   ├── test_conformal.py
│   ├── test_controller.py
│   └── test_pipeline.py            # End-to-end integration
│
├── data/                           # GITIGNORED
│   ├── download.sh                 # Fetch all public datasets
│   ├── hcrl/                       # Korea University Car-Hacking
│   ├── road/                       # ORNL ROAD
│   ├── ornl_intermittent/          # ORNL Intermittent Fault (CHASE THIS)
│   ├── kit_obd/                    # KIT decoded PIDs
│   ├── syncan/                     # Bosch/ETAS synthetic
│   ├── synthetic/                  # Simulator output
│   └── bench/                      # Bench rig captures
│
├── models/                         # GITIGNORED — trained artifacts
│   ├── bnn.keras
│   ├── xgb_residual.json
│   └── conformal_calib.pkl
│
├── notebooks/                      # Exploration, not shipped
│   ├── 01_simulator_sanity.ipynb
│   ├── 02_probe_response.ipynb
│   └── 03_attribution_analysis.ipynb
│
└── docs/
    ├── design.md                   # Locked FOAE design
    ├── prior_art.md                # Full reference table + gap analysis
    ├── claim_strategy.md           # Claim hierarchy + design-arounds
    ├── validation.md               # Results tables for IDF
    ├── bench_setup.md              # Rig BOM, wiring, methodology
    └── IDF_B.md                    # VIT Invention Disclosure draft
```

---

## 2. Layer architecture

The codebase has five conceptual layers. Data flows strictly downward — no layer
reaches back up.

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5 — PRESENTATION                                      │
│  dashboard/ · validation/reports.py                          │
│  Renders provenance, EPDG, gate log, IDF tables              │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  LAYER 4 — CONTROL (Technical Effect / Section 3(k))         │
│  controller/gate.py · dem_mock.py · embodiments.py           │
│  Confirm / Suppress / Re-tag DTC based on provenance         │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  LAYER 3 — INFERENCE                                         │
│  attribution/twins.py · attributor.py · uncertainty.py       │
│           · conformal.py                                     │
│  Three counterfactual models → ProvenanceVector + UQ         │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  LAYER 2 — EVIDENCE                                          │
│  evidence/cwai_stub.py · plausibility.py                     │
│  epdg/propagate.py                                           │
│  probe/response.py · signatures.py                           │
│  Turns raw telemetry into structured evidence                │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  LAYER 1 — DATA SOURCE                                       │
│  simulator/ (synthetic)  ·  bench/ (real rig)                │
│  data/ (public datasets)                                     │
│  probe/perturbation.py · safety.py (acts back on source)     │
└─────────────────────────────────────────────────────────────┘
```

The **one exception** to downward flow: the UTP probe (Layer 2) acts back on the
data source (Layer 1). That closed loop *is* the invention — it's why the probe
module owns both `perturbation.py` (writes to source) and `response.py` (reads
from source).

---

## 3. Data flow — one diagnostic session

```
    session_data (DataFrame: timestamp + 6 PIDs)
              │
      ┌───────┴────────┐
      ▼                ▼
 cwai_stub        plausibility
      │                │
      │  CWAIOutput    │  PlausibilityResult
      │  ├ per_pin_error_vector (16,)
      │  ├ contact_resistance_ohm
      │  ├ wear_class
      │  └ uncertainty
      │                │
      ▼                │
 epdg.propagate        │
      │                │
      │  sensor_wear_evidence: dict[str, float]
      │                │
      └───────┬────────┘
              ▼
        attribution.attribute()
              │
              │  ProvenanceVector v1
              │  ├ component / sensor / physical
              │  └ epistemic_uncertainty
              ▼
      ┌───────────────────┐
      │ uncertainty > θ?  │
      └────┬─────────┬────┘
        NO │         │ YES
           │         ▼
           │    probe.utp.maybe_probe()
           │         │
           │    safety.check_safety() ──► DENY ──► abort + log
           │         │ ALLOW
           │         ▼
           │    perturbation.generate()
           │         │
           │    probe_hook.apply()  ◄─── acts on data source
           │         │
           │    response.compute()
           │         │
           │         │  ProbeResult
           │         │  ├ response_correlations
           │         │  ├ response_lags / polarities
           │         │  └ responding_sensors
           │         ▼
           │    signatures.match()  ──► harness segment ID
           │         │
           │    attribution.attribute(probe_result)
           │         │
           │         │  ProvenanceVector v2 (refined)
           └────┬────┘
                ▼
        conformal.calibrate()
                │
                │  calibrated confidence + coverage guarantee
                ▼
        controller.gate.decide()
                │
                │  GateOutput
                │  ├ decision: CONFIRM / SUPPRESS / RETAG
                │  ├ attributed_origin
                │  └ provenance_vector
                ▼
      ┌─────────┴─────────┐
      ▼                   ▼
IntegratedEmbodiment  ServiceToolEmbodiment
(writes to DEM)       (repair guidance)
```

---

## 4. Module responsibilities

| Module | Owns | Consumes | Produces | Phase |
|---|---|---|---|---|
| `simulator/` | Ground-truth fault generation | config | Labeled sessions | 1 |
| `probe/` | **Lead claim.** Perturbation, response, safety | Session, uncertainty | ProbeResult | 2 |
| `evidence/` | CW-AI interface, plausibility residuals | Session | CWAIOutput, PlausibilityResult | 3 |
| `epdg/` | Electrical graph, evidence propagation | Harness, CWAIOutput | sensor_wear_evidence | 3 |
| `attribution/` | Counterfactual scoring, UQ | All evidence | ProvenanceVector | 4 |
| `controller/` | **Technical effect.** DTC gating | ProvenanceVector | GateOutput | 5 |
| `validation/` | All six scenarios, metrics | Pipeline outputs | IDF tables | 6 |
| `bench/` | Real hardware capture | Rig | Real captures | 6 |
| `dashboard/` | Visualization | Everything | UI | 7 |

---

## 5. Key interfaces (the contracts between modules)

These are the seams. Get them right and modules can be built in parallel by
different people.

> **Revised by the two-tier harness correction.** `SENSOR_PIN_MAP` as described
> in this document splits sensors across OBD-II J1962 pins. That is not
> physically valid — all PIDs share one CAN pair, so J1962 wear is common-mode.
> The harness model is now two-tier (`SENSOR_PIN_MAP` = Tier 1 transport,
> `SENSOR_CONNECTOR_MAP` + `SHARED_RAILS` = Tier 2 sensor harness). See
> `docs/design.md` §2.

```python
# evidence → epdg
CWAIOutput.per_pin_error_vector: np.ndarray  # shape (16,), Tier-1 / J1962 only

# epdg → attribution
# DEPRECATED — DO NOT IMPLEMENT. See docs/design.md §7.
#   propagate_wear(epdg, cwai) -> dict[str, float]
# Unsound under the corrected physics. CWAIOutput describes Tier 1 (the J1962
# connector), where wear is common-mode: it degrades all six PIDs identically.
# Forward-propagating it therefore assigns every sensor the same evidence, so
# the returned map is constant and carries zero discriminative information —
# while downstream code would consume it as per-sensor evidence and produce
# confident attributions from a signal containing none.
#
# Replaced by two interfaces that split the two distinct jobs:
assess_tier1_confound(cwai) -> float
    # Tier 1 gates trust, it does not attribute. High confound => abstain.
infer_tier2_origin(epdg, anomalous_sensors, probe_response) -> dict[str, float]
    # Tier 2 attributes by INVERSE inference: match the observed anomaly
    # footprint against each candidate connector/rail fault's expected
    # footprint. Posterior keyed by segment_id.

# evidence → attribution
PlausibilityResult.relationship_residuals: dict[str, float]
PlausibilityResult.anomalous_relationships: list[str]

# attribution → probe (the uncertainty trigger)
ProvenanceVector.epistemic_uncertainty: float

# probe → attribution (the refinement loop)
ProbeResult.response_correlations: dict[str, float]
ProbeResult.responding_sensors: list[str]

# attribution → controller
ProvenanceVector(component, sensor, physical, epistemic_uncertainty, confidence)

# controller → embodiments
GateOutput(decision, dtc_code, attributed_origin, provenance_vector, probe_fired)
```

---

## 6. Test structure

Every module has a test file. Three tiers:

**Tier 1 — Unit tests** (fast, no I/O)
- `test_simulator.py` — physics pairs correlate in healthy sessions; each fault
  type affects the right PIDs
- `test_intermittent.py` — intermittent regime is perturbation-responsive;
  fixed-resistance regime is not
- `test_epdg.py` — pin-6 wear propagates only to pin-6 sensors
- `test_safety.py` — excluded states deny; cooldown enforced; watchdog fires

**Tier 2 — Module integration**
- `test_probe.py` — probe on PhysicalFault yields correlated response;
  on ComponentFault yields none
- `test_attribution.py` — per-layer accuracy ≥ 90% on simulator data
- `test_conformal.py` — coverage matches nominal within tolerance

**Tier 3 — End-to-end**
- `test_pipeline.py` — full session → gate decision, all three fault types,
  correct decision each time

---

## 7. Configuration hierarchy

Single source of truth in `config.py`, grouped by concern:

```
config.py
├── Vehicle model      SAMPLE_RATE_HZ, SESSION_DURATION_S, NUM_PIDS
├── Pin assignments    PIN_ASSIGNMENTS (SAE J1962)
├── Harness topology   SENSOR_PIN_MAP
├── Physics pairs      PHYSICS_PAIRS
├── Fault injection    COMPONENT_DRIFT_RATE, SENSOR_BIAS_RANGE,
│                      PHYSICAL_RESISTANCE_RANGE,
│                      INTERMITTENT_* (new)
├── EPDG               CONTACT_R_SENSITIVITY_DEFAULT
├── Attribution        ANOMALY_THRESHOLD, UNCERTAINTY_PROBE_THRESHOLD,
│                      PROVENANCE_CONFIRM_THRESHOLD
├── Probe safety       MAX_PROBE_DURATION_S, MAX_BUS_UTIL_DELTA,
│                      EXCLUDED_VEHICLE_STATES, WATCHDOG_TIMEOUT_S,
│                      PROBE_COOLDOWN_S
├── DTC gate           T_CONFIRM_SESSIONS
├── ML                 XGBOOST_PARAMS, BNN_HIDDEN_LAYERS, BNN_MC_PASSES
└── Conformal          CONFORMAL_ALPHA, CALIB_SPLIT_FRACTION
```

No magic numbers anywhere else in the codebase.

---

## 8. Document structure (docs/)

| File | Purpose | Feeds |
|---|---|---|
| `design.md` | Locked architecture, three mechanisms | Team onboarding |
| `prior_art.md` | Full reference table + gap column | IDF Section 3 |
| `claim_strategy.md` | Claim hierarchy, design-arounds for GM '553 and VW '665 | Patent agent |
| `validation.md` | All six scenario results | IDF Section 8 |
| `bench_setup.md` | BOM, wiring diagram, fretting methodology | IDF + reproducibility |
| `IDF_B.md` | The VIT disclosure form itself | IPR cell submission |

---

## 9. Build order (post-research revision)

```
Week 0    Phase 0   Repo setup + IPR search request + ORNL dataset chase
Week 1-2  Phase 1   simulator/  (incl. intermittent.py)
Week 2-3  Phase 2   probe/      ← LEAD CLAIM, built early
Week 3-4  Phase 3   evidence/ + epdg/
Week 4-5  Phase 4   attribution/ (incl. conformal.py)
Week 5    Phase 5   controller/
Week 6-7  Phase 6   validation/ + bench/
Week 7-8  Phase 7   dashboard/ + docs/IDF_B.md
```

The change from the original plan: `probe/` moved from Phase 3 to Phase 2,
because the research established UTP/ADP as the lead independent claim. Proving
it works early de-risks the entire patent.

---

## 10. Ownership (3-person team)

| Person | Primary modules | Secondary |
|---|---|---|
| **Arun (lead)** | `epdg/`, `attribution/`, `docs/` | Architecture, IDF, bench rig |
| **Teammate 2** | `simulator/`, `validation/` | `evidence/`, data pipeline |
| **Teammate 3** | `probe/`, `controller/` | `dashboard/`, conformal UQ |

Cross-review all PRs. Phase boundaries are joint integration checkpoints — the
whole team pulls `main`, runs tests together, and demos before moving on.
