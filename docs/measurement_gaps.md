# FOAE — Measurement Gaps

**The bench work plan.** Every constant in the codebase that is currently a
guess, what measurement would fix it, and which claim depends on it.

Nothing here has been measured. Values in the code were chosen to be physically
plausible so the pipeline would run — **not** because anything supports them.
Where a simulation result depends on one of these, that result inherits the
guess.

Priority key: **P0** blocks a claim · **P1** affects a claim's numbers ·
**P2** affects realism only.

---

## 1. Summary by priority

| Priority | Count | Meaning |
|---|---:|---|
| P0 | 8 | A claim cannot be assessed until measured |
| P1 | 9 | Claim numbers shift, conclusions may not |
| P2 | 7 | Simulation realism only |

**24 unmeasured constants.** Of these, 4 are load-response parameters that
between them determine every probe result obtained so far, and **1 alone
determines the Claim 1 verdict** (§2.6).

---

## 2. P0 — blocks a claim

### 2.1 `CONTACT_RESPONSE_LAG_MS = 80.0` · `intermittent.py:22`
Mechanical/thermal lag of a fretted contact responding to a change in current
loading. **Pure invention** — no source.
- **Depends:** Claim 3. This constant *is* the probe's lag signature. Its value
  determined the measured lag AUC (0.53–0.68) that caused `expected_lag_ms` to
  be deleted from `ProbeSignature`.
- **Measurement:** Tier-B specimen under step-change in load current; capture
  dropout-rate onset with the scope; fit the time constant. Bench §4, §6.2.
- **If very small** (< 5 ms), lag is unmeasurable at any realistic poll rate and
  the deletion was correct. **If large** (> 50 ms) and consistent, the field may
  be reinstatable.

### 2.2 `CONTACT_LOAD_SENSITIVITY = 1.8` · `intermittent.py:25`
How strongly probe-induced load raises dropout probability.
- **Depends:** Claim 3, decisively. If real contacts do not respond to load at
  all, the probe has no mechanism and Claim 3's discrimination argument is
  permanently dead regardless of the actuation-channel point.
- **Measurement:** Bench Experiment B (§6.2). Dropout rate vs load current on
  Tier-B specimens.

### 2.3 `CONTACT_LOAD_SENSITIVITY` — the effective coupling for Claim 4
Dropout-rate response to co-resident current draw. Listed also at §2.2 for
Claim 3; it gates **both** claims by different routes.
- **Depends:** Claim 4's mechanism. Swept (`validation.md` §10.3): the type
  prior carries transferable signal only at **≥ ~0.5**. At 0.2 or below,
  transfer accuracy falls to the majority baseline and **Claim 4 has no
  mechanism at all**.
- **Measurement:** Tier-2 shared-rail injection; modulate one sensor's current
  draw, measure dropout-rate change on its rail-mate. Bench §6.2.

> **Correction 2026-08-05.** This entry previously named
> `faults.SHARED_GROUND_COUPLING` as Claim 4's gating constant. That was wrong.
> `tests/test_generalization.py:114` bypasses `faults.py` and calls
> `intermittent.contact_gate` directly, so `SHARED_GROUND_COUPLING` is **never
> read** by any Claim 2 or Claim 4 experiment — setting it to 0.0 changes
> nothing. The duplicated physics path must be unified before `epdg/` is built.
> See `validation.md` §10.4.
>
> `SHARED_GROUND_COUPLING` still governs the §5.2 identifiability pair
> (`test_identifiability_nesting.py`), which does go through `faults.py`.

### 2.4 `CONNECTOR_COMMON_MODE_COUPLING = 0.15` · `faults.py:79`
Residual coupling of bus activity into a connector-local fault. Chosen to keep
the discrimination non-trivial — i.e. **chosen to make the experiment fair**,
exactly the kind of choice that must be measured rather than assumed.
- **Depends:** Claims 3 and 4. Sets the contrast between the two fault types.
- **Measurement:** as §2.3, on a connector-local specimen.

### 2.5 `SENSOR_CONNECTOR_MAP`, `SHARED_RAILS` · `config.py`
The Tier-2 topology: which sensors share which ground and reference rails.
- **Depends:** Claim 2 entirely. Rail groupings *are* the hypothesis space, and
  topology's whole contribution was shown to be confined to shared-rail faults.
- **Measurement:** Not a bench measurement — **read from vehicle wiring
  diagrams** for a target platform. Currently invented.
- **Note:** the shuffled-topology control showed correct groupings are worth
  +0.127 overall. A wrong topology silently degrades Claim 2 with no error
  surfacing anywhere.

### 2.6 `TIER1_SPURIOUS_ANOMALY_GAIN = 0.5` · `config.py` — **HIGHEST PRIORITY**
Rate at which Tier-1 wear makes unrelated sensors read anomalous.
- **Depends:** Claim 1, *decisively and by itself.* The sensitivity sweep
  (`validation.md` §9.1) showed Claim 1 **beats** the free Tier-2 rule below
  ≈0.035 and **loses** above ≈0.10. The value 0.5 — 14x above break-even — was
  invented, lived in a test file outside the config audit, and single-handedly
  produced the Claim 1 falsification.
