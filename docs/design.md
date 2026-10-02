# FOAE — Locked Design

Status: **DRAFT.** Sections 3–5 are settled and implementable. Section 6 (claim
boundary) is a working position derived from `FOAE_Project_Structure.md`; it has
not been reconciled against `FOAE_Master_Build_Spec.md` or `claim_strategy.md`
and must be confirmed with the patent agent before it reaches the IDF.

This document supersedes the harness model in `FOAE_Project_Structure.md` §5.
See §7 for the deprecated interface.

---

## 1. What FOAE does

A DTC fires. FOAE decides **where the fault actually originated** — a degraded
component, a biased sensor, or a physical/electrical harness defect — and gates
the DTC accordingly: confirm it, suppress it as a harness artefact, or re-tag it
to the true origin.

The hard case, and the one that motivates the whole engine: a worn connector
produces sensor readings that look exactly like a failing component. Classical
diagnostics confirm the DTC and the workshop replaces a healthy part.

---

## 2. The two-tier harness model

Attribution is only as good as the physical model underneath it. FOAE models two
electrically distinct tiers.

**Tier 1 — the OBD-II J1962 connector** (pins 4/5/6/14/16). This is the
*diagnostic transport*. Every PID reaches the tester over the same CAN pair.
Wear here is **common-mode**: it degrades all six PIDs together.

**Tier 2 — the in-vehicle sensor harness.** Each sensor has its own connector
with local signal / ground / reference pins. Wear here is **specific**: it
degrades one sensor's signal path. Sensors sharing a ground or 5V reference rail
are coupled, so a rail fault degrades a *group*.

The consequence that drives everything below:

> Tier-1 wear carries **no attribution signal**. Because it moves every PID
> identically, it cannot distinguish sensor A from sensor B. It is not evidence
> *for* any hypothesis — it is a reason to distrust all of them.

This is why the old `propagate_wear(epdg, cwai)` interface is unsound (§7).

---

## 3. Tier 1 is a confounder gate, not an evidence source

CW-AI's output is used to decide **whether this session can be attributed at
all**, not to attribute it.

```python
def assess_tier1_confound(cwai: CWAIOutput) -> float:
    """Return confound score in [0, 1]. 0 = OBD-II link clean, 1 = fully confounded."""
```

**Computation.** A weighted combination of normalised per-pin error energy over
`cwai.per_pin_error_vector` and normalised worst-pin contact resistance, using
`TIER1_CONFOUND_W_PIN_ERROR` / `TIER1_CONFOUND_W_RESISTANCE`, with resistance
normalised against `TIER1_FULL_DEGRADE_OHM`.

**Gate semantics.**

| Score | Behaviour |
|---|---|
| `< TIER1_CONFOUND_CLEAN_FLOOR` | Tier-1 clean. Tier-2 attribution proceeds unmodified. |
| floor .. `TIER1_CONFOUND_THRESHOLD` | Degraded. Tier-2 proceeds, but epistemic uncertainty is inflated proportionally — which makes a UTP probe more likely to fire. |
| `> TIER1_CONFOUND_THRESHOLD` | Confounded. **Abstain.** No Tier-2 origin is asserted this session; the gate emits no CONFIRM. |

Abstention is a first-class outcome, not a failure. Asserting a confident origin
from a session whose transport is degraded is exactly the false-attribution mode
FOAE exists to prevent. Scenario 5 (false-suppression rate) must measure
abstention separately from misattribution.

---

## 4. Tier 2 is inverse inference, not forward propagation

Do not push evidence forward from a known defect to affected sensors. In the
field the defect is what's unknown. Instead, take the **observed anomaly
footprint** and ask which candidate fault would have produced it.

