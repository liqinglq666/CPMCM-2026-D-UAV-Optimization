"""Equal-width evidence panels, including zero time slack and refined link failure."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    COLORS,
    DATA,
    INK,
    MARKERS,
    RED,
    DIRECT,
    LIGHT_BLUE,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
    threshold,
    key_note,
)

paper_style()
a = load_analysis()
c = pd.read_csv(DATA / "constraint_slacks.csv")
c = c[c.question == "q3"].sort_values("soc_pct")
h = pd.read_csv(DATA / "hard_deadline_slacks.csv").sort_values("slack_s")
v = a["sampling_validation"]
fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 3.05), layout="constrained")
ax, b, comm = axes
for kind in COLORS:
    mask = c.type == kind
    ax.scatter(
        np.arange(1, len(c) + 1)[mask],
        c.soc_pct[mask],
        s=19,
        fc=COLORS[kind],
        ec=INK,
        lw=0.4,
        marker=MARKERS[kind],
    )
threshold(ax, 20)
ax.set(
    xlabel="运输架次（排序）",
    ylabel="返航 SOC (%)",
    ylim=(15, 104),
    xticks=[1, 14, len(c)],
)
key_note(
    ax, (1, c.soc_pct.min()), "最小 SOC", f"{c.soc_pct.min():.2f}%", xytext=(0.06, 0.97)
)
panel(ax, "a", "能源储备")
b.scatter(np.arange(1, len(h) + 1), h.slack_s / 60, s=16, fc=DIRECT, ec=INK, lw=0.3)
threshold(b, 0)
b.set(
    xlabel="硬时限货箱（排序）",
    ylabel="硬截止余量 (min)",
    ylim=(-3, h.slack_s.max() / 60 * 1.45),
    xticks=[1, 10, len(h)],
)
key_note(
    b,
    (1, h.slack_s.min() / 60),
    "最小时间余量",
    f"{h.slack_s.min():.3f} s",
    xytext=(0.06, 0.97),
)
panel(b, "b", "硬截止")
for i, row in enumerate(v):
    comm.scatter(
        i,
        row["minimum_margin_db"],
        s=40,
        marker=["o", "s"][i],
        fc=LIGHT_BLUE if row["violations"] == 0 else RED,
        ec=INK,
        lw=0.6,
        zorder=4,
    )
threshold(comm, 0)
val = min(r["minimum_margin_db"] for r in v)
idx = min(range(len(v)), key=lambda i: v[i]["minimum_margin_db"])
extent = max(abs(r["minimum_margin_db"]) for r in v)
comm.set(
    xlabel="最大采样步长",
    ylabel="最小链路余量 (dB)",
    xlim=(-0.45, 1.45),
    ylim=(
        min(-0.04, val - extent * 0.28),
        max(r["minimum_margin_db"] for r in v) + extent * 1.15,
    ),
    xticks=[0, 1],
    xticklabels=["1.0 s", "0.5 s"],
)
key_note(comm, (idx, val), "最小通信余量", f"{val:.3f} dB", xytext=(0.06, 0.97))
panel(comm, "c", "通信加密复核")
for target in axes:
    grid(target, "y")
fig.legend(
    handles=[
        Line2D(
            [],
            [],
            marker=MARKERS[k],
            mfc=COLORS[k],
            mec=INK,
            ls="",
            ms=4,
            label=f"{k} 型",
        )
        for k in COLORS
    ]
    + [Line2D([], [], color=RED, ls="--", lw=0.8, label="可行阈值")],
    loc="outside upper center",
    ncol=4,
)
save(fig, "fig12_validation")
