"""Time-to-detect with a full-bus tool (Fig. 7 of the paper).

A worn DLC keeps its resistance for days to weeks, far longer than any
detection window.  Here one resistance value is drawn per session and stage
and applied to the *whole* real session; the detector (trained on the other
vehicles, leave-one-vehicle-out) scores consecutive 30-s windows, and the
evidence is accumulated as the running mean log-odds.  We report, per stage,
AUROC against the same sessions unmodified (healthy) and against
confounders, as a function of driving time observed.

    python -m ocwd.experiments.time_to_detect
"""
from __future__ import annotations

import json
import zlib

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

from .. import loaders, paths, physics as ph, scenarios
from ..models import GBM
from .evaluate import feature_sets

W = 30.0
HORIZONS_MIN = (0.5, 1, 2, 5, 10, 20, 30)
CONDS = [(0, 0), (1, 1), (1, 2), (1, 3), (2, 0), (3, 0), (4, 0)]


def _session_traj(s, cls, stage, seed, p, reps):
    """Per-window features of one session under one persistent condition."""
    out = []
    for r in range(reps):
        rng = np.random.default_rng([seed, r, cls, stage, zlib.crc32(s.name.encode())])
        R = ph.sample_R(stage, rng) if cls == 1 else (ph.sample_R(int(rng.integers(2, 4)), rng) if cls == 2 else 0.0)
        n = int((s.t[-1] - s.t[0] - 4) // W)
        # a persistent fault: same R in every window; fresh interruption draws per window
        for w in range(n):
            t0 = s.t[0] + 2 + w * W
            f, _ = scenarios.passive_instance(s, t0, W, cls, stage if cls == 1 else 0, p, rng, R_fixed=R)
            f.update(rep=r, w=w)
            out.append(f)
    return out


def run(seed=0, reps=3):
    p = ph.ContactParams()
    S = [s for s in loaders.all_frame_sessions() if s.vehicle in loaders.FULLBUS_VEHICLES]
    rows = Parallel(n_jobs=4)(delayed(_session_traj)(s, c, st, seed, p, reps) for s in S for c, st in CONDS)
    d = pd.DataFrame([r for rr in rows for r in rr]).fillna(0.0)
    d.to_parquet(paths.CACHE / "ttd_fullbus.parquet")
    feats = feature_sets("fullbus")["all"]
    tr_all = pd.read_parquet(paths.CACHE / "ds_fullbus.parquet").fillna(0.0)
    d["score"] = np.nan
    for v in d.vehicle.unique():
        tr = tr_all[tr_all.vehicle != v]
        m = GBM(feats).fit(tr, (tr.cls == 1).astype(int).to_numpy())
        idx = d.vehicle == v
        d.loc[idx, "score"] = m.score(d[idx])
    pr = d.score.clip(1e-6, 1 - 1e-6)
    d["lo"] = np.log(pr / (1 - pr))
    res = {}
    for H in HORIZONS_MIN:
        k = max(1, int(round(H * 60 / W)))
        g = d[d.w < k].groupby(["session", "cls", "stage", "rep"])
        agg = g.agg(lo=("lo", "mean"), n=("lo", "size")).reset_index()
        agg = agg[agg.n >= k]
        r = {"n_trajectories": int(len(agg))}
        for st in (1, 2, 3):
            pos = (agg.cls == 1) & (agg.stage == st)
            for nm, neg in (("healthy", agg.cls == 0), ("all", agg.cls != 1)):
                m = pos | neg
                if pos.sum() > 1 and neg.sum() > 1:
                    r[f"s{st}_vs_{nm}"] = roc_auc_score(pos[m].astype(int), agg.lo[m])
        res[H] = r
        print(H, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in r.items()}, flush=True)
    with open(paths.RESULTS / "time_to_detect_fullbus.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    return res


if __name__ == "__main__":
    run()
