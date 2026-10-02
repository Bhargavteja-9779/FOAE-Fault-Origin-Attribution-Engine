# OCWD project guide

**Predictive OBD-II connector wear detection from CAN telemetry.**
Companion to the IEEE Access manuscript *"Excitation-Coherent Telemetry Analysis for Predictive
OBD-II Connector Wear Detection: A Physics-Informed Study on Real In-Vehicle Network Data"*
(P. N. Bhargav Teja, Lanka Sree Chathurya, K. Arun Reddy, Ragavan K; related to Indian Patent
Application 202641074361).

---

## 1. The problem in one paragraph

Telematics, insurance and fleet devices stay plugged into the car's SAE J1962 diagnostic connector
(DLC) for years and draw power through it. The connector was designed for occasional workshop use;
vibration slowly frets its tin-plated contacts until they open intermittently. The car never
notices. The device sees lost CAN frames, missed OBD-II responses and brown-out reboots, and the
usual "fix" (replacing the device) leaves the worn connector in place. **OCWD detects, attributes
and predicts connector wear from the device's own telemetry, with no added sensor.**

## 2. Key idea

A fretted contact interrupts more often when it is **shaken harder**. Its interruption rate
therefore follows the car's own engine and road excitation, which the device can read from the
same data stream (engine-speed and vehicle-speed signals, or PIDs 0x0C/0x0D). Logger overflow,
ECU busy states and most interference do not follow excitation, and bus-wide interference is
retransmitted rather than lost. OCWD's method, **ECTA (excitation-coherent telemetry analysis)**,
turns these physical differences into features.

## 3. What is real and what is modelled

| | Source |
|---|---|
| Healthy telemetry | **Real**: five public datasets, recorded on real vehicles, never modified |
| Engine/road excitation | **Real**: decoded from each capture; it drives the wear process |
| Usage histories (prognosis) | **Real**: one year of trips per VED vehicle |
| The connector fault | **Modelled**: physics-informed fretting → intermittency → telemetry model, applied to the real data. No public dataset of naturally worn J1962 connectors exists. |

The model's unmeasured constants are stress-tested (16 perturbations), and a structurally
different fault model (bursty Markov chatter with an energy-based brown-out rule) is used to test
cross-model generalization.

## 4. Data

| Corpus | Dataset | Vehicles | Size |
|---|---|---|---|
| Full-bus passive | can-train-and-test, HCRL Car-Hacking, CAN-MIRGU | 6 (Chevrolet Impala, Traverse, Silverado; Subaru Forester; KIA Soul; undisclosed) | 2.68 h, 17.5 M frames, 6 468 windows |
| Sampling passive | CANmodes RAW | 3 (GM Cruze, Ford Fiesta, VW Gol) | 10.65 h, 12 684 windows |
| OBD-II polling | CANmodes OBD | same 3 | 9.03 h, 8 631 windows |
| Fleet polling | VED | 381 | 11 277 trips, 8.24 M records, 236 817 windows |

Download everything with `ocwd/get_data.sh`.

## 5. Code map

```
ocwd/
  loaders.py      dataset parsers; CANmodes timestamp repair; session splitting; HCRL de-duplication
  signals.py      engine/vehicle-speed decoders per vehicle
  physics.py      wear law, excitation, Poisson and Markov interruption processes,
                  passive/polling telemetry effects, confounders
  scenarios.py    paired real/faulted window generation (5 classes, 3 wear stages)
  features.py     loss, structure and excitation-coherence features (Poisson GLM, IRLS)
  models.py       ECTA (LightGBM) and baselines: IsolationForest, OC-SVM, thresholds,
                  1D-CNN, LSTM autoencoder, Transformer
  ved.py          VED trips, exposure, wear trajectories
  experiments/
    build.py            labelled windows, 3 seeds
    evaluate.py         detection + attribution (vehicle-disjoint CV, bootstrap CIs)
    summarize.py        stage-vs-healthy, confounders, per-vehicle
    accumulate.py       multi-trip evidence pooling (VED)
    prognosis.py        fleet RUL (Bayesian, censoring-aware)
    time_to_detect.py   persistent-fault time to detect (full-bus)
    observability.py    analytical observability law
    robustness.py       16 parameter perturbations
    extras.py           cross-model, window length, hyperparameters, operating points,
                        Transformer, significance tests
    figures.py          all figures and LaTeX tables
  tests/          14 unit tests (no data needed)
  results/        every number in the paper, as JSON
  figures/        every figure in the paper, as PDF
paper/            LaTeX manuscript, supplementary material, cover letter, response template
```