```python
def infer_tier2_origin(
    epdg: EPDG,
    anomalous_sensors: set[str],
    probe_response: ProbeResult | None,
    fault_type_prior: dict[str, float] | None = None,
) -> dict[str, float]:
    """Posterior over Tier-2 fault hypotheses, keyed by segment_id.

    `fault_type_prior` carries P(connector) / P(rail) from a waveform
    discriminator. Measured to raise rail-fault localisation 0.425 -> 0.900
    on an unseen harness configuration (docs/validation.md §7), so it is a
    first-class input, not an optional refinement.
    """
```

**Procedure.**

1. **Observe.** Build the footprint from `plausibility.anomalous_relationships`
   (which sensors violate their physics pairs) plus, if a probe fired,
   `probe_response.responding_sensors`.
2. **Enumerate.** Each hypothesis in §5 has an expected footprint derived from
   `SENSOR_CONNECTOR_MAP` and `SHARED_RAILS`.
3. **Score.** Set agreement between observed and expected, discarding anything
   below `FOOTPRINT_MATCH_FLOOR`.
4. **Prior.** Weight by `PRIOR_CONNECTOR_FAULT` / `PRIOR_RAIL_FAULT`.
5. **Resolve.** If the top two are within `TIER2_AMBIGUOUS_MARGIN`, return
   AMBIGUOUS and request a probe (§5.1).

The footprint is the observable; the fault is the latent cause. FOAE inverts.

---

## 5. Identifiability

Enumerated from `config.SHARED_RAILS` and `config.SENSOR_CONNECTOR_MAP`.
**10 hypotheses, 9 distinct footprints.**

| Hypothesis | Expected footprint | Size |
|---|---|---|
| `CONN:C_CKP` | engine_rpm | 1 |
| `CONN:C_MAP` | intake_map | 1 |
| `CONN:C_ECT` | coolant_temp | 1 |
| `CONN:C_VSS` | vehicle_speed | 1 |
| `CONN:C_MAF` | maf_rate | 1 |
| `RAIL:REF_5V_B` | vehicle_speed | 1 |
| `RAIL:REF_5V_A` | engine_rpm, intake_map | 2 |
| `RAIL:SENSOR_GND_B` | vehicle_speed, maf_rate | 2 |
| `RAIL:SENSOR_GND_A` | engine_rpm, intake_map, coolant_temp | 3 |
| `TIER1:OBD` | all six PIDs | 6 |

`control_module_voltage` appears in no Tier-2 footprint — it has no sensor-
harness connector. A footprint containing it is necessarily Tier-1. This makes
it the cleanest single discriminator between an OBD-II/power fault and any
sensor-harness fault.

### 5.1 One exact collision — an identifiability failure

> **⚠ CORRECTION REQUIRED — claim below is empirically FALSIFIED.**
> The assertion "no amount of passive observation separates them" was tested
> (`tests/test_identifiability.py`, 50 seeds) and is **false**. Passive
> *footprint* inference cannot separate the pair, but passive *waveform*
> inference separates it perfectly (LOO 1.000; 0.990 severity-matched), and
> outperforms the probe (0.930). The footprint collision is real; the
> inseparability conclusion drawn from it is not. This pair does not support
> the lead claim's necessity argument. See `docs/validation.md` §4. The text
> below is retained unedited pending a decision on reframing.
>
> **UPDATE 2026-08-05.** The §5.2 nesting pair was tested as a replacement and
> is **also falsified** (probe 0.560 vs passive 0.810 at matched severity), as
> is the latency argument (passive reaches 1.000 in 1 s; probe needs 2 s for
> 0.990). Per instruction, no third pair will be sought. The
> identifiability-necessity argument is withdrawn from the design pending bench
> evidence. `ProbeSignature` has been reduced to magnitude-only accordingly.
> See `docs/validation.md` §§4-7.

```
CONN:C_VSS   ==   RAIL:REF_5V_B      both -> {vehicle_speed}
```

