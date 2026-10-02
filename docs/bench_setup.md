# FOAE — Bench Rig Setup and Pre-Registered Protocols

---

> # ⚠ STOP — READ BEFORE TOUCHING A DEGRADED CONTACT
>
> ## A standard multimeter will DESTROY a Tier-B specimen on first contact.
>
> A DMM in resistance mode applies several hundred millivolts and milliamps of
> test current. On a fretted contact this **fritts** it: the applied voltage
> electrically breaks down the oxide film at the contact interface, permanently
> collapsing the resistance to a low value.
>
> **The specimen is not damaged in a way you can see. It reads "fine" afterwards
> — because you erased the fault you spent days growing.** There is no recovery.
> The specimen must be discarded and regrown (§4, days to weeks).
>
> ### Rules
>
> 1. **Never** put a DMM in Ω mode across a Tier-B contact.
> 2. Measure only via the four-wire dry-circuit method (§3.2):
>    **< 20 mV open-circuit, ≤ 1 mA test current.**
> 3. Verify your fixture's open-circuit voltage **on the scope** before it
>    touches a specimen. Verify it again after any change to the setup.
> 4. Practise the entire measurement procedure on Tier-A hardware and on
>    sacrificial specimens first.
> 5. Label every Tier-B specimen. Store it mated and physically separated from
>    general-purpose test gear.
>
> Continuity beeps, diode test, and auto-ranging Ω all violate rule 1.
> **If in doubt, do not probe it.**

---

**Priority document.** Simulation has returned negatives on Claims 1, 3 and 4.
The bench rig is now the only path by which Claims 1 and 3 can recover, and the
only validation any fault model in this project has ever had.

**The two protocols in §5 and §6 have pass/fail thresholds fixed BEFORE any
measurement is taken.** They are written so that a negative result is
unambiguous. Do not adjust a threshold after seeing data — record the
adjustment and the reason instead, and mark the run exploratory.

---

## 1. What the rig must be able to do

| Capability | Needed for |
|---|---|
| Emit OBD-II PIDs over CAN from a controllable ECU stand-in | everything |
| Poll PIDs at controllable cadence (the probe actuation channel) | Claim 3 |
| Inject **controlled static** contact resistance into a chosen conductor | Claims 1, 2 |
| Inject **intermittent** contact behaviour | Claim 3 |
| Produce **genuinely fretted** contacts, not emulated ones | Claim 3 (see §1.1) |
| Measure contact resistance to milliohm accuracy without disturbing it | all |
| Separate a Tier-1 (J1962) injection point from Tier-2 (sensor harness) points | Claim 1 |

### 1.1 The methodological constraint that governs the whole rig

**A MOSFET or relay emulating intermittent contact CANNOT test Claim 3.**

Claim 3 asks whether real contact physics responds to electrical load
modulation. If the intermittency is produced by a switch we command, the
response to load is whatever we programmed, and the experiment is circular in
exactly the way the simulation already was.

The rig therefore has **two fidelity tiers**:

- **Tier A — emulated** (MOSFET / relay / decade box). Cheap, fast, repeatable.
  Valid for: pipeline integration, detector calibration, Claim 2 topology work,
  and rehearsing the protocols. **Not valid as evidence for Claim 3.**
- **Tier B — real degraded contacts** (§4). Slow and variable, and the only
  thing that can satisfy Claim 3's reinstatement condition or Claim 1's
  recovery condition.

Build Tier A first to debug the protocol. Run Tier B for the record.

---

## 2. Bill of materials (sourceable in India)

Suppliers: Robu.in, ElectronicsComp, Sunrom, Element14 India, Amazon.in.
Indicative prices in INR, mid-2026.

### Core — two CAN nodes

| Item | Qty | Notes | ~INR |
|---|---:|---|---:|
| ESP32-WROOM-32 DevKit v1 | 2 | Integrated TWAI (CAN 2.0B) controller. One node = ECU simulator, one = tester. | 500 ea |
| SN65HVD230 CAN transceiver breakout | 2 | 3.3 V — matches ESP32 directly, no level shifting. Preferred. | 150 ea |
| *Alt:* STM32F103C8T6 "Blue Pill" | 2 | bxCAN peripheral; needs MCP2551 (5 V) plus level shifting. Use only if ESP32 TWAI proves limiting. | 250 ea |
| *Alt:* MCP2551 transceiver | 2 | 5 V. Pair with STM32 only. | 90 ea |
| 120 Ω 1% termination resistors | 4 | Two used, two spare. | 5 ea |

