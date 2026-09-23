# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Fixed joint-plan resource partitions, deterministic; confidence intervals not applicable."""

from common import (
    BLUE,
    GRAY,
    ORANGE,
    RESULTS,
    TEAL,
    load_analysis,
    panel,
    paper_style,
    save,
)
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
r = pd.read_csv(RESULTS / "q4/Q4_resource_summary.csv")
p = pd.read_csv(RESULTS / "q4/Q4_partition_config.csv")
resources = r[r.K == 2]["资源"].tolist()
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
fig, (ax, group) = plt.subplots(
    2,
    1,
    figsize=(7, 5.1),
    gridspec_kw={"height_ratios": [2.1, 1]},
    layout="constrained",
)
for i, key in enumerate(resources):
    s = r[r["资源"] == key]
    stock = int(s["现有库存"].iloc[0])
    ax.plot([stock, s["分组独立执行总需求"].max()], [i, i], color=GRAY, lw=2)
    ax.scatter(stock, i, marker="|", s=140, color=GRAY, zorder=3)
    for k, color, mark, dy in [(2, BLUE, "o", -0.13), (3, ORANGE, "s", 0.13)]:
        value = int(s[s.K == k]["分组独立执行总需求"].iloc[0])
        ax.scatter(
            value,
            i + dy,
            color=color,
            marker=mark,
            s=35,
            label=f"K={k}" if i == 0 else None,
        )
ax.set_yticks(range(len(resources)), [labels.get(k, k) for k in resources])
ax.invert_yaxis()
ax.set_xlabel("资源数量 (台 / 组)")
ax.set_ylabel("资源类型")
ax.set_xlim(left=0)
ax.legend(loc="lower right")
ax.text(
    0.99,
    0.98,
    "N=2；灰线为现有库存",
    transform=ax.transAxes,
    ha="right",
    va="top",
    fontsize=8,
)
gaps = r.groupby("K")["缺口"].sum()
panel(ax, "a", f"独立执行资源缺口：K=2 为 {gaps[2]}，K=3 为 {gaps[3]}")
services = sorted(k for k in a["nodes"] if k != "O01")
for y, k in enumerate([2, 3]):
    for _, row in p[p.K == k].iterrows():
        idx = int(row["任务组编号"][1:]) - 1
        for sid in row["服务区列表"].split(","):
            x = services.index(sid)
            group.barh(
                y,
                0.9,
                left=x - 0.45,
                height=0.55,
                color=[BLUE, TEAL, ORANGE][idx],
                hatch=["", "//", ".."][idx],
            )
            group.text(
                x,
                y,
                row["任务组编号"],
                ha="center",
                va="center",
                fontsize=7,
                color="white",
            )
group.set_xticks(range(len(services)), [s.replace("S0", "") for s in services])
group.set_yticks([0, 1], ["K=2", "K=3"])
group.set_xlabel("服务区编号 S0xx")
group.set_ylabel("分区场景")
panel(group, "b", "保持跨区运输架次与通信保障关系")
save(fig, "fig09_partition")