`REF_5V_B` has exactly one sensor on it, so a fault on that 5V reference rail is
**footprint-indistinguishable** from a fault in the VSS connector itself. No
amount of passive observation separates them. Set agreement is identically 1.0
for both, and the `TIER2_AMBIGUOUS_MARGIN` check will always trip.

**This is the case the probe exists for.** The two faults have different
*perturbation signatures* even though they have identical footprints: a
reference-rail fault shifts the sensor's scale factor (magnitude-dominant
response, near-zero lag), while a connector contact fault produces intermittent
dropout (lag-dominant, polarity-unstable). `ProbeSignature.expected_lag_ms`,
`expected_polarity`, and `expected_magnitude_range` are precisely the fields that
separate them.

So: **Tier-2 identifiability is incomplete under passive observation, and the UTP
probe completes it.** That is a concrete, demonstrable statement of why the lead
claim is necessary rather than merely useful, and Scenario 3 (probe lift) should
be designed to measure exactly this pair.

Two options if the probe proves insufficient. Both are engineering changes, not
inference changes: move a second sensor onto `REF_5V_B` so the footprints
diverge, or drop `REF_5V_B` as a modelled rail. **Do not** resolve it by tuning
priors — that hides an identifiability failure behind a number.

### 5.2 Strict-subset nesting (18 pairs)

Every single-sensor footprint nests inside its rail's footprint, and every
Tier-2 footprint nests inside Tier-1's. E.g.
`CONN:C_MAP < RAIL:REF_5V_A < RAIL:SENSOR_GND_A < TIER1:OBD`.

This is **partial-observation ambiguity**, not a modelling error: an early-stage
rail fault that has only degraded one sensor so far is genuinely
indistinguishable from a connector fault at that instant. It resolves three ways
— severity (a rail fault degrades its group as it progresses), the
`PRIOR_CONNECTOR_FAULT` prior, and `T_CONFIRM_SESSIONS` hysteresis, which lets
the footprint grow across sessions before committing.

Nesting is why the gate is multi-session. A single session cannot always
distinguish a connector fault from a nascent rail fault, and should not pretend
to.

---

## 6. Claim boundary

**Working position — confirm with patent agent before IDF submission.**

**Hierarchy revised 2026-08-05** following the falsification of the
identifiability-necessity argument (`docs/validation.md` §§4-7). UTP was the
lead claim; it is now dependent. The reordering is evidence-driven.

### Claim 1 (LEAD, independent) — Tier-1 confounder gate with abstention

Representing the diagnostic transport (Tier 1) and the sensor harness (Tier 2)
as electrically distinct, and using transport-tier connector wear as a
**confounder that suppresses attribution** rather than as evidence for it.
When Tier-1 wear exceeds threshold, the system **abstains**: it asserts no
Tier-2 origin and emits no CONFIRM.

**Why this leads.** It is untouched by the falsification — nothing in §§5.1-5.2
bears on it. Its two supports are structural rather than empirical:

- **Prior art leaves this to a human.** US 5,491,631 and comparable workshop
  practice require a *technician* to judge whether connector/link integrity is
  good enough for the diagnostic reading to be trusted. Claim 1 automates that
  judgement and makes it a machine precondition on attribution.
- **`control_module_voltage` bypasses every sensor harness.** It is the ECU's
  own supply measurement, so it has no Tier-2 connector at all. A fault
  footprint containing it is necessarily Tier-1. This is a **structural
  property of J1962 and of what the PID measures — not a modelling
  assumption**, and it holds regardless of how fretting physics is simulated.

**Technical effect (Section 3(k)):** abstention suppresses a DTC confirmation
that would otherwise be issued, changing what the ECU's DEM records and what
the workshop replaces. The output is a changed vehicle state, not a report.

