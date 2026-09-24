"""Real discovered Pareto set and per-trip representatives, with current selection."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    INK,
    GRAY,
    PALE_BLUE,
    RESULTS,
    YELLOW,
    grid,
    panel,
    paper_style,
    save,
    load_analysis,
)

paper_style()
a = load_analysis()
d = pd.read_csv(RESULTS / "q2/Q2_tradeoff_frontier.csv")
p = pd.read_csv(RESULTS / "q2/Q2_pareto_frontier.csv")
selected = a["metrics"]["q2"]
n = selected["trips"]
fig, (ax, b) = plt.subplots(
    2,
    1,
    figsize=(WIDTH, 4.7),
    gridspec_kw={"height_ratios": [1.8, 1]},
    layout="constrained",
)
ax.scatter(
    p.energy,
    p.weighted_tardiness / 1000,
    s=21,
    fc=PALE_BLUE,
    ec="#839499",
    lw=0.4,
    zorder=2,
)
ax.scatter(
    d.energy, d.weighted_tardiness / 1000, s=30, fc="white", ec=INK, lw=0.6, zorder=3
)
ax.scatter(
    selected["energy"],
    selected["weighted_tardiness"] / 1000,
    s=120,
    marker="*",
    fc=YELLOW,
    ec=INK,
    lw=0.8,
    zorder=6,
)
for r in d.itertuples():
    if 17 <= r.trips <= 24:
        dx, dy = {
            17: (5, 3),
            18: (5, 3),
            19: (5, 3),
            20: (5, 3),
            21: (-14, 7),
            22: (-14, 7),
            23: (4, -13),
            24: (4, -13),
        }[r.trips]
        ax.annotate(
            str(r.trips),
            (r.energy, r.weighted_tardiness / 1000),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8,
            zorder=7,
        )
ax.set(xlabel="运输总能耗 (kWh)", ylabel="加权延误 ($10^3$ 系数·s)")
ax.margins(x=0.11, y=0.14)
grid(ax, "both")
panel(ax, "a", "已发现候选的能耗与软延误取舍")
fig.legend(
    handles=[
        Line2D(
            [],
            [],
            marker="o",
            mfc=PALE_BLUE,
            mec="#839499",
            ls="",
            label=f"已发现非支配解（{len(p)}）",
        ),
        Line2D([], [], marker="o", mfc="white", mec=INK, ls="", label="按架次代表解"),
        Line2D(
            [],
            [],
            marker="*",
            mfc=YELLOW,
            mec=INK,
            ls="",
            ms=9,
            label=f"正式选择：{n} 架次",
        ),
    ],
    loc="outside upper center",
    ncol=3,
)
d = d.sort_values("trips")
b.plot(
    d.trips,
    d.makespan / 60,
    color=GRAY,
    lw=0.9,
    marker="o",
    ms=4,
    mfc="white",
    mec=INK,
    mew=0.6,
)
b.scatter(
    n, selected["makespan"] / 60, s=95, marker="*", fc=YELLOW, ec=INK, lw=0.7, zorder=5
)
b.set(xlabel="运输架次数", ylabel="运输完工时间 (min)", xticks=d.trips.tolist())
b.invert_xaxis()
b.margins(y=0.2)
grid(b, "y")
panel(b, "b", "减少架次并不保证更早完工")
save(fig, "fig06_tradeoff")