## 6. Run it

```bash
pip install -r ocwd/requirements.txt
bash ocwd/get_data.sh            # ~5 GB download
bash ocwd/run_all.sh             # ~4-5 h on a 4-core CPU, no GPU needed
```

Quick check without data: `PYTHONPATH=. python -m pytest -q ocwd/tests`.

## 7. Headline results (vehicle-disjoint)

| Result | Value |
|---|---|
| Full-bus detection on unseen vehicles (6-fold LOVO), wear vs everything | AUROC **0.880** (95 % CI 0.871–0.906) |
| … moderate / severe wear vs healthy | **0.891 / 0.995** |
| … per held-out vehicle | 0.869–0.921 |
| … deep baselines (1D-CNN / LSTM-AE / Transformer) | 0.646 / 0.631 / 0.641 |
| … significance vs every non-ECTA baseline (full-bus, VED) | p ≤ 0.001 (paired vehicle bootstrap) |
| … hyperparameter sensitivity (7 configurations) | ±0.004 (full-bus), ±0.015 (VED) |
| … trained on Poisson model, tested on Markov-chatter model | 0.856 (severe 0.999) |
| Full-bus time to detect moderate wear | AUROC 0.94 after 2 min of driving |
| Full-bus false alarms at 90 % severe-wear detection | 0 per hour of real healthy driving |
| Observability law vs measured detectability | Spearman 0.93 (12 tool–stage combinations) |
| Polling: coherence features vs bus EMI | 0.947 vs 0.737 without them (VED) |
| VED fleet detection (381 vehicles) | 0.775 vs 0.704 without coherence |
| Severe wear, vehicle-level after 10 trips | 0.999 |
| Fleet early warning (functional failure at 20 Ω) | 88 % timely, 1.5 % false alarms |

Limits, stated in the paper: incipient wear is not detectable in a single window, moderate wear
is not detectable by low-rate polling tools, months-ahead RUL is not achieved for polling tools,
and telling a DLC fault from an ECU-connector fault needs multi-ECU visibility.

## 8. Extending the project

* **Bench validation (highest value):** follow `docs/bench_setup.md`. Log naturally worn J1962
  receptacles with a full-bus tool (SocketCAN, listen-only) on a vibration rig, then run
  `ocwd.features.passive_features` on the captures. Measuring the interruption-duration
  distribution and the device hold-up time fixes the two most sensitive constants.
* **New vehicle:** add a decoder to `signals.DECODERS` and a loader in `loaders.py`.
* **New tool type:** implement its telemetry effect in `physics.py` (see `simulate_poll`).
* **New baseline:** add a class with `fit`/`score` in `models.py` and register it in
  `experiments/evaluate.py`.

## 9. FAQ

**Is this real data?** The healthy telemetry, the excitation and the usage are real. The faults are
modelled; that is stated everywhere, including in the paper title ("physics-informed").

**Why trust the fault model?** Its structure follows the contact literature and the CAN/ISO 15765
standards. Results hold under 16 parameter perturbations and under a structurally different
fault process, and an analytical observability law predicts the measured performance.

**Can it run on a dongle?** Yes. Features take ~23 ms per 30-s full-bus window (58 k frames) in
unoptimized Python, and the classifier is a 1.3-MB tree ensemble.
