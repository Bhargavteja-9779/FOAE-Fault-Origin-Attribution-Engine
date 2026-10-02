# FOAE — Validation Protocol and Results

Feeds IDF Section 8. Status: **protocol only** — results tables are outstanding.

---

## 1. Scoring rule: abstention is a distinct outcome

**Decided before scenarios are built, so the metric cannot be retrofitted.**

The Tier-1 confounder gate (`docs/design.md` §3) can abstain: when OBD-II
connector wear is high enough that all PIDs are suspect, FOAE asserts no
Tier-2 origin for that session.

**An abstention under genuine Tier-1 confound is a SUCCESS, not a miss.**
Declining to attribute when the evidence cannot support attribution is the
behaviour FOAE exists to produce. Scoring it as a failure would reward exactly
the overconfidence the engine is designed to prevent.

Every scenario must therefore report a **four-way outcome**, never a binary:

| Outcome | Meaning | Counts as |
|---|---|---|
| `CORRECT` | Origin asserted, matches ground truth | Success |
| `MISATTRIBUTED` | Origin asserted, wrong | **Failure — the serious one** |
| `ABSTAINED_JUSTIFIED` | No origin asserted, Tier-1 confound genuinely present | Success |
| `ABSTAINED_UNJUSTIFIED` | No origin asserted, Tier-1 was actually clean | Weak failure (over-caution) |

Required derived metrics:

- **Misattribution rate** = `MISATTRIBUTED / (CORRECT + MISATTRIBUTED)` —
  accuracy *among sessions where a claim was made*. This is the headline
  number for the IDF.
- **Coverage** = `(CORRECT + MISATTRIBUTED) / total` — how often FOAE commits.
- **Abstention precision** = `ABSTAINED_JUSTIFIED / all abstentions`.

Reporting a single "accuracy" that pools abstentions with errors is
**prohibited**: it makes a well-calibrated abstaining system look worse than a
recklessly confident one. Scenario 5 (false-suppression rate) in particular
must separate the two abstention rows.

---

## 2. Scenarios

| # | Name | Question |
|---|---|---|
| 1 | Synthetic | Within-distribution attribution accuracy on simulator data |
| 2 | Empirical | Generalisation to HCRL / ROAD captures |
| 3 | Probe lift | Passive vs ADP-assisted attribution |
| 4 | Economy | Probe frequency and bus-utilisation overhead |
| 5 | False positives | False-suppression rate (four-way scoring above) |
| 6 | Safety | Safety-envelope compliance; zero excluded-state probes |

---

## 3. Scenario 3 (probe lift) — protocol correction

Scenario 3 was to be built around the `CONN:C_VSS` / `RAIL:REF_5V_B` footprint
collision (`design.md` §5.1), on the assumption that the pair is passively
inseparable and that the probe resolves it.

**That assumption was tested and did not hold.** See
`tests/test_identifiability.py` and §4 below. Scenario 3 must not be built on
this pair until a genuinely passively-ambiguous pair is identified.

The measurement itself remains valid and must compare, on the same sessions:

- passive-only attribution using the full residual waveform (**not** footprint
  alone — see §4), versus
- probe-assisted attribution,

reporting lift with effect size and seed-to-seed stability. A probe that does
not beat a strong passive baseline is not evidence for the lead claim.

---

## 4. Recorded result: §5.1 identifiability experiment

**Date:** 2026-08-05 · **N:** 50 seeds per condition · **Source:**
`tests/test_identifiability.py`

| Discriminator | LOO accuracy | Verdict |
|---|---|---|
| Passive footprint (set of anomalous sensors) | 0.500 (chance) | Collision confirmed |
| Passive residual waveform | **1.000** | Separates perfectly |
| Passive waveform, severity-matched control | 0.990 | Separation is not a magnitude artefact |
| Probe response features | 0.930 | Separates, but **worse than passive** |

**Conclusion: the design.md §5.1 claim that "no amount of passive observation
separates them" is false as stated.** The footprint collision is real, but
footprint is an impoverished statistic; the underlying waveforms differ
grossly because one mechanism is smooth-multiplicative and the other is
spiky-intermittent.

> **Numbers above superseded — see §6.** The dropout model used for this run
> held stale values at the internal simulation rate (~5 ms), producing a fault
> effect ~40x BELOW sensor noise. The conclusion is unchanged after the fix,
> but the figures were re-measured. Corrected: passive 0.990, probe 0.990.

---

## 5. Recorded result: §5.2 nesting pair — ALSO FALSIFIED

**Date:** 2026-08-05 · **N:** 50 seeds · **Source:**
`tests/test_identifiability_nesting.py`

Pair: early-stage `RAIL:SENSOR_GND_B` (VSS leg fretted only) vs `CONN:C_VSS`.
Same intermittent mechanism, identical footprint {vehicle_speed}. The two
differ only in that a shared ground rail carries the co-resident sensor's (MAF)
return current. The passive observer was given the MAF trace, so it had access
to the same physics the probe interrogates.

| Discriminator | LOO accuracy | Verdict |
|---|---|---|
| Passive footprint | 0.500 (chance) | Collision confirmed |
| Passive waveform (unmatched severity) | 0.990 | Separates |
| Passive waveform, **severity-matched** | 0.640 marginal / **0.810** with coupling | Separates moderately |
| Probe response | **0.560** | **Near chance — worse than passive** |

**Conclusion: this pair does not support the claim either.** At matched
severity the probe (0.560) performs barely above chance and is beaten by the
passive rail-coupling statistic (0.810). Unmatched, passive reaches 0.990 while
the probe reaches 0.710.

---

## 6. Recorded result: latency argument — NOT SUPPORTED

Question: how long must a passive observer watch before matching what one 2 s
probe achieves? Pair A, passive LOO vs observation window:

| Window | Samples | LOO (all features) | LOO (shape-only) |
|---|---|---|---|
| 1 s | 10 | **1.000** | 0.580 |
| 2 s | 20 | 1.000 | 0.570 |
| 5 s | 50 | 0.990 | 0.810 |
| 8 s | 80 | 0.980 | 0.970 |
| 12 s | 120 | 0.990 | 0.990 |
| 120 s | 1200 | 0.990 | 0.990 |
| **Probe, 2 s** | — | **0.990** | — |

**Passive reaches 1.000 within one second — faster than the probe and more
accurate.** There is no latency advantage.

A narrower reading does survive: restricted to scale-invariant shape features
(kurtosis / autocorrelation / HF ratio), passive needs ~8-12 s to reach what
the probe delivers in 2 s, a ~6x speedup. **That restriction is not defensible
in a filing** — a real passive observer would also use residual magnitude,
which separates immediately. Quoting the shape-only curve without stating the
restriction would misrepresent the result.

---

## 7. Recorded result: EPDG generalisation — PREMISE FALSIFIED, CLAIM SURVIVES REFRAMED