- **Measurement:** Bench Experiment A §5.4. Count anomalous sensors off the
  injected fault path, normalised by wear.
- **This is the single most decision-relevant unmeasured number in the
  project.**

### 2.7 `TIER1_SILENT_MASK_GAIN = 0.0` · `config.py`
Rate at which Tier-1 wear attenuates a *genuine* anomaly below detection,
leaving the footprint consistent and the attribution silently wrong.
- **Depends:** Claim 1. This is the mechanism only Tier-1 information can catch.
  Raising it from 0.0 to 1.0 moves break-even from 0.035 to 0.10.
- **Measurement:** Bench Experiment A §5.4, counting injected-path sensors that
  fail to flag.

### 2.8 `CWAI_NOISE = 0.15` · `cwai_stub.py:21`
Observation noise of the CW-AI connector-wear detector.
- **Depends:** Claim 1. Sets how detectable Tier-1 confound is (AUC 1.000 was
  obtained at this value). If real CW-AI noise is much higher, the confound
  score may not separate worn from clean at all — and Claim 1 fails for a
  second, independent reason.
- **Measurement:** from the CW-AI patent work directly. **Internal dependency,
  not a bench task** — ask that team for characterised error.

---

## 3. P1 — affects a claim's numbers

| Constant | Location | Depends | Measurement |
|---|---|---|---|
| `RAIL_QUIESCENT_SAG = 0.06` | `config.py` | Claim 2 | Inject known resistance in a 5 V reference; measure sensor-reading shift |
| `RAIL_LOAD_SENSITIVITY = 0.10` | `config.py` | Claims 2, 3 | Same, under modulated load |
| `TIER1_FULL_DEGRADE_OHM = 10.0` | `config.py` | Claim 1 | Resistance at which J1962 transport materially degrades — sweep decade box until PID corruption appears |
| `TIER1_CONFOUND_THRESHOLD = 0.50` | `config.py` | Claim 1 | Calibrate from Experiment A wear/misattribution curve |
| `TIER1_CONFOUND_CLEAN_FLOOR = 0.15` | `config.py` | Claim 1 | As above |
| `TIER1_CONFOUND_W_PIN_ERROR / _W_RESISTANCE` (0.6 / 0.4) | `config.py` | Claim 1 | Fit against Experiment A data; currently an arbitrary split |
| `RAIL_MANIFEST_PROB = 0.6` | `config.py` | Claims 2, 4 | Field data on fault progression rates; drives all partial-manifestation ambiguity |
| `PROBE_STIMULUS_HZ = 2.0` | `config.py` | Claim 3 | Sweep on Tier-B specimens; find frequency of maximum response |
| `PHYSICS_PAIRS` correlations | `config.py` | Claim 2 | Real OBD capture from a running vehicle |

---

## 4. P2 — simulation realism only

| Constant | Location | Measurement |
|---|---|---|
| `PID_NOMINAL_RANGES` | `config.py` | Real OBD capture |
| `SENSOR_NOISE_STD` | `config.py` | Real OBD capture; per-PID variance at steady state |
| `PROBE_SAMPLE_RATE_HZ = 100.0` | `config.py` | Max achievable single-PID poll rate on the bench tester |
| `ANOMALY_DETECT_STD = 2.0` | `config.py` | Set from real per-PID noise floors |
| `SENSOR_PIN_MAP` / `_OBD_TRANSPORT_PINS` | `config.py` | J1962 pinout is standardised; confirm against target platform |
| `FOOTPRINT_MATCH_FLOOR = 0.30` | `config.py` | Tuning parameter; sweep once real footprints exist |
| `TIER2_AMBIGUOUS_MARGIN = 0.10` | `config.py` | As above |
| `EPDG_PROPAGATION_DECAY = 0.6` | `config.py` | **Possibly obsolete** — forward propagation was deprecated (`design.md` §7). Delete if `epdg/` never implements it |

---

## 4A. `PRIOR_CONNECTOR_FAULT` — the gap the bench cannot close

`PRIOR_CONNECTOR_FAULT = 0.7` / `PRIOR_RAIL_FAULT = 0.3` · `config.py`

**No bench experiment can produce this number.** It is a population statistic —
the relative field incidence of connector-local versus shared-rail harness
faults — and the rig measures individual specimens, not populations.

**Why it decides Claim 4.** The hybrid attributor always trades connector-fault
accuracy (perfect under footprint-alone) for rail-fault accuracy. Whether that
trade is a net gain depends entirely on the connector/rail mix:

| Config | connector share | net gain |
|---|---|---|
| B | 64% | +0.086 |
| C | 60% | **+0.000** |

A 4-point shift in mix moved the net gain from meaningful to zero. The real mix
is unknown, and the prior currently encodes an assumption of 70/30 chosen with
no basis whatsoever.

### Candidate sources

