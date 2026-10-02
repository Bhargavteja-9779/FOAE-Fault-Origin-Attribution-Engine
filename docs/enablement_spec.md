# FOAE — Enablement Build Spec (Claim 2 only)

Scope: the minimum backend that produces a defensible results table and feeds the
review dashboard. **Three modules.** Not the 22-module master spec.

Everything here is simulation-only. No bench, no hardware, no claim that there is.

---

## 0. Before any code — Claude Code prompt

```
Read docs/handoff.md and foae/config.py before doing anything.

Task 0 — repository safety. Do these first, in order:

1. git init is already done but there are ZERO commits. Before writing any new
   code: stage everything and make one initial commit. Message must state
   plainly that 7 tests fail deliberately and encode falsified claims.

   A PRIVATE remote is ALLOWED and is the intended offsite backup - push to it
   freely. The rule is about visibility, not about pushing.

   *** THE REPOSITORY MUST NEVER BE MADE PUBLIC BEFORE THE IPR CELL CLEARS ***
   *** FILING. India applies absolute novelty: a public disclosure by the   ***
   *** applicant before the priority date destroys patentability, and there ***
   *** is no general grace period to fall back on. Making the repo public,  ***
   *** forking it to a public account, or attaching the code to a public    ***
   *** issue or gist is an irreversible disclosure. Verify visibility before ***
   *** changing any repository setting.                                     ***

   If you are unsure whether the remote is private, treat it as public and do
   not push until you have checked.

2. LICENSE is 0 bytes. Replace with exactly:
   Proprietary - all rights reserved. Not for distribution.
   (Do not add an OSS license. Patent-pending material.)

3. Move SHARED_GROUND_COUPLING and CONNECTOR_COMMON_MODE_COUPLING from
   foae/simulator/faults.py into foae/config.py. Import them in faults.py.
   Do the same for CONTACT_LOAD_SENSITIVITY and CONTACT_RESPONSE_LAG_MS in
   foae/simulator/intermittent.py, and CWAI_NOISE in foae/evidence/cwai_stub.py.
   Rule from handoff.md:122-124 - any constant that can change an experimental
   outcome belongs in config.py.

4. Add a comment block above TIER1_SPURIOUS_ANOMALY_GAIN in config.py recording:
   current value 0.5; break-even range 0.035-0.10; this value is ~14x above
   break-even and was the constant that flipped Claim 1 from DEAD to
   UNDETERMINED during the audit; a cold rerun at 0.5 will wrongly conclude
   Claim 1 is dead. Same treatment for TIER1_SILENT_MASK_GAIN = 0.0, noting it
   models the exact Claim 1 mechanism and is currently switched off.

5. Append to docs/handoff.md the NAMES of the seven deliberately-failing tests,
   not just the count. Get them by running pytest. A count-only check passes if
   one true negative silently starts passing while an unrelated test breaks.

Run pytest afterwards and confirm still exactly 7 failed / 12 passed, same names.
Report before proceeding. Do not fix any failing test.

Every file write uses encoding="utf-8". On this machine write_text truncates the
file to zero bytes THEN raises on cp1252 - it has already destroyed
measurement_gaps.md once.
```

---

## 1. `foae/epdg/graph.py`

Builds the Electrical Path Dependency Graph from **design data only** — the
topology in `config.py`. No training, no fitting. This is the point of Claim 2:
the graph comes from the wiring diagram, so it works on a harness the system has
never seen.

```
build_epdg(topology) -> EPDG
```

Nodes:
- `sensor` — one per PID that has a Tier-2 harness connector
- `connector` — a named harness connector segment
- `rail` — a shared supply or ground rail from SHARED_RAILS
- `ecu` — single sink node

Edges: sensor → connector → rail → ecu. Each edge carries the rail id it rides.

Required methods:
- `segments() -> list[SegmentId]` — every candidate fault location
- `sensors_downstream_of(segment_id) -> set[PidName]` — the **footprint** of a
  segment: which PIDs go anomalous if that segment fails
- `footprint_matrix() -> dict[SegmentId, frozenset[PidName]]`

**Do not** implement `propagate_wear`. It is deprecated as unsound — Tier-1 wear
is common-mode and weights all sensors identically.

**Do not** map OBD-II byte offsets or PIDs to individual J1962 pins. All OBD-II
PIDs traverse the same CAN pair. FOAE operates on Tier-2 harness connectors only;
Tier 1 is common-mode and enters solely through the confound gate.

## 2. `foae/attribution/footprint.py`

```
attribute(observed_anomalous: set[PidName], epdg: EPDG, tier1: Tier1Assessment)
    -> Attribution
```

