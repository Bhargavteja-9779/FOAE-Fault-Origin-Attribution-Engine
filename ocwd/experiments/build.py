"""Build every labelled dataset used in the paper (cached under data/cache).

    python -m ocwd.experiments.build            # all corpora, 3 injection seeds

Corpora
  fullbus   : full-bus passive captures (HCRL KIA Soul, CAN-MIRGU), W = 30 s
  sampler   : sampling passive logger (CANmodes RAW; GM, Ford, VW), W = 60 s
  poll      : OBD-II polling tester (CANmodes OBD; GM, Ford, VW), W = 120 s
  ved       : VED fleet trips (OBD-II logger, up to 40 trips/vehicle), W = trip
"""
from __future__ import annotations

import argparse
import zlib
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .. import loaders, physics as ph, paths, scenarios, ved
from ..models import binned_sequence

SEEDS = (0, 1, 2)
PLAN = [(0, 0), (1, 1), (1, 2), (1, 3), (2, 0), (3, 0), (4, 0)]


def _passive_session(s, W, seed, p, T_seq, step):
    rng = np.random.default_rng([seed, zlib.crc32(s.name.encode())])
    rows, seqs = [], []
    n = int((s.t[-1] - s.t[0] - 4) // W)
    for w in range(n):
        t0 = s.t[0] + 2 + w * W
        for cls, stage in PLAN:
            f, (t, cid) = scenarios.passive_instance(s, t0, W, cls, stage, p, rng)
            f["seed"] = seed
            rows.append(f)
            seqs.append(binned_sequence(t, cid, t0, W, step))
    return rows, seqs


def _poll_session(s, W, stride, seed, p, step):
    rng = np.random.default_rng([seed, zlib.crc32(s.name.encode())])
    rows, seqs = [], []
    T = s.t[-1] - s.t[0]
    n = int((T - 40 - W) // stride) + 1
    for w in range(max(n, 0)):
        t0 = s.t[0] + 2 + w * stride
        for cls, stage in PLAN:
            f, t2 = scenarios.poll_instance(s, t0, W, cls, stage, p, rng, return_seq=True)
            f["seed"] = seed
            rows.append(f)
            seqs.append(binned_sequence(t2, np.zeros(len(t2), int), t0, W, step))
    return rows, seqs


def _ved_trip(L, seed, p, Wmax, step, Tseq):
    rng = np.random.default_rng([seed, zlib.crc32(L.name.encode())])
    T = L.t[-1] - L.t[0]
    W = min(T - 35.0, Wmax)
    rows, seqs = [], []
    if W < 60:
        return rows, seqs
    for cls, stage in PLAN:
        f, t2 = scenarios.poll_instance(L, L.t[0] + 2.0, W, cls, stage, p, rng, return_seq=True)
        f.update(seed=seed, W=W, day=L.day)
        rows.append(f)
        sq = binned_sequence(t2, np.zeros(len(t2), int), L.t[0] + 2.0, Wmax, step)[[0, 2]]
        mask = (np.arange(Tseq) * step < W).astype(np.float32)[None]
        seqs.append(np.concatenate([sq * mask, mask]))
    return rows, seqs


def build(corpus: str, p: ph.ContactParams = ph.ContactParams(), seeds=SEEDS, tag: str = "",
          n_jobs: int = 4, ved_per_vehicle: int = 40):
    out = paths.CACHE / f"ds_{corpus}{tag}.parquet"
    seq_out = paths.CACHE / f"seq_{corpus}{tag}.npy"
    t0 = time.time()
    if corpus in ("fullbus", "sampler"):
        S = loaders.all_frame_sessions()
        S = [s for s in S if (s.vehicle in ("KIA-Soul", "MIRGU-car")) == (corpus == "fullbus")]
        W, step = (30.0, 0.1) if corpus == "fullbus" else (60.0, 0.2)
        jobs = [delayed(_passive_session)(s, W, sd, p, None, step) for sd in seeds for s in S]
    elif corpus == "poll":
        S = loaders.all_poll_sessions()
        jobs = [delayed(_poll_session)(s, 120.0, 60.0, sd, p, 1.0) for sd in seeds for s in S]
    elif corpus == "ved":
        T = ved.trips(max_per_vehicle=ved_per_vehicle, seed=0)
        jobs = [delayed(_ved_trip)(L, sd, p, 600.0, 2.0, 300) for sd in seeds for L in T]
    else:
        raise ValueError(corpus)
    res = Parallel(n_jobs=n_jobs, batch_size=4)(jobs)
    rows = [r for rr, _ in res for r in rr]
    seqs = [q for _, qq in res for q in qq]
    df = pd.DataFrame(rows)
    paths.CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    np.save(seq_out, np.stack(seqs).astype(np.float32))
    print(f"[build] {corpus}{tag}: {len(df)} windows, {df.vehicle.nunique()} vehicles, "
          f"{time.time() - t0:.0f}s -> {out.name}", flush=True)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("corpora", nargs="*", default=["fullbus", "sampler", "poll", "ved"])
    a = ap.parse_args()
    for c in a.corpora:
        build(c)
