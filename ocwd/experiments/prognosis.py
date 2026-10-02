"""Fleet-scale prognosis on VED (Section VI-E of the paper).

    python -m ocwd.experiments.prognosis

Every eligible VED vehicle is given an OBD-II tool whose connector wears
according to the vehicle's *own* recorded usage: each real trip adds
vibration exposure (from its logged engine and road speed) and one thermal
cycle.  The tool's telemetry for each real trip is then the real trip replayed
through a link of the current contact resistance.  From this telemetry alone
the method must estimate the health of the connector and its remaining
useful life (RUL) in calendar days.

Methods
  Proposed : learned health index (vehicle-disjoint GBM regressor of log R)
             + physics-informed fit of the log-logistic wear law in the
             *exposure* domain, extrapolated with the vehicle's usage rate.
  B1 fleet : population reliability -- failure at the fleet-median exposure.
  B2 linear: calendar-time linear extrapolation of the learned health index.
  B3 raw-HI: proposed fit, but on a raw telemetry statistic (no learning).
"""
from __future__ import annotations

import json
import time
import zlib

import numpy as np
import pandas as pd
import lightgbm as lgb
from joblib import Parallel, delayed
from sklearn.model_selection import GroupKFold

from .. import paths, physics as ph, ved, scenarios
from ..features import POLL_FAMILIES
from ..models import LGB_PARAMS

R_FAIL = 6.0       # onset of the severe stage: recurring tool brown-outs
R0, RMAX = 0.005, 60.0
WIDTH_FRAC = 0.12  # knee width relative to N50
FEATS = POLL_FAMILIES["loss"] + POLL_FAMILIES["structure"] + POLL_FAMILIES["coherence"]


def eligible(trips, min_trips=60, min_span=200):
    by = {}
    for L in trips:
        by.setdefault(L.vehicle, []).append(L)
    out = {}
    for v, Ls in by.items():
        Ls.sort(key=lambda L: L.day)
        if len(Ls) >= min_trips and Ls[-1].day - Ls[0].day >= min_span:
            out[v] = Ls
    return out


def _s_fail():
    return (np.log(R_FAIL) - np.log(R0)) / (np.log(RMAX) - np.log(R0))


def simulate_vehicle(v, Ls, N50_scale, p, seed):
    rng = np.random.default_rng([seed, zlib.crc32(v.encode())])
    E = np.array([ved.trip_exposure(L, p) for L in Ls])
    trips_cum = np.arange(1, len(Ls) + 1)
    N = np.cumsum(E) + 0.02 * trips_cum
    N50 = N50_scale * float(np.exp(0.5 * rng.standard_normal()))
    width = WIDTH_FRAC * N50
    R = ved.wear_trajectory(np.cumsum(E), trips_cum, N50, width, R0=R0, Rmax=RMAX)
    rows = []
    for L, Rk, Nk in zip(Ls, R, N):
        T = L.t[-1] - L.t[0]
        W = min(T - 35.0, 600.0)
        if W < 60:
            continue
        # cls=1 path with a fixed resistance: inject with Rk directly
        f = _trip_with_R(L, W, Rk, p, rng)
        f.update(vehicle=v, day=L.day, N=Nk, R=Rk, N50=N50, width=width, W=W)
        rows.append(f)
    return rows


def _trip_with_R(L, W, R, p, rng):
    grid = np.arange(L.t[0], L.t[-1] + 0.1, 0.1)
    v = ph.vibration(grid, L.rpm, L.speed, p, rng)
    m = (L.t >= L.t[0]) & (L.t < L.t[0] + 2 + W + 30)
    t = L.t[m]
    it = ph.sample_interruptions(grid, v, R, p, rng, poll=True)
    t2, keep = ph.simulate_poll(t, it, p, rng, L.resolution, mode="dlc")
    shift = t2 - t[keep]
    tk = t[keep]

    def surv(ts, vs):
        idx = np.clip(np.searchsorted(tk, ts), 0, len(tk) - 1)
        ok = np.abs(tk[idx] - ts) < 1e-9
        return ts[ok] + shift[idx[ok]], vs[ok]

    from ..features import poll_features
    return poll_features(t2, np.zeros(len(t2), int), L.t[0] + 2.0, W, surv(*L.rpm), surv(*L.speed))