> **⚠ TESTED 2026-08-05 — VERDICT UNDETERMINED, PENDING ONE MEASUREMENT.**
>
> **Sensitivity update.** The falsification below was a point estimate at an
> unaudited parameter. Swept, it reverses: Claim 1 **beats** the free Tier-2
> rule whenever the spurious-anomaly gain is below ≈0.035 (≈0.10 with silent
> masking). The falsification used **0.50 — about 14x above break-even**.
> Claim 1 is **not dead; it is undetermined** until that rate is measured.
> Bench Experiment A now targets it directly. See `validation.md` §9.1.
>
> **The original point-estimate result follows.**
> `tests/test_confound_gate.py`, 1500 sessions. Three of four propositions
> hold: Tier-1 wear does severely degrade Tier-2 attribution (0.601 → 0.055
> across the wear range), the confound score detects wear through CW-AI noise
> (AUC 1.000), and gating does reduce misattribution (0.743 → 0.536).
>
> **But a Tier-2-only heuristic beats it at identical coverage.** Simply
> abstaining when no hypothesis explains the observed footprint — using **no
> CW-AI input whatsoever** — gives error **0.411 at coverage 0.437**, versus
> the Tier-1 gate's **0.536 at coverage 0.433**. At matched coverage ~0.24 the
> no-CW-AI rule still wins (0.238 vs 0.256).
>
> Tier-1 wear confounds attribution *by* producing spurious anomalies, and the
> Tier-2 rule detects that corruption by its consequence rather than its cause
> — more cheaply and more accurately. **An examiner will find this design-around
> immediately.** Claim 1 as currently framed is not defensible as lead.
>
> *Caveat:* the model gives Tier-1 wear only one consequence — spurious
> anomalies — which is exactly what the Tier-2 rule detects. If real transport
> wear also biases values *without* breaking footprint consistency, Tier-1
> information would add more. That is a bench-rig question, and it is the only
> route by which Claim 1 recovers. See `docs/validation.md` §9.

### Claim 2 (independent) — Tier-2 footprint attribution over the EPDG

Inverse inference over the electrical topology: match the observed anomaly
footprint against the expected footprint of each candidate connector/rail
fault, where candidates and their footprints are derived from **harness design
data** rather than learned from fault examples.

**Tested 2026-08-05 — the generalisation premise was FALSIFIED; the claim
survives on different grounds.** See `docs/validation.md` §7.

A waveform discriminator trained on configuration A transfers to a structurally
different configuration B at 0.882 — as well as it performs in-distribution
(0.867), and better than footprint matching on the same task (0.791). The
discriminating physics (rail-coupling) is topology-independent, so **it does
not need retraining when the harness changes.** Any claim language asserting
that waveform methods fail to generalise is unsupported and must not be filed.

What survives is a **capability** difference, not a generalisation one:

- The waveform discriminator's label space is configuration A's segments. It
  **cannot name a segment in B at all** — there is no principled mapping.
- Footprint matching names a B segment from **design data alone**, with zero
  training examples from B: **0.791 against 0.091 chance** over 11 hypotheses.

Claim 2 must therefore be drafted as: *localising a fault to a specific named
harness segment in a harness for which no fault training data exists, using
topology derived from design data.* Not as: *generalising better than learned
methods.*

**Two qualifications that must reach the patent agent.**

1. **Topology's contribution is confined to shared-rail faults.** With rail
   groupings randomly shuffled, connector-fault accuracy is unchanged (1.000)
   while rail-fault accuracy collapses from 0.425 to 0.075. Connector
   hypotheses are singletons resolved by the prior, not by topology. Correct
   topology is worth +0.127 overall — real, but concentrated in the 36% of
   cases that are rail faults. Claim 2's value proposition is about
   **shared-rail** faults specifically.
2. **The methods are complementary, not competing.** Feeding the zero-shot
   transferred waveform type prediction into the footprint attributor raises
   rail-fault localisation from 0.425 to **0.900** (overall 0.791 → 0.877) with
   no training data from B. This is the best configuration measured. The EPDG
   should **consume** a waveform-derived fault-type prior rather than compete
   with one, and `infer_tier2_origin` should take that prior as an argument
   (§4 requires updating).