**Take the ESP32 + SN65HVD230 path.** Single 3.3 V rail, no level shifting, and
ESP32 TWAI gives direct programmatic control of transmit cadence — which *is*
the probe actuation channel under test.

### Fault injection

| Item | Qty | Notes | ~INR |
|---|---:|---|---:|
| Decade resistance box, 0.1 Ω–10 kΩ, 0.1 Ω steps | 1 | **Primary static-resistance injector.** | 2,500 |
| Reed relay, 5 V, <1 ms switching | 4 | Intermittent emulation, Tier A only. | 60 ea |
| N-MOSFET AO3400 / IRLZ44N + gate driver | 4 | Fast intermittent emulation to ~1 kHz, Tier A only. | 30 ea |
| Precision resistors 0.1 / 0.22 / 0.47 / 1 / 2.2 / 4.7 / 10 Ω, 1%, 1 W | 3 sets | Known-value checks and four-wire calibration. | 10 ea |
| MCP41010 / MCP41100 digital pot | 2 | **See warning.** | 150 ea |

> **Digital-pot warning.** MCP41xxx parts have wiper resistance of roughly
> 50–125 Ω and a minimum step far above the 0.1–10 Ω range that matters for
> contact degradation. **They cannot produce realistic contact resistance.**
> Buy them only for high-impedance sensor-divider emulation. Use the decade box
> wherever resistance value is the independent variable.

### Measurement

| Item | Qty | Notes | ~INR |
|---|---:|---|---:|
| Hantek 6022BE USB scope, 20 MHz 2-ch | 1 | Adequate for CAN bit timing and dropout capture. | 5,500 |
| DMM with four-wire (Kelvin) mode, or bench DMM | 1 | If unavailable, use the §3.2 current-source method. | 3,000+ |
| Precision current source, 1 mA / 10 mA (or LM334 + trim) | 1 | Four-wire measurement at dry-circuit levels. | 400 |
| Kelvin clip test leads | 1 set | Four-wire connection to pins. | 800 |
| Bench PSU 0–30 V 0–3 A, current limited | 1 | 12 V rail. Current limiting is a safety requirement. | 3,000 |

### Harness and mechanical

| Item | Qty | Notes | ~INR |
|---|---:|---|---:|
| J1962 (OBD-II) male + female connector pair | **6** | Five are sacrificial — Tier B destroys contacts. | 250 ea |
| J1962 breakout board with screw terminals | 1 | Per-pin access. | 700 |
| Automotive 3-pin / 4-pin sensor connectors | 8 | Tier-2 sensor connectors. | 60 ea |
| 0.5 mm² automotive wire, assorted | 10 m | Harness construction. | — |
| Perfboard, headers, ferrules, heatshrink | — | — | 600 |
| Eccentric-mass vibration motor (10–50 Hz) | 1 | Tier-B fretting induction (§4.2). | 200 |
| Hot-air station or thermal chamber (or hair dryer + thermocouple) | 1 | Tier-B thermal cycling. | varies |

**Indicative total: ₹25,000–35,000**, depending on DMM and thermal equipment.

---

## 3. Wiring

### 3.1 Topology