def fit_N50(N, hi, width_frac=WIDTH_FRAC):
    """Least-squares fit of the log-logistic wear law to a health-index
    history in the exposure domain (1-D search over N50)."""
    lr0, lrm = np.log10(R0), np.log10(RMAX)
    grid = np.exp(np.linspace(np.log(max(N[-1], 1e-3) * 0.3), np.log(max(N[-1], 1e-3) * 20), 400))
    best, bestc = grid[-1], np.inf
    for n50 in grid:
        pred = lr0 + (lrm - lr0) / (1 + np.exp(-(N - n50) / (width_frac * n50)))
        c = np.mean((pred - hi) ** 2)
        if c < bestc:
            best, bestc = n50, c
    return best


def failure_exposure(n50, width_frac=WIDTH_FRAC):
    s = _s_fail()
    return n50 + width_frac * n50 * np.log(s / (1 - s))


def run(seed: int = 0, n_jobs: int = 4):
    t0 = time.time()
    p = ph.ContactParams()
    T = ved.trips(min_dur=150.0)
    V = eligible(T)
    # fleet exposure scale: N50 median = fleet-median annual exposure x 0.8
    ann = []
    for v, Ls in V.items():
        E = sum(ved.trip_exposure(L, p) for L in Ls)
        span = Ls[-1].day - Ls[0].day
        ann.append(E / span * 365)
    N50_scale = 0.8 * float(np.median(ann))
    rows = Parallel(n_jobs=n_jobs)(delayed(simulate_vehicle)(v, Ls, N50_scale, p, seed) for v, Ls in V.items())
    df = pd.DataFrame([r for rr in rows for r in rr]).fillna(0.0)
    df["logR"] = np.log10(df["R"])
    df.to_parquet(paths.CACHE / "prognosis_trips.parquet")
    print(f"[prognosis] {df.vehicle.nunique()} vehicles, {len(df)} trips, {time.time() - t0:.0f}s", flush=True)

    # learned health index, vehicle-disjoint
    veh = df["vehicle"].to_numpy()
    hi = np.zeros(len(df))
    for tr, te in GroupKFold(5).split(df, groups=veh):
        m = lgb.LGBMRegressor(random_state=0, **LGB_PARAMS)
        m.fit(df.iloc[tr][FEATS].to_numpy(np.float32), df["logR"].iloc[tr])
        hi[te] = m.predict(df.iloc[te][FEATS].to_numpy(np.float32))
    df["hi"] = hi
    # raw statistic mapped to log R scale by a monotone rank map (no learning of the target)
    raw = df["excess_frac"].to_numpy()
    df["hi_raw"] = np.log10(R0) + (np.log10(RMAX) - np.log10(R0)) * pd.Series(raw).rank(pct=True).to_numpy() ** 4

    df.to_parquet(paths.CACHE / "prognosis_trips.parquet")
    # Two failure definitions: onset of the severe stage (6 ohm, pre-specified)
    # and functional failure of the tool link (20 ohm, added post hoc; see paper).
    return [evaluate(df.copy(), r) for r in (6.0, 20.0)]


