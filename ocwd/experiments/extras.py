"""Additional validation requested in a self-administered review (Supplement S7-S12).

    python -m ocwd.experiments.extras crossmodel window hparam oppoint transformer significance

crossmodel   train on the nominal (Poisson) fault model, test on a structurally
             different bursty Markov-chatter model with an energy-based brown-out
             criterion (same first-order statistics, different structure)
window       full-bus detection with 10-, 30- and 60-s windows
hparam       sensitivity of ECTA to its gradient-boosting hyperparameters
oppoint      false alarms per hour of real healthy driving at fixed detection
             rates, and probability calibration (Brier score, ECE)
transformer  supervised Transformer baseline on the binned sequences
significance paired vehicle-bootstrap CIs and p-values, ECTA vs. every baseline
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score, roc_curve, brier_score_loss
from sklearn.model_selection import GroupKFold

from .. import loaders, paths, physics as ph, ved
from ..models import GBM, SeqTransformer, LGB_PARAMS
from .build import _passive_session, _poll_session, _ved_trip
from .evaluate import feature_sets, folds, group_bootstrap

PROP = "Proposed (GBM, all features)"
WIN = {"fullbus": 30.0, "sampler": 60.0, "poll": 120.0, "ved": None}


def _save(name, obj):
    with open(paths.RESULTS / f"extra_{name}.json", "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=float)


def stage_metrics(y_cls, stage, s):
    y = (y_cls == 1).astype(int)
    out = {"auroc_all": roc_auc_score(y, s)}
    for st in (1, 2, 3):
        m = (y_cls == 0) | ((y_cls == 1) & (stage == st))
        out[f"s{st}_vs_healthy"] = roc_auc_score(y[m], s[m])
    return out


def _load(c):
    return pd.read_parquet(paths.CACHE / f"ds_{c}.parquet").fillna(0.0).reset_index(drop=True)


# ---------------------------------------------------------------------------
def crossmodel():
    t0 = time.time()
    pm = ph.with_params(ph.ContactParams(), process="markov")
    res = {}
    # full-bus: leave-one-vehicle-out, nominal training data of the other vehicles
    S = [s for s in loaders.all_frame_sessions() if s.vehicle in loaders.FULLBUS_VEHICLES]
    r = Parallel(n_jobs=4)(delayed(_passive_session)(s, 30.0, 7, pm, None, 0.1) for s in S)
    dm = pd.DataFrame([x for rr, _ in r for x in rr]).fillna(0.0)
    dn = _load("fullbus")
    feats = feature_sets("fullbus")["all"]
    sm, sn = np.zeros(len(dm)), np.zeros(len(dn))
    for v in dm.vehicle.unique():
        m = GBM(feats).fit(dn[dn.vehicle != v], (dn[dn.vehicle != v].cls == 1).astype(int).to_numpy())
        sm[(dm.vehicle == v).to_numpy()] = m.score(dm[dm.vehicle == v])
        sn[(dn.vehicle == v).to_numpy()] = m.score(dn[dn.vehicle == v])
    res["fullbus"] = {"train_nominal_test_nominal": stage_metrics(dn.cls.values, dn.stage.values, sn),
                      "train_nominal_test_markov": stage_metrics(dm.cls.values, dm.stage.values, sm)}
    print("crossmodel fullbus", res["fullbus"], flush=True)
    # polling (CANmodes): leave-one-vehicle-out
    P = loaders.all_poll_sessions()
    r = Parallel(n_jobs=4)(delayed(_poll_session)(s, 120.0, 60.0, 7, pm, 1.0) for s in P)
    dm = pd.DataFrame([x for rr, _ in r for x in rr]).fillna(0.0)
    dn = _load("poll")
    feats = feature_sets("poll")["all"]
    sm, sn = np.zeros(len(dm)), np.zeros(len(dn))
    for v in dm.vehicle.unique():
        m = GBM(feats).fit(dn[dn.vehicle != v], (dn[dn.vehicle != v].cls == 1).astype(int).to_numpy())
        sm[(dm.vehicle == v).to_numpy()] = m.score(dm[dm.vehicle == v])
        sn[(dn.vehicle == v).to_numpy()] = m.score(dn[dn.vehicle == v])
    res["poll"] = {"train_nominal_test_nominal": stage_metrics(dn.cls.values, dn.stage.values, sn),
                   "train_nominal_test_markov": stage_metrics(dm.cls.values, dm.stage.values, sm)}
    print("crossmodel poll", res["poll"], flush=True)
    # VED: 5-fold by vehicle, Markov test trips (10 per vehicle)
    T = ved.trips(max_per_vehicle=10, seed=3)
    r = Parallel(n_jobs=4, batch_size=8)(delayed(_ved_trip)(L, 7, pm, 600.0, 2.0, 300) for L in T)
    dm = pd.DataFrame([x for rr, _ in r for x in rr]).fillna(0.0)
    dn = _load("ved")
    dn = dn[dn.seed == 0].reset_index(drop=True)
    feats = feature_sets("ved")["all"]
    vehs = np.array(sorted(dn.vehicle.unique()))
    fold_of = {v: i % 5 for i, v in enumerate(vehs)}
    sm, sn = np.zeros(len(dm)), np.zeros(len(dn))
    for k in range(5):
        tr = dn[dn.vehicle.map(fold_of) != k]
        m = GBM(feats).fit(tr, (tr.cls == 1).astype(int).to_numpy())
        im = (dm.vehicle.map(fold_of) == k).to_numpy()
        inn = (dn.vehicle.map(fold_of) == k).to_numpy()
        sm[im] = m.score(dm[im])
        sn[inn] = m.score(dn[inn])
    ok = np.isfinite(dm.vehicle.map(fold_of).astype(float)).to_numpy()
    res["ved"] = {"train_nominal_test_nominal": stage_metrics(dn.cls.values, dn.stage.values, sn),
                  "train_nominal_test_markov": stage_metrics(dm.cls.values[ok], dm.stage.values[ok], sm[ok])}
    print("crossmodel ved", res["ved"], flush=True)
    res["seconds"] = time.time() - t0
    _save("crossmodel", res)


# ---------------------------------------------------------------------------
def window():
    S = [s for s in loaders.all_frame_sessions() if s.vehicle in loaders.FULLBUS_VEHICLES]
    feats = feature_sets("fullbus")["all"]
    p = ph.ContactParams()
    res = {}
    for W in (10.0, 30.0, 60.0):
        if W == 30.0:
            d = _load("fullbus")
            d = d[d.seed == 0].reset_index(drop=True)
        else:
            r = Parallel(n_jobs=4)(delayed(_passive_session)(s, W, 0, p, None, 0.1) for s in S)
            d = pd.DataFrame([x for rr, _ in r for x in rr]).fillna(0.0)
        s = np.zeros(len(d))
        for v in d.vehicle.unique():
            m = GBM(feats).fit(d[d.vehicle != v], (d[d.vehicle != v].cls == 1).astype(int).to_numpy())
            s[(d.vehicle == v).to_numpy()] = m.score(d[d.vehicle == v])
        res[f"{W:g}s"] = dict(stage_metrics(d.cls.values, d.stage.values, s), n_windows=int(len(d)))
        print("window", W, res[f"{W:g}s"], flush=True)
    _save("window", res)


# ---------------------------------------------------------------------------
GRID = {"default (400 trees, 31 leaves, lr 0.05)": {},
        "200 trees": {"n_estimators": 200}, "800 trees": {"n_estimators": 800},
        "15 leaves": {"num_leaves": 15}, "63 leaves": {"num_leaves": 63},
        "lr 0.1": {"learning_rate": 0.1}, "lr 0.02, 1000 trees": {"learning_rate": 0.02, "n_estimators": 1000}}


def hparam():
    import lightgbm as lgb
    res = {}
    for c in ("fullbus", "poll", "ved"):
        d = _load(c)
        if c == "ved":
            d = d[d.seed == 0].reset_index(drop=True)
        feats = feature_sets(c)["all"]
        F = folds(d, c)
        y = (d.cls == 1).astype(int).to_numpy()
        res[c] = {}
        for name, kw in GRID.items():
            prm = dict(LGB_PARAMS, **kw)
            s = np.zeros(len(d))
            for tr, te in F:
                m = lgb.LGBMClassifier(random_state=0, class_weight="balanced", **prm)
                m.fit(d.iloc[tr][feats].to_numpy(np.float32), y[tr])
                s[te] = m.predict_proba(d.iloc[te][feats].to_numpy(np.float32))[:, 1]
            res[c][name] = stage_metrics(d.cls.values, d.stage.values, s)
            print("hparam", c, name, {k: round(v, 3) for k, v in res[c][name].items()}, flush=True)
    _save("hparam", res)


# ---------------------------------------------------------------------------
def _ece(y, p, bins=10):
    e = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for a, b in zip(edges[:-1], edges[1:]):
        m = (p >= a) & (p < b) if b < 1 else (p >= a) & (p <= b)
        if m.any():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(e)


def oppoint():
    res = {}
    for c in ("fullbus", "sampler", "poll", "ved"):
        o = pd.read_parquet(paths.CACHE / f"oof_{c}.parquet")
        d = _load(c)
        W = WIN[c] if WIN[c] else float(d.loc[d.cls == 0, "W"].median())
        s = o[PROP].to_numpy()
        y = (o.cls == 1).to_numpy()
        h = (o.cls == 0).to_numpy()
        r = {"window_s": W, "brier": float(brier_score_loss(y, s)), "ece": _ece(y.astype(float), s)}
        for st in (2, 3):
            pos = ((o.cls == 1) & (o.stage == st)).to_numpy()
            for tpr in (0.80, 0.90, 0.95):
                thr = np.quantile(s[pos], 1 - tpr)
                fpr_h = float((s[h] >= thr).mean())
                conf = (o.cls >= 2).to_numpy()
                fpr_c = float((s[conf] >= thr).mean())
                r[f"s{st}_tpr{int(tpr * 100)}"] = {
                    "fpr_healthy": fpr_h, "false_alarms_per_hour_healthy": fpr_h * 3600.0 / W,
                    "fpr_confounders": fpr_c}
        res[c] = r
        print("oppoint", c, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if not isinstance(v, dict)},
              r["s3_tpr90"], flush=True)
    _save("oppoint", res)


# ---------------------------------------------------------------------------
def transformer(deep_max=10000):
    res = {}
    rng = np.random.default_rng(0)
    for c in ("fullbus", "sampler", "poll", "ved"):
        t0 = time.time()
        d = _load(c)
        seq = np.load(paths.CACHE / f"seq_{c}.npy", mmap_mode="r")
        yc = d.cls.to_numpy().astype(int)
        s = np.zeros(len(d))
        for tr, te in folds(d, c):
            sub = np.sort(tr if len(tr) <= deep_max else rng.choice(tr, deep_max, replace=False))
            m = SeqTransformer(seq.shape[1], 5, epochs=8, max_tokens=60).fit(np.asarray(seq[sub]), yc[sub])
            s[te] = m.proba(np.asarray(seq[te]))[:, 1]
        r = stage_metrics(d.cls.values, d.stage.values, s)
        y = (yc == 1)
        r["auroc_all_ci"] = group_bootstrap(d.vehicle.to_numpy(), lambda ii: roc_auc_score(y[ii], s[ii]))
        r["seconds"] = time.time() - t0
        res[c] = r
        o = pd.read_parquet(paths.CACHE / f"oof_{c}.parquet")
        o["Transformer (supervised)"] = s
        o.to_parquet(paths.CACHE / f"oof_{c}.parquet")
        print("transformer", c, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    _save("transformer", res)


# ---------------------------------------------------------------------------
def significance(B=1000):
    res = {}
    for c in ("fullbus", "sampler", "poll", "ved"):
        o = pd.read_parquet(paths.CACHE / f"oof_{c}.parquet")
        y = (o.cls == 1).to_numpy()
        g = o.vehicle.to_numpy()
        ug = np.unique(g)
        idx = {v: np.flatnonzero(g == v) for v in ug}
        rng = np.random.default_rng(0)
        draws = [np.concatenate([idx[v] for v in rng.choice(ug, len(ug), replace=True)]) for _ in range(B)]
        p0 = o[PROP].to_numpy()
        res[c] = {}
        for m in o.columns:
            if m in (PROP, "cls", "stage", "vehicle", "session", "R", "seed") or m.startswith("p_cls"):
                continue
            s = o[m].to_numpy()
            delta = roc_auc_score(y, p0) - roc_auc_score(y, s)
            ds = []
            for ii in draws:
                if y[ii].all() or (~y[ii]).all():
                    continue
                ds.append(roc_auc_score(y[ii], p0[ii]) - roc_auc_score(y[ii], s[ii]))
            ds = np.asarray(ds)
            pval = float(min(1.0, 2 * min((ds <= 0).mean(), (ds >= 0).mean())))
            res[c][m] = {"delta_auroc": float(delta), "ci": [float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))],
                         "p_value": max(pval, 1.0 / len(ds)), "n_groups": int(len(ug))}
        print("significance", c, {k: (round(v["delta_auroc"], 3), round(v["p_value"], 4)) for k, v in res[c].items()}, flush=True)
    _save("significance", res)


if __name__ == "__main__":
    for task in sys.argv[1:]:
        globals()[task]()
