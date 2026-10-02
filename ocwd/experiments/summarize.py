"""Secondary metrics from the out-of-fold scores (Table IV of the paper).

    python -m ocwd.experiments.summarize

* stage-vs-healthy AUROC: each wear stage against real healthy windows only
  (the pure detection question, without the confounders);
* wear-vs-confounder AUROC: moderate+severe wear against each confounder
  (the attribution question);
* attribution macro-F1 with and without incipient windows.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score

from .. import paths
from .evaluate import group_bootstrap

PROP = "Proposed (GBM, all features)"
METHODS = [PROP, "GBM w/o coherence", "GBM loss only", "1D-CNN (supervised)", "LSTM autoencoder",
           "Isolation Forest", "One-class SVM", "Loss-rate threshold", "U-code timeout rule",
           "Coherence test (no training)"]


def run():
    out = {}
    for c in ("fullbus", "sampler", "poll", "ved"):
        o = pd.read_parquet(paths.CACHE / f"oof_{c}.parquet")
        groups = (o.session.str.split("#").str[0] if c == "fullbus" else o.vehicle).to_numpy()
        res = {}
        for m in METHODS:
            if m not in o:
                continue
            r = {}
            for st in (1, 2, 3):
                mm = ((o.cls == 0) | ((o.cls == 1) & (o.stage == st))).to_numpy()
                y = (o.cls[mm] == 1).to_numpy()
                r[f"s{st}_vs_healthy"] = roc_auc_score(y, o[m][mm])
                if m in (PROP, "GBM w/o coherence") and st >= 2:
                    s_, y_, g_ = o[m][mm].to_numpy(), y, groups[mm]
                    r[f"s{st}_vs_healthy_ci"] = group_bootstrap(g_, lambda ii: roc_auc_score(y_[ii], s_[ii]), B=300)
            for cf, nm in ((2, "ecu"), (3, "emi"), (4, "ovf")):
                mm = ((o.cls == cf) | ((o.cls == 1) & (o.stage >= 2))).to_numpy()
                r[f"wear_vs_{nm}"] = roc_auc_score(o.cls[mm] == 1, o[m][mm])
            res[m] = r
        P = o[[f"p_cls{k}" for k in range(5)]].to_numpy()
        pred = P.argmax(1)
        keep = ~((o.cls == 1) & (o.stage == 1)).to_numpy()
        res["attribution"] = {
            "macro_f1_all": f1_score(o.cls, pred, average="macro"),
            "macro_f1_excl_incipient": f1_score(o.cls[keep], pred[keep], average="macro"),
            "per_class_f1_excl_incipient": f1_score(o.cls[keep], pred[keep], average=None).tolist(),
        }
        out[c] = res
        print(c, {k: round(v, 3) for k, v in res["attribution"].items() if k.startswith("macro")})
    with open(paths.RESULTS / "detection_extra.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    run()
