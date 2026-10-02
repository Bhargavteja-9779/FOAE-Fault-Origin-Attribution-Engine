# FOAE — Briefing for Patent Agent

**To:** Kuldeep Singh · **From:** Arun Reddy (FOAE project, VIT)
**Date:** 2026-08-05 · **Purpose:** decide what to draft, and what not to

---

## What the invention does

A vehicle's diagnostic system reports a fault code, and the workshop replaces
the part it names. Often the part is healthy — a worn electrical connector was
producing readings that merely *looked* like a failing component.

FOAE decides **where the fault actually originated** — the component, the
sensor, or the wiring — and then confirms, suppresses, or re-labels the fault
code before a technician acts on it.

**Technical effect (relevant to §3(k)):** the system writes to the vehicle's
Diagnostic Event Manager. The output is a change in the vehicle's recorded
state, not a report or a calculation.

---

## The four candidate claims

We tested each of these against its own strongest counter-argument before
bringing them to you. Three did not survive intact.

| # | Mechanism | Status |
|---|---|---|
| 1 | Treat wear in the diagnostic socket as a reason to **decline to answer**, rather than as evidence | **UNDETERMINED** — hinges on one bench measurement |
| 2 | Locate the fault to a named wiring segment using the vehicle's **wiring design data**, with no fault examples from that vehicle | **SUPPORTED**, but narrower than hoped |
| 3 | Perturb the vehicle using the **diagnostic protocol itself** as the stimulus, needing no added hardware | **PARTLY FALSIFIED** — only the "no added hardware" argument survives |
| 4 | Transfer a fault-*type* judgement learned on one vehicle onto a fault-*location* space built from another vehicle's wiring | **NOT FILEABLE YET** — depends on data we do not have |

**Claim 2 is the strongest and should anchor the filing.**

---

## What each needs, in one line

**Claim 1 — undetermined.** Our simulation suggested a simpler method (using no
socket-wear data at all) worked better. On re-examination, that conclusion
depended entirely on one invented number that turned out to be roughly **14×**
away from the value where the answer flips. Claim 1 wins across the whole
plausible range on the other side of that line. **One bench measurement decides
it**, and the threshold is fixed in advance (below).

**Claim 2 — supported.** Locates a fault to a named wiring segment on a vehicle
it has no fault data for: **79% accuracy against 9% chance.** Important caveat
for scope: the wiring data only helps for faults on *shared* wires (about a
third of cases). For faults in a single sensor's own connector it adds nothing.
**Draft it around shared-wire faults.**

**Claim 3 — partly falsified.** We could not show that perturbing the vehicle
beats simply watching it. We tried two different fault pairs, extended the
observation window 60-fold, and swept every relevant parameter; passive
observation won every time. **We are not asking you to claim that it works
better.** What survives is narrower and structural: existing prior art assumes
you need a dedicated actuator to perturb the vehicle, whereas we use the
diagnostic communication protocol that every compliant vehicle already has.
**Draft Claim 3 so it stands or falls on that point alone.**

**Claim 4 — not fileable.** Its advantage depends on how often real-world wiring
faults occur in shared wires versus individual connectors. We do not have that
statistic, and no bench experiment can produce it — it needs warranty or field
failure data. On one test configuration the advantage was meaningful; on
another it was exactly zero. **Do not draft this until we have field data.**
One point in its favour: two independent lines of analysis, using different
parameters, converge on the same physical requirement for the mechanism to
exist — evidence the effect is real even though its real-world magnitude is
still unmeasured.

---

## The bench measurements that resolve Claims 1 and 3

Thresholds were fixed **before** any measurement, so the outcome cannot be
argued after the fact.

| Claim | What we measure | Result |
|---|---|---|
| **1** | How often socket wear makes an *unrelated* sensor look faulty | **< 3.5%** → Claim 1 works, file it · **> 10%** → withdraw it |
| **3** | Whether perturbing beats watching, on real worn connectors, given equal time | Probe must win by **≥ 10 percentage points** to reinstate. Otherwise the claim keeps only the hardware argument |

Rig cost ≈ **₹25,000–35,000**. The limiting factor is growing genuinely worn
connectors, which takes weeks.

---

## Two things we must disclose as prior art

Please confirm these are handled correctly in the specification.

1. **Cross-checking sensors against each other is not ours.** Our system checks
   whether sensor readings are consistent with one another. This is standard and
   well-published (Chow & Willsky, 1984, and a large literature since). It must
   appear as prior art we *use*, not as something we invented. **A claim written
   over "detecting that a sensor reading is implausible" would fail.**

2. **Deliberately perturbing a system to diagnose it is not ours either.** This
   is an established field (Nikoukhah 1998; Šimandl & Punčochář 2009). Only our
   *means* of perturbing — the diagnostic protocol, no added hardware — is
   arguably new.

We also consume our own already-filed connector-wear patent as a component; it
is not re-claimed.

---

## Open risk: two patents we have not read

**Two patents identified in our prior-art search have not yet been analysed
against our claims.** This is the largest unquantified risk in the filing.

| Internal name | Publication number |
|---|---|
| **GM '553** | **US 10,574,553 B2** |
| **VW '665** | **US 2009/0271665 A1** (application), granted as **US 7,894,949 B2** |

> **Please verify current legal status on USPTO Patent Center.** Our numbers
> came from a Google Patents search, and Google Patents carries an explicit
> disclaimer on legal-status data — it is machine-generated, not a legal
> determination, and may not reflect current assignment, term adjustment,
> maintenance-fee status, or expiry. Do not rely on it for freedom-to-operate.

- **GM '553** — if it covers using connector condition as an input to diagnostic
  decisions, it may read directly on Claim 1. Note our own evidence already
  favours a version of the system that uses **no** connector-wear input, so a
  design-around may be available and preferable.
- **VW '665** — if it covers triggered diagnostic interrogation over a vehicle
  bus, it threatens Claim 3's *only* surviving feature. **This is the highest
  priority item for you.**

**Request: please retrieve and read both before any drafting begins.**

---

## Question for you: publication sequencing

We intend to publish two things after filing — a dataset of connector-fault
measurements (no equivalent exists publicly) and a methodology paper.

We understand the order is: **file first, publish after the priority date**, and
that a dataset release counts as a public disclosure. Please confirm.

One complication we want your guidance on: **our internal record documents
workable design-arounds for our own claims.** It was written that way
deliberately, so we would not file something that collapses at examination. But
publishing it hands those design-arounds to a competitor or an examiner.

**How much of the negative record belongs in the specification, and how much
should stay unpublished?**

---

## What we are asking for

1. Retrieve and clear **GM '553** and **VW '665** (highest priority).
2. Confirm the two prior-art disclosures are correctly framed.
3. Advise on publication sequencing and on the design-around disclosure issue.
4. Draft **Claim 2** as the anchor; hold **Claims 1 and 3** for bench results;
   **do not draft Claim 4**.

Supporting detail, if wanted: `claim_strategy.md` (full record),
`validation.md` (all experiments and numbers), `bench_setup.md` (protocols).
