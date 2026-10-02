# FOAE — Claim Strategy and Falsification Record

**Prepared for the patent agent. Assumes no prior familiarity with the project.**
Date: 2026-08-05

---

## 0. Read this first

This document reports **more negative results than positive ones**. That is
deliberate. Every mechanism proposed for this filing has been subjected to a
falsification test designed to break it, and most broke in some respect. The
record is presented in full so that claim drafting proceeds from what actually
survived rather than from the original design intent.

**Three things you should know before reading further:**

1. **No result here has been validated against physical hardware.** All
   evidence is simulation, using fault models written from physical reasoning
   with no measurement behind them. The bench rig does not yet exist. A
   negative result from this simulator is reasonably trustworthy (there was
   every incentive to produce a pass); a *positive* one proves little.
2. **The claim hierarchy has been reordered once already**, after the original
   lead claim's supporting argument was falsified. The replacement lead has now
   also been tested and has serious problems (§3.1).
3. **The project's authoritative specification document does not exist.** The
   mechanisms described below were inferred from a repository structure
   document. **No author has ratified this claim set.** This should be resolved
   before drafting.

---

## 1. What the invention does

A diagnostic trouble code fires. Conventional practice confirms it and the
workshop replaces the indicated part. FOAE instead attributes the fault to its
**origin** — a degraded component, a biased sensor, or a physical/electrical
harness defect — and then confirms, suppresses, or re-tags the DTC.

The motivating failure mode: a worn wiring connector produces readings that
look exactly like a failing component, causing replacement of a healthy part.

**Technical effect for Section 3(k):** the system acts on the ECU's Diagnostic
Event Manager. The output is a changed vehicle state, not a report or a
computation result.

### The two-tier physical model (foundational, not itself claimed)

- **Tier 1** — the OBD-II J1962 connector. The *diagnostic transport*. All PIDs
  traverse one CAN pair, so wear here is **common-mode**: it degrades every
  reading together and carries no per-sensor information.
- **Tier 2** — the in-vehicle sensor harness. Each sensor has its own connector;
  sensors sharing a ground or 5V-reference rail are electrically coupled, so a
  rail fault degrades a *group*.

An earlier design split sensors across J1962 pins. That was physically invalid
and was corrected. The correction eliminated one planned interface entirely
(`propagate_wear`), which would have produced confident attributions from a
signal containing no information.

---

## 2. Claim set as it currently stands

| # | Mechanism | Status | Evidence |
|---|---|---|---|
| 1 | Tier-1 confounder gate with abstention | **UNDETERMINED** — one bench measurement decides it | §3.1 |
| 2 | Tier-2 footprint attribution over harness topology | **Supported, narrower than hoped** | §3.2 |
| 3 | Diagnostic protocol as probe actuation channel | **Necessity ROBUSTLY falsified; channel argument intact** | §3.3 |
| 4 | Transferred type prior over topology hypothesis space | **Weakened; rail-faults only** | §3.4 |

**Blunt summary: there is currently no mechanism with strong, reproduced,
simulation-supported evidence.** Claim 2 is the most defensible. Claim 3's
distinguishing feature is structural rather than experimental and does not
depend on the falsified evidence.

---

## 3. Claim-by-claim assessment

### 3.1 Claim 1 — Tier-1 confounder gate

**Mechanism.** Treat OBD-II connector wear as a *confounder that suppresses
attribution* rather than as evidence for any hypothesis. Above a threshold the
system **abstains**: it asserts no origin and issues no DTC confirmation.

**What supports it.**
- Structural, independent of fault modelling: `control_module_voltage` is the
  ECU's own supply measurement and has **no Tier-2 connector at all**, so a
  fault footprint containing it is necessarily Tier-1. This is a property of
  J1962 and of what the PID measures.
- Prior art (US 5,491,631 and comparable workshop practice) leaves the
  equivalent judgement — *is the connection good enough to trust this reading?*
  — to a human technician. Claim 1 automates it as a machine precondition.
