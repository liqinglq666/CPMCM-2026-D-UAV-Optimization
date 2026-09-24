"""Categorical service comparisons, not a distance-only payload response."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    COLORS,
    GRAY,
    INK,
    MARKERS,
    LINESTYLES,
    RESULTS,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
)

paper_style()
a = load_analysis()
d = pd.read_csv(RESULTS / "q1/Q1_max_safe_payload.csv")
fig, (ax, ratio) = plt.subplots(
    2,
    1,
    figsize=(WIDTH, 3.9),
    sharex=True,
    gridspec_kw={"height_ratios": [1.5, 1]},
    layout="constrained",
)
x = np.arange(len(d))
for kind in COLORS:
    values = d[f"{kind}型最大安全载荷（kg）"]
    rated = a["types"][kind]["max_payload"]
    restricted = values < rated - 1e-8
    for target, y in [(ax, values), (ratio, 100 * values / rated)]:
        target.plot(x, y, color=COLORS[kind], ls=LINESTYLES[kind], lw=1.15)
        for mask, filled in [(~restricted, True), (restricted, False)]:
            target.scatter(
                x[mask],
                y[mask],
                s=22,
                marker=MARKERS[kind],
                facecolor=COLORS[kind] if filled else "white",
                edgecolor=INK,
                lw=0.65,
                zorder=4,
            )
    ax.axhline(rated, color=GRAY, ls="--", lw=0.65, zorder=0)
ax.set(
    ylabel="最大安全载荷 (kg)",
    ylim=(0, max(t["max_payload"] for t in a["types"].values()) * 1.13),
)
fig.legend(
    handles=[
        Line2D(
            [],
            [],
            color=COLORS[k],
            marker=MARKERS[k],
            ls=LINESTYLES[k],
            mec=INK,
            ms=4,
            label=f"{k} 型",
        )
        for k in COLORS
    ]
    + [
        Line2D(
            [], [], color=INK, marker="o", mfc="white", ls="", ms=4, label="能源受限"
        ),
        Line2D([], [], color=GRAY, ls="--", label="额定上限"),
    ],
    loc="outside upper center",
    ncol=5,
)
panel(ax, "a", "额定载荷不能在所有服务区用足")
ratio.axhline(100, color=GRAY, ls="--", lw=0.65)
ratio.set(
    ylabel="额定载荷占比 (%)",
    ylim=(65, 105),
    xlabel="服务区编号（分类比较，连线仅辅助阅读）",
)
ratio.set_xticks(x, d["服务区编号"].str.replace("S0", ""))
panel(ratio, "b", "地形与能量造成不同程度的能力收缩")
for target in (ax, ratio):
    grid(target, "y")
save(fig, "fig04_payload_boundary")