**Date:** 2026-08-05 · **Source:** `tests/test_generalization.py`
Config A: 5 sensors, 4 rails (2/1/3/2). Config B: 7 sensors, 4 rails (3/1/2/4),
one sensor on no rail. B is not a relabelling of A. 180 A-trials, 220 B-trials.

### The premise under test

*"Waveform discrimination requires a trained per-fault-pair discriminator that
does not transfer across harness configurations."*

**This is false.**

| Discriminator | Task | Accuracy |
|---|---|---|
| Waveform, A→A (in-distribution LOO) | connector vs rail | 0.867 |
| **Waveform, A→B (transfer)** | connector vs rail | **0.882** |
| B majority-class baseline | — | 0.636 |
| Footprint →B (topology only) | connector vs rail | 0.791 |

The A-trained waveform discriminator transfers to B **as well as it performs
in-distribution** (0.882 vs 0.867), and on the shared task it **beats**
footprint matching (0.882 vs 0.791). The reason is physical: the discriminating
feature is rail-coupling — correlation between a co-resident sensor's current
draw and dropout energy — and that relationship is topology-independent. It
does not need retraining when the harness changes.

### What survives: capability, not generalisation

| Method | Segment-level accuracy on B | Notes |
|---|---|---|
| Chance (11 hypotheses) | 0.091 | — |
| Waveform (A-trained) | **not applicable** | Label space is A's segments; cannot name a B segment |
| Footprint (topology only) | **0.791** | 8.7x chance, zero training data from B |

The waveform discriminator cannot output a segment identifier for a harness it
was not trained on — there is no principled mapping from A's segment labels to
B's. Footprint matching names a segment in B from design data alone.

**The EPDG's justification is a capability difference, not a generalisation
difference.** Claim 2 must be reframed accordingly.

### How much work is the topology doing?

| Trial class | True topology | Rails shuffled | Share of trials |
|---|---|---|---|
| Connector faults | 1.000 | 1.000 ± 0.000 | 64% |
| **Rail faults** | **0.425** | **0.075 ± 0.048** | 36% |
| Overall | 0.791 | 0.664 ± 0.017 | — |

Honest answer: **topology does nothing for connector faults and everything for
rail faults.** Connector hypotheses are singletons, correctly resolved by the
singleton structure and the connector prior whether or not rail groupings are
correct. On rail faults the true topology gives a 5.7x lift over shuffled.
Since connector faults are 64% of trials, the headline 0.791 overstates
topology's contribution; the marginal effect of correct topology is +0.127.

> **QUALIFICATION — which attributor produced these numbers.**
>
> Every figure in §7, including `0.791` and the `0.425` rail-fault number, was
> produced by `footprint_attribute` in `tests/test_generalization.py`
> (lines 180–199). That function is a Bayesian posterior: it imposes a strict
> subset constraint (`observed <= expected`) and weights each hypothesis by an
> explicit binomial manifestation likelihood `p^k (1-p)^(m-k)` with
> `p = RAIL_MANIFEST_PROB`, plus connector/rail priors.
>
> **The shipped attributor is not that function.**
> `foae/attribution/footprint.py` scores by Jaccard set agreement and has **no
> manifestation model at all**. These figures therefore do not describe the
> code that ships, and `0.425` should not be quoted as the shipped system's
> rail-fault performance. §12 and §13 measure the shipped path directly, and
> §14 measures a graded-evidence variant against the same sweep.

### The two methods are complementary, not competing

| Method | B segment accuracy | Rail trials only |
|---|---|---|
| Footprint alone | 0.791 | 0.425 |
| **Footprint + A-trained waveform type** | **0.877** | **0.900** |

Feeding the zero-shot transferred waveform type prediction into the footprint
attributor **more than doubles rail-fault localisation** (0.425 → 0.900). This
is the strongest configuration measured, and it uses no training data from B.

**Design implication:** the EPDG should consume a waveform-derived fault-type
prior, not compete with one. `infer_tier2_origin` should take a type prior as
an argument.

### Caveat

The waveform feature set deliberately included the config-independent coupling
statistic — the fair steelman. A discriminator relying on sensor-specific
waveform shapes would transfer worse. This makes the transfer result a strong
negative for the premise, but it is a statement about *this* feature set.

---

## 8. Recorded result: Claim 4 hybrid — WEAKENED

**Date:** 2026-08-05 · **Source:** `tests/test_hybrid_claim4.py`
Config C introduced: 6 sensors, rail cardinalities 4/2/3/3, **no singleton
rail** (so no connector/rail footprint collision) — structurally distinct from
both A (2/1/3/2) and B (3/1/2/4).

| Test | Result | Verdict |
|---|---|---|
| T1 — gain reproduces on config C | rail 0.500 → 0.762 | **PASS** |
| T2 — survives 20% prior error | hybrid 0.775 < footprint 0.800 | **FAIL** |
| T3 — robust across prior weights | no gain at w ≤ 0.7 | **FAIL** |

Per-class breakdown (the finding that matters):

| | overall | connector | rail |
|---|---|---|---|
| B footprint | 0.791 | 1.000 | 0.425 |
| B hybrid | 0.877 | 0.864 | 0.900 |
| C footprint | 0.800 | 1.000 | 0.500 |
| C hybrid | **0.800** | 0.825 | 0.762 |

**The previously reported "0.877 vs 0.791" overstates the mechanism.** The
hybrid always trades connector accuracy (perfect under footprint-alone) for
rail accuracy. On config B the mix makes that net +0.086; on config C it nets
exactly **zero**. Break-even prior error is ~15% and the transferred classifier
sits at 13% — no margin. The gain also requires near-hard weighting (w ≥ 0.8).

**Claim 4 is a rail-fault-specific mechanism, not a general improvement.**

---

## 9. Recorded result: Claim 1 confounder gate — DOMINATED

**Date:** 2026-08-05 · **N:** 1500 sessions · **Source:**
`tests/test_confound_gate.py`

Claim 1 was promoted to lead because it was untouched by earlier
falsifications. It has now been tested.

**F1 — does Tier-1 wear degrade Tier-2 attribution? YES, severely.**

| Tier-1 wear | n | Attribution accuracy |
|---|---:|---|
| 0.00-0.25 | 368 | 0.601 |
| 0.25-0.50 | 414 | 0.244 |
| 0.50-0.75 | 355 | 0.124 |
| 0.75-1.00 | 363 | 0.055 |

**F2 — does the confound score detect wear through CW-AI noise? YES.**
AUC 1.000 (clean mean 0.210, worn mean 0.929) at CW-AI noise σ = 0.15.

**F3 — does gating reduce misattribution? YES.** 0.743 → 0.536.

**F4 — does Tier-1 information add anything a Tier-2-only rule cannot get for
free? NO. This is the failure.**

| Gate | Misattribution (committed) | Coverage | CW-AI needed? |
|---|---|---|---|
| No gate | 0.743 | 1.000 | — |
| **Tier-1 gate (Claim 1)** | 0.536 | 0.433 | **yes** |
| **Tier-2-only heuristic** | **0.411** | 0.437 | **no** |
| Tier-2 `\|footprint\| ≤ 1` | **0.238** | 0.241 | no |
| Tier-2 + strict Tier-1 | 0.256 | 0.182 | yes |

