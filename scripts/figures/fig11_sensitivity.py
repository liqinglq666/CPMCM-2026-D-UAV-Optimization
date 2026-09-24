"""Continuous payload response and exact parametric set-partition breakpoints."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    WIDTH,
    COLORS,
    DATA,
    GRAY,
    INK,
    MARKERS,
    LINESTYLES,
    RED,
    DIRECT,
    RESULTS,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
    threshold,
)

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "payload_reserve.csv")
s = pd.read_csv(RESULTS / "q1/Q1_sensitivity_summary.csv")
stair = pd.read_csv(DATA / "reserve_staircase.csv")
fig, (ax, b) = plt.subplots(
    2,
    1,
    figsize=(WIDTH, 4.45),
    sharex=True,
    gridspec_kw={"height_ratios": [1.55, 1]},
    layout="constrained",
)
for kind in COLORS:
    pivot = (
        d[d.type == kind].pivot(index="reserve", columns="service", values="payload_kg")
        / a["types"][kind]["max_payload"]
        * 100
    )
    for col in pivot:
        ax.plot(
            pivot.index * 100,
            pivot[col],
            color=COLORS[kind],
            alpha=0.15,
            lw=0.5,
            ls=LINESTYLES[kind],
        )
    sid = pivot.loc[np.isclose(pivot.index, 0.2)].iloc[0].idxmin()
    ax.plot(
        pivot.index * 100,
        pivot[sid],
        color=COLORS[kind],
        marker=MARKERS[kind],
        mec=INK,
        mew=0.4,
        markevery=10,
        ms=4,
        ls=LINESTYLES[kind],
        lw=1.5,
        label=f"{kind} 型 · {sid}",
    )
    invalid = pivot[sid].isna()
    if invalid.any():
        ax.scatter(
            pivot.index[invalid] * 100,
            np.full(invalid.sum(), -5),
            marker="x",
            s=12,
            color=RED,
        )
ax.set(ylabel="安全载荷 / 额定载荷 (%)", ylim=(-10, 108))
grid(ax, "y")
ax.legend(loc="lower left", ncol=3)
threshold(ax, 20, axis="x", color=GRAY)
panel(ax, "a", "储备提高使连续运载能力收缩")
for i, row in stair.iterrows():
    if not row.reachable:
        b.axvspan(
            row.reserve_lower * 100,
            row.reserve_upper * 100,
            fc="#FAF0F3",
            ec=RED,
            lw=0,
            hatch="///",
            alpha=0.5,
        )
        b.text(
            (row.reserve_lower + row.reserve_upper) * 50,
            20.5,
            "不可行",
            ha="center",
            fontsize=8,
            color=RED,
        )
        continue
    lo, hi = row.reserve_lower * 100, row.reserve_upper * 100
    b.plot([lo, hi], [row.trips] * 2, color=DIRECT, lw=1.5)
    if i and stair.iloc[i - 1].reachable:
        b.plot([lo, lo], [stair.iloc[i - 1].trips, row.trips], color=DIRECT, lw=1.1)
    b.scatter(hi, row.trips, s=17, fc=DIRECT, ec=INK, lw=0.4, zorder=4)
b.scatter(
    s["返航安全余量"] * 100,
    s["最少往返架次数"],
    s=32,
    fc="white",
    ec=INK,
    lw=0.7,
    zorder=5,
    label="原五场景独立重算",
)
crit = a["fixed_plan_thresholds"]["q1"]["maximum_common_reserve"] * 100
threshold(b, 20, axis="x", color=GRAY)
threshold(b, crit, axis="x", color=GRAY)
b.text(
    crit + 0.35,
    0.94,
    f"固定原方案阈值 {crit:.2f}%",
    transform=b.get_xaxis_transform(),
    va="top",
    fontsize=7.5,
)
b.set(
    xlabel="返航储备 (%)",
    ylabel="精确最少架次",
    xlim=(10, 40),
    ylim=(stair.trips.min() - 0.6, stair.trips.max() + 1.6),
    yticks=sorted(stair.trips.dropna().unique()),
)
grid(b, "y")
b.legend(loc="lower right")
panel(b, "b", "货箱不可拆使最少架次发生离散跳变")
save(fig, "fig11_sensitivity")
