"""Typed stock/gaps and indivisible components inherited from fixed Q3 trips."""

import matplotlib.pyplot as plt
import pandas as pd
from common import BLUE, GRAY, INK, ORANGE, RED, RESULTS, grid, panel, paper_style, save
from matplotlib.lines import Line2D

from src.q4.partition import atomic_components

paper_style()
r = pd.read_csv(RESULTS / "q4/Q4_resource_summary.csv")
p = pd.read_csv(RESULTS / "q4/Q4_partition_config.csv")
atoms = atomic_components(
    pd.read_csv(RESULTS / "q3/Q3_transport_trips.csv").to_dict("records")
)
labels = {
    "A_uav": "A 无人机",
    "B_uav": "B 无人机",
    "C_uav": "C 无人机",
    "A_bat": "A 电池",
    "B_bat": "B 电池",
    "C_bat": "C 电池",
    "relay_uav": "中继无人机",
    "relay_comp": "中继能源组件",
}
fig, (ax, groups) = plt.subplots(
    2,
    1,
    figsize=(6.5, 5.5),
    gridspec_kw={"height_ratios": [2.5, 1]},
    layout="constrained",
)
keys = r[r.K == 2]["资源"].tolist()
for i, key in enumerate(keys):
    sub = r[r["资源"] == key]
    stock = int(sub["现有库存"].iloc[0])
    ax.plot([stock, stock], [i - 0.33, i + 0.33], color=INK, lw=1.5)
    for k, color, marker, dy in [(2, BLUE, "o", -0.16), (3, ORANGE, "s", 0.16)]:
        row = sub[sub.K == k].iloc[0]
        value = int(row["分组独立执行总需求"])
        gap = int(row["缺口"])
        ax.plot([stock, value], [i + dy, i + dy], color=GRAY, lw=0.8)
        ax.scatter(
            value,
            i + dy,
            s=42,
            facecolor=color,
            edgecolor=INK,
            lw=0.5,
            marker=marker,
            zorder=4,
        )
        if gap:
            ax.text(value + 0.18, i + dy, f"+{gap}", color=RED, fontsize=9, va="center")
ax.set_yticks(range(len(keys)), [labels[k] for k in keys])
ax.invert_yaxis()
ax.set(xlabel="资源数量 (台 / 组)", xlim=(0, 8))
grid(ax)
ax.legend(
    handles=[
        Line2D([], [], color=INK, marker="|", ls="", ms=12, label="库存"),
        Line2D([], [], color=BLUE, marker="o", ls="", mec=INK, label="K=2"),
        Line2D([], [], color=ORANGE, marker="s", ls="", mec=INK, label="K=3"),
    ],
    ncol=3,
    loc="lower right",
    bbox_to_anchor=(1, 1.04),
    fontsize=9,
)
panel(ax, "a", "总量不能抵消类型缺口：红字为缺少数量")
services = [sid for atom in atoms for sid in atom]
for y, k, color in [(0, 2, BLUE), (1, 3, ORANGE)]:
    for _, row in p[p.K == k].iterrows():
        idx = int(row["任务组编号"][1:]) - 1
        for sid in row["服务区列表"].split(","):
            x = services.index(sid)
            groups.barh(
                y,
                0.9,
                left=x - 0.45,
                height=0.55,
                color=color,
                edgecolor=INK,
                lw=0.5,
                hatch=["", "//", ".."][idx],
            )
            groups.text(
                x,
                y,
                row["任务组编号"],
                ha="center",
                va="center",
                fontsize=8.5,
                color=INK,
                bbox={
                    "facecolor": "white",
                    "edgecolor": "none",
                    "pad": 0.2,
                    "alpha": 0.85,
                },
            )
start = 0
for i, atom in enumerate(atoms):
    end = start + len(atom)
    groups.plot([start - 0.45, end - 0.55], [1.55, 1.55], color=INK, lw=0.75)
    groups.text((start + end - 1) / 2, 1.68, f"C{i + 1}", ha="center", fontsize=9)
    start = end
    if end < len(services):
        groups.axvline(end - 0.5, color=GRAY, ls="--", lw=0.6)
groups.set_xticks(
    range(len(services)), [s.replace("S0", "") for s in services], rotation=0
)
groups.set_yticks([0, 1], ["K=2", "K=3"])
groups.set(
    xlabel="服务区编号（按不可拆连通分量排序）",
    ylim=(-0.6, 2.03),
    xlim=(-0.6, len(services) - 0.4),
)
panel(groups, "b", f"{len(atoms)} 个连通分量必须整体归组")
save(fig, "fig10_partition")