### Claim 3 (DEPENDENT on Claim 2) — diagnostic protocol as actuation channel

When footprint inference is ambiguous, apply a perturbation to resolve it **by
modulating diagnostic request cadence on the existing OBD-II/UDS link**. No
signal is injected into any sensor path and no additional hardware is required.
Classical active fault diagnosis assumes an actuator or auxiliary input into
the plant; here the diagnostic protocol *is* the actuator.

**Explicitly NOT claimed as independently novel:**

- **The uncertainty trigger.** Initiating a test when model uncertainty crosses
  a threshold is ordinary engineering and is vulnerable to an obviousness
  rejection. It is claimed only as a limitation on when Claim 3 fires.
- **The safety envelope.** Excluded-state gating, rate limits, watchdogs, and
  audit logs are standard automotive safety practice. Also obviousness-
  vulnerable. Claimed only as a limitation.
- **Active fault diagnosis as a concept.** Mature field — Nikoukhah 1998,
  Šimandl & Punčochář 2009. See `docs/prior_art.md` §4.

The actuation channel is the only element of Claim 3 with a credible novelty
argument, and Claim 3 should be drafted so that it survives only on that point.

**Technical effect (Section 3(k)):** the gate acts on the ECU's DEM — confirm,
suppress, or re-tag a DTC. The output is a changed vehicle state, not a report.

### Not claimed

- **Generic sensor-vs-component fault discrimination.** Classical parity-space
  FDI and analytical-redundancy residual generation own this outright, going
  back to Chow & Willsky. FOAE's plausibility residuals are a *standard* parity
  check and must be described as prior art in the IDF, not as contribution.
- **Connector wear detection per se** — that is the already-filed CW-AI patent,
  consumed here as a black box.
- **MC-Dropout / conformal prediction as UQ methods.** Both are published
  technique. Claimed only in combination, as the *trigger* for mechanism 1.
- **CAN intrusion or anomaly detection.** Different problem; the HCRL/ROAD
  datasets are used for realism, not to claim IDS novelty.

### Claim 4 (CANDIDATE) — transferred type prior over a topology-derived hypothesis space

**Mechanism.** A fault-type classifier (connector-local vs shared-rail) is
trained on waveform features from **one** harness configuration. Its output — a
probability over two *types* — re-weights a hypothesis posterior whose
candidates and footprints are derived from a **different** harness's design
data. The classifier is never retrained on the target harness.

**Why this is not a routine ensemble.** Ensembling combines models that share an
output space and vote. These two do not:

| | Output space | Source | Transfers? |
|---|---|---|---|
| Waveform classifier | fault **type** (binary) | learned from fault examples | yes — physics is topology-independent |
| Footprint attributor | **named segment** (11 classes on config B) | harness design data | n/a — constructed, not learned |

Neither can produce the other's output. The classifier cannot name a segment in
a harness it has never seen; the attributor cannot judge type from a footprint
that is consistent with both. The combination is a **type-to-identity lift**:
information that exists only as a type is projected onto an identity space that
exists only as topology. That asymmetry is the candidate inventive step.

**Measured support and its limits.** Type prior transfers zero-shot at 0.882
(config B) and 0.870 (config C). But the headline "0.877 overall" figure is
**mix-dependent and does not generalise**:

| | overall | connector | rail |
|---|---|---|---|
| **Config B** footprint | 0.791 | 1.000 | 0.425 |
| **Config B** hybrid | **0.877** | 0.864 | **0.900** |
| delta | +0.086 | **−0.136** | +0.475 |
| **Config C** footprint | 0.800 | 1.000 | 0.500 |
| **Config C** hybrid | **0.800** | 0.825 | **0.762** |
| delta | **+0.000** | **−0.175** | +0.262 |