- Tested and confirmed: Tier-1 wear genuinely destroys Tier-2 attribution
  (accuracy 0.601 → 0.055 across the wear range); the confound score detects
  wear through detector noise (AUC 1.000); gating reduces misattribution
  (0.743 → 0.536).

**What failed — and why that finding did not hold up.** A Tier-2-only heuristic
beat it at identical coverage using no connector-wear input at all:

| Gate | Misattribution | Coverage | Needs CW-AI? |
|---|---|---|---|
| Tier-1 gate (Claim 1) | 0.536 | 0.433 | yes |
| *"abstain when no hypothesis explains the footprint"* | **0.411** | 0.437 | **no** |

Transport wear confounds attribution *by* producing spurious anomalies; the
free rule detects that corruption by its consequence rather than its cause.

**Obviousness exposure: HIGH.**
- *"Abstaining when your input is unreliable is a confidence threshold."*
- *"The applicant's own data shows a simpler method without the claimed input
  performs better."* — the second is the serious one, because it is a
  **design-around demonstrated by the applicant's own evidence.**

**That result was then overturned by a sensitivity audit.** It depended on a
single invented constant — the rate at which transport wear makes *unrelated*
sensors look anomalous — which was set to 0.50. Break-even sits at **0.035 to
0.10**. The falsification therefore used a value roughly **14x** beyond the
point where the answer flips, and Claim 1 **wins** across the whole region below
that line:

| spurious rate | margin (positive = Claim 1 wins) |
|---|---|
| 0.00 | +0.043 |
| 0.03 | +0.006 |
| 0.10 | −0.051 |
| **0.50** *(value used)* | **−0.090** |

**Corrected status: UNDETERMINED, not dominated.** The advantage is also robust
to connector-wear-detector noise up to σ≈0.5.

**Recovery route (single).** Bench Experiment A measures the spurious rate
directly, against a threshold fixed in advance: **< 0.035 → file Claim 1;
> 0.10 → withdraw it.**

**Recommendation: hold Claim 1 pending that measurement. Do not withdraw it, and
do not draft it as lead yet.**

### 3.2 Claim 2 — Tier-2 footprint attribution over the EPDG

**Mechanism.** Inverse inference: match the observed anomaly footprint against
the expected footprint of each candidate connector/rail fault, where candidates
and footprints come from **harness design data**, not from fault training
examples.

**What supports it.** On a harness configuration with **zero fault training
data**, it localises to a named segment at **0.791 against 0.091 chance** (11
hypotheses) — an 8.7× lift.

**A premise that was falsified and must not be filed.** The original
justification was that learned waveform methods do not transfer across harness
configurations. **Measured false.** A classifier trained on configuration A
transferred to structurally different configuration B at **0.882 — better than
its own in-distribution 0.867, and better than footprint matching (0.791).**
The discriminating physics is topology-independent. **Any claim language
asserting that learned methods fail to generalise is unsupported.**

**What survives is a capability difference.** The learned model's label space is
configuration A's segments; it **cannot name a segment in an unseen harness**.
Footprint matching can, from design data alone. Claim 2 should be drafted as
*localising to a named segment in a harness for which no fault training data
exists*, never as *generalising better than learned methods*.

**Material qualification for scope.** With rail groupings randomly shuffled,
connector-fault accuracy is **unchanged** (1.000) while rail-fault accuracy
collapses (0.425 → 0.075). Topology contributes **nothing** to connector faults
and **everything** to shared-rail faults. Correct topology is worth +0.127
overall. **The claim's real scope is shared-rail faults.**

**Obviousness exposure: MEDIUM.**
- *"Bayesian inference over a known dependency graph is well established."*
- *"A learned discriminator outperforms this on the shared task."*
- Answer: the output space. No learned model can name a segment in a harness it
  has no data for; the topology is available from design documents at zero
  marginal cost. That asymmetry is the inventive step.

### 3.3 Claim 3 — diagnostic protocol as actuation channel

**Mechanism.** When attribution is ambiguous, perturb the system by
**modulating diagnostic request cadence on the existing OBD-II/UDS link**.
Nothing is injected into any sensor path; no additional hardware is required.

