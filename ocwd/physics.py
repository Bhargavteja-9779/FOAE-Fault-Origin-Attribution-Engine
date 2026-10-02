"""Physics-informed model of OBD-II data-link-connector (DLC) degradation.

The model has three layers, each tied to an established body of evidence:

1. **Wear state.**  Fretting corrosion of tin-plated terminals raises the
   constriction resistance R slowly for a long incubation period and then
   steeply (Antler 1985; Bryant 1994; Park et al. 2008).  We use a logistic
   law in log-resistance driven by accumulated fretting cycles N, which are in
   turn driven by the vehicle's own measured excitation (engine speed, road
   speed) and by thermal cycles (one per trip).

2. **Intermittency.**  Under vibration the instantaneous resistance of a
   fretted contact fluctuates; an *interruption* is an excursion above the
   discontinuity threshold R_th (7 ohm, as in USCAR-2 vibration testing).
   With log-normal fluctuation of spread sigma, the excursion probability per
   micro-motion cycle is Phi((ln R - ln R_th)/sigma); interruptions form an
   inhomogeneous Poisson process whose rate is proportional to the
   instantaneous vibration intensity v(t).

3. **Telemetry effect.**  What the diagnostic tool (dongle / logger) at the
   DLC observes:  an interruption on CAN-H/CAN-L destroys every frame that is
   on the wire during it -- for the tool only, the vehicle network is
   unaffected, so nothing is retransmitted.  An interruption on the supply
   pins (16, 4/5) longer than the tool's hold-up time causes a brown-out reset
   and a silence of hundreds of milliseconds.  In polling mode a lost request
   or response costs the tester a timeout.

The confounders (ECU-side intermittent, bus-wide EMI, logger overflow,
vibration-independent loss) are modelled with the same care so that the
detector cannot win by recognising an artefact of the injector.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.signal import lfilter
from scipy.special import ndtr

BITRATE = 500_000.0


@dataclass(frozen=True)
class ContactParams:
    R_th: float = 7.0            # discontinuity threshold (ohm)
    sigma: float = 0.8           # log-normal spread of instantaneous resistance
    nu0: float = 20.0            # micro-motion "opportunities" per s at v = 1
    d0: float = 2e-4             # median interruption duration at R = R_th (s)
    d_gamma: float = 1.0         # duration growth exponent with R
    d_sigma: float = 1.0         # log-normal spread of durations
    d_cap: float = 0.05          # longest single interruption (s)
    p_power: float = 0.3         # fraction of interruptions on supply pins
    holdup: float = 2e-3         # tool supply hold-up time (s)
    reset_lo: float = 0.3        # brown-out reset silence (s), passive logger
    reset_hi: float = 1.5
    poll_reset_lo: float = 1.0   # re-initialisation time of a polling tester (s)
    poll_reset_hi: float = 3.0
    poll_timeout: float = 0.2    # tester response timeout (s), ELM327-class default
    # vibration proxy
    w_engine: float = 0.5
    w_road: float = 0.5
    ou_sigma: float = 0.5        # unobserved road-input variability (log-normal)
    ou_tau: float = 2.0          # its correlation time (s)


STAGES = {  # contact resistance ranges (ohm) per wear stage
    0: (0.002, 0.05),
    1: (0.3, 1.5),    # incipient
    2: (1.5, 6.0),    # moderate
    3: (6.0, 30.0),   # severe
}


def sample_R(stage: int, rng: np.random.Generator) -> float:
    lo, hi = STAGES[stage]
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


# ---------------------------------------------------------------------------
# Vibration intensity from measured engine and road speed
# ---------------------------------------------------------------------------
def vibration(grid: np.ndarray, rpm: tuple, speed: tuple, p: ContactParams,
              rng: np.random.Generator) -> np.ndarray:
    """v(t) on ``grid``.  Engine-order excitation scales with rpm, road
    excitation with speed; an Ornstein-Uhlenbeck log-normal factor models the
    road input that no OBD signal measures.  E[v] ~ 1 in typical driving."""
    rt, rv = rpm
    st, sv = speed
    r = np.interp(grid, rt, rv) if len(rt) else np.full(len(grid), 1500.0)
    s = np.interp(grid, st, sv) if len(st) else np.full(len(grid), 40.0)
    base = p.w_engine * (r / 2000.0) + p.w_road * (s / 60.0)
    return base * ou_lognormal(grid, p.ou_sigma, p.ou_tau, rng)


def ou_lognormal(grid: np.ndarray, sigma: float, tau: float, rng: np.random.Generator) -> np.ndarray:
    """Stationary log-normal Ornstein-Uhlenbeck factor with unit mean on a
    uniform grid (AR(1) recursion evaluated with a linear filter)."""
    if sigma <= 0 or len(grid) == 0:
        return np.ones(len(grid))
    step = float(np.median(np.diff(grid))) if len(grid) > 1 else 0.1
    a = np.exp(-step / tau)
    e = rng.standard_normal(len(grid))
    z0 = rng.standard_normal()
    z, _ = lfilter([np.sqrt(1 - a * a)], [1.0, -a], e[1:], zi=[a * z0]) if len(grid) > 1 else (np.zeros(0), None)
    z = np.r_[z0, z]
    return np.exp(sigma * z - sigma ** 2 / 2)


# ---------------------------------------------------------------------------
# Interruption process
# ---------------------------------------------------------------------------
@dataclass
class Interruptions:
    start: np.ndarray
    dur: np.ndarray
    power: np.ndarray      # bool: on supply pins
    reset_len: np.ndarray  # silence caused (0 if no reset)


def interruption_rate(R: float, v: np.ndarray, p: ContactParams) -> np.ndarray:
    return p.nu0 * v * ndtr((np.log(R) - np.log(p.R_th)) / p.sigma)


def sample_interruptions(grid: np.ndarray, v: np.ndarray, R: float, p: ContactParams,
                         rng: np.random.Generator, poll: bool = False) -> Interruptions:
    dt = np.diff(grid, append=grid[-1] + (grid[-1] - grid[-2] if len(grid) > 1 else 0.1))
    lam = interruption_rate(R, v, p) * dt
    n = rng.poisson(lam)
    k = n.sum()
    if k == 0:
        z = np.zeros(0)
        return Interruptions(z, z, z.astype(bool), z)
    idx = np.repeat(np.arange(len(grid)), n)
    start = grid[idx] + rng.uniform(0, 1, k) * dt[idx]
    med = p.d0 * (R / p.R_th) ** p.d_gamma
    dur = np.minimum(med * np.exp(p.d_sigma * rng.standard_normal(k)), p.d_cap)
    power = rng.uniform(size=k) < p.p_power
    reset = power & (dur > p.holdup)
    lo, hi = (p.poll_reset_lo, p.poll_reset_hi) if poll else (p.reset_lo, p.reset_hi)
    rlen = np.where(reset, rng.uniform(lo, hi, k), 0.0)
    o = np.argsort(start)
    return Interruptions(start[o], dur[o], power[o], rlen[o])


def frame_airtime(dlc: np.ndarray) -> np.ndarray:
    """On-wire duration of a standard data frame incl. ~10 % bit stuffing."""
    return (47 + 8 * np.asarray(dlc)) * 1.1 / BITRATE


def _overlaps(a0: np.ndarray, a1: np.ndarray, b0: np.ndarray, b1: np.ndarray) -> np.ndarray:
    """For each interval [a0,a1] report whether it intersects any [b0,b1] (b sorted by b0)."""
    if len(b0) == 0:
        return np.zeros(len(a0), dtype=bool)
    # running max of b1 lets one searchsorted answer the query
    i = np.searchsorted(b0, a1, side="right") - 1
    cm = np.maximum.accumulate(b1)
    hit = np.zeros(len(a0), dtype=bool)
    ok = i >= 0
    hit[ok] = cm[i[ok]] >= a0[ok]
    return hit


# ---------------------------------------------------------------------------
# Effects on a passive capture (listen-only logger at the DLC)
# ---------------------------------------------------------------------------
def apply_dlc_passive(t: np.ndarray, dlc: np.ndarray, it: Interruptions, resolution: float,
                      rng: np.random.Generator) -> np.ndarray:
    """Return a keep-mask for frames of a passive capture."""
    tt = t + rng.uniform(0, resolution, len(t)) if resolution > 1e-5 else t
    air = frame_airtime(dlc)
    sig = ~it.power
    # CAN-line interruptions (and supply interruptions shorter than hold-up do nothing)
    lost = _overlaps(tt - air, tt, it.start[sig], it.start[sig] + it.dur[sig])
    r = it.reset_len > 0
    lost |= _overlaps(tt - air, tt, it.start[r], it.start[r] + it.dur[r] + it.reset_len[r])
    return ~lost


def apply_ecu_local(t: np.ndarray, can_id: np.ndarray, dlc: np.ndarray, group: np.ndarray,
                    it: Interruptions, rng: np.random.Generator,
                    busoff_after: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Intermittent contact at ONE ECU's connector.  The ECU's frames that hit
    an interruption are corrupted on the bus, error-signalled and retransmitted
    after reconnection (delayed, not lost); interruptions longer than
    ``busoff_after`` drive the ECU bus-off and its frames are lost until
    software recovery.  Other ECUs' frames are untouched."""
    t = t.copy()
    keep = np.ones(len(t), dtype=bool)
    m = np.isin(can_id, group)
    air = frame_airtime(dlc)
    s, e = it.start, it.start + it.dur
    hit = _overlaps(t - air, t, s, e) & m
    if hit.any():
        j = np.searchsorted(s, t[hit], side="right") - 1
        j = np.clip(j, 0, len(s) - 1)
        d = it.dur[j]
        short = d < busoff_after
        hi = np.flatnonzero(hit)
        t[hi[short]] = e[j[short]] + air[hi[short]] + 40 / BITRATE
        rec = rng.uniform(0.05, 0.5, (~short).sum())
        keep[hi[~short]] = False
        # bus-off recovery silences the ECU for a while
        for st, ln in zip(e[j[~short]], rec):
            keep &= ~(m & (t >= st) & (t <= st + ln))
    return keep, t