Algorithm:
1. If `tier1.gate == "TRIPPED"` → return `ABSTAIN`, reason `tier1_confound`.

   **State the justification precisely.** `control_module_voltage` has no
   Tier-2 harness connector, so it is observable only via the Tier-1 path. But
   it can move from charging-system or battery causes — a failing alternator, a
   weak battery — not only from connector wear. So the rule is **not** "Tier 1
   is degraded"; that asserts a cause we have not established. The rule is that
   **a common-mode explanation exists that a Tier-2 verdict would ignore**:
   something is moving every PID at once, we do not know what, and naming a
   harness segment would silently discard that possibility. Same abstention,
   accurate reason.

   Governed by `config.CMV_ANOMALY_FORCES_ABSTAIN` (default `True`), exposed as
   a constant so Rule 1 can sweep it: setting it `False` must change S3's
   outcome, and if it does not, the CMV path is not doing what we think it is.
2. Score every segment by set agreement between its footprint and the observed
   anomalous set. Jaccard is fine; record the raw intersection/difference too.
3. Rank. If top-1 minus top-2 < `TIER2_AMBIGUOUS_MARGIN` → `ABSTAIN`, reason
   `footprint_collision`. This is the Pair A case and it must be reachable.
4. Otherwise return the named segment, score, and the ranked candidate list.

`Attribution` must carry: `origin_layer`, `segment_id`, `confidence`,
`abstained`, `reason`, `candidates[]`. The dashboard reads all of these.

Confidence is a match score, not a calibrated probability. Name the field so
nobody later reports it as one.

## 3. `foae/pipeline.py`

```
run_scenario(scenario) -> ScenarioResult
export_run(results, path) -> None
```

Wires: simulator → anomaly detection → `assess_tier1_confound` → `attribute`,
then serialises to the JSON contract in §4.

Ship **four** scenarios, and make them the ones that show judgement:

| id | what it is | expected |
|---|---|---|
| `S1_shared_rail` | 5V rail branch degrades; two sensors on it go anomalous | names the rail segment |
| `S2_single_connector` | one sensor's own harness connector | names it; topology contributes nothing here, and that's fine |
| `S3_tier1_confound` | OBD-II connector wear; everything incl. `control_module_voltage` moves | **ABSTAIN** — gate trips |
| `S4_footprint_collision` | two segments with identical footprints | **ABSTAIN** — margin too small |

S3 and S4 are not padding. A system that declines when it cannot answer is more
credible to a review panel than one that is always right, and S3 is the Claim 1
story in visual form.

---

## 4. JSON export contract

The dashboard is built against exactly this. **Field names are binding — do not
rename them. Values below are illustrative** and use the real identifiers from
`config.py`, not invented ones.

```json
{
  "meta": {
    "run_id": "foae-2026-08-15-a",
    "generated_utc": "2026-08-15T09:00:00Z",
    "harness_id": "FOAE_TIER2",
    "evidence_basis": "simulation",
    "hardware_validated": false,
    "seed": 1337,
    "config_hash": "sha256:...",
    "commit": "abc1234"
  },
  "topology": {
    "nodes": [
      {"id": "intake_map", "label": "MAP", "kind": "sensor"},
      {"id": "C_MAP", "label": "MAP connector", "kind": "connector"},
      {"id": "REF_5V_A", "label": "5V ref A", "kind": "rail"},
      {"id": "ECU", "label": "ECU", "kind": "ecu"}
    ],
    "edges": [
      {"from": "intake_map", "to": "C_MAP", "rail": null},
      {"from": "C_MAP", "to": "REF_5V_A", "rail": "REF_5V_A"},
      {"from": "REF_5V_A", "to": "ECU", "rail": "REF_5V_A"}
    ]
  },
  "scenarios": [
    {
      "id": "S1_shared_rail",
      "label": "Shared 5V rail degradation",
      "ground_truth": {
        "origin_layer": "physical",
        "segment_id": "SEG_RAIL_REF_5V_A",
        "fault_type": "rail_resistance",
        "severity": 0.6
      },
      "traces": {
        "t_s": [0.0, 0.5, 1.0],
        "pids": {
          "intake_map": {
            "values": [101.2, 101.0, 88.4],
            "nominal": [20.0, 255.0],
            "anomalous_from_index": 2
          }
        }
      },
      "tier1": {
        "confound_score": 0.11,
        "threshold": 0.50,
        "gate": "PASS",
        "cmv_anomalous": false
      },
      "observed_anomalous": ["engine_rpm", "intake_map"],
      "candidates": [
        {"segment_id": "SEG_RAIL_REF_5V_A", "label": "5V ref A rail",
         "match_score": 0.86, "footprint": ["engine_rpm", "intake_map"]},
        {"segment_id": "SEG_CONN_MAP", "label": "MAP connector",
         "match_score": 0.50, "footprint": ["intake_map"]}
      ],
      "verdict": {
        "origin_layer": "physical",
        "segment_id": "SEG_RAIL_REF_5V_A",
        "confidence": 0.86,
        "abstained": false,
        "reason": null,
        "correct": true
      }
    }
  ],
  "validation": {
    "claims": [
      {"id": "C1", "title": "Tier-1 confounder gate + abstention",
       "status": "UNDETERMINED", "note": "needs one bench measurement"},
      {"id": "C2", "title": "Tier-2 footprint attribution over EPDG",
       "status": "SUPPORTED", "note": "the anchor claim"},
      {"id": "C3", "title": "Diagnostic protocol as actuation channel",
       "status": "FALSIFIED", "note": "passive wins at every grid point"},
      {"id": "C4", "title": "Hybrid type-prior over topology",
       "status": "FALSIFIED", "note": "no margin at realistic prior error"}
    ],
    "experiments": "GENERATED AT RUNTIME - see note below, do not transcribe"
  }
}
```