**What was falsified — twice.** The original argument was that active probing
resolves ambiguity passive observation cannot. Two fault pairs were constructed
to demonstrate this; **both failed**, and so did the fallback latency argument:

| Test | Passive | Probe |
|---|---|---|
| Pair 1 (connector vs reference rail) | 0.990 | 0.990 |
| Pair 2 (connector vs shared ground), severity-matched | **0.810** | **0.560** |
| Time to reach probe-equivalent accuracy | **1.000 @ 1 s** | 0.990 @ 2 s |

**No simulated condition has been found in which the probe outperforms passive
observation.** Probe necessity must not be asserted in the IDF.

**Unlike Claim 1, this falsification survived a full sensitivity audit.** The
load-response constants were swept across a 3x3 grid (passive won at every
point, including the maximum-contrast case); probe duration was extended 60x
beyond the 2 s safety cap (the margin got *worse*, not better); and the contact
time constant was swept from 5 ms to 400 ms (lag AUC peaked at 0.682, below the
0.75 reinstatement bar). **Claim 3's discrimination argument is not
parameter-fragile — it is dead.**

Two structural fields were removed from the design as a result: expected
response **lag** (AUC 0.53–0.68) and **polarity** (indistinguishable from chance
for both fault classes). They were deleted rather than left aspirational, so
that no claim element depends on something the evidence does not support.

**What remains, and it is not affected by the above.** Classical active fault
diagnosis assumes an actuator or auxiliary input into the plant. Here **the
diagnostic protocol itself is the actuator** — a channel that exists in every
compliant vehicle and requires no added hardware. This is a structural
distinction from the prior art, not an empirical claim.

**Explicitly NOT claimed as independently novel** (both obviousness-vulnerable,
claimed only as limitations):
- the uncertainty trigger — a threshold on model confidence;
- the safety envelope — excluded-state gating, rate limits, watchdog, audit log.

**Obviousness exposure: HIGH except on the actuation channel.** Active fault
diagnosis is mature (Nikoukhah 1998; Šimandl & Punčochář 2009; Ashari 2012;
Poulsen & Niemann 2008). **Draft Claim 3 so that it survives only on the
actuation channel**, and expect everything else to be rejected.

### 3.4 Claim 4 (candidate) — transferred type prior over topology hypotheses

**Mechanism.** A fault-type classifier (connector-local vs shared-rail) trained
on **one** harness re-weights a hypothesis posterior derived from a **different**
harness's design data. Never retrained on the target.

**Why not a routine ensemble.** The two components have **different output
spaces** — type vs named segment — and neither can produce the other's. The
classifier cannot name a segment in an unseen harness; the attributor cannot
judge type from a footprint consistent with both. The combination projects
information that exists only as a *type* onto an identity space that exists
only as *topology*.

**What was measured, and how it weakened.** The type prior transfers zero-shot
(0.882 / 0.870). But the headline improvement does not reproduce:

| | overall | connector | rail |
|---|---|---|---|
| Config B footprint → hybrid | 0.791 → **0.877** | 1.000 → 0.864 | 0.425 → **0.900** |
| Config C footprint → hybrid | 0.800 → **0.800** | 1.000 → 0.825 | 0.500 → **0.762** |

The hybrid **always damages connector accuracy** (perfect under footprint
alone) to improve rail accuracy. On config B the mix nets +0.086; on config C
it nets **exactly zero**. Break-even prior error is ~15% and the classifier
sits at 13% — no margin. The gain requires near-hard weighting (w ≥ 0.8).

**Obviousness exposure: HIGH.** *"Using a classifier output as a Bayesian prior
is textbook, and the applicant's own third configuration shows no overall
improvement over the Bayesian component alone."* Only the output-space
asymmetry answers this. **If the claim cannot be drafted so that asymmetry is
the inventive step, drop it rather than file it as an ensemble.**

---

## 4. Prior art requiring mandatory disclosure

Two items must appear in the IDF **as prior art, not as contribution**.

