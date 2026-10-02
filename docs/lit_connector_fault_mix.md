# FOAE — Literature Review: Connector-Local vs Shared-Rail Fault Mix

**Task 3 of the handoff (§4, "no-hardware" list). Feeds `measurement_gaps.md`
§4A — the `PRIOR_CONNECTOR_FAULT / PRIOR_RAIL_FAULT` prior that gates Claim 4.**

The question this review had to answer: *does the published automotive
contact-reliability literature report the relative field incidence of
connector-local faults versus shared-rail (shared ground / 5 V reference)
faults, well enough to bound the prior?*

**Short answer: no.** The literature is deep on fretting/corrosion *mechanisms*
and establishes that contact-interface faults dominate automotive electrical
"no-fault-found" returns, but it classifies faults by *component and mechanism*,
not by *circuit topology*. "Shared rail vs dedicated connector" is a
system-integration attribute the component-reliability literature does not
track. The literature route — the one `measurement_gaps.md` §4A called
"immediately accessible" — has now been run, and it cannot close this prior.

That is a useful result: it retires the cheapest candidate source and moves the
binding path to warranty / Tier-1-manufacturer data (§4A rows 1–2), which needs
VIT-mediated NDA access and therefore should be started now.

---

## 1. What the prior actually needs

Claim 4's hybrid attributor trades connector-fault accuracy for rail-fault
accuracy. Whether that trade is a *net* gain depends on the population mix of
the two fault classes (`validation.md` §10; reproduced in `measurement_gaps.md`
§4A):

| Config | connector-local share | net gain |
|---|---|---|
| B | 64% | +0.086 |
| C | 60% | **+0.000** |

The break-even sits inside a 4-point band. So the literature would have to
resolve the connector/rail split to within a few percent to be decision-useful.
Nothing found comes close to that resolution — and, more fundamentally, nothing
found reports this split *at all*.

The distinction the prior needs is **not** the distinction the literature draws:

- **Literature axis** — *what part failed and by what mechanism*: connector
  contact, crimp/terminal, splice, bulk wire; via fretting, corrosion,
  stress relaxation, chafe.
- **FOAE axis (what Claim 4 needs)** — *is the faulted conductor shared across
  multiple sensors (rail) or dedicated to one (connector-local)?* A fretted
  contact can sit on either; a corroded splice is usually shared; a chafed
  wire can be either. The mechanism does not determine the topology, so a
  mechanism-keyed distribution cannot be re-keyed to topology.

This mismatch is the core finding. It is why no amount of the accessible
literature substitutes for warranty data that records the *replaced conductor*
in its harness context.

---

## 2. What the literature does establish (real, cited)

These are genuine, verifiable sources. Where a source is paywalled or was read
only at abstract/summary level, it is marked. Figures are attributed to the
specific source, not stated as consensus.

| # | Source | What it supports | Access |
|---|---|---|---|
| 1 | Qi, Ganesan & Pecht, "No-fault-found and intermittent failures in electronic products," *Microelectronics Reliability* **48**(5) (2008) 663–674, DOI 10.1016/j.microrel.2008.02.003 | NFF/intermittent is a large share of electronic field returns (commonly cited 30–55%; one cited apparatus study: components 21% / customer 17% / apparatus 24% / NFF 38%). Intermittent contact — loose/corroded connections — is a primary NFF cause. | Abstract + open PDF (smtnet mirror) |
| 2 | *Engineering Failure Analysis*, "Mechanisms of failure and state analysis of electrical connectors in automobiles," Vol. 173 (2025), art. 109427 (PII S1350630725001682) | Recent unified review of automotive connector degradation: fretting corrosion, oxidation, coating wear-through, stress relaxation → rising contact resistance. Confirms contact-interface degradation as the dominant automotive connector failure family. | Paywalled; abstract/summary only. Vol/art-no from indexing, unverified against full text |
| 3 | "Failure mechanisms and precautions in plug connectors and relays," *Microelectronics Reliability* (2016), PII S0026271416301743 | Connector/relay contact failure taxonomy by mechanism. | Paywalled; abstract only |
| 4 | Swingler, "The automotive connector: the influence of powering and lubricating a fretting contact interface," *Proc. IMechE Part D: J. Automobile Engineering* (2000), DOI 10.1243/0954407001527484 | Automotive fretting contact is *load/power-sensitive* — supports the physical premise behind the load-response mechanism (relevant also to Claim 3/§2.2). | Paywalled; abstract only |
| 5 | IEEE (Holm/related), "The Analysis of Failure Mechanisms of Electrical Connectors in Long-term Use Field Vehicles," IEEE Xplore | Field-vehicle connector failure-mechanism analysis. | Abstract only; full field distribution behind full text |
| 6 | IEEE Holm Conference on Electrical Contacts (ieee-holm.org) — venue | Standard venue for fretting-corrosion contact statistics; multiple mechanism/threshold papers (e.g. vibration thresholds, tin-plated fretting factors). | Venue confirmed; individual papers mostly paywalled |

