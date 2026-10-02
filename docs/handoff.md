# FOAE — Handoff

**For whoever picks this up next.** Assumes you have not followed any of the
work. Written on the assumption you may be running the bench rig while Arun is
in exams.

Read this, then `README.md`, then `bench_setup.md`. Nothing else is required to
start.

**If you are here to write code, read `docs/enablement_spec.md` first** — it,
not this document, defines the current build scope. See §4 below.

---

## 1. What this project is, in four sentences

A car reports a fault code and the workshop replaces the part it names. Often
that part is fine — a worn electrical connector was producing readings that only
*looked* like a failing component. FOAE works out whether the fault is really in
the component, the sensor, or the wiring, and suppresses or re-labels the code
before anyone acts on it.

It exists to support an Indian patent filing. That framing matters: the goal is
not a working product, it is claims that survive examination.

---

## 2. Where things stand

**Feature development is stopped.** Roughly 12% of the planned code exists. The
substantive output so far is a set of *negative* results — mechanisms we
proposed, tested against their strongest counter-argument, and mostly broke.

That is not a failure mode. A claim that dies on our bench is far cheaper than
one that dies at examination.

### Claim status

| # | Mechanism, plainly | Status |
|---|---|---|
| 1 | Treat wear in the diagnostic socket as a reason to **decline to answer**, not as evidence | **UNDETERMINED** — one bench measurement decides it |
| 2 | Locate a fault to a named wiring segment using **wiring design data**, with no fault examples from that vehicle | **NOT FILEABLE AS CONCEIVED** — a partially manifested rail fault is misattributed to a connector segment at full confidence; four fixes tested and rejected |
| 3 | Perturb the car using the **diagnostic protocol itself**, needing no extra hardware | **DISCRIMINATION ROBUSTLY FALSIFIED** — only the no-extra-hardware argument survives |
| 4 | Transfer a fault-*type* judgement from one car onto a fault-*location* space built from another car's wiring | **NOT FILEABLE** — needs field data no bench can produce |

Claim 2 **was** the anchor and no longer is. Building it end to end (see §2a)
exposed a failure the paper design could not show: when a shared-rail fault
manifests on only some of the sensors that ride the rail, the observed set is a
strict subset of the rail's footprint and an exact match for one member
sensor's own connector — so the system names the connector, confidently and
silently. Claim 3 is dead on discrimination and will not recover — we swept
every relevant parameter and passive observation won every time. Claim 1 looked
dead and then recovered when we audited the number the conclusion rested on; it
is genuinely open, and is now the strongest thing here.

Full detail: `claim_strategy.md`. Every experiment and number: `validation.md`.

---

## 2a. Enablement build outcome (2026-08-15)

The three modules in `docs/enablement_spec.md` were built — `foae/epdg/graph.py`,
`foae/attribution/footprint.py`, `foae/pipeline.py` — and the first end-to-end
run produced the finding above. **Read `validation.md` §12–§15 before doing
anything with Claim 2.** In order:

| § | What it records |
|---|---|
| **§12** | The S1 finding. A partially manifested `REF_5V_A` fault is attributed to `SEG_CONN_CKP` at confidence 1.000. The cause is structural, not a bug in the attributor — the better validation attributor gets it wrong too, by 4.7× |
| **§13** | Manifestation sweep, and the nested-abstention prototype. Fixes S1, but makes 7 of 9 segments permanently unnameable and breaks S2 and S5. Net accuracy **falls** 0.67 → 0.57. `ABSTAIN_ON_NESTED_FOOTPRINT` stays `False` |
| **§14** | Graded (soft) evidence. Negative at every width, and its only favourable region requires inverting `PRIOR_CONNECTOR_FAULT` — importing Claim 4's unmeasured field-data blocker into Claim 2. `USE_GRADED_EVIDENCE` stays `False` |
| **§15** | Strict-subset abstention judged on cost asymmetry. Achieves genuine zero misattribution in clean detection, but answers 78% fewer faults and the zero collapses on a single spurious anomaly |

Four mechanisms have now been tried against the S1 case — the probe (Claim 3),
the type prior (Claim 4), graded evidence (§14), and subset abstention
(§13, §15). **None recovers it** without either destroying the common case or
importing an unmeasured constant. `validation.md` §15 states this as the closing
line and it is the current standing position.

What survives: Claim 2 attribution is correct for **fully manifested** rail
faults and for single-connector faults. S5 (`S5_rail_full_manifest`) is the
control that demonstrates this — same fault as S1 at higher severity, correctly
named. The scope that has to be written into any filing is therefore narrower
than "locate a fault to a named segment", and §13.2 measures the partial case as
the **majority** regime for manifesting rail faults (57–77%) under a
`RAIL_MANIFEST_PROB` that is itself PROVISIONAL and unmeasured.

One untried route is named in §13: per-sensor severity information, which
detection currently discards at the threshold. It is the only avenue not already
closed.

The demo at `docs/demo/foae_dashboard.html` shows S1 beside S5 and is hardcoded
to the real run — it is not wired to the live export.