**4.1 Plausibility residuals are a parity-space check.** The system computes
residuals against known PID-to-PID physical relationships and flags deviations.
This is textbook analytical redundancy: Chow & Willsky (1984); Gertler (1988);
Frank (1990); Isermann (2006). Generic sensor-vs-component discrimination from
passive residuals is owned by this literature. Any claim over *"detecting that a
sensor reading is implausible given other sensors"* will read on Chow & Willsky.

**4.2 Active fault diagnosis is mature.** Nikoukhah (1998); Šimandl &
Punčochář (2009); Ashari et al. (2012); Poulsen & Niemann (2008). Perturbing a
system to improve fault isolation is established. See §3.3 for what remains.

**4.3 Consumed, not claimed:** the group's own already-filed CW-AI
connector-wear patent (black box); MC-Dropout and split-conformal prediction as
UQ methods; CAN intrusion detection (different problem — public datasets used
for signal realism only).

---

## 5. Design-arounds required — GM '553 and VW '665

**Status: NOT STARTED. This is a gap, not an omission.** Neither patent has been
retrieved or analysed. The following is the required work, not its result.

**Publication numbers**, from the project's earlier prior-art search:

| Internal name | Number |
|---|---|
| **GM '553** | **US 10,574,553 B2** |
| **VW '665** | **US 2009/0271665 A1** (application); granted as **US 7,894,949 B2** |

> **Legal status must be verified on USPTO Patent Center.** These numbers came
> from Google Patents, whose legal-status data carries an explicit disclaimer:
> it is machine-generated, is not a legal conclusion, and may not reflect
> current assignment, term adjustment, maintenance-fee payment, or expiry.
> **Not usable for freedom-to-operate without independent verification.**

For each, the analysis must establish:

1. **What is actually claimed** — independent claims, element by element.
2. **Element-wise read-across** against FOAE Claims 1–4.
3. **The distinguishing element** we intend to rely on, and whether our
   evidence supports it. Given §3, several intended distinctions have already
   failed, so this must be done against the *surviving* evidence only.
4. **Design-around options** if a claim reads across, with the engineering cost
   of each.

**Specific concerns to test, based on what these patents are understood to
cover:**

- **GM '553** — if it covers using connector/contact condition as an input to
  diagnostic decision-making, it may read directly on **Claim 1**. Given Claim
  1 is already dominated by a method requiring no such input (§3.1), the
  design-around may be to abandon the Tier-1 input entirely and claim the
  Tier-2 consistency rule instead. **That should be evaluated seriously rather
  than defensively** — the evidence currently favours it.
- **VW '665** — if it covers scheduled or triggered diagnostic interrogation
  over a vehicle bus, it threatens **Claim 3**'s actuation channel, which is
  the only surviving element of that claim. This is the highest-risk unexamined
  item in the filing.

**Recommendation: retrieve both patents before any drafting begins.** Claim 3
in particular has one surviving distinguishing feature and it has not been
cleared against the most likely prior art.

---

## 6. Honest overall assessment

**Strongest:** Claim 2, drafted narrowly around named-segment localisation
without target-harness training data, scoped to shared-rail faults.

**Structurally interesting but empirically unsupported:** Claim 3's actuation
channel. It does not depend on the falsified evidence, but it has not been
cleared against VW '665.

**Currently weak:** Claim 1 (dominated by a free alternative), Claim 4
(no overall gain on a third configuration).

**What would change the picture most, in order:**
1. **Bench rig.** It is the only route by which Claim 1 recovers, the only way
   probe necessity can ever be reasserted, and the only validation any of the
   fault models have.
2. **Retrieve GM '553 and VW '665.** Claim 3's single surviving feature is
   uncleared.
3. **Ratify the claim set with an author.** No specification document exists;
   this hierarchy was inferred.

**What we would advise against:** filing Claims 1 and 4 on current evidence.
Both have a design-around visible in the applicant's own data, which is a worse
position at examination than a narrower filing.