def apply_emi(t: np.ndarray, dlc: np.ndarray, bursts_start: np.ndarray, bursts_dur: np.ndarray):
    """Bus-wide disturbance: every node (logger included) sees the error
    frames, so frames are retransmitted after the burst -- delayed and
    bunched, but not lost."""
    t = t.copy()
    air = frame_airtime(dlc)
    if len(bursts_start) == 0:
        return t, np.arange(len(t))
    e = bursts_start + bursts_dur
    j = np.searchsorted(bursts_start, t, side="right") - 1
    inside = (j >= 0) & (t - air <= e[np.clip(j, 0, None)])
    if inside.any():
        ii = np.flatnonzero(inside)
        for b in np.unique(j[ii]):
            sel = ii[j[ii] == b]
            # backlog released back-to-back after the burst
            t[sel] = e[b] + np.cumsum(air[sel] + 3 / BITRATE)
    o = np.argsort(t, kind="stable")
    return t, o


def apply_overflow(t: np.ndarray, capacity_per_10ms: int, rng: np.random.Generator) -> np.ndarray:
    """Logger buffer overflow: frames beyond the logger's capacity within a
    10 ms service interval are dropped.  Load-driven, vibration-independent."""
    b = np.floor((t - t[0]) / 0.01).astype(np.int64)
    # rank of each frame within its bin
    _, start_idx, counts = np.unique(b, return_index=True, return_counts=True)
    rank = np.arange(len(t)) - np.repeat(start_idx, counts)
    return rank < capacity_per_10ms


