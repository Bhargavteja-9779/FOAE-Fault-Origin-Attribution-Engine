"""Evidence accumulation across trips (Fig. 6 / Table V).

Connector wear is persistent: a worn DLC stays worn from one trip to the
next, whereas the healthy-telemetry irregularities and most confounders are
trip-local.  A vehicle-level decision can therefore pool the per-trip
evidence.  Using the out-of-fold (vehicle-disjoint) per-trip scores, we form
K-trip decisions by averaging the log-odds of K distinct trips of the same
vehicle in the same condition, and report AUROC versus K for each stage.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .. import paths

KS = (1, 2, 3, 5, 10, 20)


def run(corpus="ved", method="Proposed (GBM, all features)", n_draw=4, seed=0):
    o = pd.read_parquet(paths.CACHE / f"oof_{corpus}.parquet")
    o = o[o.seed == 0]  # one injection realisation per real trip
    p = o[method].clip(1e-6, 1 - 1e-6)
    o = o.assign(lo=np.log(p / (1 - p)), cond=o.cls.astype(str) + "_" + o.stage.astype(str))
    rng = np.random.default_rng(seed)
    res = {}
    for K in KS:
        rows = []
        for (veh, cond), g in o.groupby(["vehicle", "cond"]):
            x = g["lo"].to_numpy()
            if len(x) < K:
                continue
            for _ in range(n_draw):
                rows.append((veh, cond, x[rng.choice(len(x), K, replace=False)].mean()))
        d = pd.DataFrame(rows, columns=["veh", "cond", "s"])
        neg = ~d.cond.str.startswith("1_")
        r = {"n_vehicles": int(d.veh.nunique())}
        for st in (1, 2, 3):
            m = neg | (d.cond == f"1_{st}")
            r[f"auroc_s{st}"] = roc_auc_score((d.cond[m] == f"1_{st}").astype(int), d.s[m])
            mh = (d.cond == "0_0") | (d.cond == f"1_{st}")
            r[f"auroc_s{st}_vs_healthy"] = roc_auc_score((d.cond[mh] == f"1_{st}").astype(int), d.s[mh])
        res[K] = r
        print(K, {k: round(v, 3) for k, v in r.items()}, flush=True)
    with open(paths.RESULTS / f"accumulation_{corpus}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    return res


if __name__ == "__main__":
    run()
