# FOAE — Fault-Origin Attribution Engine

> **New (2026-10): `ocwd/` — Predictive OBD-II Connector Wear Detection.**
> A complete, reproducible study for Indian Patent Application 202641074361,
> evaluated on four public real-vehicle datasets (HCRL Car-Hacking,
> CAN-MIRGU, CANmodes, and the 381-vehicle VED fleet), with an IEEE Access
> manuscript in `paper/` (`paper/main.pdf`). Start with `ocwd/README.md`
> and `paper/SUBMISSION_CHECKLIST.md`. It is independent of the FOAE code
> below and does not change its tests.

Vehicle-diagnostics research backing an Indian patent filing. FOAE attributes a
diagnostic trouble code to its true origin — degraded component, biased sensor,
or electrical harness defect — and gates the DTC accordingly.

**Status: feature development is STOPPED.** The project is awaiting bench-rig
data. Do not build `epdg/` or anything downstream until it exists. See
`docs/bench_setup.md`.

---

## ⚠ Windows / cp1252 file-writing hazard — READ BEFORE WRITING ANY DOC

**A document was destroyed by this on 2026-08-05.** It is easy to repeat.

On Windows, Python's default text encoding is **cp1252**, not UTF-8. Every
document in `docs/` contains characters cp1252 cannot encode — `—` (em dash),
`≥`, `≈`, `→`, `⚠`, `σ`, `₹`.

The failure is destructive, not merely an error:

```python
pathlib.Path("docs/x.md").write_text(s)   # NEVER DO THIS
```

`write_text` opens the file — **truncating it to zero bytes** — and only then
hits `UnicodeEncodeError`. The exception looks like a harmless failed write. It
is not: the original content is already gone, and a retry that reads the
now-empty file will happily overwrite it with nothing.

### Rules

1. **Always pass `encoding="utf-8"` on every read and write of a text file.**
   ```python
   p.write_text(s, encoding="utf-8")
   s = p.read_text(encoding="utf-8")
   open(path, "w", encoding="utf-8")
   ```
2. Set `PYTHONIOENCODING=utf-8` when running scripts that print these
   characters, or console output raises the same error.
3. **Read the file back and check its size** after any scripted edit to a
   document. A zero-byte result means it was destroyed.
4. Prefer editing docs through tooling that handles encoding, rather than
   ad-hoc `write_text` scripts.
5. `foae/validation/reports.py` will generate the IDF tables. **It must open
   every output file with `encoding="utf-8"` explicitly** — the report content
   contains all of the characters above.

Committing frequently is the real safety net. A destroyed document is
unrecoverable without version control.

---

## What's here

| Path | State |
|---|---|
| `foae/config.py`, `foae/types.py` | Complete for scope built |
| `foae/simulator/`, `foae/probe/`, `foae/evidence/` | Partial — enough to run the falsification experiments |
| `foae/epdg/`, `attribution/`, `controller/`, `validation/`, `bench/`, `dashboard/`, `pipeline.py` | **Empty stubs. Not started.** |
| `tests/` | 19 tests: 12 pass, **7 fail deliberately** (see below) |
| `docs/` | The substantive output so far |

### The 7 failing tests are not defects

They are true negatives that encode falsified claims. **Do not fix them.** Each
asserts something the design originally predicted; the assertion fails because
the prediction was wrong, and the failure is the record. See
`docs/validation.md`.

---

## Documents, in reading order

| Document | Purpose |
|---|---|
| `docs/handoff.md` | **New to the project? Start here.** Status, bench thresholds, what to do first |
| `docs/ipr_briefing.md` | One page for the patent agent |
| `docs/claim_strategy.md` | Full claim set, falsification record, obviousness exposure |
| `docs/design.md` | Architecture, the two-tier harness model, claim boundary |
| `docs/validation.md` | Every experiment, its numbers, and its verdict |
| `docs/bench_setup.md` | **Priority.** Rig BOM, wiring, pre-registered protocols |
| `docs/measurement_gaps.md` | The 24 unmeasured constants and what fixes each |
| `docs/prior_art.md` | Two mandatory disclosures |

---

## Running the experiments

```bash
pip install -e ".[dev]"
PYTHONIOENCODING=utf-8 python -m pytest tests/ -q
```

Expected: **12 passed, 7 failed.** Any other result means something changed —
investigate before proceeding.

---

## ⚠ Never invent a citation

**This happened on 2026-08-05.** Two patent numbers were written into a document
intended for the patent agent. Neither had been supplied; both were plausible-
looking inventions. They were caught before the document was sent.

**Rule: never write a patent number, publication number, case citation, standard
number, DOI, or bibliographic reference that was not explicitly supplied or read
from a source in front of you.**

If a reference is needed and the identifier is not on record, write:

```
[NUMBER NOT ON RECORD]
```

Example: `GM '553 [NUMBER NOT ON RECORD] — retrieve before drafting`.

A missing identifier is a visible gap someone will fill. A fabricated one is
invisible and propagates into a legal filing. This applies to short forms too:
expanding "GM '553" into a full number is fabrication unless the full number was
given.

**Corollary for legal status:** even a correct number carries no status
guarantee. Google Patents legal-status data is machine-generated and explicitly
disclaimed. Status must be verified on USPTO Patent Center before any
freedom-to-operate reliance.

---

## Ground rules

- **Every constant that can change an experimental outcome belongs in
  `config.py`**, never in a test file. One such constant sat outside the audit
  and flipped a claim verdict (`validation.md` §9.1).
- **Sweep to a value that should break the mechanism.** A sensitivity sweep that
  never breaks anything may be measuring nothing — exactly what happened in
  `validation.md` §10.4.
- **No result here is validated against hardware.** All fault models are
  physical reasoning with no measurement behind them.