The falsification record itself is an asset. It demonstrates that the surviving
claims survived adversarial testing, and it prevents the filing from resting on
assertions that would not withstand examination.

---

## 7. Publication route — a parallel track

**This is not a fallback for a failed patent. It is a second output from the
same bench work, and it should be planned as such from the start.**

### 7.1 What we would have that does not currently exist publicly

There is **no public labelled dataset of automotive connector-fault signatures
with ground-truth contact resistance.** The datasets this field relies on —
HCRL Car-Hacking, ORNL ROAD, SynCAN — are all *intrusion detection* corpora.
They label message-level attacks, not physical-layer degradation, and none
carries measured contact resistance alongside the bus traffic.

The bench protocol in `bench_setup.md` produces exactly that:

- OBD-II PID traces under **graded, measured** contact degradation,
- **four-wire dry-circuit resistance** logged per specimen per cycle, including
  the variance statistics that distinguish intermittent from stable faults,
- **ground-truth fault location** — which connector, which conductor, Tier 1 vs
  Tier 2,
- both **connector-local and shared-rail** faults, a distinction absent from
  every public corpus,
- specimens produced by **real fretting** (mating-cycle wear, vibration under
  thermal cycling), not switch emulation.

Even a modest 30-specimen corpus would be the first of its kind.

### 7.2 What the falsification record contributes

Unusually, the negative results are publishable in their own right:

- **Footprint-level identifiability is not passive identifiability.** Two faults
  can share an anomaly footprint and still be trivially separable from the
  waveform. This is a clean, quantified correction to an intuition the FDI
  literature does not address directly.
- **A confounder gate can be dominated by a free consistency rule.** Detecting
  corruption by its *consequence* outperformed detecting it by its *cause*, at
  equal coverage. That is a general result about diagnostic gating, not a FOAE
  quirk.
- **Learned fault-type discrimination transfers across harness topologies.**
  Measured 0.882 zero-shot to a structurally different configuration — better
  than in-distribution. Useful to anyone assuming per-vehicle retraining is
  required.
- **The type/identity asymmetry.** A learned model can transfer *type* but
  cannot name a *segment* in an unseen harness; topology can name the segment
  but cannot judge type. This framing is, as far as we know, novel and is
  independently interesting even where the accuracy gain is mix-dependent.

Pre-registered thresholds (`bench_setup.md` §§5.3, 6.3) make the bench results
publishable whichever way they fall — which is precisely the property a patent
filing cannot offer.

### 7.3 Interaction with the filing — sequencing matters

**Publication before filing destroys novelty.** In India, and under the
absolute-novelty standard generally, a public disclosure before the priority
date is prior art against your own application. The order is not negotiable:

1. File the provisional (or complete) specification **first**;
2. publish only after the priority date is secured;
3. confirm the sequencing with the IPR cell before submitting anything —
   including conference abstracts, preprints, and dataset releases. **A dataset
   release is a disclosure.**

The falsification record complicates this in one specific way worth raising
with the agent: **§§3.1–3.4 document design-arounds for our own claims.**
Publishing that record hands an examiner or a competitor those design-arounds
directly. That is a reason to sequence carefully, not a reason to suppress the
record — but the agent should advise on how much of the negative detail belongs
in the specification versus in a later paper.

### 7.4 Recommended targets

| Output | Venue type | Timing |
|---|---|---|
| Dataset + descriptor paper | *Data in Brief*, Zenodo/IEEE DataPort | After priority date |
| Falsification methodology | SAE Technical Paper, or IEEE Trans. Instrumentation & Measurement | After priority date |
| Type/identity asymmetry | FDI/PHM venue (e.g. PHM Society, SAFEPROCESS) | After priority date |

### 7.5 Why this is a real track, not a consolation

Three of four claims are currently weak, and the bench may weaken them further.
If that happens, the project still produces: a first-of-its-kind public dataset,
a reusable falsification methodology, and three quantified negative results that
correct plausible but wrong assumptions in the field.

That is a defensible research contribution independent of whether any claim is
granted — and it is a stronger position than a patent application resting on
assertions that would not survive examination.
