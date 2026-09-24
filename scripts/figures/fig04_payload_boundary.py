"""Formal Q1 safe payloads; service order shows geography without a false distance response."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    COLORS,
    GRAY,
    INK,
    LINESTYLES,
    MARKERS,
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
    figsize=(6.5, 4.5),
    sharex=True,
    gridspec_kw={"height_ratios": [1.5, 1]},
    layout="constrained",
)
x = np.arange(len(d))
for kind in COLORS:
    values = d[f"{kind}型最大安全载荷（kg）"]
    rated = a["types"][kind]["max_payload"]
    for target, y in [(ax, values), (ratio, 100 * values / rated)]:
        target.plot(
            x,
            y,
            color=COLORS[kind],
            marker=MARKERS[kind],
            ls=LINESTYLES[kind],
            ms=4.5,
            mec=INK,
            mew=0.45,
            label=f"{kind} 型",
        )
    ax.axhline(rated, color=GRAY, ls="--", lw=0.65, zorder=0)
    restricted = values < rated - 1e-8
    if kind == "C":
        ax.scatter(
            x[restricted],
            values[restricted],
            s=85,
            facecolor="none",
            edgecolor=INK,
            lw=0.6,
            zorder=4,
            label="C 型能源受限",
        )
ax.set(ylabel="最大安全载荷 (kg)", ylim=(0, 92))
ax.legend(ncol=4, loc="upper left", fontsize=9)
panel(ax, "a", "额定载荷并非各服务区都能用足")
ratio.axhline(100, color=GRAY, ls="--", lw=0.7)
ratio.set(
    ylabel="额定载荷占比 (%)", ylim=(65, 105), xlabel="服务区编号（连线仅便于对照）"
)
ratio.set_xticks(x, d["服务区编号"].str.replace("S0", ""), rotation=0)
for target in (ax, ratio):
    grid(target, "y")
panel(ratio, "b", "同一储备下，各机型受限程度不同")
save(fig, "fig04_payload_boundary")