At essentially identical coverage (0.433 vs 0.437), the rule *"abstain when no
hypothesis explains the observed footprint"* — requiring **no CW-AI input at
all** — is substantially more accurate than the Tier-1 gate. At matched
coverage ~0.24 the no-CW-AI rule still wins.

**Verdict: the mechanism works but is dominated by a simpler free alternative.**
Tier-1 wear confounds attribution *by* producing spurious anomalies; the Tier-2
rule detects that corruption by its consequence rather than its cause, more
cheaply and more accurately. This is an obvious design-around.

**Caveat and the only recovery route.** The model gives Tier-1 wear a single
consequence — spurious anomalies — which is precisely what the Tier-2 rule
detects. If real transport wear also *biases values without breaking footprint
consistency*, Tier-1 information would carry something the Tier-2 rule cannot
see. **That is a bench-rig question and it is the only way Claim 1 recovers.**

### 9.1 SENSITIVITY — the verdict above is NOT robust

**Date:** 2026-08-05. The result in §9 was a point estimate at one unaudited
parameter value. It has now been swept.

The corruption model has two competing parameters, both moved into `config.py`:

- `TIER1_SPURIOUS_ANOMALY_GAIN` — wear ADDS unrelated anomalous sensors,
  usually breaking footprint consistency, which the free Tier-2 rule detects.
- `TIER1_SILENT_MASK_GAIN` — wear ATTENUATES a genuine anomaly, leaving the
  footprint consistent with a smaller hypothesis. The free rule accepts it and
  attributes confidently to the wrong segment. Only Tier-1 can catch this.

Comparison at **matched coverage 0.40** (both gates abstain on their worst 60%
of sessions). Margin = free-rule error − Tier-1 error; **positive means Claim 1
wins**. n = 3000.

| spurious | margin @ silent = 0.0 | margin @ silent = 1.0 |
|---|---|---|
| 0.000 | **+0.043** | **+0.073** |
| 0.010 | **+0.032** | **+0.071** |
| 0.020 | **+0.018** | **+0.061** |
| 0.030 | **+0.006** | **+0.053** |
| 0.050 | −0.015 | **+0.037** |
| 0.070 | −0.035 | **+0.017** |
| 0.100 | −0.051 | +0.001 |
| 0.250 | −0.152 | −0.117 |
| **0.500** *(the §9 value)* | **−0.090** | −0.082 |

**Break-even sits at a spurious gain of ≈ 0.035 (no silent masking) to ≈ 0.10
(maximal silent masking). §9 used 0.50 — roughly 14x above break-even.**

**Corrected verdict: Claim 1 is UNDETERMINED, not dead.** The §9 falsification
holds only if real transport wear produces spurious anomalies at a rate well
above ~3.5% per sensor per unit wear. That number was invented and has never
been measured. Claim 1 wins across the entire low-spurious region, and silent
masking widens the region in which it wins.

**This is now the single most decision-relevant measurement in the project**,
and it converts bench Experiment A from a qualitative question into a
quantitative one with a pre-registered threshold (`bench_setup.md` §5.3).

**Process note.** This parameter sat in a test file, outside the config audit,
and by itself determined a claim-level verdict. All three such constants have
been moved to `config.py`. Any future constant that governs an experimental
outcome belongs there, not in a test.

---

## 10. Sensitivity audit of the remaining invented constants

**Date:** 2026-08-05. Prompted by §9.1, where one unaudited constant sitting 14x
from break-even had flipped a claim verdict. Every constant that gates a claim
has now been swept.

**Headline: Claim 3's falsification is ROBUST. Claim 1's was not. Claim 4 is
gated by one measurable quantity.**

### 10.1 Claim 3 — robustly falsified, three independent ways

*Load-response grid* (pair B, severity re-matched at every point, N=30).
Reinstatement bar is probe − passive ≥ +0.10:

| conn coupling | load sens | passive | probe | margin |
|---|---|---|---|---|
| 0.00 | 0.9 / 1.8 / 3.6 | 0.617 / 0.850 / 0.817 | 0.317 / 0.533 / 0.483 | −0.300 / −0.317 / −0.333 |
| 0.15 | 0.9 / 1.8 / 3.6 | 0.617 / 0.850 / 0.817 | 0.333 / 0.500 / 0.250 | −0.283 / −0.350 / −0.567 |
| 0.35 | 0.9 / 1.8 / 3.6 | 0.617 / 0.850 / 0.817 | 0.367 / 0.317 / 0.550 | −0.250 / −0.533 / −0.267 |

Passive wins at **every** grid point, including zero connector coupling — the
maximum-contrast case most favourable to the probe.

*Probe duration* (equal observation time both arms):

| duration | passive | probe | margin |
|---|---|---|---|
| 2 s (safety cap) | 0.600 | 0.533 | −0.067 |
| 10 s | 0.683 | 0.500 | −0.183 |
| 60 s | 0.717 | 0.550 | −0.167 |
| 120 s | 0.783 | 0.583 | −0.200 |

The 2 s safety cap is **not** what defeats the probe — extending it 60x does not
help. The margin gets worse, not better.

*Contact time constant* (is `expected_lag_ms` reinstatable?):

| `CONTACT_RESPONSE_LAG_MS` | 5 | 20 | 80 | 200 | 400 |
|---|---|---|---|---|---|
| signed-lag AUC | 0.521 | 0.516 | 0.521 | 0.609 | 0.511 |
| envelope-lag AUC | 0.519 | 0.533 | 0.587 | **0.682** | 0.504 |

Peak 0.682 at 200 ms, below the 0.75 reinstatement bar. **Lag is not
reinstatable at any plausible contact time constant.** The deletion of
`ProbeSignature.expected_lag_ms` stands.

**Verdict: unlike Claim 1, Claim 3's falsification does not depend on a
parameter guess.** It survives every sweep attempted. Claim 3 is dead on
discrimination; only the actuation-channel argument remains.

### 10.2 Claim 1 — favourable-region win is robust to CW-AI noise

At spurious = 0.02, silent = 0.5 (the region where Claim 1 wins):

| `CWAI_NOISE` | 0.05 | 0.15 | 0.30 | 0.50 | 0.80 |
|---|---|---|---|---|---|
| confound AUC | 1.000 | 1.000 | 0.997 | 0.955 | 0.829 |
| Claim-1 margin | +0.041 | +0.040 | +0.029 | +0.030 | +0.005 |

Claim 1's advantage survives CW-AI noise up to ~0.5 and only collapses at 0.8.
**Its fate rests on the spurious rate (§9.1), not on detector quality.**

### 10.3 Claim 4 — gated by one measurable quantity