def _posterior_rul(N, h, floor, tau, prior_mu, prior_sd, Nk, rate, use_hi=True):
    """Posterior median RUL (days) of the unit-specific wear law.

    Prior: log N50 ~ Normal(prior_mu, prior_sd), the fleet's failure
    statistics.  Evidence: health-index readings above the detection floor
    are Gaussian observations of log10 R(N); readings at or below the floor
    are left-censored (they only say R is below the floor).  Survival so far
    truncates the posterior to failure exposures beyond the current one."""
    lr0, lrm = np.log10(R0), np.log10(RMAX)
    g = np.exp(np.linspace(prior_mu - 4 * prior_sd, prior_mu + 4 * prior_sd, 600))
    lp = -0.5 * ((np.log(g) - prior_mu) / prior_sd) ** 2
    Nf = np.array([failure_exposure(x) for x in g])
    lp[Nf <= Nk] = -np.inf
    if use_hi and len(N):
        from scipy.stats import norm
        pred = lr0 + (lrm - lr0) / (1 + np.exp(-(N[None, :] - g[:, None]) / (WIDTH_FRAC * g[:, None])))
        obs = h > floor
        ll = np.zeros(len(g))
        if obs.any():
            ll += norm.logpdf((h[obs][None, :] - pred[:, obs]) / tau).sum(1)
        if (~obs).any():
            ll += norm.logcdf((floor - pred[:, ~obs]) / tau).sum(1)
        lp = lp + ll
    if not np.isfinite(lp).any():
        return 0.0
    w = np.exp(lp - lp[np.isfinite(lp)].max())
    w[~np.isfinite(w)] = 0
    w /= w.sum()
    rul = (Nf - Nk) / max(rate, 1e-6)
    o = np.argsort(rul)
    c = np.cumsum(w[o])
    return float(rul[o][np.searchsorted(c, 0.5)])