```
   ┌──────────────┐                              ┌──────────────┐
   │ ESP32 #1     │                              │ ESP32 #2     │
   │ ECU SIM      │                              │ TESTER       │
   │ emits 6 PIDs │                              │ polls PIDs,  │
   │ incl. 0x42   │                              │ cadence under│
   └──┬────────┬──┘                              │ program ctrl │
      │CTX  CRX│                                 └──┬────────┬──┘
   ┌──▼────────▼──┐                              ┌──▼────────▼──┐
   │ SN65HVD230   │                              │ SN65HVD230   │
   └──┬────────┬──┘                              └──┬────────┬──┘
      │CANH CANL│                                   │CANH CANL│
      │         │                                   │         │
      │      ┌──┴───────────── TIER-1 INJECTION ────┴──┐      │
      └──────┤  J1962 pair (6/14) + decade box / relay ├──────┘
             │  ** Claim 1 experiment injects HERE **  │
             └───────────────────┬─────────────────────┘
                           120 Ω │ 120 Ω  (both ends)
                                 │
   ── TIER-2 INJECTION (sensor side of ECU SIM) ───────────────
   Analog sensor emulation into ESP32 #1 ADC inputs, each via
   its own 3-pin connector: SIGNAL / GND / 5V-REF.
   Shared rails wired per config.SHARED_RAILS so one injected
   fault affects a GROUP:
        REF_5V_A -> ckp, map          GND_A -> ckp, map, ect
        REF_5V_B -> vss               GND_B -> vss, maf
   ** Claim 2 topology experiments inject HERE **
```

**The Tier-1 / Tier-2 separation is the physical embodiment of the design.**
Tier-1 injection sits between the two transceivers, degrading the transport
common-mode. Tier-2 injection sits on individual sensor conductors, degrading
one sensor or one rail group.

### 3.2 Four-wire (Kelvin) contact-resistance protocol

Contact resistances of interest are 0.05–10 Ω. Test-lead and connector
resistance is 0.1–0.5 Ω, so **two-wire measurement is useless here.**

```
        ┌─────────── FORCE (outer pair) ───────────┐
        │  I = 1 mA constant                       │
        │                                          │
   ─────●══════[ CONTACT UNDER TEST ]══════●───────
        │                                  │
        └──── SENSE (inner pair) ──────────┘
             V measured;  R = V / I
```

**Procedure.**

1. Attach force leads *outside* the contact pair; attach sense leads directly
   to the pin barrels, inside the force connection. Sense leads must carry no
   force current.
2. **Dry-circuit conditions — the critical constraint.** Limit open-circuit
   voltage to **< 20 mV** and test current to **≤ 1 mA**. Higher voltage or
   current *fritts* the contact: it electrically breaks down the fretting oxide
   film, permanently lowering measured resistance and destroying the very
   degradation being measured. A standard DMM in ohms mode typically applies
   far more than this and **must not be used** on a fretted contact you intend
   to keep.
3. Take 10 readings at 1 s intervals. Record **mean, standard deviation, min,
   max**. For fretted contacts the *variance* is as diagnostically meaningful
   as the mean, and is the quantity every intermittency model here depends on.
4. Zero the fixture against a 0.1 Ω 1% reference before each session; log the
   offset.
5. Record ambient temperature. Contact resistance is temperature-sensitive and
   Tier-B protocols involve thermal cycling.

**Log every measurement with:** connector serial, pin number, cycle count,
timestamp, temperature, and the 10-sample statistics. This log is the dataset
(see `claim_strategy.md` §7).

---

## 4. Producing genuinely degraded contacts (Tier B)

Required for Claims 1 and 3. Emulation cannot substitute (§1.1).

### 4.1 Method A — mating-cycle wear (simplest; start here)

1. Take a sacrificial J1962 pair. Record four-wire resistance on pins 6 and 14
   at cycle 0.
2. Perform partial mate/unmate cycles — insert to ~70% of full depth, withdraw.
   Partial insertion concentrates wear on a small contact area.
3. Measure every 50 cycles, to 500 cycles.
4. **Expect** resistance to rise and, more importantly, **variance** to rise. A
   contact whose mean is stable but whose standard deviation has grown by an
   order of magnitude is the intermittent regime the models assume.

### 4.2 Method B — fretting by vibration under thermal cycling

Fretting corrosion is what the design actually models: micro-motion at the
contact interface, oxide build-up, intermittent conduction.

1. Mate the connector; secure both halves to a rigid base leaving ~1 mm
   compliance.
2. Attach the eccentric-mass motor to one half. Run at 10–50 Hz.
3. Cycle temperature 25 °C ↔ 80 °C, ~30 min per cycle. Differential expansion
   plus vibration produces micro-motion.
4. Run 20–100 cycles, measuring four-wire resistance (dry-circuit) at each
   cycle boundary **without unmating**.
