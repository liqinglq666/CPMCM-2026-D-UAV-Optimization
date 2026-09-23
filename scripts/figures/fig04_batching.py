# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Allocation and binding capacities, deterministic; confidence intervals not applicable."""

from common import (
    BLUE,
    DATA,
    GRAY,
    ORANGE,
    RED,
    RESULTS,
    TEAL,
    load_analysis,
    panel,
    paper_style,
    save,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

paper_style()
a = load_analysis()
b = pd.read_csv(RESULTS / "q1/Q1_batch_solution.csv")
c = pd.read_csv(DATA / "constraint_slacks.csv")
c = c[c.question == "q1"].set_index("trip").loc[b["架次编号"]]
boxes = {x["id"]: x for x in a["boxes"]}
kinds = list(dict.fromkeys(x["kind"] for x in a["boxes"]))
kind_colors = [BLUE, TEAL, ORANGE, GRAY]
hatches = ["", "//", "..", "xx"]
fig, (ax, util) = plt.subplots(
    1,
    2,
    figsize=(7, 6.0),
    gridspec_kw={"width_ratios": [2.15, 1]},
    layout="constrained",
    sharey=True,
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
                height=0.68,
                color=kind_colors[j],
                hatch=hatches[j],
                edgecolor="white",
                lw=0.7,
            )
            ax.text(
                left + mass / 2,
                i,
                str(len(cargo)),
                ha="center",
                va="center",
                fontsize=8,
                color="white" if j < 3 else "#24333E",
                bbox={"facecolor": kind_colors[j], "edgecolor": "none", "pad": 0.6},
            )
            left += mass
ax.set_yticks(
    range(len(b)),
    [r["架次编号"].replace("Q1-", "") + " " + r["机型编号"] for _, r in b.iterrows()],
)
ax.invert_yaxis()
ax.set_xlabel("货箱质量 (kg)；条内数字为箱数")
ax.set_ylabel("服务区—批次 / 机型")
panel(ax, "a", f"{len(a['boxes'])} 个货箱的 {len(b)} 架次精确组批")
ax.legend(
    handles=[
        Patch(facecolor=kind_colors[i], hatch=hatches[i], label=k)
        for i, k in enumerate(kinds)
    ],
    loc="upper center",
    bbox_to_anchor=(0.5, -0.1),
    ncol=2,
    fontsize=8,
)
for j, (field, name) in enumerate(
    [
        ("mass_fraction", "质量"),
        ("volume_fraction", "体积"),
        ("energy_fraction", "能量"),
    ]
):
    util.scatter(
        c[field] * 100,
        np.arange(len(b)) + (j - 1) * 0.17,
        s=20,
        marker=["o", "s", "^"][j],
        color=[BLUE, TEAL, ORANGE][j],
        label=name,
    )
util.axvline(100, color=RED, ls="--", lw=0.9)
util.set_xlabel("约束占用 (%)")
util.set_xlim(0, 110)
util.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8)
panel(util, "b", f"N={len(b)} 约束核验")
save(fig, "fig04_batching")
