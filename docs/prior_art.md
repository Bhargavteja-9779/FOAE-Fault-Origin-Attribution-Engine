# FOAE — Prior Art and Gap Analysis

Feeds IDF Section 3. Status: **partial** — this file currently records only the
prior-art findings established during design. The full reference table is
outstanding and must be completed before filing.

---

## 1. MANDATORY DISCLOSURE — plausibility residuals are prior art

**This must not be lost at filing.**

FOAE's `evidence/plausibility.py` computes residuals against known
PID-to-PID physical relationships (`config.PHYSICS_PAIRS`) and flags
relationships that deviate beyond tolerance.

**This is a textbook parity-space / analytical-redundancy check.** It is not a
FOAE contribution and must be described in the IDF as prior art.

| Reference | Establishes |
|---|---|
| Chow, E.Y. & Willsky, A.S., "Analytical redundancy and the design of robust failure detection systems," *IEEE Trans. Automatic Control*, 29(7), 1984 | The parity-space formulation itself: generating residuals from analytically redundant relations among sensors, and using residual structure to detect and isolate faults. |
| Gertler, J., "Survey of model-based failure detection and isolation in complex plants," *IEEE Control Systems Magazine*, 8(6), 1988 | Structured residuals for fault isolation — directly anticipates "which relationships are anomalous" as an isolation signal. |
| Isermann, R., *Fault-Diagnosis Systems*, Springer, 2006 | Consolidated treatment; automotive applications specifically. |
| Frank, P.M., "Fault diagnosis in dynamic systems using analytical and knowledge-based redundancy," *Automatica*, 26(3), 1990 | Residual generation and evaluation as the standard FDI pipeline. |

**Consequence for the claim set.** Generic sensor-fault vs component-fault
discrimination from passive residuals is owned by this literature. Any claim
drafted over "detecting that a sensor reading is implausible given other
sensors" will read on Chow & Willsky and should be expected to fail.

The IDF must state plainly: *plausibility residual generation is prior art,
used here as an input.* FOAE's asserted contribution begins after the residual
— in what is done when residuals are ambiguous.

See `docs/design.md` §6 "Not claimed".

---

## 2. Other prior art consumed, not claimed

| Item | Status |
|---|---|
| CW-AI connector-wear detection | Already-filed patent by this group. Consumed as a black box (`evidence/cwai_stub.py`). Not re-claimed. |
| MC-Dropout (Gal & Ghahramani, 2016) | Published UQ technique. Not claimed as a method. |
| Split-conformal prediction (Vovk et al.; Lei et al., 2018) | Published. Not claimed as a method. |
| CAN intrusion detection (HCRL, ROAD datasets) | Different problem. Datasets used for signal realism only; no IDS novelty asserted. |

---

## 3. Outstanding — required before filing

- [ ] Full reference table with gap column for each competing patent.
- [ ] Design-arounds for GM '553 and VW '665 (tracked in `claim_strategy.md`).
- [ ] Full active-fault-diagnosis search per §4 below.
- [ ] ORNL intermittent-fault dataset licensing.

---

## 4. MANDATORY DISCLOSURE — active fault diagnosis is mature prior art

**Second item that must not be lost at filing.**

Mechanism 1 (UTP/ADP) perturbs the system in order to diagnose it. **The idea
of perturbing a system to improve fault isolation is an established field and
must not be claimed.**

| Reference | Establishes |
|---|---|
| Nikoukhah, R., "Guaranteed active failure detection and isolation for linear dynamical systems," *Automatica*, 34(11), 1998 | Auxiliary input design for guaranteed fault isolation — active diagnosis in its canonical form. |
| Šimandl, M. & Punčochář, I., "Active fault detection and control: Unified formulation and optimal design," *Automatica*, 45(9), 2009 | Unified formulation of active fault detection; optimal input design under uncertainty. |
| Ashari, A.E., Nikoukhah, R. & Campbell, S.L., "Active robust fault detection in closed-loop systems," *IEEE Trans. Automatic Control*, 57(7), 2012 | Active detection with a controller in the loop. |
| Poulsen, N.K. & Niemann, H.H., "Active fault diagnosis based on stochastic tests," *Int. J. Applied Mathematics and Computer Science*, 18(4), 2008 | Stochastic test-signal design for diagnosis. |

**The IDF must state explicitly that mechanism 1's novelty rests on three
things, and NOT on active diagnosis as a concept:**

1. **The uncertainty trigger** — the perturbation is initiated by the
   attribution model's own epistemic uncertainty crossing a threshold, rather
   than being scheduled, operator-initiated, or continuously applied.
2. **The safety envelope** — perturbation is gated by an enforced envelope
   (excluded vehicle states, bus-utilisation ceiling, duration bound, watchdog,
   cooldown) with an immutable audit record of every allow/deny decision.
3. **The diagnostic-communication schedule as the actuation channel** — the
   stimulus is applied by modulating diagnostic request cadence on an existing
   OBD-II/UDS link. Nothing is injected into sensor signal paths and no
   additional hardware is required. Classical active FDI assumes an actuator or
   auxiliary input into the plant; here the *diagnostic protocol itself* is the
   actuator.

A claim drafted over "perturb the system and observe the response to isolate a
fault" reads on Nikoukhah and Šimandl & Punčochář and should be expected to
fail. Point 3 is likely the strongest distinguishing feature and should carry
weight in the independent claim.

See `docs/design.md` §6.