| `CONTACT_LOAD_SENSITIVITY` | A→C type transfer | C rail: footprint → hybrid | mechanism? |
|---|---|---|---|
| 0.0 | 0.447 | 0.467 → 0.600 | **NO** |
| 0.2 | 0.653 | 0.467 → 0.650 | **NO** |
| 0.5 | 0.787 | 0.467 → 0.667 | yes |
| 1.0 | 0.873 | 0.467 → 0.717 | yes |
| 1.8 | 0.893 | 0.467 → 0.750 | yes |
| 3.6 | 0.927 | 0.467 → 0.750 | yes |

**Claim 4 requires `CONTACT_LOAD_SENSITIVITY` ≥ ~0.5.** Below that the type
prior carries no transferable signal — accuracy falls to the majority baseline.
This is directly measurable on the bench (dropout rate vs co-resident current
draw) and joins the spurious rate as a pre-registered target.

### 10.4 Code-hygiene finding: a duplicated physics path

While sweeping, `foae/simulator/faults.SHARED_GROUND_COUPLING` was found to have
**no effect on any Claim 2 or Claim 4 result** — including when set to 0.0,
which should have destroyed the mechanism entirely.

Cause: `tests/test_generalization.py:114` calls `intermittent.contact_gate`
directly rather than going through `faults.SharedGroundIntermittentFault`, so
the constant is never read. The generalisation experiments run their own
duplicate physics path.

Consequences:
- `measurement_gaps.md` §2.3 attributed Claim 4's mechanism to the wrong
  constant. **Corrected.**
- Three experiments now instantiate contact physics by two different routes.
  This must be unified before `epdg/` is built, or further sweeps will
  silently measure nothing — as this one did.

**This is the same failure mode as §9.1**: a quantity believed to govern a
result did not, and nothing surfaced the discrepancy. It was caught only by
sweeping to an extreme value and noticing the output did not move. **Sweeping to
a value that should break the mechanism is now a required step in any
sensitivity analysis here.**

### 10.5 Physics path unified — Claim 2 and Claim 4 re-run

**Date:** 2026-08-05. `test_generalization._faulted_residual` now routes through
`faults.ConnectorDropoutFault` / `faults.SharedGroundIntermittentFault`. There
is one physics implementation.

*Liveness confirmed:* `SHARED_GROUND_COUPLING` at 0.0 gives A→B type transfer
**0.527** (chance); at 1.0 it gives **0.861**. Previously both gave 0.864.

*Re-run at defaults — every figure bit-identical:*

| | before | after |
|---|---|---|
| waveform A→A / A→B | 0.867 / 0.882 | 0.867 / 0.882 |
| footprint →B overall / conn / rail | 0.791 / 1.000 / 0.425 | identical |
| shuffled topology overall / rail | 0.664 / 0.075 | identical |
| Config B hybrid net gain | +0.086 | +0.086 |
| Config C hybrid net gain | +0.000 | +0.000 |

Expected: at coupling 1.0 the unified path computes `mod = 1.0 * load`, exactly
the old expression, and the `clip(0, 2)` is a no-op for load ∈ [0, 1]. **No
claim result changes. The refactor is behaviour-preserving and the constant is
now sweepable.**

*The sweep that was previously impossible:*

| `SHARED_GROUND_COUPLING` | A→B type | B rail fp→hyb | C rail fp→hyb | mechanism? |
|---|---|---|---|---|
| 0.00 | 0.527 | 0.400 → 0.733 | 0.467 → 0.600 | **NO** |
| 0.10 | 0.600 | 0.400 → 0.700 | 0.467 → 0.650 | **NO** |
| 0.25 | 0.752 | 0.400 → 0.800 | 0.467 → 0.667 | yes |
| 0.50 | 0.824 | 0.400 → 0.850 | 0.467 → 0.717 | yes |
| 1.00 | 0.861 | 0.400 → 0.900 | 0.467 → 0.750 | yes |
| 2.00 | 0.879 | 0.400 → 0.917 | 0.467 → 0.750 | yes |

**Claim 4 requires shared-ground coupling ≥ ~0.25.** Below that the type prior
degrades to chance and the mechanism is absent — the same conclusion the
`CONTACT_LOAD_SENSITIVITY` sweep (§10.3) reached by the other route, now
confirmed on the parameter that directly represents the physics. Both are
measurable in bench Experiment B.

---

## 11. Recorded result: Claim 1 gate, measured on live code — GATE IS LOAD-BEARING

**Date:** 2026-08-15 · **Source:** `foae/attribution/footprint.py` +
`foae/epdg/graph.py` · **Status:** live-code result, not a simulation sweep

Every other Claim 1 number in this document came from a parameterised sweep over
invented constants (§9, §9.1). This one is different in kind: it is the actual
attributor, running on the actual EPDG, on the S3 observation. It measures what
the gate *prevents*, which is the only part of Claim 1 that does not depend on
`TIER1_SPURIOUS_ANOMALY_GAIN`.

### Protocol

Present the S3 observation — all six PIDs anomalous, including
`control_module_voltage` — and attribute it twice: once with the Tier-1 gate
tripped, once with the gate forced to `PASS`.

### Result

| gate | outcome | segment | score | top-2 margin |
|---|---|---|---|---|
| `TRIPPED` | **ABSTAIN**, reason `tier1_confound` | — | `null` | — |
| `PASS` (gate disabled) | **attributes, does not abstain** | `SEG_RAIL_GND_A` | **0.500** | **0.167** |

With the gate disabled the system names `SEG_RAIL_GND_A` — a Tier-2 shared
ground rail — for an observation whose actual cause is common-mode. It is not a
marginal call that a threshold would have caught: the margin over the runner-up
is 0.167, comfortably above `TIER2_AMBIGUOUS_MARGIN` (0.10), so the collision
abstention does **not** fire either. The wrong answer arrives with confidence.

This is the Claim 1 argument demonstrated rather than asserted: without the
gate, a common-mode fault is silently converted into a specific, confident,
incorrect harness-segment verdict, and nothing downstream flags it.

### Reproduce

```
python -c "from foae.epdg.graph import build_epdg; from foae.attribution.footprint import attribute, Tier1Assessment, GATE_PASS; g=build_epdg(); obs={'engine_rpm','vehicle_speed','coolant_temp','intake_map','maf_rate','control_module_voltage'}; a=attribute(obs, g, Tier1Assessment(gate=GATE_PASS, confound_score=0.11)); c=a.candidates; print('segment=%s score=%.3f margin=%.3f abstained=%s' % (a.segment_id, a.confidence, c[0].match_score-c[1].match_score, a.abstained))"
```

Expected output:

```
segment=SEG_RAIL_GND_A score=0.500 margin=0.167 abstained=False
```

### What this does and does not establish

It establishes that the gate changes the outcome on a case where the
un-gated answer is wrong — the mechanism is load-bearing, not decorative. The
`CMV_ANOMALY_FORCES_ABSTAIN` sweep confirms the same thing from the other side:
flipping it to `False` flips S3 from abstention to `SEG_RAIL_GND_A`.

