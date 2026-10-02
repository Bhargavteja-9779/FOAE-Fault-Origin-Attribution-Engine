# IEEE Access submission checklist: ECTA / OBD-II connector wear

Build the paper: `cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main`
(13 pages, official IEEE Access class `ieeeaccess.cls`).
Cover letter: `pdflatex cover_letter` (2 pages).

## Already done

- [x] Abstract 244 words (IEEE Access limit 150–250), 10 index terms, no citations in the abstract.
- [x] All results reproducible from `ocwd/`. Every table body is generated from `ocwd/results/*.json`.
- [x] References checked against publisher and indexing records (October 2026). Corrected:
      Flowers et al. 2004 (title and authors), ROAD (author list), can-train-and-test
      (journal version, vol. 140, 103777). DOIs added where confirmed. Three
      directly relevant connector-fault papers added (Shen et al. 2017, 2018; Park et al. 2006).
- [x] Affiliation (School of Computer Science and Engineering, VIT) and corresponding author (Ragavan K).
- [x] Limitations, post-hoc choices and the related patent application disclosed in the paper.
- [x] Cover letter with the originality, approval and competing-interest statements.
- [x] Self-review as three referees; every fixable concern answered with new experiments:
      cross-model test (Markov fault process), Transformer baseline, hyperparameter sensitivity,
      window length, operating points and calibration, paired significance tests (Supplement S8–S13).
- [x] Supplementary Material (generated from the result files), graphical abstract, highlights,
      response-to-reviewers template, Word versions of all documents.
- [x] Reproducibility: `ocwd/requirements.txt`, `ocwd/get_data.sh`, `ocwd/run_all.sh`, CI workflow,
      `CITATION.cff`, 14 unit tests.

## What to upload (IEEE Author Portal / ScholarOne)

| Item | File |
|---|---|
| Main manuscript (PDF, version of record) | `main.pdf` |
| LaTeX source | `main.tex`, `sections/`, `tables/`, `figures/`, `refs.bib`, `main.bbl`, `ieeeaccess.cls`, logo PNGs |
| Cover letter | `cover_letter.pdf` (Word: `word/Cover_Letter.docx`) |
| Supplementary material | `supplementary.pdf` (Word: `word/Supplementary_Material.docx`) |
| Graphical abstract (optional) | `figures/graphical_abstract.png` |
| Editable Word copy of the manuscript | `word/Manuscript_IEEE_Access.docx` (LaTeX PDF remains the version of record) |
| Kept for the revision round | `response_to_reviewers.tex` / `word/Response_to_Reviewers_Template.docx`, `highlights.md` |

## You must do before uploading (search the source for `[ADD`)

1. **Corresponding author e-mail.** Replace `[ADD E-MAIL]` in `main.tex` (`\corresp`)
   and in `cover_letter.tex`.
2. **Biographies and photos** for all four authors (end of `main.tex`, `[ADD BIOGRAPHY]`).
   IEEE Access requires both. Put the photo in the optional argument of
   `\begin{IEEEbiography}[...]`; the exact syntax is in the comment above the biographies.
3. **Funding.** If the work was funded, add a `\tfootnote{...}` after `\address`. If not, nothing is needed.
4. **Code link.** The paper cites
   `https://github.com/Bhargavteja-9779/FOAE-Fault-Origin-Attribution-Engine` (directory `ocwd`).
   Push or merge the `claude/obdii-wear-detection-dataset-c3g668` branch so that the link works
   for reviewers.
5. **Licence (important).** The repository's `LICENSE` file says *"Proprietary – all rights
   reserved"*, but the paper says the code is publicly available. Either make the repository
   public under an open licence (MIT or Apache-2.0; see `ocwd/docs/GIT_GUIDE.md` §5), or change
   the availability sentence to "available from the corresponding author on reasonable request".
   Reviewers do check this.
6. **Patent.** Confirm with your patent agent that publishing is fine (application
   202641074361 is already filed, so this is normally fine).
7. **IEEE Author Portal (ScholarOne).** Upload `main.pdf` and the LaTeX source (`main.tex`,
   `sections/`, `tables/`, `figures/`, `refs.bib`, `main.bbl`, `ieeeaccess.cls`, the logo PNGs),
   run PDF eXpress if asked, and pay the article processing charge on acceptance.

## What the paper claims, and what it must not claim

- Healthy telemetry, excitation and usage histories are **real**. The connector **faults are
  modelled** on top of them. Never describe this as "real worn-connector data".
- Incipient wear is not detectable per window; moderate wear only with full-bus capture;
  months-ahead RUL is not achieved for polling tools. These are stated, and they are strengths.

## Likely reviewer requests, and how to answer them

| Request | Answer / action |
|---|---|
| "Validate on naturally worn connectors" | Strongest upgrade. Use `docs/bench_setup.md`; even 2–3 worn J1962 receptacles logged with a full-bus tool would answer it. |
| "Why these parameter values?" | Table I plus the robustness study: full-bus results hold under every perturbation (0.84–0.95). For polling, measure the interruption-duration distribution and the tool hold-up time first. |
| "Manufacturer coverage" | Six full-bus vehicles (three of them GM), leave-one-vehicle-out. Adding ROAD or CANdid would broaden it. |
| "More deep baselines (Transformer)" | Add in `ocwd/models.py`; the 1D-CNN and LSTM-AE are already included and are far behind (0.646 / 0.631). |