5. Optional acceleration: brief salt/humidity exposure before cycling. Document
   if used — it changes the corrosion chemistry.

### 4.3 Acceptance criterion for a usable Tier-B specimen

A specimen is usable when, at dry-circuit conditions, it shows
**σ(R) / mean(R) > 0.2 across 10 readings** — genuine intermittency rather than
a stable elevated resistance.

Log specimens that fail this. A rig that only produces stable-resistance
degradation is itself a finding: it would mean the intermittent regime central
to `simulator/intermittent.py` does not occur under these conditions, which
would undercut the fault models independently of Claims 1 and 3.

---

## 5. EXPERIMENT A (pre-registered) — Claim 1 recovery

### 5.1 The question

Simulation killed Claim 1 because a Tier-2-only rule — *"abstain when no
hypothesis explains the observed footprint"* — beat the Tier-1 confounder gate
at equal coverage while requiring no connector-wear input at all
(`validation.md` §9). That happened because the model gave Tier-1 wear a single
consequence: spurious anomalies, which the free rule detects.

**Claim 1 recovers if and only if real transport-path wear ALSO biases PID
values while leaving footprint consistency intact.** Such a session is silently
wrong and invisible to the free rule, and only Tier-1 information would catch
it.

### 5.2 Protocol

1. Prepare 5 Tier-B J1962 specimens at graded wear (§4), plus 1 pristine
   control. Record dry-circuit resistance for each.
2. Install each at the Tier-1 injection point (§3.1). With **no Tier-2 fault
   present**, capture 50 sessions of all six PIDs, 120 s each.
3. Repeat with a known Tier-2 fault injected (single connector fault on VSS),
   50 sessions per specimen.
