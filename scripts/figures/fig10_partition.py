"""Typed resource deficits and a restrained service-to-group assignment matrix."""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    BLUE,
    GRAY,
    INK,
    ORANGE,
    RED,
    RESULTS,
    grid,
    panel,
    paper_style,
    save,
)
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
    figsize=(WIDTH, 4.75),
    gridspec_kw={"height_ratios": [2.4, 1]},
    layout="constrained",
)
keys = r[r.K == 2]["资源"].tolist()
for i, key in enumerate(keys):
    sub = r[r["资源"] == key]
    stock = int(sub["现有库存"].iloc[0])
    ax.plot([stock, stock], [i - 0.34, i + 0.34], color=INK, lw=1.4)
    for k, color, marker, dy in [(2, BLUE, "o", -0.16), (3, ORANGE, "s", 0.16)]:
        row = sub[sub.K == k].iloc[0]
        value = int(row["分组独立执行总需求"])
        gap = int(row["缺口"])
        ax.plot([stock, value], [i + dy] * 2, color=GRAY, lw=0.7)
        ax.scatter(
            value, i + dy, s=30, fc=color, ec=INK, lw=0.5, marker=marker, zorder=4
        )
        if gap:
            ax.text(
                value + 0.18, i + dy, f"+{gap}", color=RED, fontsize=7.5, va="center"
            )
ax.set_yticks(range(len(keys)), [labels[k] for k in keys])
ax.invert_yaxis()
ax.set(xlabel="资源数量 (台 / 组)", xlim=(0, r["分组独立执行总需求"].max() + 1.2))
grid(ax)
fig.legend(
    handles=[
        Line2D([], [], color=INK, marker="|", ls="", ms=10, label="现有库存"),
        Line2D([], [], color=BLUE, marker="o", ls="", mec=INK, label="K=2"),
        Line2D([], [], color=ORANGE, marker="s", ls="", mec=INK, label="K=3"),
    ],
    loc="outside upper center",
    ncol=3,
)
panel(ax, "a", "库存冗余不能抵消其他资源类型的缺口")
services = [sid for atom in atoms for sid in atom]
for y, k, marker, color in [(0, 2, "o", BLUE), (1, 3, "s", ORANGE)]:
    for _, row in p[p.K == k].iterrows():
        xs = [services.index(sid) for sid in row["服务区列表"].split(",")]
        groups.scatter(
            xs, np.full(len(xs), y), marker=marker, s=205, fc="white", ec=color, lw=0.9
        )
        for x in xs:
            groups.text(
                x,
                y,
                row["任务组编号"].replace("G", ""),
                ha="center",
                va="center",
                fontsize=7.5,
            )
start = 0
for i, atom in enumerate(atoms):
    end = start + len(atom)
    groups.plot([start - 0.35, end - 0.65], [1.55] * 2, color=INK, lw=0.7)
    groups.text((start + end - 1) / 2, 1.69, f"C{i + 1}", ha="center", fontsize=7.5)
    start = end
    if end < len(services):
        groups.axvline(end - 0.5, color=GRAY, ls="--", lw=0.65)
groups.set_xticks(range(len(services)), [s.replace("S0", "") for s in services])
groups.set_yticks([0, 1], ["K=2", "K=3"])
groups.set(
    xlabel="服务区编号；标记内数字为组号",
    ylim=(-0.55, 2.0),
    xlim=(-0.55, len(services) - 0.45),
)
panel(groups, "b", f"{len(atoms)} 个不可拆组件整体归组")
save(fig, "fig10_partition")