---

## 3. The three pre-registered bench thresholds

**These were fixed before any measurement. Do not change them after seeing
data.** If one proves wrong, record the original, the change, and why, and mark
that run exploratory. Their entire value is that they were set in advance.

| # | Measure | Threshold | Resolves |
|---|---|---|---|
| **A** | How often socket wear makes an **unrelated** sensor look faulty (the "spurious rate") | **< 0.035** → Claim 1 works, file it. **> 0.10** → withdraw it. Between → report both rates, re-run the sweep with measured values | **Claim 1** |
| **B** | Whether perturbing beats passively watching, on real worn connectors, at matched fault severity and equal observation time | Probe must win by **≥ 0.10** to reinstate. Within ±0.10 → probe is useful but not necessary. Below → confirmed dead | **Claim 3** |
| **C** | How strongly a fault on a shared ground wire responds to a neighbouring sensor's current draw | Coupling **≥ 0.25** (equivalently load-sensitivity **≥ 0.5**) or the mechanism does not exist at all | **Claim 4** |

Protocols, wiring, and BOM: `bench_setup.md` §§5–6. Rig cost ≈ ₹25,000–35,000.

**Note on C, worth understanding before you run it.** Two independent analyses,
sweeping different parameters by different routes, converge on the same physical
requirement. That convergence is evidence the mechanism is real; what is unknown
is only its magnitude in real hardware. If your measurement lands below
threshold, that is a genuine negative and should be reported as one — not
re-tuned.

### Two things about the rig that are easy to get wrong

1. **A normal multimeter destroys a worn-connector specimen on contact.** In
   resistance mode it applies enough voltage to break down the oxide film — the
   specimen then reads *fine*, because you erased the fault that took weeks to
   grow. Measure only via the four-wire dry-circuit method (< 20 mV, ≤ 1 mA).
   The full warning is at the top of `bench_setup.md`. Read it before touching
   anything.
2. **A MOSFET emulating an intermittent connection cannot test Claim 3.** If we
   command the intermittency, the response to load is whatever we programmed —
   the experiment answers itself. Claim 3 needs genuinely fretted contacts
   (`bench_setup.md` §4). Emulation is fine for everything else.

---

## 4. Four tasks needing no hardware — start these first

Current phase spec: `docs/enablement_spec.md` - Claim 2 enablement only,
three modules (epdg, attribution, pipeline). Read it before building.

Task 3 is **done** — see the row below. The remaining three are unblocked today
and task 4 has a long lead time.

| # | Task | Why it matters |
|---|---|---|
| 1 | **Read real harness topology from vehicle wiring diagrams** — which sensors share which ground and 5 V reference wires | Closes a P0 gap outright. Our current topology is invented, and a wrong one silently degrades Claim 2 with no error surfacing anywhere |
| 2 | **Ask the CW-AI team for their detector's characterised error** | Internal request, no bench needed. Feeds Claim 1's confound score |
| 3 | ~~**Literature search: how often are automotive wiring faults in shared wires vs individual connectors?**~~ **DONE 2026-08-10 — `lit_connector_fault_mix.md`** | **Result: NEGATIVE.** The literature classifies faults by component and mechanism, not by circuit topology, so it does not report this split at all and cannot bound the prior. The cheapest source is now spent; the binding path is Tier-1 manufacturer / warranty data under NDA (that doc, §5). Claim 4 stays unfileable |
| 4 | **Patent agent: retrieve and clear US 10,574,553 B2 (GM) and US 2009/0271665 A1 / US 7,894,949 B2 (VW)** | The largest unquantified risk. VW '665 threatens Claim 3's *only* surviving feature. Verify legal status on USPTO Patent Center — Google Patents status data is machine-generated and disclaimed |

Details and further sources: `measurement_gaps.md`.

---

## 5. Two process rules that each caught a real error

Not general advice. Both of these caught mistakes that had already made it into
documents.

### Rule 1 — sweep to a value that should break the mechanism

Three times, a number nobody had reason to doubt distorted a conclusion.

- One constant sat **14× away** from the value where a claim verdict flips. It
  had made Claim 1 look dead. Claim 1 is now open.
- Another constant turned out to be **read by nothing at all** — every value
  gave an identical answer, including zero, which should have destroyed the
  mechanism outright.

Both were caught the same way: set the parameter to a value that *ought* to
break the thing, and check the output actually moves. A sweep where nothing ever
breaks may be measuring nothing.

**Corollary:** any constant that can change an experimental outcome belongs in
`foae/config.py`, never in a test file. Three such constants were found living
in tests, outside the audit.

### Rule 2 — never write an identifier that was not supplied

Two patent numbers were written into a document meant for the patent agent.
Neither had been given; both were plausible-looking inventions. They were caught
before the document went out.

If you need a reference and do not have the identifier in front of you, write
`[NUMBER NOT ON RECORD]`. **Expanding a short form — "GM '553" into a full
number — is fabrication unless the full number was given.** A visible gap gets
filled; a fabricated number propagates into a legal filing.

