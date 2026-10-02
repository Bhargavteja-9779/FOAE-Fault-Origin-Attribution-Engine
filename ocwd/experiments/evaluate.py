"""Detection and attribution experiments (Tables III-VI of the paper).

    python -m ocwd.experiments.evaluate fullbus sampler poll ved

All splits are disjoint in the *real* data: no real window, session or
vehicle contributes to both training and test, so the healthy baseline the
detector is scored against is always unseen telemetry.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, confusion_matrix, roc_curve
from sklearn.model_selection import GroupKFold

from .. import paths
from ..features import FAMILIES, POLL_FAMILIES
from ..models import GBM, OneClass, Threshold, CoherenceTest, SeqCNN, LSTMAE

CLASS_NAMES = ["healthy", "DLC wear", "ECU-side", "bus EMI", "overflow/random"]


def feature_sets(corpus):
    fam = POLL_FAMILIES if corpus in ("poll", "ved") else FAMILIES
    loss, struct, coh = fam["loss"], fam["structure"], fam["coherence"]
    return {"all": loss + struct + coh, "loss": loss, "loss+struct": loss + struct,
            "loss+coh": loss + coh}


def folds(df, corpus):
    if corpus == "ved":
        g = df["vehicle"].to_numpy()
        return list(GroupKFold(5).split(df, groups=g))
    if corpus == "fullbus":
        g = df["session"].str.split("#").str[0].to_numpy()  # capture-disjoint
    else:
        g = df["vehicle"].to_numpy()                          # vehicle-disjoint
    out = []
    for v in np.unique(g):
        te = np.flatnonzero(g == v)
        tr = np.flatnonzero(g != v)
        out.append((tr, te))
    return out


def tpr_at(y, s, fpr=0.01):
    f, t, _ = roc_curve(y, s)
    return float(np.interp(fpr, f, t))


def binary_metrics(y, s, stage):
    m = {"auroc": roc_auc_score(y, s), "auprc": average_precision_score(y, s), "tpr@1%": tpr_at(y, s)}
    neg = y == 0
    for st in (1, 2, 3):
        pos = stage == st
        mm = pos | neg
        m[f"auroc_s{st}"] = roc_auc_score(y[mm], s[mm])
        m[f"tpr1_s{st}"] = tpr_at(y[mm], s[mm])
    return m


def group_bootstrap(groups, fn, B=500, seed=0):
    rng = np.random.default_rng(seed)
    ug = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in ug}
    vals = []
    for _ in range(B):
        pick = rng.choice(ug, len(ug), replace=True)
        ii = np.concatenate([idx[g] for g in pick])
        try:
            vals.append(fn(ii))
        except ValueError:
            continue
    v = np.asarray(vals)
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def run(corpus: str, tag: str = "", deep: bool = True, deep_max: int = 40000):
    t_start = time.time()
    df = pd.read_parquet(paths.CACHE / f"ds_{corpus}{tag}.parquet").reset_index(drop=True)
    seq = np.load(paths.CACHE / f"seq_{corpus}{tag}.npy", mmap_mode="r")
    df = df.fillna(0.0)
    y = (df["cls"] == 1).to_numpy().astype(int)
    ycls = df["cls"].to_numpy().astype(int)
    stage = df["stage"].to_numpy()
    FS = feature_sets(corpus)
    loss_stat = "excess_frac" if corpus in ("poll", "ved") else "miss_pm"
    if corpus == "sampler":
        loss_stat = "silences_pm"
    timeout_stat = "max_gap" if corpus in ("poll", "ved") else "max_silence"
    methods = {
        "Proposed (GBM, all features)": lambda: GBM(FS["all"]),
        "GBM w/o coherence": lambda: GBM(FS["loss+struct"]),
        "GBM loss only": lambda: GBM(FS["loss"]),
        "GBM loss+coherence": lambda: GBM(FS["loss+coh"]),
        "Isolation Forest": lambda: OneClass(FS["all"], "iforest"),
        "One-class SVM": lambda: OneClass(FS["all"], "ocsvm"),
        "Loss-rate threshold": lambda: Threshold(loss_stat),
        "U-code timeout rule": lambda: Threshold(timeout_stat),
        "Coherence test (no training)": lambda: CoherenceTest("coh_z", loss_stat),
    }
    oof = {k: np.zeros(len(df)) for k in methods}
    if deep:
        oof["1D-CNN (supervised)"] = np.zeros(len(df))
        oof["LSTM autoencoder"] = np.zeros(len(df))
    oof_cls = np.zeros((len(df), 5))
    oof_cls_cnn = np.zeros((len(df), 5))
    imp = []
    rng = np.random.default_rng(0)
    F = folds(df, corpus)
    for k, (tr, te) in enumerate(F):
        dtr, dte = df.iloc[tr], df.iloc[te]
        for name, mk in methods.items():
            m = mk()
            if isinstance(m, OneClass):
                m.fit(dtr[dtr["cls"] == 0])
            else:
                m.fit(dtr, y[tr])
            oof[name][te] = m.score(dte)
            if name.startswith("Proposed"):
                imp.append(pd.Series(m.m.booster_.feature_importance("gain"), index=m.features))
        mc = GBM(FS["all"], multiclass=True).fit(dtr, ycls[tr])
        oof_cls[te] = mc.score(dte)
        if deep:
            sub = tr if len(tr) <= deep_max else rng.choice(tr, deep_max, replace=False)
            Xs = np.asarray(seq[np.sort(sub)])
            cnn = SeqCNN(Xs.shape[1], 5).fit(Xs, ycls[np.sort(sub)])
            P = cnn.proba(np.asarray(seq[te]))
            oof_cls_cnn[te] = P
            oof["1D-CNN (supervised)"][te] = P[:, 1]
            h = np.sort(sub)[ycls[np.sort(sub)] == 0]
            ae = LSTMAE(Xs.shape[1]).fit(np.asarray(seq[h]))
            oof["LSTM autoencoder"][te] = ae.score(np.asarray(seq[te]))
        print(f"  [{corpus}] fold {k + 1}/{len(F)} done ({time.time() - t_start:.0f}s)", flush=True)

    groups = df["vehicle"].to_numpy() if corpus != "fullbus" else df["session"].str.split("#").str[0].to_numpy()
    res = {"corpus": corpus, "n_windows": int(len(df)), "n_vehicles": int(df.vehicle.nunique()),
           "n_real_windows": int((df.cls == 0).sum()), "folds": len(F), "detection": {}, "attribution": {}}
    for name, s in oof.items():
        m = binary_metrics(y, s, stage)
        if name.startswith("Proposed") or name in ("GBM w/o coherence", "1D-CNN (supervised)", "Isolation Forest"):
            m["auroc_ci"] = group_bootstrap(groups, lambda ii: roc_auc_score(y[ii], s[ii]))
        res["detection"][name] = m
    # paired bootstrap: proposed vs the strongest other method
    prop = oof["Proposed (GBM, all features)"]
    others = {k: v for k, v in res["detection"].items() if not k.startswith("Proposed")}
    best = max(others, key=lambda k: others[k]["auroc"])
    diff_ci = group_bootstrap(groups, lambda ii: roc_auc_score(y[ii], prop[ii]) - roc_auc_score(y[ii], oof[best][ii]))
    res["vs_best_baseline"] = {"baseline": best, "delta_auroc_ci": diff_ci}
    for nm, P in (("Proposed (GBM, all features)", oof_cls), ("1D-CNN (supervised)", oof_cls_cnn)):
        if not deep and nm.startswith("1D"):
            continue
        pred = P.argmax(1)
        res["attribution"][nm] = {
            "macro_f1": f1_score(ycls, pred, average="macro"),
            "per_class_f1": dict(zip(CLASS_NAMES, f1_score(ycls, pred, average=None).tolist())),
            "confusion": confusion_matrix(ycls, pred, labels=range(5)).tolist(),
        }
    res["importance"] = (pd.concat(imp, axis=1).mean(axis=1) / pd.concat(imp, axis=1).mean(axis=1).sum()
                         ).sort_values(ascending=False).round(4).to_dict()
    res["seconds"] = time.time() - t_start
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    with open(paths.RESULTS / f"detection_{corpus}{tag}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    o = pd.DataFrame({k: v for k, v in oof.items()})
    o[["cls", "stage", "vehicle", "session", "R", "seed"]] = df[["cls", "stage", "vehicle", "session", "R", "seed"]]
    for c in range(5):
        o[f"p_cls{c}"] = oof_cls[:, c]
    o.to_parquet(paths.CACHE / f"oof_{corpus}{tag}.parquet")
    print(json.dumps({k: {m: round(v[m], 3) for m in ("auroc", "auprc", "tpr@1%", "auroc_s1", "auroc_s2", "auroc_s3")}
                      for k, v in res["detection"].items()}, indent=1))
    print("attribution", {k: round(v["macro_f1"], 3) for k, v in res["attribution"].items()})
    print("vs best", res["vs_best_baseline"])
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("corpora", nargs="*", default=["fullbus", "sampler", "poll", "ved"])
    ap.add_argument("--no-deep", action="store_true")
    a = ap.parse_args()
    for c in a.corpora:
        run(c, deep=not a.no_deep)
