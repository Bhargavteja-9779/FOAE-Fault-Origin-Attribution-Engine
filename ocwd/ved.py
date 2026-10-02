"""VED fleet: trip-level detection and fleet-scale prognosis.

Each VED trip is a real OBD-II polling session (an aftermarket logger on the
DLC).  We treat every logged row as one polling transaction, so the physics
of :mod:`ocwd.physics` applies unchanged: a lost transaction disappears and
costs the logger a timeout; a brown-out costs it a re-initialisation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import physics as ph
from .loaders import PollLog, ved_frames


def trips(min_dur: float = 150.0, max_per_vehicle: int | None = None, seed: int = 0,
          d: pd.DataFrame | None = None) -> list[PollLog]:
    d = ved_frames() if d is None else d
    rng = np.random.default_rng(seed)
    out = []
    for (veh, trip), g in d.groupby(["veh", "trip"], sort=False):
        t = g["ts_ms"].to_numpy() / 1000.0
        if len(t) < 50 or t[-1] - t[0] < min_dur:
            continue
        r = g["rpm"].to_numpy()
        s = g["speed"].to_numpy()
        mr, ms = np.isfinite(r), np.isfinite(s)
        if mr.sum() < 20 or ms.sum() < 20:
            continue
        L = PollLog(f"VED-{veh}-{trip}", f"VED-{veh}", "naturalistic", t, np.zeros(len(t), int),
                    (t[mr], r[mr]), (t[ms], s[ms]), 1e-3)
        L.day = float(g["day"].iloc[0])
        out.append(L)
    if max_per_vehicle:
        by = {}
        for L in out:
            by.setdefault(L.vehicle, []).append(L)
        out = []
        for v, Ls in by.items():
            if len(Ls) > max_per_vehicle:
                idx = rng.choice(len(Ls), max_per_vehicle, replace=False)
                Ls = [Ls[i] for i in sorted(idx)]
            out += Ls
    return out


def trip_dataset(trip_list, p: ph.ContactParams = ph.ContactParams(), seed: int = 0,
                 Wmax: float = 600.0, plan=None) -> pd.DataFrame:
    from .scenarios import poll_instance
    rng = np.random.default_rng(seed)
    plan = plan or [(0, 0), (1, 1), (1, 2), (1, 3), (2, 0), (3, 0), (4, 0)]
    rows = []
    for L in trip_list:
        T = L.t[-1] - L.t[0]
        W = min(T - 35.0, Wmax)
        if W < 60:
            continue
        for cls, stage in plan:
            f = poll_instance(L, L.t[0] + 2.0, W, cls, stage, p, rng)
            f["W"] = W
            rows.append(f)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Prognosis: wear driven by each vehicle's real usage history
# ---------------------------------------------------------------------------
def trip_exposure(L: PollLog, p: ph.ContactParams) -> float:
    """Fretting exposure of one trip: integral of the vibration intensity
    (without the zero-mean road factor), in units of 'v-hours'."""
    g = np.arange(L.t[0], L.t[-1], 1.0)
    rt, rv = L.rpm
    st, sv = L.speed
    v = p.w_engine * np.interp(g, rt, rv) / 2000.0 + p.w_road * np.interp(g, st, sv) / 60.0
    return float(v.sum() / 3600.0)


def wear_trajectory(exposure_cum: np.ndarray, trips_cum: np.ndarray, N50: float, width: float,
                    c_thermal: float = 0.02, R0: float = 0.005, Rmax: float = 60.0) -> np.ndarray:
    """log-logistic rise of contact resistance with accumulated fretting
    (vibration exposure plus a thermal-cycle term per trip)."""
    N = exposure_cum + c_thermal * trips_cum
    s = 1.0 / (1.0 + np.exp(-(N - N50) / width))
    return np.exp(np.log(R0) + (np.log(Rmax) - np.log(R0)) * s)