It does **not** establish the rate at which this happens in the field. That is
still bench Experiment A, and `TIER1_SPURIOUS_ANOMALY_GAIN` is still ~14× above
its break-even range (see `config.py`). This result says the gate matters when
the confound occurs; it says nothing about how often it occurs.

The anomaly set here is constructed, not simulated from a fault model. It is the
footprint a common-mode fault produces by definition — every PID moves — so it
does not depend on the unvalidated fault models, but it is also not evidence
that real Tier-1 wear produces exactly this set.

---

## 12. Recorded result: partial manifestation defeats footprint attribution — SILENTLY

**Date:** 2026-08-15 · **Source:** `foae/pipeline.py` scenario `S1_shared_rail`,
commit `82a7526` · **Status:** live-code result

The pipeline's first end-to-end run attributed S1 to the wrong segment. The
cause is not in the attributor. It is worth stating in full because the failure
mode is confident, silent, and structural.

### The mechanism

S1 is a `REF_5V_A` rail fault touching `engine_rpm` and `intake_map`. The
`ReferenceRailFault` kernel applies a **multiplicative** sag, so the residual it
produces scales with each PID's **signal span**. Anomaly detection thresholds
that residual against `ANOMALY_DETECT_STD` in units of each PID's **noise
floor**. Those two quantities are unrelated, so whether a sensor clears
detection is decided by the ratio of span to noise in `config.py` — not by the
severity of the fault.

| PID | residual ratio | noise floor | span | clears `ANOMALY_DETECT_STD = 2.0` |
|---|---|---|---|---|
| `engine_rpm` | **3.235** | 12.00 | 3141.7 | yes |
| `intake_map` | **1.605** | 1.20 | 139.2 | **no** |

Same fault, same severity, same instant — opposite detection outcomes.

### The consequence

The observed footprint truncates from `{engine_rpm, intake_map}` to
`{engine_rpm}`. That truncated set is explained **perfectly** by the CKP
connector:

| candidate | footprint | Jaccard |
|---|---|---|
| `SEG_CONN_CKP` | `{engine_rpm}` | **1.000** |
| `SEG_RAIL_REF_5V_A` (truth) | `{engine_rpm, intake_map}` | 0.500 |
| `SEG_RAIL_GND_A` | `{engine_rpm, intake_map, coolant_temp}` | 0.333 |

Attribution returns `SEG_CONN_CKP` at confidence **1.000**, with a **0.500**
margin over the true segment. That margin is five times
`TIER2_AMBIGUOUS_MARGIN`, so the collision abstention does not fire. Nothing in
the output distinguishes this from a correct answer: **a shared-rail fault is
converted into a confident single-connector verdict, and no signal is raised.**

The workshop consequence is the exact failure FOAE exists to prevent — replacing
a good CKP connector while the degraded 5V rail stays in the car.

### Why this is structural, not incidental

Every connector footprint is a **singleton**, and every sensor that sits on a
rail has its connector footprint nested strictly inside that rail's footprint.
Enumerated over the current topology, 7 of 9 segments are strict subsets of
another:

```
SEG_CONN_CKP       nested inside SEG_RAIL_GND_A, SEG_RAIL_REF_5V_A
SEG_CONN_ECT       nested inside SEG_RAIL_GND_A
SEG_CONN_MAF       nested inside SEG_RAIL_GND_B
SEG_CONN_MAP       nested inside SEG_RAIL_GND_A, SEG_RAIL_REF_5V_A
SEG_CONN_VSS       nested inside SEG_RAIL_GND_B
SEG_RAIL_REF_5V_A  nested inside SEG_RAIL_GND_A
SEG_RAIL_REF_5V_B  nested inside SEG_RAIL_GND_B
```

So **any** partially manifested rail fault produces an observation that some
smaller segment explains at least as well, and usually better — a subset always
matches a subset more tightly under set agreement. Partial manifestation does
not merely add noise to the verdict; it systematically biases it **toward the
smaller, more specific, wrong hypothesis.**

This is the same nesting structure as the §5 Pair B result, where the
early-stage `SENSOR_GND_B` fault manifests as `{vehicle_speed}` — nested inside
the rail's eventual `{vehicle_speed, maf_rate}` — and is indistinguishable from
a `C_VSS` connector fault. There it was recorded as an identifiability limit
between two hypotheses. Here it is the general case across the whole hypothesis
space.

### Relationship to the recorded 0.791 / 0.425 figures

`RAIL_MANIFEST_PROB` **was** applied when those figures were measured — they are
not full-manifestation numbers. The code path is
`tests/test_generalization.py::generate_trials` lines 154–163, which masks each
rail member at `MANIFEST_PROB` and forces at least one to manifest.

Two things follow, and they pull in opposite directions:

1. **The §7 figures already price this in.** `0.425` for rail faults against
   `1.000` for connectors *is* the measured cost of partial manifestation. The
   headline `0.791` is a blend dominated by connector faults (64% of trials),
   which is why §7 already says the headline "overstates topology's
   contribution".

2. **That experiment used a different, better attributor.**
   `footprint_attribute` (same file, lines 180–199) is a Bayesian posterior with
   a strict-subset constraint and an explicit binomial manifestation likelihood
   `p^k (1-p)^(m-k)`, plus connector/rail priors. `attribution/footprint.py`
   ships **Jaccard set agreement, which has no manifestation model at all.**

The second point does not rescue S1. Running the validation attributor's
posterior on S1's truncated observation gives:

| candidate | posterior | k / m |
|---|---|---|
| `SEG_CONN_CKP` | **0.084** | 1 / 1 |
| `SEG_RAIL_REF_5V_A` | 0.018 | 1 / 2 |

The connector still wins, by 4.7x. `PRIOR_CONNECTOR_FAULT = 0.7` is doing that,
and `config.py` already records this: the connector prior "is what breaks the
strict-subset nesting when a probe is unavailable". **Both attributors get S1
wrong.** The shipped one is worse in general — it has no manifestation model —
but this particular failure survives the better one too.

---

## 13. Recorded result: manifestation sweep and the nested-abstention prototype

**Date:** 2026-08-15 · **Source:** `tests/measure_rail_manifestation.py`
(measurement, not a test — pytest does not collect it) · **Status:** live-code

### 13.1 Accuracy against how many rail sensors clear detection

21 rail trials: three multi-sensor rails × seven severities (0.4 … 1.0).

| sensors clearing | trials | named correctly | abstained | wrong segment |
|---|---|---|---|---|
| **1 of 2** | 7 | **0 (0.00)** | 2 | **5** |
| 2 of 2 | 7 | 7 (1.00) | 0 | 0 |
| 2 of 3 | 5 | 5 (1.00) | 0 | 0 |
| 3 of 3 | 2 | 2 (1.00) | 0 | 0 |

**Full manifestation is solved; partial manifestation on a two-sensor rail is a
total loss.** Accuracy is not a gentle curve — it is a cliff at the point where
the observation stops being distinguishable from a singleton.