def evaluate(df=None, r_fail: float = None):
    global R_FAIL
    if r_fail is not None:
        R_FAIL = r_fail
    t0 = time.time()
    if df is None:
        df = pd.read_parquet(paths.CACHE / "prognosis_trips.parquet")
    vehs = np.array(sorted(df.vehicle.unique()))
    half = {v: i % 2 for i, v in enumerate(vehs)}
    df["half"] = df.vehicle.map(half)
    # calibration of the HI floor / noise and of the fleet prior on the OTHER half
    cal = {}
    for hf in (0, 1):
        c = df[df.half != hf]
        floor = float(np.quantile(c.hi[c.R < 1.0], 0.99))
        above = c[c.hi > floor]
        tau = float(np.std(above.hi - above.logR)) if len(above) > 20 else 0.3
        fN = []
        for v, g in c.groupby("vehicle"):
            if (g.R >= R_FAIL).any():
                fN.append(g.N[g.R >= R_FAIL].iloc[0])
        fN = np.asarray(fN)
        conv = 1 + WIDTH_FRAC * np.log(_s_fail() / (1 - _s_fail()))
        n50 = np.log(fN / conv)
        cal[hf] = dict(floor=floor, tau=tau, mu=float(n50.mean()), sd=float(max(n50.std(), 0.1)),
                       fleet_Nf=float(np.median(fN)))
    evals = []
    for v, g in df.groupby("vehicle"):
        g = g.sort_values("day")
        cc = cal[half[v]]
        days, N, Rtrue = g["day"].to_numpy(), g["N"].to_numpy(), g["R"].to_numpy()
        hi, hraw = g["hi"].to_numpy(), g["hi_raw"].to_numpy()
        failed = Rtrue >= R_FAIL
        t_fail = days[np.argmax(failed)] if failed.any() else None
        for k in range(10, len(g)):
            if failed[k]:
                break
            rate = (N[k] - N[0]) / max(days[k] - days[0], 1.0)
            out = {"vehicle": v, "day": days[k], "failed_in_data": t_fail is not None,
                   "true_rul": (t_fail - days[k]) if t_fail is not None else np.nan,
                   "censor_rul": days[-1] - days[k], "hi_now": hi[k], "logR_now": np.log10(Rtrue[k])}
            out["proposed"] = _posterior_rul(N[:k + 1], hi[:k + 1], cc["floor"], cc["tau"], cc["mu"], cc["sd"], N[k], rate)
            out["raw_hi"] = _posterior_rul(N[:k + 1], hraw[:k + 1], cc["floor"], cc["tau"], cc["mu"], cc["sd"], N[k], rate)
            out["conditional"] = _posterior_rul(N[:k + 1], hi[:k + 1], cc["floor"], cc["tau"], cc["mu"], cc["sd"], N[k], rate,
                                                use_hi=False)
            out["fleet"] = max(cc["fleet_Nf"] - N[k], 0.0) / max(rate, 1e-6)
            hh, dd = hi[max(0, k - 30): k + 1], days[max(0, k - 30): k + 1]
            slope = np.polyfit(dd, hh, 1)[0] if np.ptp(dd) > 0 else 0.0
            out["linear"] = (np.log10(R_FAIL) - hh[-1]) / slope if slope > 1e-6 else 1e4
            evals.append(out)
    ev = pd.DataFrame(evals)
    ev.to_parquet(paths.CACHE / f"prognosis_eval_R{R_FAIL:g}.parquet")

    res = {"n_vehicles": int(df.vehicle.nunique()), "n_trips": int(len(df)),
           "n_failing": int(ev.groupby("vehicle")["failed_in_data"].first().sum()),
           "hi_r2": float(1 - np.mean((df.hi - df.logR) ** 2) / np.var(df.logR)),
           "hi_spearman": float(pd.Series(df.hi).corr(df.logR, method="spearman")),
           "calibration": cal, "methods": {}}
    f = ev[ev.failed_in_data]
    bins = [(0, 30), (30, 60), (60, 120), (120, 400)]
    for name in ("proposed", "raw_hi", "conditional", "fleet", "linear"):
        pred = np.clip(f[name].to_numpy(), 0, 1000)
        err = np.abs(pred - f["true_rul"].to_numpy())
        r = {"mae_all": float(np.mean(err)), "median_ae_all": float(np.median(err))}
        for lo, hi_ in bins:
            mm = ((f.true_rul >= lo) & (f.true_rul < hi_)).to_numpy()
            r[f"mae_{lo}_{hi_}"] = float(np.mean(err[mm])) if mm.any() else None
        r["alpha30_acc"] = float(np.mean(np.abs(pred - f.true_rul) <= 0.3 * f.true_rul))
        # alarm policy: warn when predicted RUL < 30 days
        timely = premature = missed = 0
        lead = []
        fa = 0
        for v, g in ev.groupby("vehicle"):
            al = g[np.clip(g[name], 0, 1e4) < 30]
            if g.failed_in_data.iloc[0]:
                tf = g.day.iloc[0] + g.true_rul.iloc[0]
                if len(al) == 0:
                    missed += 1
                    lead.append(0.0)
                else:
                    L = tf - al.day.iloc[0]
                    lead.append(L)
                    if L > 60:
                        premature += 1
                    else:
                        timely += 1
            elif len(al) and (g.loc[al.index, "censor_rul"] > 30).any():
                fa += 1
        nf = timely + premature + missed
        n_ok = int((~ev.groupby("vehicle").failed_in_data.first()).sum())
        r.update(timely_rate=timely / nf, premature_rate=premature / nf, missed_rate=missed / nf,
                 median_lead_days=float(np.median(lead)), false_alarm_rate_nonfailing=fa / max(n_ok, 1))
        res["methods"][name] = r
    res["seconds"] = time.time() - t0
    res["r_fail"] = R_FAIL
    with open(paths.RESULTS / f"prognosis_R{R_FAIL:g}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(json.dumps(res["methods"], indent=1))
    print({k: res[k] for k in ("n_vehicles", "n_trips", "n_failing", "hi_r2", "hi_spearman")})
    return res


if __name__ == "__main__":
    import sys
    if "--eval" in sys.argv:
        for r in (6.0, 20.0):
            evaluate(r_fail=r)
    else:
        run()