| Source | Route | Realism |
|---|---|---|
| **OEM / Tier-1 warranty claim databases** | Via VIT industry contacts or a sponsored-project MoU. Warranty data records replaced part plus failure mode | Best data; access is the obstacle. Usually needs an NDA and a named academic collaboration |
| **Tier-1 connector manufacturers** (TE Connectivity, Aptiv, Yazaki, Sumitomo — all have Indian operations) | Application-engineering contact via VIT | Realistic. These firms routinely engage with academic reliability work and hold contact-reliability statistics |
| **Published automotive connector reliability literature** | SAE Technical Papers; IEEE Holm Conference on Electrical Contacts; *IEEE Trans. Components, Packaging and Manufacturing Technology* | ~~Immediately accessible~~ **RUN 2026-08-10 — does not close the prior.** Literature keys on component/mechanism, not shared-vs-dedicated topology. See `lit_connector_fault_mix.md` |
| **ARAI / ICAT** (Indian automotive test agencies) | Institutional approach via VIT | May hold Indian-market field-failure data — more relevant to an Indian filing than US/EU warranty data |
| **Fleet operators / large service chains** | State transport undertakings; chains such as Bosch Car Service | Repair records are coarser than warranty data but obtainable, and Indian-market specific |
| **NHTSA / vehicle-owner complaint databases** | Public | Free but weak — self-reported, rarely identifies the conductor |

**Recommended first move:** ~~the published literature (row 3) to bound the
ratio~~ **The literature route was run 2026-08-10 and does not bound the ratio**
(`lit_connector_fault_mix.md`): published contact-reliability work keys on
component and mechanism, not on shared-rail vs connector-local topology, so it
cannot be re-keyed to the split the prior needs. The binding path is now the
VIT-mediated approach to a Tier-1 connector manufacturer (row 2) or OEM warranty
data (row 1) — with the data request phrased to ask explicitly for the
shared-conductor vs single-conductor breakdown, or per-claim detail sufficient
to derive it. Longest lead time of anything on the no-hardware list; start now.

### Claim status consequence

> **Claim 4 is UNFILEABLE until this prior is grounded in field data.**
>
> Its only measured advantage is mix-dependent, it vanishes entirely on one of
> two tested configurations, and the parameter controlling that outcome is
> currently a guess. Filing it means asserting an advantage that the applicant's
> own evidence shows is contingent on an unmeasured population statistic — a
> position that does not survive examination.
>
> This is a **hard gate**, not a caution. It is also not resolvable by any
> amount of bench or simulation work.

---

## 5. Constants formerly embedded in tests

These governed experimental results while living in test files, outside the
config audit.

| Constant | Now | Role |
|---|---|---|
| ~~`MANIFEST_PROB = 0.6`~~ | `config.RAIL_MANIFEST_PROB` | **MOVED 2026-08-05.** Probability a rail fault has reached each of its sensors |
| ~~`ANOMALY_STD_THRESHOLD = 2.0`~~ | `config.ANOMALY_DETECT_STD` | **MOVED 2026-08-05.** Detection threshold for "sensor is anomalous" |
| ~~`wear * 0.5`~~ | `config.TIER1_SPURIOUS_ANOMALY_GAIN` (§2.6) | **MOVED 2026-08-05.** Determined the Claim 1 verdict single-handedly |

The suite was verified unchanged at default values (12 passed, 7 failed at the
time of the move), so the move is behaviour-preserving. The suite now stands at
**60 passed, 7 failed** — unit tests for `epdg/graph.py`,
`attribution/footprint.py` and `pipeline.py` were added 2026-08-30. The seven
failures are the same seven throughout; see §6 of `handoff.md`.

A fourth parameter, `config.TIER1_SILENT_MASK_GAIN` (§2.7), was added at the
same time. The previous model had no way to express transport wear that corrupts
attribution *without* breaking footprint consistency — which is precisely the
mechanism Claim 1 depends on. That absence was a **modelling omission, not a
tuning choice**, and it is why the original Claim 1 result looked conclusive.

**Process lesson.** A constant governing a claim-level verdict sat outside the
audit for the entire investigation. Any constant that can change an experimental
outcome belongs in `config.py`, never in a test file.

---

## 6. What to measure first

1. **§2.6 `TIER1_SPURIOUS_ANOMALY_GAIN`** — decides Claim 1 outright. Bench
   Experiment A §5.4.
2. **§2.2 `CONTACT_LOAD_SENSITIVITY`** — a single measurement that can
   permanently settle Claim 3's discrimination argument. If real contacts do not
   respond to load, stop pursuing it.
3. **§2.5 topology** — read from wiring diagrams. Costs only time and removes a
   P0 gap immediately.
4. **§2.8 `CWAI_NOISE`** — internal request to the CW-AI team. No bench needed.
5. **§4A `PRIOR_CONNECTOR_FAULT`** — start the literature search now; it gates
   Claim 4 and has the longest lead time of anything here.
6. **§2.3 / §2.4 coupling constants** — determine whether Claim 4 has a
   mechanism at all.
7. **§3 `TIER1_*`** — calibrate from Experiment A once it runs.

Items 3, 4 and 5 need no hardware and should start immediately, in parallel with
rig construction.
