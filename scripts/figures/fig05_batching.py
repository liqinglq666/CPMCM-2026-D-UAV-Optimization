"""Exact cargo groups and constraint occupancy, with independent cargo encoding."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from common import (
    WIDTH,
    DATA,
    INK,
    RED,
    RESULTS,
    load_analysis,
    panel,
    paper_style,
    save,
    grid,
)

paper_style()
a = load_analysis()
b = pd.read_csv(RESULTS / "q1/Q1_batch_solution.csv")
c = pd.read_csv(DATA / "constraint_slacks.csv")
c = c[c.question == "q1"].set_index("trip").loc[b["架次编号"]]
boxes = {v["id"]: v for v in a["boxes"]}
kinds = list(dict.fromkeys(v["kind"] for v in a["boxes"]))
colors = ["#DFDFD4", "#C7D7D5", "#DBCEDB", "#D6C9B8"]
hatches = ["", "///", "..", "xx"]
fig, (ax, util) = plt.subplots(
    1,
    2,
    figsize=(WIDTH, 5.1),
    sharey=True,
    gridspec_kw={"width_ratios": [1.65, 1]},
    layout="constrained",
)
for i, r in b.iterrows():
    left = 0
    for j, kind in enumerate(kinds):
        cargo = [
            boxes[k] for k in r["货箱编号列表"].split(",") if boxes[k]["kind"] == kind
        ]
        mass = sum(k["mass"] for k in cargo)
        if mass:
            ax.barh(
                i,
                mass,
                left=left,
                height=0.62,
                color=colors[j],
                hatch=hatches[j],
                edgecolor=INK,
                lw=0.45,
            )
            if mass >= 5:
                ax.text(
                    left + mass / 2,
                    i,
                    str(len(cargo)),
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    bbox={"fc": colors[j], "ec": "none", "pad": 0.2},
                )
            left += mass
ax.set_yticks(
    range(len(b)),
    [
        r["架次编号"].replace("Q1-S0", "") + " / " + r["机型编号"]
        for _, r in b.iterrows()
    ],
)
ax.invert_yaxis()
ax.set(xlabel="货箱质量 (kg)；数字为箱数", ylabel="服务区—批次 / 机型")
panel(ax, "a", f"{len(a['boxes'])} 箱经精确划分形成 {len(b)} 批")
fields = ["mass_fraction", "volume_fraction", "energy_fraction"]
for j, (field, name, marker) in enumerate(
    zip(fields, ["质量", "体积", "能量"], ["o", "s", "^"])
):
    util.scatter(
        c[field] * 100,
        np.arange(len(b)) + (j - 1) * 0.17,
        s=21,
        marker=marker,
        facecolor="white" if j == 1 else "#7C8C91",
        edgecolor=INK,
        lw=0.55,
        label=name,
        zorder=3,
    )
util.axvline(100, color=RED, ls="--", lw=0.8)
for tid in c[fields].max(axis=1).nlargest(3).index:
    i = list(c.index).index(tid)
    j = int(np.argmax(c.loc[tid, fields]))
    value = c.loc[tid, fields[j]] * 100
    util.annotate(
        f"{value:.1f}%",
        (value, i + (j - 1) * 0.17),
        xytext=(5, 0),
        textcoords="offset points",
        va="center",
        fontsize=7.5,
        color=INK,
    )
util.set(xlabel="约束占用 (%)", xlim=(0, 127), xticks=[0, 50, 100])
grid(util)
grid(ax)
panel(util, "b", "各批次均不越过容量上限")
fig.legend(
    handles=[
        Patch(fc=colors[i], ec=INK, lw=0.4, hatch=hatches[i], label=k)
        for i, k in enumerate(kinds)
    ],
    loc="outside lower left",
    ncol=2,
)
util.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=1)
save(fig, "fig05_batching")
