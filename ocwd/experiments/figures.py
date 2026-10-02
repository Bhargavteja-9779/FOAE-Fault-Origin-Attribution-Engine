"""Generate every figure and LaTeX table of the paper from cached results.

    python -m ocwd.experiments.figures
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from .. import loaders, paths, physics as ph, scenarios, signals

# validated categorical palette (light mode), fixed order
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#9a998f", "#e4e3dd"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 1.5, "savefig.dpi": 300, "savefig.bbox": "tight",
    "pdf.fonttype": 42})
CORPUS_LABEL = {"fullbus": "Full-bus passive", "sampler": "Sampling passive",
                "poll": "OBD-II polling", "ved": "VED fleet (381 veh.)"}
PROP = "Proposed (GBM, all features)"
FIG = paths.FIGURES


def load(c):
    with open(paths.RESULTS / f"detection_{c}.json", encoding="utf-8") as fh:
        return json.load(fh)


def fig_trace():
    """Real HCRL drive, healthy vs. moderate/severe DLC wear."""
    S = [s for s in loaders.all_frame_sessions() if "normal_run" in s.name][0]
    t0, W = S.t[0] + 2, 480.0
    rng = np.random.default_rng(3)
    p = ph.ContactParams()
    fig, ax = plt.subplots(3, 1, figsize=(3.5, 3.3), sharex=True,
                           gridspec_kw={"height_ratios": [1, 1.2, 1.2]})
    ts, v = signals.decode(S.vehicle, S.t, S.can_id, S.payload, "speed")
    tr, r = signals.decode(S.vehicle, S.t, S.can_id, S.payload, "rpm")
    ax[0].plot(ts - t0, v, color=INK2, lw=1.0)
    ax[0].set_ylabel("Speed\n(km/h)")
    for k, (R, col, lab) in enumerate([(3.0, ORANGE, "moderate, R = 3 Ω"), (12.0, RED, "severe, R = 12 Ω")]):
        grid = np.arange(t0, t0 + W, 0.1)
        vv = ph.vibration(grid, (tr, r), (ts, v), p, rng)
        it = ph.sample_interruptions(grid, vv, R, p, rng)
        m = (S.t >= t0) & (S.t < t0 + W)
        keep = ph.apply_dlc_passive(S.t[m], S.dlc[m], it, S.resolution, rng)
        # expected-but-missing frames per second (periodic IDs)
        tt, cc = S.t[m], S.can_id[m]
        lost_t = tt[~keep]
        y = np.bincount(np.floor(lost_t - t0).astype(int), minlength=int(W))[: int(W)]
        ax[1 + k].bar(np.arange(int(W)) + 0.5, y, width=1.0, color=col, linewidth=0)
        ax[1 + k].set_ylabel("Lost frames/s")
        ax[1 + k].text(0.01, 0.92, lab, transform=ax[1 + k].transAxes, va="top", color=INK, fontsize=7)
    ax[-1].set_xlabel("Time in drive (s)  —  HCRL KIA Soul capture")
    ax[-1].set_xlim(0, W)
    fig.align_ylabels(ax)
    fig.savefig(FIG / "fig_trace.pdf")
    plt.close(fig)


def fig_roc(corpora):
    meths = [(PROP, BLUE, "-"), ("GBM w/o coherence", AQUA, "-"), ("1D-CNN (supervised)", VIOLET, "--"),
             ("Isolation Forest", ORANGE, "--"), ("U-code timeout rule", MUTED, ":")]
    fig, axs = plt.subplots(1, len(corpora), figsize=(7.16, 1.95), sharey=True)
    for ax, c in zip(axs, corpora):
        o = pd.read_parquet(paths.CACHE / f"oof_{c}.parquet")
        y = (o.cls == 1).astype(int)
        for m, col, ls in meths:
            if m not in o:
                continue
            f, t, _ = roc_curve(y, o[m])
            ax.plot(f, t, color=col, ls=ls, lw=1.3, label=m.replace(" (GBM, all features)", ""))
        ax.plot([0, 1], [0, 1], color=GRID, lw=0.8)
        ax.set_title(CORPUS_LABEL[c])
        ax.set_xlabel("False-positive rate")
        ax.set_aspect("equal")
    axs[0].set_ylabel("True-positive rate")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.1), handlelength=2.2)
    fig.savefig(FIG / "fig_roc.pdf")
    plt.close(fig)


def fig_stage(corpora):
    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    w = 0.2
    cols = [YELLOW, ORANGE, RED]
    for k, st in enumerate((1, 2, 3)):
        vals = [load(c)["detection"][PROP][f"auroc_s{st}"] for c in corpora]
        x = np.arange(len(corpora)) + (k - 1) * w
        ax.bar(x, vals, width=w - 0.02, color=cols[k], label=["incipient", "moderate", "severe"][k])
    ax.set_xticks(np.arange(len(corpora)))
    ax.set_xticklabels([CORPUS_LABEL[c].replace(" (381 veh.)", "") for c in corpora])
    ax.set_ylim(0.4, 1.0)
    ax.axhline(0.5, color=MUTED, lw=0.8, ls=":")
    ax.set_ylabel("AUROC (wear vs. rest)")
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.18))
    fig.savefig(FIG / "fig_stage.pdf")
    plt.close(fig)


def fig_accumulation():
    with open(paths.RESULTS / "accumulation_ved.json", encoding="utf-8") as fh:
        a = json.load(fh)
    K = sorted(int(k) for k in a)
    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    for st, col, lab in ((1, YELLOW, "incipient"), (2, ORANGE, "moderate"), (3, RED, "severe")):
        ax.plot(K, [a[str(k)][f"auroc_s{st}"] for k in K], color=col, marker="o", ms=3.5, label=lab)
    ax.set_xscale("log")
    ax.set_xticks(K)
    ax.set_xticklabels([str(k) for k in K])
    ax.set_xlabel("Trips pooled per vehicle-level decision")
    ax.set_ylabel("AUROC (wear vs. rest)")
    ax.set_ylim(0.45, 1.01)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(FIG / "fig_accumulation.pdf")
    plt.close(fig)


def fig_confusion(c="ved"):
    r = load(c)["attribution"][PROP]
    M = np.asarray(r["confusion"], float)
    M = M / M.sum(1, keepdims=True)
    names = ["Healthy", "DLC wear", "ECU-side", "Bus EMI", "Ovfl./rand."]
    fig, ax = plt.subplots(figsize=(2.9, 2.5))
    ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6.5,
                    color="white" if M[i, j] > 0.55 else INK)
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_yticklabels(names)
    ax.set_xlabel("Predicted origin")
    ax.set_ylabel("True origin")
    ax.grid(False)
    fig.savefig(FIG / f"fig_confusion_{c}.pdf")
    plt.close(fig)


def fig_importance(c="ved"):
    imp = pd.Series(load(c)["importance"]).sort_values().tail(12)
    fam = {"coh": BLUE}
    cols = [BLUE if k.startswith("coh") or k.startswith("exc") else MUTED for k in imp.index]
    fig, ax = plt.subplots(figsize=(3.5, 2.2))
    ax.barh(range(len(imp)), imp.values, color=cols, height=0.7)
    ax.set_yticks(range(len(imp)))
    ax.set_yticklabels([k.replace("_", r"\_") if False else k for k in imp.index])
    ax.set_xlabel("Share of total split gain")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG / f"fig_importance_{c}.pdf")
    plt.close(fig)


def fig_prognosis():
    ev = pd.read_parquet(paths.CACHE / "prognosis_eval_R20.parquet")
    tr = pd.read_parquet(paths.CACHE / "prognosis_trips.parquet")
    f = ev[ev.failed_in_data].copy()
    fig, axs = plt.subplots(1, 2, figsize=(7.16, 2.1))
    # (a) one vehicle: true log R and learned health index vs day
    vid = f.groupby("vehicle").size().sort_values().index[len(f.vehicle.unique()) // 2]
    g = tr[tr.vehicle == vid].sort_values("day")
    ax = axs[0]
    ax.plot(g.day, g.logR, color=INK2, lw=1.2, label="true log$_{10}$ R")
    ax.scatter(g.day, g.hi, s=6, color=BLUE, label="health index (per trip)", zorder=3)
    ax.axhline(np.log10(20.0), color=RED, lw=0.9, ls="--", label="functional failure (20 Ω)")
    ax.axhline(np.log10(6.0), color=ORANGE, lw=0.9, ls=":", label="severe onset (6 Ω)")
    ax.set_xlabel("Day of year (VED)")
    ax.set_ylabel("log$_{10}$ contact resistance (Ω)")
    ax.legend(frameon=False, loc="upper left", fontsize=6)
    ax.set_title(f"(a) {vid}: real usage history")
    # (b) RUL error vs true RUL
    ax = axs[1]
    bins = np.array([0, 15, 30, 45, 60, 90, 120, 180, 270])
    mid = 0.5 * (bins[1:] + bins[:-1])
    for name, col, lab in (("proposed", BLUE, "Bayesian wear law + HI"), ("conditional", AQUA, "Conditional reliability (no HI)"),
                           ("raw_hi", ORANGE, "Bayesian wear law + raw statistic"), ("fleet", MUTED, "Fleet reliability")):
        err = np.abs(np.clip(f[name], 0, 1000) - f.true_rul)
        b = np.digitize(f.true_rul, bins) - 1
        mae = [err[b == i].median() if (b == i).any() else np.nan for i in range(len(mid))]
        ax.plot(mid, mae, color=col, marker="o", ms=3, label=lab)
    ax.set_xlabel("True remaining useful life (days)")
    ax.set_ylabel("Median |RUL error| (days)")
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("(b) RUL error across the fleet")
    fig.savefig(FIG / "fig_prognosis.pdf")
    plt.close(fig)


def fig_robustness():
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    with open(paths.RESULTS / "robustness_ved.json", encoding="utf-8") as fh:
        r = json.load(fh)["results"]
    names = list(r)
    s2 = [r[n]["auroc_s2"] for n in names]
    s3 = [r[n]["auroc_s3"] for n in names]
    y = np.arange(len(names))[::-1]
    ax.scatter(s3, y, color=RED, s=12, label="severe", zorder=3)
    ax.scatter(s2, y, color=ORANGE, s=12, label="moderate", zorder=3)
    ax.axvline(r["nominal"]["auroc_s3"], color=RED, lw=0.6, ls=":")
    ax.axvline(r["nominal"]["auroc_s2"], color=ORANGE, lw=0.6, ls=":")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("AUROC on mis-specified test physics (VED)")
    ax.legend(frameon=False, loc="lower left")
    fig.savefig(FIG / "fig_robustness.pdf")
    plt.close(fig)


def _bold_best(vals, fmt="{:.3f}"):
    best = max(v for v in vals if v is not None)
    return [("--" if v is None else (r"\textbf{" + fmt.format(v) + "}" if abs(v - best) < 5e-4 else fmt.format(v)))
            for v in vals]


def tables(corpora):
    """LaTeX table bodies written to ocwd/results/*.tex (pasted into the paper)."""
    order = [PROP, "GBM w/o coherence", "GBM loss only", "1D-CNN (supervised)", "LSTM autoencoder",
             "Isolation Forest", "One-class SVM", "Loss-rate threshold", "U-code timeout rule",
             "Coherence test (no training)"]
    nice = {PROP: r"\textbf{ECTA (proposed)}", "GBM w/o coherence": "ECTA w/o coherence",
            "GBM loss only": "ECTA loss features only", "Coherence test (no training)": r"Coherence test $z_\beta$ (no training)"}
    R = {c: load(c) for c in corpora}
    with open(paths.RESULTS / "detection_extra.json", encoding="utf-8") as fh:
        X = json.load(fh)
    # Table: detection.  per corpus: AUROC(all), moderate-vs-healthy, severe-vs-healthy
    cols = {}
    for c in corpora:
        cols[(c, "all")] = [R[c]["detection"].get(m, {}).get("auroc") for m in order]
        cols[(c, "s2")] = [X[c].get(m, {}).get("s2_vs_healthy") for m in order]
        cols[(c, "s3")] = [X[c].get(m, {}).get("s3_vs_healthy") for m in order]
    cols = {k: _bold_best(v) for k, v in cols.items()}
    lines = []
    for i, m in enumerate(order):
        cells = [cols[(c, k)][i] for c in corpora for k in ("all", "s2", "s3")]
        lines.append(nice.get(m, m) + " & " + " & ".join(cells) + r" \\")
    (paths.RESULTS / "table_detection.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Table: discrimination against confounders
    lines = []
    for c in corpora:
        ms = [PROP, "GBM w/o coherence", "1D-CNN (supervised)", "U-code timeout rule"]
        for j, m in enumerate(ms):
            row = [X[c][m][f"wear_vs_{k}"] for k in ("ecu", "emi", "ovf")]
            name = (CORPUS_LABEL[c] if j == 0 else "")
            lines.append(f"{name} & {nice.get(m, m)} & " + " & ".join(f"{v:.3f}" for v in row) + r" \\")
        lines.append(r"\midrule")
    (paths.RESULTS / "table_confounders.tex").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    # Table: attribution
    lines = []
    for c in corpora:
        a = X[c]["attribution"]
        pc = a["per_class_f1_excl_incipient"]
        cnn = R[c]["attribution"].get("1D-CNN (supervised)", {}).get("macro_f1")
        lines.append(f"{CORPUS_LABEL[c]} & {a['macro_f1_all']:.3f} & {a['macro_f1_excl_incipient']:.3f} & "
                     + " & ".join(f"{v:.2f}" for v in pc) + f" & {cnn:.3f}" + r" \\")
    (paths.RESULTS / "table_attribution.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Table: prognosis
    lines = []
    nm = {"proposed": "Bayesian wear law + HI (proposed)", "conditional": "Conditional reliability (no HI)",
          "linear": "HI trend extrapolation", "raw_hi": "Bayesian wear law + raw statistic",
          "fleet": "Fleet reliability (exposure)"}
    for rf in (6, 20):
        f = paths.RESULTS / f"prognosis_R{rf}.json"
        if not f.exists():
            continue
        P = json.load(open(f, encoding="utf-8"))
        lines.append(r"\multicolumn{7}{@{}l}{\emph{Failure at " + f"{rf}" + r"\,$\Omega$" +
                     (" (pre-specified)" if rf == 6 else " (functional failure; added post hoc)") +
                     f", {P['n_failing']} of {P['n_vehicles']} vehicles fail" + r"}} \\")
        for k in ("proposed", "conditional", "linear", "fleet"):
            r = P["methods"][k]
            mae = "--" if r["mae_all"] > 300 else f"{r['mae_all']:.0f}"
            lines.append(f"{nm[k]} & {mae} & {r['timely_rate']*100:.0f} & {r['premature_rate']*100:.0f} & "
                         f"{r['missed_rate']*100:.0f} & {r['median_lead_days']:.1f} & {r['false_alarm_rate_nonfailing']*100:.1f}" + r" \\")
    (paths.RESULTS / "table_prognosis.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    corpora = ["fullbus", "sampler", "poll", "ved"]
    fig_trace()
    fig_roc(corpora)
    fig_stage(corpora)
    tables(corpora)
    fig_confusion("ved")
    fig_confusion("fullbus")
    fig_importance("ved")
    for fn in (fig_accumulation, fig_prognosis, fig_robustness):
        try:
            fn()
        except FileNotFoundError as e:
            print("skip", fn.__name__, e)
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