---

## 6. Hazards in the codebase

### The duplicated physics path (fixed, but understand why)

`tests/test_generalization.py` used to simulate contact physics itself instead
of calling `foae/simulator/faults.py`. Consequence: `SHARED_GROUND_COUPLING` was
**never read** by any Claim 2 or Claim 4 experiment, so sweeping it measured
nothing for the whole investigation.

It has been unified — every experiment now routes through `faults.py`, and the
re-run reproduced every previous figure bit-identically. The old code happened to
be correct *at the default value only* and wrong everywhere else, which is
exactly why it read as a flat line rather than an obvious bug.

**If you add an experiment, route it through `faults.py`. Do not write local
physics.** A second implementation will drift from the first and nothing will
tell you.

### The Windows encoding hazard (destroyed a document)

On Windows, Python defaults to cp1252, and every document here contains
characters it cannot encode (`—`, `≥`, `≈`, `₹`, `σ`). `pathlib.write_text(s)`
**truncates the file to zero bytes and only then raises** — the exception looks
like a harmless failed write while the content is already gone.

Always pass `encoding="utf-8"` on every read and write, and check the file size
afterwards. Full detail in `README.md`.

### The three enablement modules have no unit tests

`foae/epdg/graph.py`, `foae/attribution/footprint.py` and `foae/pipeline.py` are
1,426 lines and are covered by **no unit tests at all** — `tests/test_epdg.py`,
`tests/test_attribution.py` and `tests/test_pipeline.py` are all still 0 bytes.
The 12 passing tests predate these modules and exercise the simulator, probe and
confound layers only.

The sole end-to-end check on the attribution path is that `python -m foae.pipeline`
exits 0 and that the five scenario verdicts look right by inspection. A
regression in scoring, ranking or the abstention thresholds would not be caught.
`tests/measure_rail_manifestation.py` and `tests/measure_subset_abstention.py`
exercise the path more thoroughly but are **measurement scripts, not tests** —
pytest does not collect them (no `test_` prefix) and they assert nothing.

Write these three before changing anything in the attribution path.

### The 7 failing tests are deliberate

`pytest` gives **12 passed, 7 failed**. The failures are not defects — each
asserts something the design originally predicted, and fails because the
prediction was wrong. They are the record. **Do not fix them.**

**Check the names, not just the count.** A count-only check passes if one true
negative silently starts passing while an unrelated test breaks — the tally
still reads 7, and you would have lost a recorded result and gained a real bug
in the same run, invisibly. The seven, verbatim:

| # | Test | Claim |
|---|---|---|
| 1 | `test_confound_gate.py::test_F4_tier1_gate_beats_tier2_only_heuristic` | 1 |
| 2 | `test_generalization.py::test_waveform_does_not_transfer_better_than_footprint` | 2 / 3 |
| 3 | `test_hybrid_claim4.py::test_hybrid_not_worse_than_footprint_at_realistic_prior_error` | 4 |
| 4 | `test_hybrid_claim4.py::test_hybrid_gain_robust_across_prior_weights` | 4 |
| 5 | `test_identifiability.py::test_rail_polarity_is_stable` | 3 (§5.1 pair) |
| 6 | `test_identifiability_nesting.py::test_marginal_waveform_does_not_separate` | 3 (nesting pair) |
| 7 | `test_identifiability_nesting.py::test_probe_separates_the_pair` | 3 (nesting pair) |

Regenerate this list with:

```
python -m pytest -q 2>&1 | grep "^FAILED"
```

Two of them also carry reference figures that reproduce bit-identically and are
worth diffing after any refactor of the physics path: test 6 measures
`acc = 0.990` against a `< 0.75` bound, and test 7 measures `acc = 0.710`
against a `>= 0.90` bound.

Any other tally, **or the same tally with different names**, means something
changed. Investigate before proceeding; do not repair.

---

## 7. If you only do one thing

Build the rig and run **Experiment A** (`bench_setup.md` §5). It decides Claim 1,
which is the only claim currently sitting on a knife edge, and the threshold is
already fixed so the result will be unambiguous either way.

While the rig is being built, start **task 4** in §4 — the patent-agent
clearance. Task 3, the literature search, has been run and came back negative
(`lit_connector_fault_mix.md`); its successor is the Tier-1 manufacturer
approach in that document's §5, which now has the longest lead time of anything
here and should be started in parallel.

---

## 8. Honest summary

No mechanism here currently has strong, reproduced, hardware-validated support.
Claim 2 is defensible **only for fully manifested rail faults and single-connector
faults** — the partial-manifestation case is an open, unfixed failure and is the
majority regime (§2a). Claim 1 is genuinely open and is now the strongest claim
here. Claim 3 keeps one structural argument. Claim 4 needs data we do not have.

Everything measured so far is simulation, using fault models written from
physical reasoning with **no measurement behind them**. The negatives are
reasonably trustworthy — there was every incentive to produce a pass and they
came out negative anyway. A *positive* result from this simulator would prove
very little.

That is what the bench is for.