`SEG_RAIL_REF_5V_A` never clears both sensors below severity 0.9, so it is
wrong at every severity from 0.4 to 0.8 — this is not a narrow band. The two
abstentions at 1-of-2 are `SEG_RAIL_GND_B` at low severity, where the truncated
observation `{vehicle_speed}` happens to land on the known `C_VSS` / `REF_5V_B`
collision and abstains for the right reason by luck of topology.

The 2-of-3 row succeeds only because the two sensors that clear on `GND_A` are
`engine_rpm` and `coolant_temp`, which no smaller segment covers. Had
`intake_map` cleared instead of `coolant_temp`, `REF_5V_A` would have matched at
1.000 and won. **That row is fortunate, not robust.**

### 13.2 How often does partial manifestation happen?

At `RAIL_MANIFEST_PROB = 0.6`, 200,000 Monte Carlo draws per rail:

| rail | m | P(none) | P(partial) | P(all) | P(partial \| ≥1) |
|---|---|---|---|---|---|
| `SEG_RAIL_REF_5V_A` | 2 | 0.159 | 0.481 | 0.360 | **0.572** |
| `SEG_RAIL_GND_A` | 3 | 0.064 | 0.720 | 0.216 | **0.769** |
| `SEG_RAIL_GND_B` | 2 | 0.160 | 0.479 | 0.361 | **0.570** |

**Between 57% and 77% of manifesting rail faults manifest only partially.** The
regime in which §13.1 measures a total loss is the *majority* regime, not an
edge case. `RAIL_MANIFEST_PROB` is itself PROVISIONAL and unmeasured.

### 13.3 Prototype: `ABSTAIN_ON_NESTED_FOOTPRINT` — DOES NOT WORK

Rule: abstain when the winning segment's footprint is a strict subset of another
viable candidate's and the difference is explainable by non-manifestation.
Implemented behind `config.ABSTAIN_ON_NESTED_FOOTPRINT`, **default off**.

Effect on the scenarios:

| scenario | flag OFF | flag ON |
|---|---|---|
| `S1_shared_rail` | names `SEG_CONN_CKP` (wrong) | ABSTAIN `nested_footprint` ✔ |
| `S2_single_connector` | names `SEG_CONN_ECT` (**correct**) | **ABSTAIN** ✘ |
| `S5_rail_full_manifest` | names `SEG_RAIL_REF_5V_A` (**correct**) | **ABSTAIN** ✘ |
| `S3_tier1_confound` | ABSTAIN `tier1_confound` | unchanged |
| `S4_footprint_collision` | ABSTAIN `footprint_collision` | unchanged |

Effect on the 21-trial sweep:

| | correct | abstained | wrong |
|---|---|---|---|
| flag OFF | 14 (0.67) | 2 | 5 |
| flag ON | **12 (0.57)** | 9 | **0** |

It eliminates every wrong answer and costs two correct ones, and net accuracy
**falls** from 0.67 to 0.57.

**Why it fails, precisely.** A segment is nameable under this rule only if its
footprint is *maximal* — a strict subset of nothing else. In the current
topology exactly **two of nine** segments qualify: `SEG_RAIL_GND_A` and
`SEG_RAIL_GND_B`. Every connector segment and both reference rails become
permanently unnameable, whatever the evidence.

That is fatal, and not because of a tuning choice. Connector faults are the most
common failure mode in the field — `PRIOR_CONNECTOR_FAULT = 0.7` encodes exactly
that — and a connector footprint is a singleton nested inside its rails by
construction. **The rule abstains on the majority failure mode by design.** S2
is a clean, correctly-attributed single-connector fault and the rule refuses it.

**Verdict: do not enable.** The flag stays `False` and the prototype is retained
only as the record of a mechanism that was tested and rejected. Suppressing the
§12 failure by this route costs the claim its usefulness — it converts FOAE from
a system that is sometimes wrong into a system that is almost always silent.

A correction that distinguishes "subset because non-manifestation" from "subset
because the fault really is the smaller segment" needs evidence the footprint
does not contain — a probe (Claim 3, falsified for discrimination), a fault-type
prior (Claim 4, not fileable), or the sensor-level severity information that
detection currently discards at the threshold. That last one is untried and is
the only route not already closed.

---

## 14. Recorded result: graded evidence — NEGATIVE, and it re-imports Claim 4's problem

**Date:** 2026-08-15 · **Source:** `foae/attribution/footprint.py`
`score_segments_graded`, measured by `tests/measure_rail_manifestation.py` ·
**Status:** live-code result

§13.3 closed the abstention route and noted one mechanism still untried: the
residual magnitude that detection discards at the threshold. This section tests
it. **It does not work, and it fails in an informative way.**

### What was built

Thresholding is removed from the path before attribution: per-sensor residual
ratios are passed through to `attribute()` intact. Each ratio becomes a soft
membership `s_i` via a logistic centred on `ANOMALY_DETECT_STD`, so the graded
path is a softening of the existing boundary, not a new one. Candidates are then
scored with the binomial manifestation likelihood from
`tests/test_generalization.py::footprint_attribute`, conditioned on graded rather
than thresholded evidence:

```
P(evidence | F) = PROD_{i in F}    [ p*s_i + (1-p)*(1-s_i) ]
                * PROD_{j not in F} [ (1-s_j) ]
```

With every `s_i` in {0,1} this reduces exactly to `p^k (1-p)^(m-k)` with the
`observed <= expected` constraint, so the graded scorer is a strict
generalisation of the validated attributor. The binary path is untouched and
remains the default (`config.USE_GRADED_EVIDENCE = False`).

### Result at the configured constants — strictly worse

| scenario | binary | graded |
|---|---|---|
| S1 (partial rail) | `SEG_CONN_CKP` wrong, 1.000 | `SEG_CONN_CKP` **still wrong**, 0.536 |
| S2 (connector) | `SEG_CONN_ECT` correct | `SEG_CONN_ECT` correct, 0.890 |
| S5 (full rail) | `SEG_RAIL_REF_5V_A` **correct** | `SEG_CONN_CKP` **REGRESSES to wrong** |
| S4 (collision) | ABSTAIN `footprint_collision` | `SEG_CONN_VSS` **REGRESSES to wrong** |
| S3 (Tier-1) | ABSTAIN | ABSTAIN (unchanged) |

The 21-trial sweep, by sensors clearing detection:

| sensors clearing | trials | binary ok/abst/wrong | graded ok/abst/wrong |
|---|---|---|---|
| **1 of 2** | 7 | 0 / 2 / 5 | **0 / 0 / 7** |
| 2 of 2 | 7 | **7 / 0 / 0** | 3 / 3 / 1 |
| 2 of 3 | 5 | **5 / 0 / 0** | 3 / 1 / 1 |
| 3 of 3 | 2 | 2 / 0 / 0 | 2 / 0 / 0 |
| **TOTAL** | 21 | **14 / 2 / 5 — 0.67** | **8 / 4 / 9 — 0.38** |