4. For every session compute:
   - **Bias** — per-PID mean deviation from the pristine-control mean, in units
     of the pristine per-PID standard deviation.
   - **Footprint consistency** — does an anomalous-sensor set exist that no
     Tier-2 hypothesis explains? (the free rule's abstention trigger)
   - **Attribution outcome** under footprint-only attribution.
5. **Blind the analyst to specimen wear level during scoring.**

### 5.3 Pre-registered pass/fail

Let *S* = sessions at high Tier-1 wear (top two specimens) that are
**footprint-consistent** — the sessions the free rule would accept.

| Outcome | Criterion | Verdict |
|---|---|---|
| **RECOVER** | Misattribution rate within *S* exceeds that at pristine/low wear by **≥ 0.15 absolute**, AND **≥ 30%** of high-wear sessions are footprint-consistent, AND the Tier-1 confound score separates high- from low-wear sessions at **AUC ≥ 0.75** | Claim 1 revives: Tier-1 carries information the free rule cannot see |
| **INCONCLUSIVE** | Misattribution difference 0.05–0.15, or footprint-consistent fraction 10–30% | Report as inconclusive. Do not file Claim 1 |
| **DEAD** | Misattribution difference **< 0.05**, or **< 10%** of high-wear sessions footprint-consistent | Claim 1 confirmed dead on hardware. Withdraw; recommend the Tier-2 consistency rule instead |

**All three RECOVER conditions must hold.** The AUC condition matters
independently: if the confound score cannot detect the wear, the mechanism has
no trigger even when the confounding is real.

### 5.4 The primary quantitative target — measure this above all else

The sensitivity sweep (`validation.md` §9.1) reduced Claim 1's entire fate to
one measurable ratio. Report both quantities explicitly:

- **Spurious rate** — probability that a sensor *unrelated to the injected
  Tier-2 fault* reads anomalous, per unit of Tier-1 wear.
- **Silent-mask rate** — probability that a sensor *which should be anomalous*
  is attenuated below the detection threshold, per unit of Tier-1 wear.

| Measured spurious rate | Consequence |
|---|---|
| **< 0.035** | Claim 1 **wins** against the free Tier-2 rule. File it |
| 0.035 – 0.10 | Depends on silent-mask rate; report both and re-run the sweep with measured values |
| **> 0.10** | Claim 1 loses at any silent-mask rate. Withdraw |

Break-even is ≈0.035 with no silent masking, rising to ≈0.10 at maximal silent
masking. **The simulation assumed 0.50 — roughly 14x above break-even — and
that single unmeasured number produced the original falsification.**

**Measurement.** From §5.2 step 4: across sessions at known Tier-1 wear with a
known single-sensor Tier-2 fault injected, count (a) sensors flagged anomalous
that are not on the injected fault's path, and (b) injected-path sensors that
fail to flag. Normalise each by wear level. No blinding issue — these are
counts, not judgements.

---

## 6. EXPERIMENT B (pre-registered) — Claim 3 reinstatement

### 6.1 The question

Two fault pairs and a latency argument were falsified in simulation; passive
observation beat the probe in every configuration (`validation.md` §§4–6). The
reinstatement condition in `design.md` §6.1 requires bench evidence at matched
severity against a full-featured passive baseline.

**Tier-A emulation is invalid here (§1.1). Tier-B specimens only.**

### 6.2 Protocol

1. Prepare ≥ 30 Tier-B specimens meeting the §4.3 intermittency criterion, in
   two groups:
   - **Group C** — degradation on a single sensor's own connector.
   - **Group R** — degradation on a shared rail conductor serving two sensors.
2. **Severity matching (mandatory).** Before any discrimination test, measure
   the residual RMS each specimen induces on its affected PID. Discard
   specimens until the two groups' residual-RMS distributions match
   (two-sample KS test, p > 0.2). Unmatched severity is what invalidated the
   simulated pair-B result; uncontrolled here, the experiment is void.
3. **Passive arm.** Capture 120 s per specimen at normal polling. Compute the
   **full** feature set: residual magnitude/std, kurtosis, lag-1
   autocorrelation, high-frequency ratio, rail-coupling correlation. The
   baseline **must** include residual magnitude — excluding it was the
   indefensible restriction that made the simulated latency argument appear to
   work.
4. **Probe arm.** Capture 2 s per specimen with tester polling cadence
   modulated per `probe/perturbation.py`. Extract signed and envelope response
   features.
5. Classify Group C vs Group R by leave-one-out on each arm.
6. **Blind the analyst to group membership** during feature extraction and
   classification.

### 6.3 Pre-registered pass/fail

| Outcome | Criterion | Verdict |
|---|---|---|
| **REINSTATE** | Probe LOO exceeds best passive LOO by **≥ 0.10 absolute**, at matched severity, with passive granted **equal or greater** wall-clock observation time, over **≥ 30 specimens** | Probe necessity reinstated; Claim 3 may assert it |
| **UTILITY ONLY** | Probe LOO within ±0.10 of passive | Probe works but is not necessary. Claim 3 stands **only** on the actuation-channel argument, as now |
| **DEAD** | Probe LOO **more than 0.10 below** passive | Consistent with simulation. Drop all probe-discrimination claim language; retain the actuation channel only if VW '665 clears |

Independently: if lag or polarity features reach **AUC ≥ 0.75** on real
contacts, the corresponding `ProbeSignature` fields may be reinstated — but only
with the measurement recorded alongside (see `foae/types.py`).

---

## 7. Build order

1. Tier-A rig; two CAN nodes talking; six PIDs flowing including 0x42.
2. Four-wire fixture; validate against precision resistors; confirm dry-circuit
   compliance with the scope.
3. Rehearse both protocols end-to-end on Tier A. **Expect Experiment B to be
   uninformative on Tier A** — that is the point of §1.1, and confirming it is a
   useful check that the protocol is not self-fulfilling.
4. Tier-B specimen production (§4). Slowest step; start early and in parallel.
5. Experiment A, then Experiment B.
6. Log everything per §3.2. The log is the dataset.

---

## 8. Safety and integrity

- Current-limit the bench PSU. A shorted J1962 pin 16 to ground is a fire risk.
- **Never connect this rig to a real vehicle.** It emits CAN traffic that would
  be unsafe on a live bus, and the probe deliberately perturbs polling cadence.
- **Do not adjust a §5.3 or §6.3 threshold after seeing data.** If a threshold
  proves wrong, record the original, the change, and the justification, and
  mark the run exploratory. The value of this record is that its criteria were
  fixed in advance.
