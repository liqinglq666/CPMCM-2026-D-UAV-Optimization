"""Reachable capacity curves and five exact reoptimizations; no fictitious jump location."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    BLUE,
    COLORS,
    DATA,
    INK,
    LINESTYLES,
    MARKERS,
    ORANGE,
    RED,
    RESULTS,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
)

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "payload_reserve.csv")
s = pd.read_csv(RESULTS / "q1/Q1_sensitivity_summary.csv")
fig, (ax, b) = plt.subplots(
    2,
    1,
    figsize=(6.5, 4.8),
    gridspec_kw={"height_ratios": [1.6, 1]},
    layout="constrained",
)
for kind in COLORS:
    pivot = (
        d[d.type == kind].pivot(index="reserve", columns="service", values="payload_kg")
        / a["types"][kind]["max_payload"]
        * 100
    )
    # Show individual service traces faintly; never substitute zero for unreachable.
    for column in pivot:
        ax.plot(
            pivot.index * 100,
            pivot[column],
            color=COLORS[kind],
            alpha=0.32,
            lw=0.65,
            ls=LINESTYLES[kind],
        )
    # Choose the service most restricted at baseline, then track that fixed service.
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
        label=f"{kind} 型：{sid}",
    )
    invalid = pivot[sid].isna()
    if invalid.any():
        ax.scatter(
            pivot.index[invalid] * 100,
            np.full(invalid.sum(), -7),
            marker="x",
            s=13,
            color=RED,
        )
ax.set(xlabel="返航储备 (%)", ylabel="安全载荷 / 额定载荷 (%)", ylim=(-12, 108))
grid(ax, "y")
ax.legend(loc="lower left", fontsize=9, ncol=3)
panel(ax, "a", "提高储备压缩能力；不可达不记为零载荷")
b.scatter(
    s["返航安全余量"] * 100,
    s["最少往返架次数"],
    s=55,
    color=BLUE,
    edgecolor=INK,
    lw=0.6,
    zorder=4,
)
for _, row in s.iterrows():
    b.annotate(
        str(int(row["最少往返架次数"])),
        (row["返航安全余量"] * 100, row["最少往返架次数"]),
        xytext=(0, 7),
        textcoords="offset points",
        ha="center",
        fontsize=9,
    )
crit = a["fixed_plan_thresholds"]["q1"]["maximum_common_reserve"] * 100
b.axvline(crit, color=ORANGE, ls="--", lw=1)
b.text(
    crit - 0.7,
    s["最少往返架次数"].min() + 0.35,
    f"固定基准阈值\n{crit:.2f}%",
    fontsize=9,
    va="bottom",
    ha="right",
)
b.set(
    xlabel="返航储备 (%)",
    ylabel="重新求解的最少架次",
    xticks=s["返航安全余量"] * 100,
    yticks=sorted(s["最少往返架次数"].unique()),
    ylim=(s["最少往返架次数"].min() - 0.5, s["最少往返架次数"].max() + 0.7),
)
grid(b, "y")
panel(b, "b", f"仅 {len(s)} 个场景重新优化；不推断精确跳变位置")
save(fig, "fig11_sensitivity")
