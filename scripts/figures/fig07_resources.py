"""Independent UAV/battery occupancy, including recharge; original resource log."""

import matplotlib.pyplot as plt
import pandas as pd
from common import COLORS, GRAY, HATCH, INK, RESULTS, grid, panel, paper_style, save
from matplotlib.patches import Patch

paper_style()
d = pd.read_csv(RESULTS / "q2/Q2_resource_check.csv")
fig, (uav, bat) = plt.subplots(
    2,
    1,
    figsize=(6.5, 6.5),
    sharex=True,
    gridspec_kw={"height_ratios": [8, 14]},
    layout="constrained",
)
for ax, kind in [(uav, "无人机"), (bat, "电池")]:
    rows = d[d["资源类型"] == kind]
    ids = sorted(rows["资源编号"].unique())
    for _, r in rows.iterrows():
        y = ids.index(r["资源编号"])
        begin = r["任务占用开始（s）"] / 3600
        end = r["任务占用结束（s）"] / 3600
        ax.barh(
            y,
            end - begin,
            left=begin,
            height=0.64,
            color=COLORS[r["机型"]],
            edgecolor=INK,
            lw=0.45,
            hatch=HATCH[r["机型"]],
        )
        ax.text(
            (begin + end) / 2,
            y,
            r["架次编号"].split("-")[-1],
            va="center",
            ha="center",
            fontsize=8.5,
            color=INK,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.1, "alpha": 0.82},
        )
        if kind == "电池":
            cb, ce = r["充电开始（s）"] / 3600, r["充电结束（s）"] / 3600
            ax.barh(
                y,
                ce - cb,
                left=cb,
                height=0.64,
                facecolor="white",
                edgecolor=GRAY,
                lw=0.6,
                hatch="////",
            )
    ax.set_yticks(range(len(ids)), [k.replace("-BAT-", "-") for k in ids])
    ax.invert_yaxis()
    grid(ax)
    ax.set_ylabel(kind)
    ax.set_xlim(left=0)
panel(uav, "a", "实体无人机：任务占用至返航")
panel(bat, "b", "独立电池：任务结束后仍需充电")
bat.set_xlabel("从任务起点计时 (h)")
uav.legend(
    handles=[
        Patch(facecolor=COLORS[k], edgecolor=INK, hatch=HATCH[k], label=f"{k} 型")
        for k in COLORS
    ]
    + [Patch(facecolor="white", edgecolor=GRAY, hatch="////", label="充电")],
    ncol=4,
    loc="lower left",
    bbox_to_anchor=(0, 1.14),
    fontsize=9,
)
save(fig, "fig07_resources")
