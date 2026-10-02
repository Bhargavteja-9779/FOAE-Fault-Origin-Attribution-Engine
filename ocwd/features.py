"""Window-level features computed only from what a diagnostic tool sees.

Three families:

* **Loss/gap** features: inferred from the periodicity of each CAN ID (passive)
  or of the polling loop (active).  Self-referenced: no healthy reference of
  the same unit is needed.
* **Structure** features: *how* the losses are distributed -- across IDs
  (selectivity vs. the airtime-proportional pattern a DLC fault produces),
  in time (silences, bunching, retransmission lateness), and against bus load.
* **Excitation-coherence** features (the core contribution): whether loss
  intensity co-varies with the vehicle's measured mechanical excitation.  A
  fretting contact interrupts more when it is shaken harder; logger
  overflow, ECU busy states and most EMI do not.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr, chi2

EPS = 1e-9


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def poisson_slope(y: np.ndarray, x: np.ndarray, iters: int = 25):
    """Poisson GLM  y ~ exp(a + b x)  by IRLS; returns (b, z_b).  x standardised."""
    if len(y) < 5 or y.sum() < 2 or np.std(x) < EPS:
        return 0.0, 0.0
    x = (x - x.mean()) / (x.std() + EPS)
    X = np.c_[np.ones_like(x), x]
    beta = np.array([np.log(y.mean() + EPS), 0.0])
    for _ in range(iters):
        eta = np.clip(X @ beta, -20, 20)
        mu = np.exp(eta)
        W = mu
        z = eta + (y - mu) / (mu + EPS)
        XtW = X.T * W
        H = XtW @ X + 1e-6 * np.eye(2)
        try:
            nb = np.linalg.solve(H, XtW @ z)
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(nb - beta)) < 1e-6:
            beta = nb
            break
        beta = nb
    try:
        cov = np.linalg.inv(H)
        se = np.sqrt(max(cov[1, 1], EPS))
    except np.linalg.LinAlgError:
        se = np.inf
    b = float(np.clip(beta[1], -10, 10))
    return b, float(np.clip(b / se, -50, 50))


def coherence(y: np.ndarray, v: np.ndarray, prefix: str = "coh") -> dict:
    """Excitation-coherence statistics of event counts y against excitation v."""
    out = {f"{prefix}_rho": 0.0, f"{prefix}_beta": 0.0, f"{prefix}_z": 0.0, f"{prefix}_hilo": 0.0}
    if len(y) < 5 or y.sum() == 0 or np.std(v) < EPS:
        return out
    r = spearmanr(y, v).correlation
    out[f"{prefix}_rho"] = 0.0 if not np.isfinite(r) else float(r)
    out[f"{prefix}_beta"], out[f"{prefix}_z"] = poisson_slope(y.astype(float), np.log(v + 0.05))
    med = np.median(v)
    hi, lo = y[v > med], y[v <= med]
    if len(hi) and len(lo):
        out[f"{prefix}_hilo"] = float(np.log((hi.mean() + 0.1) / (lo.mean() + 0.1)))
    return out


def excitation_series(grid, rpm, speed):
    """Observed excitation proxy (same functional form as the physical model,
    but WITHOUT the unobservable road-input factor)."""
    rt, rv = rpm
    st, sv = speed
    if len(rt) < 2 and len(st) < 2:
        return None
    r = np.interp(grid, rt, rv) if len(rt) >= 2 else np.full(len(grid), 1500.0)
    s = np.interp(grid, st, sv) if len(st) >= 2 else np.full(len(grid), 40.0)
    return 0.5 * r / 2000.0 + 0.5 * s / 60.0


# ---------------------------------------------------------------------------
# Passive capture
# ---------------------------------------------------------------------------
PASSIVE_FEATURES = [
    "rate", "n_ids", "miss_ratio", "gap_events_pm", "miss_pm",
    "max_silence", "silences_pm", "late_ratio", "bunch_ratio", "jitter_mad",
    "sel_chi2", "sel_gini", "sel_frac_ids", "load_at_gap", "load_corr",
    "coh_rho", "coh_beta", "coh_z", "coh_hilo", "coh2_rho", "coh2_beta", "coh2_z", "coh2_hilo", "exc_mean", "exc_avail",
]
FAMILIES = {
    "loss": ["rate", "n_ids", "miss_ratio", "gap_events_pm", "miss_pm", "max_silence", "silences_pm"],
    "structure": ["late_ratio", "bunch_ratio", "jitter_mad", "sel_chi2", "sel_gini", "sel_frac_ids",
                  "load_at_gap", "load_corr"],
    "coherence": ["coh_rho", "coh_beta", "coh_z", "coh_hilo", "coh2_rho", "coh2_beta", "coh2_z",
                  "coh2_hilo", "exc_mean", "exc_avail"],
}


def passive_features(t: np.ndarray, can_id: np.ndarray, t0: float, W: float,
                     rpm=None, speed=None) -> dict:
    m = (t >= t0) & (t < t0 + W)
    t, can_id = t[m], can_id[m]
    f = dict.fromkeys(PASSIVE_FEATURES, 0.0)
    f["rate"] = len(t) / W
    if len(t) < 20:
        return f
    o = np.argsort(t, kind="stable")
    t, can_id = t[o], can_id[o]
    ids, inv = np.unique(can_id, return_inverse=True)
    f["n_ids"] = len(ids)
    sec = np.floor(t - t0).astype(int)
    nb = int(np.ceil(W))
    miss_sec = np.zeros(nb)
    per_id_miss = np.zeros(len(ids))
    per_id_n = np.bincount(inv, minlength=len(ids)).astype(float)
    late = bunch = norm_n = 0
    jit = []
    gap_mid = []
    tot_miss = gap_ev = 0
    expected = 0.0
    for k in range(len(ids)):
        tk = t[inv == k]
        if len(tk) < 6:
            continue
        d = np.diff(tk)
        P = np.median(d)
        if P <= 0:
            continue
        r = d / P
        core = r[(r > 0.5) & (r < 1.5)]
        if len(core) < 0.6 * len(r):      # not periodic enough (event-driven ID)
            continue
        miss = np.where(r >= 1.5, np.round(r) - 1, 0)
        tot_miss += miss.sum()
        expected += len(tk) + miss.sum()
        gi = np.flatnonzero(miss > 0)
        gap_ev += len(gi)
        per_id_miss[k] = miss.sum()
        for g in gi:
            mid = 0.5 * (tk[g] + tk[g + 1])
            gap_mid.append(mid)
            s = int(min(max(mid - t0, 0), W - 1e-6))
            miss_sec[s] += miss[g]
        late += np.sum((r > 1.08) & (r < 1.5))
        bunch += np.sum(r < 0.5)
        norm_n += len(r)
        jit.append(np.abs(core - 1))
    f["miss_ratio"] = tot_miss / (expected + EPS)
    f["gap_events_pm"] = gap_ev * 60 / W
    f["miss_pm"] = tot_miss * 60 / W
    f["late_ratio"] = late / (norm_n + EPS)
    f["bunch_ratio"] = bunch / (norm_n + EPS)
    f["jitter_mad"] = float(np.median(np.concatenate(jit))) if jit else 0.0
    dt_all = np.diff(t)
    f["max_silence"] = float(dt_all.max()) if len(dt_all) else W
    thr = max(0.25, 20 * np.median(dt_all))
    f["silences_pm"] = float(np.sum(dt_all > thr)) * 60 / W
    # selectivity: are losses spread across IDs in proportion to traffic (DLC)
    # or concentrated on a subset (ECU-local)?
    act = per_id_n > 5
    if per_id_miss[act].sum() >= 3:
        obs = per_id_miss[act]
        expv = per_id_n[act] / per_id_n[act].sum() * obs.sum()
        stat = np.sum((obs - expv) ** 2 / (expv + EPS))
        dof = max(act.sum() - 1, 1)
        f["sel_chi2"] = float(np.log1p(stat / dof))
        sh = np.sort(obs / (per_id_n[act] + EPS))
        n = len(sh)
        f["sel_gini"] = float((2 * np.arange(1, n + 1) - n - 1) @ sh / (n * sh.sum() + EPS))
        f["sel_frac_ids"] = float(np.mean(obs > 0))
    # load at the moment of loss (logger overflow signature)
    cnt10 = np.bincount(np.floor((t - t0) / 0.01).astype(int).clip(0, int(W * 100) - 1),
                        minlength=int(W * 100))
    if gap_mid:
        gb = np.floor((np.asarray(gap_mid) - t0) / 0.01).astype(int).clip(0, len(cnt10) - 1)
        loc = np.array([cnt10[max(0, b - 3): b + 4].mean() for b in gb])
        f["load_at_gap"] = float(np.log((loc.mean() + 0.1) / (cnt10.mean() + 0.1)))
        rate_sec = np.bincount(sec.clip(0, nb - 1), minlength=nb)
        if np.std(miss_sec) > 0 and np.std(rate_sec) > 0:
            rr = spearmanr(miss_sec, rate_sec).correlation
            f["load_corr"] = 0.0 if not np.isfinite(rr) else float(rr)
    # excitation coherence
    if rpm is not None and speed is not None:
        grid = t0 + np.arange(nb) + 0.5
        v = excitation_series(grid, rpm, speed)
        if v is not None:
            f["exc_avail"] = 1.0
            f["exc_mean"] = float(v.mean())
            f.update(coherence(miss_sec, v))
            # silences (all-ID gaps): the only loss evidence a sampling logger keeps
            sil_sec = np.zeros(nb)
            big = np.flatnonzero(dt_all > thr)
            np.add.at(sil_sec, np.floor(t[big] - t0).astype(int).clip(0, nb - 1), 1)
            f.update(coherence(sil_sec, v, "coh2"))
    return f


# ---------------------------------------------------------------------------
# Active (polling) capture
# ---------------------------------------------------------------------------
POLL_FEATURES = [
    "txn_rate", "med_dt", "gap_ratio", "gaps_pm", "excess_frac", "long_gaps_pm",
    "max_gap", "jitter_mad", "pid_miss", "gap_dur_med", "gap_dur_cv",
    "coh_rho", "coh_beta", "coh_z", "coh_hilo", "coh2_rho", "coh2_beta", "coh2_z", "coh2_hilo", "exc_mean",
]
POLL_FAMILIES = {
    "loss": ["txn_rate", "med_dt", "gap_ratio", "gaps_pm", "excess_frac", "long_gaps_pm", "max_gap", "pid_miss"],
    "structure": ["jitter_mad", "gap_dur_med", "gap_dur_cv"],
    "coherence": ["coh_rho", "coh_beta", "coh_z", "coh_hilo", "coh2_rho", "coh2_beta", "coh2_z",
                  "coh2_hilo", "exc_mean"],
}


def poll_features(t: np.ndarray, pid: np.ndarray, t0: float, W: float, rpm, speed) -> dict:
    m = (t >= t0) & (t < t0 + W)
    t, pid = t[m], pid[m]
    f = dict.fromkeys(POLL_FEATURES, 0.0)
    f["txn_rate"] = len(t) / W
    if len(t) < 10:
        f["max_gap"] = W
        return f
    d = np.diff(t)
    med = np.median(d)
    f["med_dt"] = med
    # a timeout shows up as an inter-response gap well above the loop period
    g = d > med + 0.12
    f["gap_ratio"] = g.mean()
    f["gaps_pm"] = g.sum() * 60 / W
    f["excess_frac"] = float(np.clip(d - med, 0, None)[g].sum() / W)
    f["long_gaps_pm"] = float(np.sum(d > 0.8)) * 60 / W
    f["max_gap"] = float(d.max())
    core = d[(d > 0.5 * med) & (d < 1.5 * med)]
    f["jitter_mad"] = float(np.median(np.abs(core / med - 1))) if len(core) else 0.0
    if g.any():
        gd = d[g] - med
        f["gap_dur_med"] = float(np.median(gd))
        f["gap_dur_cv"] = float(np.std(gd) / (np.mean(gd) + EPS))
    # PID cycle completeness
    up = np.unique(pid)
    miss = exp = 0
    for p_ in up:
        tp = t[pid == p_]
        if len(tp) < 4:
            continue
        dp = np.diff(tp)
        P = np.median(dp)
        if P <= 0:
            continue
        mm = np.where(dp / P >= 1.5, np.round(dp / P) - 1, 0).sum()
        miss += mm
        exp += len(tp) + mm
    f["pid_miss"] = miss / (exp + EPS)
    nb = int(np.ceil(W / 2.0))
    y = np.zeros(nb)
    for gi in np.flatnonzero(g):
        y[int(min((t[gi] - t0) / 2.0, nb - 1))] += 1
    grid = t0 + 2.0 * np.arange(nb) + 1.0
    v = excitation_series(grid, rpm, speed)
    if v is not None:
        f["exc_mean"] = float(v.mean())
        f.update(coherence(y, v))
        # strong events only: gaps of more than three loop periods
        y2 = np.zeros(nb)
        for gi in np.flatnonzero(d > max(3 * med, med + 0.5)):
            y2[int(min((t[gi] - t0) / 2.0, nb - 1))] += 1
        f.update(coherence(y2, v, "coh2"))
    return f
