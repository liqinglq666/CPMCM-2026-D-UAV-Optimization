"""Feasible is not robust: energy, time and sampling are distinct deterministic evidence."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    BLUE,
    COLORS,
    DATA,
    INK,
    MARKERS,
    ORANGE,
    RED,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
)

paper_style()
a = load_analysis()
c = pd.read_csv(DATA / "constraint_slacks.csv")
c = c[c.question == "q3"].sort_values("soc_pct")
h = pd.read_csv(DATA / "hard_deadline_slacks.csv").sort_values("slack_s")
fig = plt.figure(figsize=(6.5, 5.7), layout="constrained")
gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1])
ax = fig.add_subplot(gs[0, :])
b = fig.add_subplot(gs[1, 0])
comm = fig.add_subplot(gs[1, 1])
for kind in COLORS:
    mask = c.type == kind
    ax.scatter(
        np.arange(len(c))[mask],
        c.soc_pct[mask],
        s=34,
        facecolor=COLORS[kind],
        edgecolor=INK,
        lw=0.5,
        marker=MARKERS[kind],
        label=f"{kind} 型",
    )
ax.axhline(20, color=RED, ls="--", lw=0.9)
ax.set_xticks(range(len(c)), c.trip.str.replace("Q3-", ""), rotation=90)
ax.set(
    xlabel="运输架次（按 SOC 排序）",
    ylabel="返航 SOC (%)",
    ylim=(17, c.soc_pct.max() + 6),
)
grid(ax, "y")
ax.legend(ncol=3, loc="upper left", fontsize=9)
ax.annotate(
    f"最低 {c.soc_pct.min():.2f}%",
    (0, c.soc_pct.min()),
    xytext=(3, 36),
    arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.7},
    fontsize=9,
)
panel(ax, "a", "全部达到 20% 储备；最紧架次余量有限")
b.scatter(
    np.arange(1, len(h) + 1),
    h.slack_s / 60,
    s=18,
    facecolor=BLUE,
    edgecolor=INK,
    lw=0.3,
)
b.axhline(0, color=RED, ls="--", lw=0.8)
b.set(xlabel="硬时限货箱（排序）", ylabel="硬截止余量 (min)")
grid(b, "y")
panel(b, "b", f"{len(h)} 个硬时限均满足")
b.text(
    0.04,
    0.95,
    f"最小 {h.slack_s.min():.3f} s",
    transform=b.transAxes,
    va="top",
    fontsize=9,
)
v = a["sampling_validation"]
for i, r in enumerate(v):
    comm.scatter(
        i,
        r["minimum_margin_db"],
        s=55,
        marker=["o", "s"][i],
        facecolor=[BLUE, ORANGE][i],
        edgecolor=INK,
        lw=0.6,
    )
    comm.annotate(
        f"{r['minimum_margin_db']:.3f} dB\n{r['checked_states']:,} 条",
        (i, r["minimum_margin_db"]),
        xytext=(0, -15),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=9,
    )
comm.axhline(0, color=RED, ls="--", lw=0.8)
comm.set(
    xlim=(-0.45, 1.45),
    ylim=(-0.01, 0.17),
    xticks=[0, 1],
    xticklabels=[f"{r['step_s']:.1f} s" for r in v],
    xlabel="最大回放步长",
    ylabel="最小链路余量 (dB)",
)
grid(comm, "y")
panel(comm, "c", "加密通过仍非连续证明")
save(fig, "fig12_validation")
