"""Robustness to mis-specification of the physical model (Table VII).

    python -m ocwd.experiments.robustness

The detector is trained on data generated with the nominal parameters and
tested, on disjoint real data, against data generated with each parameter
perturbed.  This bounds how much the reported performance depends on the
exact values chosen for the unmeasured constants of the wear model.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

from .. import loaders, paths, physics as ph, ved
from ..models import GBM
from .build import _passive_session, _ved_trip
from .evaluate import feature_sets

NOMINAL = ph.ContactParams()
PERTURB = {
    "sigma=0.5": dict(sigma=0.5), "sigma=1.2": dict(sigma=1.2),
    "d0 x0.25": dict(d0=NOMINAL.d0 / 4), "d0 x4": dict(d0=NOMINAL.d0 * 4),
    "nu0 x0.5": dict(nu0=NOMINAL.nu0 / 2), "nu0 x2": dict(nu0=NOMINAL.nu0 * 2),
    "R_th=3": dict(R_th=3.0), "R_th=15": dict(R_th=15.0),
    "p_power=0.1": dict(p_power=0.1), "p_power=0.6": dict(p_power=0.6),
    "holdup=0.5ms": dict(holdup=5e-4), "holdup=10ms": dict(holdup=1e-2),
    "road noise 0": dict(ou_sigma=0.0), "road noise x2": dict(ou_sigma=1.0),
    "engine-only excitation": dict(w_engine=1.0, w_road=0.0),
    "road-only excitation": dict(w_engine=0.0, w_road=1.0),
}


def _dataset(corpus, units, p, seed):
    if corpus == "fullbus":
        res = Parallel(n_jobs=4)(delayed(_passive_session)(s, 30.0, seed, p, None, 0.1) for s in units)
    else:
        res = Parallel(n_jobs=4, batch_size=8)(delayed(_ved_trip)(L, seed, p, 600.0, 2.0, 300) for L in units)
    return pd.DataFrame([r for rr, _ in res for r in rr]).fillna(0.0)


def run(corpus="ved"):
    t0 = time.time()
    if corpus == "ved":
        T = ved.trips(max_per_vehicle=10, seed=1)
        vehs = sorted({L.vehicle for L in T})
        rng = np.random.default_rng(0)
        test_v = set(rng.choice(vehs, len(vehs) // 2, replace=False))
        train_u = [L for L in T if L.vehicle not in test_v]
        test_u = [L for L in T if L.vehicle in test_v]
    else:
        S = [s for s in loaders.all_frame_sessions() if s.vehicle in ("KIA-Soul", "MIRGU-car")]
        train_u = [s for s in S if "normal_run" not in s.name]
        test_u = [s for s in S if "normal_run" in s.name]
    feats = feature_sets(corpus)["all"]
    dtr = _dataset(corpus, train_u, NOMINAL, 10)
    m = GBM(feats).fit(dtr, (dtr.cls == 1).astype(int).to_numpy())
    out = {}
    for name, kw in [("nominal", {})] + list(PERTURB.items()):
        p = ph.with_params(NOMINAL, **kw)
        dte = _dataset(corpus, test_u, p, 20)
        y = (dte.cls == 1).to_numpy()
        s = m.score(dte)
        r = {"auroc": roc_auc_score(y, s)}
        neg = ~y
        for st in (1, 2, 3):
            mm = neg | (dte.stage == st).to_numpy()
            r[f"auroc_s{st}"] = roc_auc_score(y[mm], s[mm])
        out[name] = r
        print(f"  [{corpus}] {name:24s} AUROC {r['auroc']:.3f}  s1 {r['auroc_s1']:.3f}  "
              f"s2 {r['auroc_s2']:.3f}  s3 {r['auroc_s3']:.3f}", flush=True)
    with open(paths.RESULTS / f"robustness_{corpus}.json", "w", encoding="utf-8") as fh:
        json.dump({"results": out, "seconds": time.time() - t0}, fh, indent=2)
    return out


if __name__ == "__main__":
    import sys
    for c in (sys.argv[1:] or ["fullbus", "ved"]):
        run(c)
