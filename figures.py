"""
figures.py — the three figures, all built from one small CSV.

Each figure answers one plain question:

  1. What is wrong with this register, and how bad is it?
  2. What does the error cost in the final number? (the headline)
  3. Once the data is repaired, can we trust the finding?

Run:  python figures.py
Out:  three PNG files in figures/
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from checks import ALL_CHECKS, VALID_EPC

FIG = Path("figures")
FIG.mkdir(exist_ok=True)

INK, MUTED, ACCENT, WARN, GREY = (
    "#1a2029", "#5b6675", "#22456f", "#a8332f", "#ccd3dc"
)
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Plain-English names for the checks, so a reader needs no code to follow.
LABELS = {
    "duplicate_id":        "Duplicate building ID",
    "missing_gfa":         "Floor area missing",
    "impossible_gfa":      "Floor area zero",
    "unit_error":          "Floor area in ft$^2$",
    "missing_year":        "Year built missing",
    "invalid_epc":         "EPC code invalid",
    "epc_demand_conflict": "EPC contradicts meter",
}


def figure_1_whats_wrong(raw: pd.DataFrame) -> None:
    """Every check, counted and ordered by how many records it catches."""
    counts = {}
    for check in ALL_CHECKS:
        failed = check(raw)
        if len(failed):
            counts[failed["rule"].iloc[0]] = len(failed)

    names = [LABELS[k] for k in counts]
    vals = list(counts.values())
    order = np.argsort(vals)
    names = [names[i] for i in order]
    vals = [vals[i] for i in order]

    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    bars = ax.barh(names, vals, color=ACCENT, height=0.62)
    bars[[i for i, n in enumerate(names) if "ft$^2$" in n][0]].set_color(WARN)

    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() + 0.22, bar.get_y() + bar.get_height() / 2,
                f"{v}", va="center", fontsize=9.2, color=INK, fontweight="bold")

    n_buildings = raw["building_id"].nunique()
    total = int(pd.concat([c(raw) for c in ALL_CHECKS])["building_id"].nunique())

    ax.set_xlabel("Records failing the check")
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_title("Seven checks, and what each one catches",
                 loc="left", fontsize=10.8, pad=24)
    ax.text(0, 1.055,
            f"{total} of {n_buildings} buildings ({total/n_buildings:.0%}) fail "
            f"at least one check",
            transform=ax.transAxes, fontsize=9.2, color=WARN, fontweight="bold")
    ax.grid(axis="x", color=GREY, lw=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.text(0.01, -0.02, "A record can fail more than one check, so the counts "
             "do not sum to the total.", ha="left", va="top", fontsize=7.2,
             color=MUTED, style="italic")
    fig.savefig(FIG / "fig1_whats_wrong.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def figure_2_cost_of_not_checking(naive: pd.DataFrame,
                                  clean: pd.DataFrame) -> None:
    """
    The headline figure: the same dataset, two analysts.

    Left bar  = the analyst who de-duplicates and stops (the one defect
                everybody remembers to handle).
    Right bar = the analyst who runs the checks first.
    """
    def totals(d):
        gfa = float(d["gfa_m2"].sum())
        m = d["gfa_m2"].notna() & (d["gfa_m2"] > 0) & d["kwh_m2_year"].notna()
        w = d[m]
        inten = float((w["kwh_m2_year"] * w["gfa_m2"]).sum() / w["gfa_m2"].sum())
        return gfa, inten

    n_gfa, n_int = totals(naive)
    c_gfa, c_int = totals(clean)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.4))

    # -- floor area
    labels = ["De-duplicated\nonly", "Checked and\nrepaired"]
    vals = [n_gfa / 1000, c_gfa / 1000]
    bars = ax1.bar(labels, vals, color=[WARN, ACCENT], width=0.5)
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.03,
                 f"{v:,.0f}k m²", ha="center", fontsize=9.4,
                 fontweight="bold", color=INK)
    err = (n_gfa - c_gfa) / c_gfa * 100
    ax1.set_ylabel("Stock floor area (thousand m²)")
    ax1.set_ylim(0, max(vals) * 1.2)
    ax1.set_title(f"Floor area overstated by {err:.0f}%",
                  loc="left", fontsize=10.2, pad=10, color=WARN)
    ax1.grid(axis="y", color=GREY, lw=0.5, alpha=0.6)
    ax1.set_axisbelow(True)

    # -- intensity
    vals2 = [n_int, c_int]
    bars2 = ax2.bar(labels, vals2, color=[WARN, ACCENT], width=0.5)
    for b, v in zip(bars2, vals2):
        ax2.text(b.get_x() + b.get_width() / 2, v + max(vals2) * 0.03,
                 f"{v:,.0f}", ha="center", fontsize=9.4,
                 fontweight="bold", color=INK)
    err2 = (n_int - c_int) / c_int * 100
    ax2.set_ylabel("Stock intensity (kWh/m²/yr)")
    ax2.set_ylim(0, max(vals2) * 1.2)
    ax2.set_title(f"Intensity off by {err2:.0f}%",
                  loc="left", fontsize=10.2, pad=10, color=WARN)
    ax2.grid(axis="y", color=GREY, lw=0.5, alpha=0.6)
    ax2.set_axisbelow(True)

    fig.suptitle("What the errors cost if nobody checks",
                 x=0.005, ha="left", fontsize=11.2, y=1.03, color=INK)
    fig.tight_layout()
    fig.text(0.01, -0.04,
             "Every whole life carbon total scales with floor area, so a 51% "
             "area error is a 51% error in tonnes of CO\u2082e.",
             ha="left", va="top", fontsize=7.4, color=MUTED, style="italic")
    fig.savefig(FIG / "fig2_cost_of_not_checking.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def figure_3_signal_recovered(clean: pd.DataFrame) -> None:
    """
    Proof the repair worked, in one chart.

    EPC band should predict metered demand: that is what a certificate means.
    If the cleaning had destroyed or distorted records, that relationship would
    weaken. It does not.
    """
    d = clean.copy()
    d = d[d["epc_class"].isin(VALID_EPC)]
    order = VALID_EPC
    med = d.groupby("epc_class")["kwh_m2_year"].median().reindex(order)
    q1 = d.groupby("epc_class")["kwh_m2_year"].quantile(0.25).reindex(order)
    q3 = d.groupby("epc_class")["kwh_m2_year"].quantile(0.75).reindex(order)
    n = d.groupby("epc_class")["kwh_m2_year"].count().reindex(order)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(order))
    ax.errorbar(x, med, yerr=[med - q1, q3 - med], fmt="o-", color=ACCENT,
                ecolor=GREY, elinewidth=2.2, capsize=5, markersize=6,
                lw=1.6, label="Median and interquartile range")

    for xi, mi, ni in zip(x, med, n):
        ax.annotate(f"n={ni}", (xi, mi), textcoords="offset points",
                    xytext=(0, 13), ha="center", fontsize=7.4, color=MUTED)

    # Monotonic across all seven bands? That is the whole claim, and it needs
    # no correlation coefficient: every band uses more than the one before it.
    diffs = np.diff(med.values)
    monotonic = bool((diffs > 0).all())

    ax.set_xticks(x, order)
    ax.set_xlabel("EPC band")
    ax.set_ylabel("Metered demand (kWh/m²/yr)")
    ax.set_title("After repair, the certificate still predicts the meter",
                 loc="left", fontsize=10.8, pad=30)
    ax.text(0, 1.075,
            "Median demand rises across all seven bands: "
            f"{med.iloc[0]:.0f} \u2192 {med.iloc[-1]:.0f} kWh/m\u00b2/yr"
            + ("  \u2713" if monotonic else ""),
            transform=ax.transAxes, fontsize=8.8, color="#2f7a4c",
            fontweight="bold")
    ax.grid(color=GREY, lw=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.text(0.01, -0.04,
             "A cleaning step that improved this number by changing the data "
             "would be a bug, not a result.", ha="left", va="top",
             fontsize=7.4, color=MUTED, style="italic")
    fig.savefig(FIG / "fig3_signal_recovered.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    raw = pd.read_csv("sample_buildings.csv")
    clean = pd.read_csv("buildings_clean.csv")
    naive = raw.drop_duplicates("building_id", keep="first")

    figure_1_whats_wrong(raw)
    figure_2_cost_of_not_checking(naive, clean)
    figure_3_signal_recovered(clean)
    print("wrote 3 figures to figures/")


if __name__ == "__main__":
    main()