**Deliberately excluded.** Several SEO/blog pages surfaced with crisp-sounding
figures ("23% of electrical failures from connectors," "84% of 2021 China
electrical recalls were harness defects"). None cite a locatable primary source
and the "23% … SAE study" attribution could not be traced to any SAE paper.
Under handoff Rule 2 these are treated as **not on record** and are not used.
They are logged here only so a future reader does not re-discover them and
mistake them for evidence.

---

## 3. What can and cannot be bounded

**Weakly bounded (one direction only).** Contact-interface faults — the
connector/terminal family — dominate automotive electrical field failures over
bulk-wire faults, and the intermittent subset (where load-sensitive, shared-rail
behaviour would live) is a large fraction of returns (source 1). This supports
the *existence* and *materiality* of both fault classes FOAE models.

**Not bounded (the number the prior needs).** The connector-local vs shared-rail
*ratio* is not reported by any source found, because:

1. Reliability studies key on component + mechanism, not shared-vs-dedicated
   topology (§1).
2. Field-distribution tables, where they exist, sit behind paywalls and — from
   abstracts — still use the component/mechanism axis, not topology.
3. Warranty-grade data that records the replaced conductor in harness context
   (the only data that *could* be re-keyed to topology) is proprietary.

So the literature moves the prior from "pure guess" to "connectors plausibly
outnumber shared-rail faults" — consistent with the 70/30 assumption's
*direction* but giving no support for its *magnitude*, and none at the few-point
resolution the break-even demands.

---

## 4. Consequence for Claim 4

`measurement_gaps.md` §4A already rules Claim 4 **UNFILEABLE until the prior is
grounded in field data**, and calls it a hard gate not resolvable by bench or
simulation. This review adds one thing: **it is not resolvable by the accessible
published literature either.**

The advantage is mix-dependent, vanishes at Config C (60%), and the controlling
parameter cannot be bounded to the needed precision from open sources. Filing
Claim 4 on this basis would assert an advantage the applicant's own evidence
shows is contingent on an unmeasured, and now demonstrably hard-to-measure,
population statistic. The gate stands.

---

## 5. Recommended next move (revised)

§4A recommended the literature route *in parallel with* a Tier-1 manufacturer
approach, with literature as the immediate, zero-cost first move. That first move
is now spent. The binding path is the proprietary-data route:

1. **VIT-mediated approach to a Tier-1 connector manufacturer** (TE
   Connectivity, Aptiv, Yazaki, Sumitomo — all with Indian operations) via
   application-engineering, ideally under an NDA / sponsored-project MoU. These
   firms hold contact-reliability statistics and routinely engage academic
   reliability work. **Longest lead time; start now.**
2. **OEM / Tier-1 warranty databases** via VIT industry contacts — best data
   (replaced part + failure mode), access is the obstacle.
3. **ARAI / ICAT** (Indian test agencies) — potentially Indian-market
   field-failure data, more relevant to an Indian filing than US/EU warranty
   data.

If none returns usable data, Claim 4 stays unfileable and should be held as a
dependent fallback, not an independent claim — consistent with the handoff's
current standing.

Even proprietary sources will likely report the component/mechanism axis, so any
data request must **explicitly ask for the shared-conductor vs
single-conductor breakdown** (or for enough per-claim detail to derive it).
Asking for "connector failure rates" will return the wrong axis again.

---

## 6. Provenance

All citations in §2 were located via web search on 2026-08-10; identifiers were
taken from indexing services (ScienceDirect PII, ADS bibcode, DOI) and are
marked where they were derived rather than read off the paper. No full paywalled
text was accessed. No identifier was expanded or inferred beyond what a source
directly showed (handoff Rule 2). Blog/SEO figures were excluded by the same
rule.