**The 1-of-2 case, which this mechanism was built to fix, does not improve at
all: 0 correct before, 0 correct after.** The two cases binary got right by
abstaining (`SEG_RAIL_GND_B` at low severity, landing on the `C_VSS`/`REF_5V_B`
collision) become confident wrong answers. Graded evidence converted two honest
declines into two errors and gained nothing.

### Why S4 regresses — the prior does the work

`SEG_CONN_VSS` and `SEG_RAIL_REF_5V_B` have **identical** footprints, so their
likelihoods are identical by construction. Only the priors differ
(`0.7/5 = 0.14` against `0.3/4 = 0.075`), giving a 1.87x ratio, a normalised
margin of 0.215, and no abstention. The binary path scored both at Jaccard
1.000, saw a zero margin, and correctly declined.

Two segments with identical footprints are genuinely indistinguishable from
footprint evidence. **The graded path manufactures a verdict from the prior and
presents it as a finding.** That is worse than being wrong — it is being wrong
in a way that looks like evidence.

### Dependence on `PRIOR_CONNECTOR_FAULT` — the decisive result

Sweeping the prior, with sweep accuracy over the same 21 trials:

| `PRIOR_CONNECTOR_FAULT` | binary S1 | binary acc | graded S1 | graded acc |
|---|---|---|---|---|
| 0.3 | wrong | 0.67 | **correct** | **0.86** |
| 0.5 | wrong | 0.67 | ABSTAIN | 0.62 |
| **0.7 (configured)** | wrong | 0.67 | wrong | **0.38** |
| 0.9 | wrong | 0.67 | wrong | 0.24 |

The full grid over both invented constants:

```
  width \ prior_conn   0.3     0.5     0.7     0.9
  0.10                 0.76    0.67    0.67    0.52
  0.25                 0.86    0.67    0.52    0.38
  0.50                 0.86    0.62    0.38    0.24
  1.00                 0.81    0.57    0.24    0.10
  2.00                 0.43    0.33    0.10    0.00
```

**Graded evidence beats binary only in the `prior_conn = 0.3` column, and S1 is
attributed correctly only there.** Everywhere else it is equal or worse, and at
the configured 0.7 it is far worse. Answering the question directly: graded
evidence does not remove the dependency on that constant — **it creates one.**

