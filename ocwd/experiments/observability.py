"""Analytical observability model (Section V-F / Fig. 5 of the paper).

For a contact of resistance R under excitation v, interruptions arrive at
rate lambda(R, v) (Eq. 4).  A unit of telemetry (a frame for a passive tool,
a request/response pair for a tester; a sampling logger only sees
brown-outs, because a lost frame is replaced by the next one) occupying the wire for T is destroyed
when an interruption starts within [t - T - d, t], so the expected number of
destroyed units per second is

    a_sig(R) = r * lambda * (T_obs + E[d])                (signal-line losses)
    a_pwr(R) = lambda * p_pwr * P(d > T_h) * E[T_r] * r   (brown-out losses)

with r the tool's unit rate.  For a window of W seconds the predicted number
of fault-induced events is A = (a_sig + a_pwr) W, and the tool's own
background irregularity is measured on the REAL healthy windows as the
standard deviation sigma_B of the same event count.  The observability
signal-to-noise ratio is SNR = A / sigma_B.  No detector is involved: if the
SNR orders the measured AUROCs across tools and stages, detectability is a
property of the physics and the tool, not of the classifier.

    python -m ocwd.experiments.observability
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import lognorm, spearmanr

from .. import paths, physics as ph

# corpus -> (unit, window W, event-count feature (per minute) measured on healthy windows)
CORPORA = {
    "fullbus": ("frame", 30.0, "miss_pm"),
    "sampler": ("sample", 60.0, "silences_pm"),
    "poll": ("txn", 120.0, "gaps_pm"),
    "ved": ("txn", None, "gaps_pm"),
}
STAGE_R = {1: np.sqrt(0.3 * 1.5), 2: np.sqrt(1.5 * 6.0), 3: np.sqrt(6.0 * 30.0)}  # geometric mid-points


def expected_rates(R, v, r_units, unit, p=ph.ContactParams()):
    lam = float(ph.interruption_rate(R, np.array([v]), p)[0])
    med = p.d0 * (R / p.R_th) ** p.d_gamma
    Ed = min(med * np.exp(p.d_sigma ** 2 / 2), p.d_cap)
    T = ph.frame_airtime(np.array([8]))[0] * (2 if unit == "txn" else 1)
    a_sig = r_units * lam * (1 - p.p_power) * (T + Ed) * (2 if unit == "txn" else 1)
    p_long = 1 - lognorm(s=p.d_sigma, scale=med).cdf(p.holdup)
    reset_rate = lam * p.p_power * p_long
    Tr = (p.poll_reset_lo + p.poll_reset_hi) / 2 if unit == "txn" else (p.reset_lo + p.reset_hi) / 2
    down = min(reset_rate * Tr, 1.0)
    if unit == "frame":
        a_pwr = down * r_units                        # frames lost while the tool reboots
    elif unit == "sample":
        # a sampling logger records whichever frame is next on the bus: a lost
        # frame is silently replaced, so only reboots (silences) are visible
        a_sig, a_pwr = 0.0, reset_rate
    else:
        a_pwr = reset_rate                            # each reboot is one long gap event
    return a_sig, a_pwr, reset_rate


def run():
    with open(paths.RESULTS / "detection_extra.json", encoding="utf-8") as fh:
        X = json.load(fh)
    rows = []
    for c, (unit, W, stat) in CORPORA.items():
        d = pd.read_parquet(paths.CACHE / f"ds_{c}.parquet")
        h = d[d.cls == 0]
        Wc = W if W else float(h["W"].median())
        r_units = float((h["rate"] if unit in ("frame", "sample") else h["txn_rate"]).median())
        v = float(h["exc_mean"].replace(0, np.nan).median()) if "exc_mean" in h else 0.6
        v = v if np.isfinite(v) else 0.6
        sigma_b = float((h[stat] * Wc / 60).std())
        for st, R in STAGE_R.items():
            a_sig, a_pwr, rr = expected_rates(R, v, r_units, unit)
            A = (a_sig + a_pwr) * Wc
            auc = X[c]["Proposed (GBM, all features)"][f"s{st}_vs_healthy"]
            best = max(X[c][m][f"s{st}_vs_healthy"] for m in X[c] if m not in ("attribution", "per_vehicle"))
            rows.append(dict(corpus=c, stage=st, R=R, unit_rate=r_units, v=v, W=Wc, A=A, sigma_b=sigma_b,
                             snr=A / max(sigma_b, 1e-3), auroc_ecta=auc, auroc_best=best, reset_per_min=rr * 60))
    df = pd.DataFrame(rows)
    rho = spearmanr(df.snr, df.auroc_best).correlation
    print(df.round(4).to_string())
    print("Spearman(SNR, best AUROC) =", round(rho, 3))
    out = {"rows": df.to_dict(orient="records"), "spearman_snr_auroc_best": rho,
           "spearman_snr_auroc_ecta": spearmanr(df.snr, df.auroc_ecta).correlation}
    with open(paths.RESULTS / "observability.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return df


if __name__ == "__main__":
    run()