# ---------------------------------------------------------------------------
# Effects on an OBD-II polling session (active tester at the DLC)
# ---------------------------------------------------------------------------
def _merge(starts: np.ndarray, ends: np.ndarray):
    if len(starts) == 0:
        return starts, ends
    o = np.argsort(starts)
    s, e = starts[o], ends[o]
    ms, me = [s[0]], [e[0]]
    for a, b in zip(s[1:], e[1:]):
        if a <= me[-1]:
            me[-1] = max(me[-1], b)
        else:
            ms.append(a)
            me.append(b)
    return np.asarray(ms), np.asarray(me)


def simulate_poll(t: np.ndarray, it: Interruptions, p: ContactParams, rng: np.random.Generator,
                  resolution: float, mode: str = "dlc", extra_lost: np.ndarray | None = None):
    """Replay a real polling session through a degraded link.

    The tester keeps the capture's own inter-transaction gaps.  A transaction
    whose request or response is on the wire during a CAN-line interruption
    is lost and costs one timeout.  A supply brown-out (``mode='dlc'``)
    reboots the *tester*: nothing is polled until re-initialisation ends.  In
    ``mode='ecm'`` the brown-out reboots the *ECU* instead: the tester keeps
    polling and collects a run of consecutive timeouts.

    Returns (new response times of surviving transactions, keep mask).
    """
    n = len(t)
    gaps = np.diff(t)
    lat = rng.uniform(0.002, 0.015, n)
    air = frame_airtime(np.array([8]))[0]
    sig = ~it.power
    cs, ce = it.start[sig], it.start[sig] + it.dur[sig]
    cmax = np.maximum.accumulate(ce) if len(ce) else ce
    r = it.reset_len > 0
    rs, re_ = _merge(it.start[r], it.start[r] + it.dur[r] + it.reset_len[r])
    jit = rng.uniform(0, resolution, n)
    keep = np.ones(n, dtype=bool)
    out = np.empty(n)
    cur = t[0]
    for i in range(n):
        ti = cur if i == 0 else cur + gaps[i - 1]
        x = ti + jit[i]
        lost = False
        if len(rs):
            j = np.searchsorted(rs, x, side="right") - 1
            if j >= 0 and x <= re_[j]:
                lost = True
                cur = re_[j] if mode == "dlc" else x - lat[i] + p.poll_timeout
        if not lost and len(cs):
            q0 = x - lat[i] - air
            j = np.searchsorted(cs, x, side="right") - 1
            if j >= 0 and cmax[j] >= q0:
                # overlap with request window or response window
                k0 = np.searchsorted(cs, q0 - p.d_cap, side="left")
                for k in range(k0, j + 1):
                    if (ce[k] >= q0 and cs[k] <= q0 + air) or (ce[k] >= x - air and cs[k] <= x):
                        lost = True
                        break
            if lost:
                cur = x - lat[i] + p.poll_timeout
        if not lost and extra_lost is not None and extra_lost[i]:
            lost = True
            cur = x - lat[i] + p.poll_timeout
        if lost:
            keep[i] = False
        else:
            cur = ti
        out[i] = ti
    return out[keep], keep


with_params = replace