The binary path is *prior-independent*: `score_segments` is pure Jaccard and
reads neither `PRIOR_CONNECTOR_FAULT` nor `PRIOR_RAIL_FAULT`. Those two
constants are dead in the shipped attributor. Graded scoring makes them
load-bearing, and the value at which the mechanism works — `0.3`, meaning rail
faults *more* common than connector faults — is the **opposite** of the
justification recorded for the constant in `config.py` ("connector faults are
the more common failure mode in field data").

**This is Claim 4's problem reappearing inside Claim 2.** Claim 4 was ruled NOT
FILEABLE because it needs field data on connector-vs-shared-wire fault rates
that no bench can produce (`handoff.md` §4 task 3, the longest-lead item). The
graded mechanism's entire benefit is purchased with that same unmeasured
quantity, set to a value the project's own documentation contradicts. A claim
resting on it would inherit Claim 4's blocker.

### Rule 1 sweep of the invented width

`GRADED_EVIDENCE_WIDTH` is invented, so it was swept (at `prior_conn = 0.7`):

| width | S1 | S5 | sweep acc |
|---|---|---|---|
| 0.10 | wrong | correct | 0.67 |
| 0.25 | wrong | ABSTAIN | 0.52 |
| 0.50 | wrong | wrong | 0.38 |
| 1.00 | wrong | wrong | 0.24 |
| 2.00 | ABSTAIN | wrong | 0.10 |
| 4.00 | ABSTAIN | ABSTAIN | 0.00 |

Accuracy is monotonically decreasing in width. The best available width is the
limit `width -> 0`, which **is** the binary path. At the configured prior there
is no width at which graded evidence helps.

### Verdict

**Negative. Do not enable.** `USE_GRADED_EVIDENCE` stays `False`.

Soft evidence was the last untried mechanism after the probe (Claim 3,
falsified) and the type prior (Claim 4, not fileable). It does not recover the
partial-manifestation case. Its only favourable region requires inverting an
unmeasured field-data constant, which converts a Claim 2 result into a Claim 4
dependency.

Stated plainly for the IDF: **on the shipped attributor, a partially manifested
shared-rail fault is attributed to a connector segment with full confidence, and
no mechanism tested so far detects or prevents it.** Claim 2's value is real for
fully manifested rail faults and for connector faults; it does not extend to the
partial case, and §13.2 measures that case as the majority regime (57–77% of
manifesting rail faults) under an unmeasured `RAIL_MANIFEST_PROB`.

---

## 15. Recorded result: strict-subset abstention under cost-asymmetric metrics — ZERO, THEN BROKEN

**Date:** 2026-08-15 · **Source:** `tests/measure_subset_abstention.py`
(measurement, not a test) · **Status:** live-code result

§13.3 rejected the strict-subset rule on raw accuracy (0.67 → 0.57). Accuracy
weights a wrong answer and a decline equally, and in a workshop they are not
equal: a misattribution replaces a good part and leaves the fault in the car; a
decline sends someone to look harder. This re-runs the same rule at large n
against **misattribution rate**, the number that actually matters.

**Protocol.** 1260 trials — 560 rail (4 rails × 7 severities × 20 seeds) and 700
connector (5 connectors × 7 severities × 20 seeds). Manifestation is generative:
each rail trial draws a manifest mask at `RAIL_MANIFEST_PROB`, forcing at least
one member, and the fault kernel is applied only to those sensors. All physics
routes through `simulator/faults.py`. Trial seeding uses `zlib.crc32`, not
`hash()` — Python salts string hashing per process, and the first draft of this
harness was not reproducible between runs. Two consecutive processes now produce
byte-identical output.

### 15.1 Rates at the configured values

| | binary only | binary + strict-subset |
|---|---|---|
| **ALL** (n=1260) | correct 0.5198 · abstain 0.3294 · **misattrib 0.1508 (190)** | correct 0.0762 · abstain 0.9238 · **misattrib 0.0000 (0)** |
| connector (n=700) | correct **0.7814** · abstain 0.2186 · misattrib 0.0000 | correct **0.0000** · abstain **1.0000** · misattrib 0.0000 |
| rail (n=560) | correct 0.1929 · abstain 0.4679 · **misattrib 0.3393** | correct 0.1714 · abstain 0.8286 · **misattrib 0.0000** |

Broken out by sensors of the true footprint clearing detection:

| clearing | n | binary correct / abstain / **wrong** | subset correct / abstain / **wrong** |
|---|---|---|---|
| 0 of 1 / 2 / 3 | 15 / 56 / 14 | 0.000 / 1.000 / **0.000** | 0.000 / 1.000 / **0.000** |
| 1 of 1 | 825 | 0.663 / 0.337 / **0.000** | 0.000 / 1.000 / **0.000** |
| **1 of 2** | 170 | 0.000 / 0.306 / **0.694 (118)** | 0.000 / 1.000 / **0.000** |
| **1 of 3** | 67 | 0.000 / 0.000 / **1.000 (67)** | 0.000 / 1.000 / **0.000** |
| 2 of 2 | 54 | **1.000** / 0.000 / 0.000 | 0.778 / 0.222 / 0.000 |
| 2 of 3 | 53 | 0.906 / 0.000 / **0.094 (5)** | 0.906 / 0.094 / 0.000 |
| 3 of 3 | 6 | 1.000 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 |

Two things stand out. Binary **never misattributes a connector fault** (0 of
700) — all 190 of its errors are rail faults, and partial manifestation is where
they live: 1-of-3 misattributes at rate 1.000. And the subset rule's benefit is
purchased almost entirely from connector faults, which drop from 0.7814 correct
to **zero, by construction**.

### 15.2 Is misattribution actually zero? Yes — and then no

**At n=1260 with the configured constants, and across all nine cells of the
parameter grid in §15.4, misattribution is exactly 0.** Not small — zero. No
counter-example exists in ~2900 evaluated trials.

That is a strong claim, so it was attacked. Every measurement above shares one
assumption: **detection never produces a false positive.** No sensor outside the
true footprint is ever flagged. That assumption is not safe — `config.py`'s
`TIER1_SPURIOUS_ANOMALY_GAIN` exists precisely because Tier-1 wear "makes
unrelated sensors look anomalous", and its comment says this *adds* sensors to
the observed footprint.

Injecting **one** spurious anomalous sensor per trial:

```
evaluated 4480 perturbed observations
>>> 1070 MISATTRIBUTIONS (0.2388) - THE RULE IS BREAKABLE
```

| truth | named | spurious sensor | observed |
|---|---|---|---|
| `SEG_RAIL_REF_5V_A` | `SEG_RAIL_GND_A` | `coolant_temp` | `{coolant_temp, engine_rpm}` |
| `SEG_RAIL_REF_5V_B` | `SEG_RAIL_GND_B` | `maf_rate` | `{maf_rate, vehicle_speed}` |
| `SEG_RAIL_GND_A` | `SEG_RAIL_REF_5V_A` | `maf_rate` | `{engine_rpm, intake_map, maf_rate}` |
| **`SEG_CONN_CKP`** | **`SEG_RAIL_GND_A`** | `coolant_temp` | `{coolant_temp, engine_rpm}` |
| **`SEG_CONN_MAP`** | **`SEG_RAIL_GND_A`** | `coolant_temp` | `{coolant_temp, intake_map}` |

(10 distinct `(truth, named, spurious)` combinations; first trial listed for
each. Severity and seed recorded in the harness output.)

**The mechanism.** The rule fires only when `observed ⊆ top.footprint`. A single
stray sensor breaks that containment, the subset test never runs, and a larger
segment is named with nothing declining. The protection is not a property of the
rule — it is a property of clean detection.

Note the direction of the last two rows: a **connector** fault misattributed to
a **shared ground rail**. That is the reverse of the §12 failure and
operationally worse — it sends a workshop to replace a ground harness instead of
one connector.

**So: "never misattributes" is false.** It holds only in a regime with no
false-positive detection, which is precisely the regime the project already
knows does not hold.

### 15.3 What remains nameable

| nameable segment | footprint |
|---|---|
| `SEG_RAIL_GND_A` | `coolant_temp, engine_rpm, intake_map` |
| `SEG_RAIL_GND_B` | `maf_rate, vehicle_speed` |

**2 of 9 segments.** As predicted structurally in §13.3, only footprints that
are maximal under inclusion survive. Every connector segment and both reference
rails can only ever be declined, never named, whatever the evidence.

Share of trials whose true segment is even nameable: **280/1260 = 0.222.**
The other 77.8% are unanswerable by construction — and since connector faults
are the majority field failure mode (`PRIOR_CONNECTOR_FAULT = 0.7`), the real
share is worse than this trial mix suggests.

### 15.4 Grid over `RAIL_MANIFEST_PROB` × `ANOMALY_DETECT_STD`

Strict-subset ON, 180 trials per cell:

| manifest_p | detect_std 1.5 | 2.0 | 3.0 |
|---|---|---|---|
| 0.4 | 0.0389 / **0.0000** | 0.0333 / **0.0000** | 0.0167 / **0.0000** |
| 0.6 | 0.1056 / **0.0000** | 0.0833 / **0.0000** | 0.0556 / **0.0000** |
| 0.8 | 0.1778 / **0.0000** | 0.1389 / **0.0000** | 0.0833 / **0.0000** |

*(correct rate / misattribution rate)*

Zero misattribution is **not** an artifact of the configured values — it holds
across the whole grid. What varies is the correct-naming rate, which rises with
manifestation probability and falls with detection threshold, peaking at 0.1778
in the most favourable cell. Even there, the rule answers fewer than one fault
in five.

### 15.5 The cost ratio at which the rule would pay

Treating an abstention as zero utility, a correct naming as `V` and a
misattribution as `-C`:

```
binary:  655 correct, 190 wrong   ->  655V - 190C
subset:   96 correct,   0 wrong   ->   96V
subset wins iff  190C > 559V  ->  C/V > 2.94
```

**The rule pays off only if one misattribution is worse than ~2.94 correct
attributions.** That is a defensible threshold for a workshop — a wrongly
replaced part plus an unfixed car plausibly costs more than three correct
diagnoses are worth — so on the configured constants, judged purely on
cost-asymmetry, the rule is arguably favourable.

**That argument does not survive §15.2.** The zero it depends on is conditional
on false-positive-free detection, and one spurious sensor drives misattribution
to 0.2388 — worse than binary's 0.1508. Under spurious detection the rule is not
a safer trade; it is a worse one that also answers 78% fewer faults.

### Verdict

**Do not enable.** `ABSTAIN_ON_NESTED_FOOTPRINT` stays `False`.

The rule achieves genuine zero misattribution in a clean-detection regime, and
that is a real property worth recording. But it costs every connector fault
(0.7814 → 0.0000 correct), leaves 2 of 9 segments nameable covering 22% of
trials, and its central guarantee fails on the addition of a single spurious
anomaly — a failure mode the project already models with a PROVISIONAL constant
set 14× above its break-even range.

This was the last option on the table. **No mechanism tested — probe (Claim 3),
type prior (Claim 4), graded evidence (§14), or subset abstention (§13.3, §15) —
recovers attribution under partial manifestation without either destroying the
common case or importing an unmeasured field-data constant.**

---

## 16. Standing conclusion

Across two candidate pairs and a latency analysis, **no simulated condition has
yet been found in which the probe outperforms passive observation.** The
identifiability-necessity argument for the lead claim is unsupported by
simulation and must not be asserted in the IDF on this evidence.

This does not falsify the lead claim's *utility*, and it says nothing about
real hardware — the simulator's fault models are unvalidated (see
`bench_setup.md`). It does mean the empirical case must come from the bench
rig, not from simulation.
