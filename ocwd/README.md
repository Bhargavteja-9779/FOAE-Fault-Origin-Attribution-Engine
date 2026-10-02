# OCWD — Predictive OBD-II Connector Wear Detection from CAN Telemetry

Companion code for the paper *"Excitation-Coherent Telemetry Analysis for
Predictive OBD-II Connector Wear Detection"* (P. N. Bhargav Teja, Lanka Sree
Chathurya, K. Arun Reddy, Ragavan K), related to Indian Patent Application
202641074361.

The SAE J1962 diagnostic connector (DLC) carries a growing population of
permanently installed dongles (telematics, insurance, fleet). Vibration
causes fretting corrosion of its contacts; the result is intermittent data
loss and brown-out resets that are routinely misattributed to the device.
OCWD detects, attributes and predicts DLC wear **from the telemetry the
attached tool already records**, with no added sensor.

## What is real and what is modelled

| | Source |
|---|---|
| Healthy telemetry | **Real.** Four public datasets recorded on real vehicles (below). Never modified. |
| Excitation (engine / road speed) | **Real.** Decoded from each capture. Drives the wear process. |
| Usage history for prognosis | **Real.** One year of trips per VED vehicle. |
| The connector fault itself | **Modelled.** Physics-informed fretting / intermittency / brown-out model (`physics.py`) applied to the real telemetry. No public dataset of naturally worn J1962 connectors exists. |

The model's unmeasured constants are stress-tested by deliberate
mis-specification (`experiments/robustness.py`). Validation on naturally
worn connectors is the stated next step (see `docs/bench_setup.md` for the
bench protocol of the wider project).

## Datasets (all public)

| Corpus | Dataset | Vehicles | How to obtain |
|---|---|---|---|
| Full-bus passive | HCRL Car-Hacking (Seo et al., PST 2018) | KIA Soul | `git clone https://github.com/JehadAlyateem/Car-Hacking-Dataset` → unzip to `data/raw/CHD/x/` |
| Full-bus passive | CAN-MIRGU sample (Rajapaksha et al., VehicleSec 2024) | undisclosed | `git clone https://github.com/sampathrajapaksha/CAN-MIRGU data/raw/CAN-MIRGU` |
| Sampling passive + OBD polling | CANmodes (Roque et al., WCNPS 2024) | GM Cruze, Ford Fiesta, VW Gol | `git clone https://github.com/Asr-roque/canmodes-datasets data/raw/canmodes-datasets` |
| Fleet polling | VED (Oh et al., IEEE T-ITS 2022) | 383 vehicles | `git clone https://github.com/gsoh/VED data/raw/VED`, then `7z x` both `Data/VED_DynamicData_Part*.7z` into `data/raw/VED/dyn/` |

Set `OCWD_DATA` to use another location.

## Reproduce every number in the paper

```bash
pip install numpy pandas scipy scikit-learn lightgbm torch pyarrow openpyxl matplotlib joblib pytest
python -m pytest ocwd/tests -q                      # 11 unit tests, no data needed
python -m ocwd.experiments.build                    # labelled windows, 3 seeds (~15 min)
python -m ocwd.experiments.evaluate                 # detection + attribution tables (~40 min)
python -m ocwd.experiments.accumulate               # multi-trip evidence pooling
python -m ocwd.experiments.prognosis                # fleet RUL study
python -m ocwd.experiments.robustness fullbus ved   # model mis-specification
python -m ocwd.experiments.figures                  # all figures / LaTeX tables
```

Results land in `ocwd/results/*.json`, figures in `ocwd/figures/`, the paper
in `paper/` (`pdflatex main && bibtex main && pdflatex main && pdflatex main`).

## Layout

| File | Purpose |
|---|---|
| `loaders.py` | Dataset parsers, timestamp repair (CANmodes), session splitting, HCRL de-duplication |
| `signals.py` | Engine/vehicle-speed decoders for each vehicle |
| `physics.py` | Wear law, vibration, interruption process, passive/polling telemetry effects, confounders |
| `scenarios.py` | Paired real/faulted window generation |
| `features.py` | Loss, structure and excitation-coherence features (Poisson GLM) |
| `models.py` | ECTA (LightGBM) and all baselines incl. 1D-CNN and LSTM autoencoder |
| `ved.py` | VED trips, exposure, wear trajectories |
| `experiments/` | One script per table / figure |
