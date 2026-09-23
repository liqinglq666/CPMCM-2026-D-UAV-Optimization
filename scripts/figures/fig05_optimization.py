# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Finite heuristic candidate set; no claim of a global Pareto frontier or statistical confidence interval."""

from common import (
    BLUE,
    GRAY,
    ORANGE,
    RESULTS,
    gantt,
    load_analysis,
    panel,
    paper_style,
    save,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
d = pd.read_csv(RESULTS / "q2/Q2_tradeoff_frontier.csv")
trips = pd.read_csv(RESULTS / "q2/Q2_transport_trips_balanced.csv")
fig, (ax, g) = plt.subplots(
    2,
    1,
    figsize=(7, 5.5),
    gridspec_kw={"height_ratios": [1.9, 1]},
    layout="constrained",
)
selected = d[d.trips == len(trips)].iloc[0]
ax.scatter(
    d.energy,
    d.weighted_tardiness / 1000,
    s=45,
    color=GRAY,
    marker="o",
    label="启发式候选",
)
# Dominance shown for these two displayed objectives only; trip count is omitted.
vals = d[["energy", "weighted_tardiness"]].to_numpy()
dom = np.array([any(np.all(v <= w) and np.any(v < w) for v in vals) for w in vals])
front = d[~dom].sort_values("energy")
ax.plot(
    front.energy,
    front.weighted_tardiness / 1000,
    color=BLUE,
    lw=1,
    label="所示两目标非支配集",
)
ax.scatter(
    selected.energy,
    selected.weighted_tardiness / 1000,
    color=ORANGE,
    marker="*",
    s=150,
    zorder=4,
    label="选定方案",
)
for r in d.itertuples():
    ax.annotate(
        f"{r.trips} 架次",
        (r.energy, r.weighted_tardiness / 1000),
        xytext=(5, 5 if r.trips != 21 else -14),
        textcoords="offset points",
        fontsize=8,
    )
ax.set_xlabel("运输能耗 (kWh)")
ax.set_ylabel("加权延误 ($10^3$ 优先系数·s)")
ax.legend(loc="upper right")
panel(ax, "a", "少飞行并不意味着更及时：展示实际候选的权衡")
ax.text(
    0.36,
    0.96,
    f"N={len(d)}；无全局最优性保证",
    transform=ax.transAxes,
    va="top",
    fontsize=9,
)
gantt(g, trips, "q2")
panel(g, "b", f"选定 {len(trips)} 架次：实体资源不重叠")
save(fig, "fig05_optimization")
