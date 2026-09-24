"""Joint entity timeline; charging is a separate light-grey battery interval."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from common import (
    WIDTH,
    COLORS,
    GRAY,
    HATCH,
    INK,
    RESULTS,
    grid,
    panel,
    paper_style,
    save,
)

paper_style()
d = pd.read_csv(RESULTS / "q2/Q2_resource_check.csv")
counts = [d[d["资源类型"] == k]["资源编号"].nunique() for k in ["无人机", "电池"]]
fig, (uav, bat) = plt.subplots(
    2,
    1,
    figsize=(WIDTH, 6.3),
    sharex=True,
    gridspec_kw={"height_ratios": counts},
    layout="constrained",
)
for ax, kind in [(uav, "无人机"), (bat, "电池")]:
    rows = d[d["资源类型"] == kind]
    ids = sorted(rows["资源编号"].unique())
    for _, r in rows.iterrows():
        y = ids.index(r["资源编号"])
        begin = r["任务占用开始（s）"] / 60
        end = r["任务占用结束（s）"] / 60
        ax.barh(
            y,
            end - begin,
            left=begin,
            height=0.65,
            color=COLORS[r["机型"]],
            edgecolor=INK,
            lw=0.4,
            hatch=HATCH[r["机型"]],
        )
        ax.text(
            (begin + end) / 2,
            y,
            r["架次编号"].split("-")[-1],
            ha="center",
            va="center",
            fontsize=7.5,
            bbox={"fc": "white", "ec": "none", "pad": 0.1, "alpha": 0.86},
        )
        if kind == "电池":
            cb, ce = r["充电开始（s）"] / 60, r["充电结束（s）"] / 60
            ax.barh(
                y,
                ce - cb,
                left=cb,
                height=0.65,
                fc="#F5F6F6",
                ec=GRAY,
                lw=0.4,
                hatch="///",
            )
    ax.set_yticks(range(len(ids)), [k.replace("-BAT-", "-") for k in ids])
    ax.invert_yaxis()
    grid(ax)
    ax.set_ylabel(kind)
panel(uav, "a", "无人机占用至返航，实体任务不冲突")
panel(bat, "b", "电池充满后才能再次投入运输")
bat.set_xlabel("从任务起点计时 (min)")
bat.set_xlim(
    0, max(d["任务占用结束（s）"].max(), d["充电结束（s）"].max()) / 60 * 1.025
)
fig.legend(
    handles=[
        Patch(fc=COLORS[k], ec=INK, hatch=HATCH[k], lw=0.4, label=f"{k} 型")
        for k in COLORS
    ]
    + [Patch(fc="#F5F6F6", ec=GRAY, hatch="///", label="充电")],
    loc="outside upper center",
    ncol=4,
)
save(fig, "fig07_resources")