The rail-fault gain reproduces on a third configuration (+0.262). The **overall
gain does not** — on config C it is exactly zero. The hybrid always *damages*
connector-fault accuracy, which footprint-alone gets perfect, and whether the
trade nets positive depends entirely on the connector/rail mix.

Two further fragilities (`tests/test_hybrid_claim4.py`):

- **Break-even prior error is ~15%; the actual transferred classifier sits at
  13%.** There is almost no margin. At 20% prior error the hybrid is *worse*
  than footprint alone (0.775 vs 0.800).
- **The gain requires near-hard weighting** (w ≥ 0.8). At w ≤ 0.7 there is no
  gain at all. It needs the prior to be trusted almost absolutely, which is
  precisely what its 13% error rate does not justify.

**Verdict: weakened, not falsified.** Claim 4 should be drafted narrowly — as a
mechanism applied *only to footprints ambiguous between a connector and a
partially-manifested rail fault*, not as a general improvement. That
restriction is currently **untested**.

**The obviousness attack I would make as examiner:** *"Applying a classifier
output as a prior in Bayesian inference is textbook. The applicant has combined
a known classifier with known Bayesian updating and obtained a result that, on
their own third configuration, is no better overall than the Bayesian component
alone."*

**What answers it:** not the accuracy numbers — they are too weak. Only the
output-space asymmetry: that the transferred quantity is *unnameable* in the
target harness by the learned model, and the naming is *unlearnable* from the
target harness because no fault data exists for it. If the claim cannot be
drafted so that this asymmetry is the inventive step, Claim 4 should be dropped
rather than filed as an ensemble.

### 6.1 Probe necessity is UNSUPPORTED BY SIMULATION

Recorded so it cannot be quietly reasserted.

Two candidate fault pairs were constructed to demonstrate that active probing
resolves an ambiguity passive observation cannot. **Both were falsified**, and
the latency fallback was falsified too:

| Test | Passive | Probe |
|---|---|---|
| §5.1 pair (C_VSS vs REF_5V_B) | 0.990 | 0.990 |
| §5.2 pair (C_VSS vs early GND_B), severity-matched | 0.810 | 0.560 |
| Latency to match probe accuracy | 1.000 @ 1 s | 0.990 @ 2 s |

**No simulated condition has been found in which the probe outperforms passive
observation.** The IDF must not assert probe necessity on simulation evidence,
and no third pair is to be sought.

This does not falsify the probe's *utility* and says nothing about real
hardware — the fretting models are unvalidated. It means any empirical case
must come from the bench rig.

**Reinstatement condition.** Probe necessity may be reasserted only on bench
measurement showing, on physically fretted contacts and at matched fault
severity, that probe-assisted discrimination exceeds the best passive
discriminator given equal observation time — with the passive baseline allowed
its full feature set, including residual magnitude. Simulation results do not
satisfy this condition.

`ProbeSignature` has been reduced to magnitude-only on the same evidence: lag
(AUC 0.53-0.68) and polarity (chance for both classes) were unsupported.
`probe/signatures.py` ships with an empty library by design.

### 6.2 The boundary to defend

Prior art discriminates fault *classes* from passive
residuals. FOAE localises fault *origin* to a harness segment, and when passive
evidence is provably insufficient (§5.1), actively intervenes to disambiguate.
The intervention is the invention.

---

## 7. Deprecated interface

`propagate_wear(epdg: EPDG, cwai: CWAIOutput) -> dict[str, float]`
(`FOAE_Project_Structure.md` §5, `epdg/propagate.py`) — **do not implement.**

Unsound under the corrected physics: `CWAIOutput` is Tier-1 only, and Tier-1
wear is common-mode. Any propagation from it necessarily weights all six sensors
identically, so the returned `dict[str, float]` is a constant map carrying zero
discriminative information. Worse, downstream code would read it as per-sensor
evidence and produce confident attributions from a signal that contains none.

Replaced by `assess_tier1_confound` (§3) and `infer_tier2_origin` (§4).