Export to `data/runs/<run_id>.json`, UTF-8.

### `validation.experiments` must be measured, never transcribed

An earlier revision of this spec carried four hardcoded experiment rows
(`Pair B nesting: passive 0.810, probe 0.560` among them). **Those numbers did
not match the suite.** The live figures are `0.990` and `0.710` — see
`handoff.md` §6, which records both against their bounds. The stale values were
transcribed by hand and drifted.

`pipeline.py` must therefore compute `validation.experiments` from an actual run
and write the measured values into the export. Do not paste figures into this
document and do not read them from it. Same rule as `handoff.md` §5 Rule 2: a
number you did not measure this run is a number you cannot defend.

`validation.claims` status wording is taken from `handoff.md` §2, which is
authoritative. Note that C3 and C4 there read `DISCRIMINATION ROBUSTLY
FALSIFIED` and `NOT FILEABLE` respectively — richer than the one-word statuses
above; reconcile before the results table ships.

### Enumerated values

Two fields carry a closed set of values. Both are switched on by the dashboard,
so adding a value means updating the frontend too.

**`tier1.gate`** — three states, mirroring `evidence/confound.py`'s `GateAction`:

| value | from | meaning |
|---|---|---|
| `PASS` | `PROCEED` | Tier 1 clean. Attribute normally. |
| `DEGRADED` | `INFLATE` | Tier 1 worn but below the abstain threshold. Attribution proceeds; read the verdict as lower-trust. |
| `TRIPPED` | `ABSTAIN` | Abstain. Also set when `cmv_anomalous` and `config.CMV_ANOMALY_FORCES_ABSTAIN`. |

`DEGRADED` has no downstream consumer yet. It is in the contract so the state
stays visible rather than being absorbed into `PASS` and quietly lost.

**`verdict.reason`** — `null` when `abstained` is `false`, otherwise one of:

| value | meaning |
|---|---|
| `tier1_confound` | A common-mode explanation exists that a Tier-2 verdict would ignore. `confidence` is `null` — this is no answer, not a weak one. |
| `footprint_collision` | Two or more segments within `TIER2_AMBIGUOUS_MARGIN`. `confidence` is retained: there is a well-supported explanation, just more than one. |
| `no_supported_hypothesis` | Nothing cleared `FOOTPRINT_MATCH_FLOOR` — an empty anomaly set, or one no segment in the graph explains. `confidence` is `null`. |

`no_supported_hypothesis` is not reached by S1–S4. It is documented and
implemented anyway: it is a real outcome of `attribute()`, and the alternative
is mislabelling it as one of the other two when it occurs.

### Two corrections to the example above

1. **`origin_layer`** reads `"physical"`, not `"interconnect"`. The codebase has
   a three-valued `FaultLayer` enum (`component` / `sensor` / `physical`, see
   `types.py`); `interconnect` is not one of its members. If the patent language
   genuinely needs a fourth layer, add it to the enum deliberately rather than
   letting the export disagree with the type system.
2. **Edge `rail` fields.** The sensor's own signal leg is upstream of any shared
   rail and carries `"rail": null`. Rail ids appear on `connector -> rail` and
   `rail -> ecu` edges. A connector riding both a ground and a reference rail
   emits one edge per rail, so a single edge cannot name "the" rail.

---

## 5. What NOT to build this week

`controller/`, `probe/utp.py`, `probe/safety.py`, `bench/`, `dashboard/` (the
Python one — the frontend replaces it), `validation/`, the conformal layer, the
BNN. All stay 0 bytes.

Claim 3 is withdrawn, so nothing that exercises the probe path needs to work.
