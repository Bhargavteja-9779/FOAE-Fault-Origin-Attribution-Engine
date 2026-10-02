"""Graphical abstract (IEEE Access optional item): problem -> method -> results."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from .. import paths

BLUE, ORANGE, RED, INK, INK2, MUTED, BG = "#2a78d6", "#eb6834", "#e34948", "#0b0b0b", "#52514e", "#9a998f", "#f4f3ee"
plt.rcParams.update({"font.family": "DejaVu Sans"})


def box(ax, x, y, w, h, title, lines, accent):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc="white", ec=accent, lw=1.6))
    ax.text(x + w / 2, y + h - 0.055, title, ha="center", va="top", fontsize=11.5, weight="bold", color=accent)
    for i, ln in enumerate(lines):
        ax.text(x + 0.02, y + h - 0.14 - i * 0.058, ln, ha="left", va="top", fontsize=9.6, color=INK)


def main():
    fig = plt.figure(figsize=(13.2, 5.9), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.patch.set_facecolor(BG)
    ax.text(0.5, 0.95, "Excitation-Coherent Telemetry Analysis for Predictive OBD-II Connector Wear Detection",
            ha="center", fontsize=14.5, weight="bold", color=INK)
    ax.text(0.5, 0.895, "Real telemetry from 5 public datasets  ·  9 vehicles in detail + 381-vehicle fleet  ·  vehicle-disjoint validation",
            ha="center", fontsize=9.5, color=INK2)
    box(ax, 0.025, 0.12, 0.29, 0.71, "Problem", [
        "Telematics / insurance dongles stay", "plugged into the J1962 port for years.",
        "Vibration frets the tin-plated contacts:", "  milliohms  →  intermittent ohms.",
        "The car never notices. The dongle sees", "lost frames, timeouts and brown-outs,",
        "and gets replaced while the worn", "connector stays in service."], ORANGE)
    box(ax, 0.355, 0.12, 0.29, 0.71, "Method: ECTA", [
        "Uses only what the tool already records.", "1  Loss features (self-referenced)",
        "2  Loss-structure features", "    (selectivity, lateness, load)",
        "3  Excitation coherence: do losses rise", "    with the car's own rpm and speed?",
        "    Poisson GLM  y ~ exp(α + β·log v)", "Physics model + first-principles",
        "observability law."], BLUE)
    box(ax, 0.685, 0.12, 0.29, 0.71, "Results", [
        "Unseen vehicles (full-bus, 6-fold LOVO):", "  AUROC 0.880; moderate 0.891,",
        "  severe 0.995; deep baselines ≤ 0.65", "Moderate wear confirmed in ~2 min",
        "Observability law predicts", "  detectability: Spearman ρ = 0.93",
        "Holds on a different fault model (0.856)", "Fleet: 88 % timely warnings,",
        "  1.5 % false alarms"], RED)
    for x0, x1 in ((0.318, 0.352), (0.648, 0.682)):
        ax.add_patch(FancyArrowPatch((x0, 0.475), (x1, 0.475), arrowstyle="-|>", mutation_scale=22, color=MUTED, lw=2))
    ax.text(0.5, 0.045, "No added hardware  ·  open, reproducible code  ·  limits reported (incipient wear, low-rate tools, long-horizon RUL)",
            ha="center", fontsize=9, color=INK2, style="italic")
    out = paths.FIGURES
    fig.savefig(out / "graphical_abstract.png", dpi=150, facecolor=BG)
    fig.savefig(out / "graphical_abstract.pdf", facecolor=BG)
    print("saved", out / "graphical_abstract.png")


if __name__ == "__main__":
    main()
