"""Build labelled window datasets from real captures.

Every window starts as a *real*, unmodified segment of a real vehicle's
capture (label: healthy).  Labelled fault windows are produced by applying
the physical effect of a fault to that same real segment.  Classes:

passive (listen-only logger at the DLC)
    0 healthy | 1 DLC wear | 2 ECU-side intermittent | 3 bus-wide EMI | 4 logger overflow
polling (OBD-II tester at the DLC)
    0 healthy | 1 DLC wear | 2 ECM-side intermittent | 3 bus-wide EMI | 4 vibration-independent loss
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import physics as ph
from . import signals
from .features import passive_features, poll_features

CLASSES = ["healthy", "dlc_wear", "ecu_local", "emi", "overflow_or_random"]


def _grid(t0, t1, step=0.1):
    return np.arange(t0, t1, step)


def _true_excitation(sess, t0, t1):
    if signals.has_decoder(sess.vehicle):
        m = (sess.t >= t0 - 5) & (sess.t <= t1 + 5)
        rpm = signals.decode(sess.vehicle, sess.t[m], sess.can_id[m], sess.payload[m], "rpm")
        spd = signals.decode(sess.vehicle, sess.t[m], sess.can_id[m], sess.payload[m], "speed")
        return rpm, spd
    return (np.zeros(0), np.zeros(0)), (np.zeros(0), np.zeros(0))


def _emi_bursts(grid, rpm, rng, coupled: bool):
    rate = rng.uniform(0.05, 1.0)
    rt, rv = rpm
    if coupled and len(rt) > 1:
        lam = rate * np.interp(grid, rt, rv) / 2000.0
    else:
        lam = np.full(len(grid), rate)
    dt = np.diff(grid, append=grid[-1] + 0.1)
    n = rng.poisson(lam * dt)
    idx = np.repeat(np.arange(len(grid)), n)
    s = np.sort(grid[idx] + rng.uniform(0, 1, len(idx)) * dt[idx])
    d = np.minimum(0.002 * np.exp(1.0 * rng.standard_normal(len(s))), 0.05)
    return s, d


def passive_instance(sess, t0: float, W: float, cls: int, stage: int, p: ph.ContactParams,
                     rng: np.random.Generator, use_excitation: bool = True, R_fixed: float = None):
    pad = 2.0
    m = (sess.t >= t0 - pad) & (sess.t < t0 + W + pad)
    t, cid, dlc, pl = sess.t[m].copy(), sess.can_id[m].copy(), sess.dlc[m].copy(), sess.payload[m]
    rpm_true, spd_true = _true_excitation(sess, t0 - pad, t0 + W + pad)
    grid = _grid(t0 - pad, t0 + W + pad)
    v = ph.vibration(grid, rpm_true, spd_true, p, rng)
    R = 0.0
    keep = np.ones(len(t), dtype=bool)
    if cls == 1:
        R = R_fixed if R_fixed else ph.sample_R(stage, rng)
        it = ph.sample_interruptions(grid, v, R, p, rng)
        keep = ph.apply_dlc_passive(t, dlc, it, sess.resolution, rng)
    elif cls == 2:
        R = R_fixed if R_fixed else ph.sample_R(int(rng.integers(2, 4)), rng)
        it = ph.sample_interruptions(grid, v, R, p, rng)
        ids = np.unique(cid)
        k = max(1, int(round(len(ids) * rng.uniform(0.1, 0.3))))
        group = rng.choice(ids, size=k, replace=False)
        keep, t = ph.apply_ecu_local(t, cid, dlc, group, it, rng)
    elif cls == 3:
        s, d = _emi_bursts(grid, rpm_true, rng, coupled=bool(rng.uniform() < 0.5))
        if len(s):
            t, o = ph.apply_emi(t, dlc, s, d)
            t, cid, dlc, pl = t[o], cid[o], dlc[o], pl[o]
    elif cls == 4:
        cnt = np.bincount(np.floor((t - t[0]) / 0.01).astype(int))
        target = np.exp(rng.uniform(np.log(5e-4), np.log(2e-2)))
        cap = int(cnt.max())
        for c in range(1, int(cnt.max()) + 1):
            if np.clip(cnt - c, 0, None).sum() / max(len(t), 1) <= target:
                cap = c
                break
        keep = ph.apply_overflow(t, cap, rng)
    t, cid, pl = t[keep], cid[keep], pl[keep]
    rpm_obs = spd_obs = None
    if use_excitation and signals.has_decoder(sess.vehicle):
        rpm_obs = signals.decode(sess.vehicle, t, cid, pl, "rpm")
        spd_obs = signals.decode(sess.vehicle, t, cid, pl, "speed")
    f = passive_features(t, cid, t0, W, rpm_obs, spd_obs)
    f.update(cls=cls, stage=stage if cls == 1 else 0, R=R, vehicle=sess.vehicle,
             scenario=sess.scenario, session=sess.name, t0=t0)
    return f, (t, cid)


def passive_dataset(sessions, W: float = 60.0, p: ph.ContactParams = ph.ContactParams(),
                    seed: int = 0, plan=None, keep_seq: bool = False):
    """One healthy copy, one DLC copy per stage and one copy per confounder,
    for every non-overlapping window of every session."""
    rng = np.random.default_rng(seed)
    plan = plan or [(0, 0), (1, 1), (1, 2), (1, 3), (2, 0), (3, 0), (4, 0)]
    rows, seqs = [], []
    for s in sessions:
        T = s.t[-1] - s.t[0]
        n = int((T - 4) // W)
        for w in range(n):
            t0 = s.t[0] + 2 + w * W
            for cls, stage in plan:
                f, seq = passive_instance(s, t0, W, cls, stage, p, rng)
                rows.append(f)
                if keep_seq:
                    seqs.append(seq)
    df = pd.DataFrame(rows)
    return (df, seqs) if keep_seq else df


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
def poll_instance(sess, t0: float, W: float, cls: int, stage: int, p: ph.ContactParams,
                  rng: np.random.Generator, return_seq: bool = False):
    pad = 2.0
    m = (sess.t >= t0 - pad) & (sess.t < t0 + W + 30)
    t, pid = sess.t[m].copy(), sess.pid[m].copy()
    grid = _grid(t[0], t[-1] + 0.1)
    v = ph.vibration(grid, sess.rpm, sess.speed, p, rng)
    R = 0.0
    empty = ph.Interruptions(np.zeros(0), np.zeros(0), np.zeros(0, bool), np.zeros(0))
    if cls == 1:
        R = ph.sample_R(stage, rng)
        it = ph.sample_interruptions(grid, v, R, p, rng, poll=True)
        t2, keep = ph.simulate_poll(t, it, p, rng, sess.resolution, mode="dlc")
    elif cls == 2:
        # ECM-side connector: same physics, but a supply interruption reboots
        # the ECM (0.2-0.8 s) and the tester keeps timing out against it.
        R = ph.sample_R(int(rng.integers(2, 4)), rng)
        q = ph.with_params(p, poll_reset_lo=0.2, poll_reset_hi=0.8)
        it = ph.sample_interruptions(grid, v, R, q, rng, poll=True)
        t2, keep = ph.simulate_poll(t, it, q, rng, sess.resolution, mode="ecm")
    elif cls == 3:
        s, d = _emi_bursts(grid, sess.rpm, rng, coupled=bool(rng.uniform() < 0.5))
        d = d * 20  # a polling transaction is delayed by the whole disturbance
        t = t.copy()
        lost = np.zeros(len(t), dtype=bool)
        if len(s):
            j = np.clip(np.searchsorted(s, t, side="right") - 1, 0, None)
            hit = (np.searchsorted(s, t, side="right") > 0) & (t <= s[j] + d[j])
            lost = hit & (d[j] > p.poll_timeout)
            delay = np.where(hit & ~lost, d[j], 0.0)
            t = t + np.cumsum(delay)
        t2, keep = ph.simulate_poll(t, empty, p, rng, sess.resolution, extra_lost=lost)
    elif cls == 4:
        rate = float(np.exp(rng.uniform(np.log(0.01), np.log(0.5))))
        dt = np.diff(t, prepend=t[0])
        lost = rng.uniform(size=len(t)) < 1 - np.exp(-rate * dt)
        t2, keep = ph.simulate_poll(t, empty, p, rng, sess.resolution, extra_lost=lost)
    else:
        t2, keep = t.copy(), np.ones(len(t), dtype=bool)
    pid2 = pid[keep]
    # excitation as decoded from surviving responses (shifted with the loop)
    shift = t2 - t[keep]
    rt, rv = sess.rpm
    st, sv = sess.speed
    tk = t[keep]
    def surv(ts, vs):
        idx = np.searchsorted(tk, ts)
        idx = np.clip(idx, 0, len(tk) - 1)
        ok = np.abs(tk[idx] - ts) < 1e-9
        return ts[ok] + shift[idx[ok]], vs[ok]
    rpm_obs = surv(rt, rv)
    spd_obs = surv(st, sv)
    f = poll_features(t2, pid2, t0, W, rpm_obs, spd_obs)
    f.update(cls=cls, stage=stage if cls == 1 else 0, R=R, vehicle=sess.vehicle,
             scenario=sess.scenario, session=sess.name, t0=t0)
    if return_seq:
        return f, t2
    return f


def poll_dataset(sessions, W: float = 120.0, p: ph.ContactParams = ph.ContactParams(),
                 seed: int = 0, plan=None, stride: float = None):
    rng = np.random.default_rng(seed)
    plan = plan or [(0, 0), (1, 1), (1, 2), (1, 3), (2, 0), (3, 0), (4, 0)]
    stride = stride or W / 2
    rows = []
    for s in sessions:
        T = s.t[-1] - s.t[0]
        n = int((T - 40 - W) // stride) + 1
        for w in range(max(n, 0)):
            t0 = s.t[0] + 2 + w * stride
            for cls, stage in plan:
                rows.append(poll_instance(s, t0, W, cls, stage, p, rng))
    return pd.DataFrame(rows)
