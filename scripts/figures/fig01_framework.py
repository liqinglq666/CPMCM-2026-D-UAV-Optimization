"""Argument architecture and exactly scoped inheritance; results read from files."""

import matplotlib.pyplot as plt
import pandas as pd
from common import (
    BACKGROUND,
    BLUE,
    GRAY,
    INK,
    PALE_BLUE,
    RESULTS,
    load_analysis,
    paper_style,
    save,
)
from matplotlib.patches import FancyArrowPatch, Rectangle

paper_style()
a = load_analysis()
m = a["metrics"]
gaps = pd.read_csv(RESULTS / "q4/Q4_resource_summary.csv").groupby("K")["缺口"].sum()
fig, ax = plt.subplots(figsize=(6.5, 6.3))
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis("off")
ax.text(
    0.5,
    0.975,
    "官方题目 · 节点与货箱 · 30 m DEM · 机型与库存",
    ha="center",
    va="top",
    fontsize=11,
    weight="bold",
)
ax.add_patch(
    Rectangle((0.02, 0.805), 0.96, 0.105, facecolor=PALE_BLUE, edgecolor=GRAY, lw=0.6)
)
ax.text(0.5, 0.877, "统一物理计算", ha="center", fontsize=12, weight="bold")
ax.text(
    0.5,
    0.834,
    "航高 → 动态载荷 → 分阶段能量 → 返航储备与充电",
    ha="center",
    fontsize=10,
)
rows = [
    (
        0.70,
        "Q1  能不能运",
        "安全载荷 → 不可拆货箱划分",
        f"{m['q1']['trips']} 架次\n单点组批精确",
    ),
    (
        0.52,
        "Q2  能否按时",
        "实体飞机 + 共享电池 + 交付时限",
        f"{m['q2']['trips']} 架次折中\n有限启发式候选",
    ),
    (
        0.34,
        "Q3  能否通信",
        "地形遮挡 + 指定中继 + 服务窗口",
        f"{m['q3']['transport_trips']} 运输 / {m['q3']['relay_sorties']} 中继\n固定方案时序 LP",
    ),
    (
        0.16,
        "Q4  能否独立",
        "不可拆分量 → 分区 → 资源缺口",
        f"两组缺 {gaps.loc[2]} / 三组缺 {gaps.loc[3]}\n固定计划精确枚举",
    ),
]
for y, title, model, result in rows:
    ax.add_patch(
        Rectangle(
            (0.02, y - 0.052), 0.96, 0.105, facecolor=BACKGROUND, edgecolor=GRAY, lw=0.6
        )
    )
    ax.plot([0.02, 0.02], [y - 0.052, y + 0.053], color=BLUE, lw=3)
    ax.text(0.04, y + 0.019, title, fontsize=11, weight="bold")
    ax.text(0.04, y - 0.023, model, fontsize=9.5)
    ax.plot([0.70, 0.70], [y - 0.037, y + 0.037], color=GRAY, lw=0.6)
    ax.text(0.84, y, result, ha="center", va="center", fontsize=9.5, linespacing=1.5)
for y, label in [
    (0.61, "重新多点组批；并不沿用 Q1 批次"),
    (0.43, "另行固定离散候选；非机械继承所选 Q2 分组"),
    (0.25, "固定正式联合计划：架次、时刻与中继保障关系"),
]:
    ax.add_patch(
        FancyArrowPatch(
            (0.07, y + 0.027),
            (0.07, y - 0.027),
            arrowstyle="-|>",
            mutation_scale=12,
            color=INK,
            lw=0.8,
        )
    )
    ax.text(0.12, y, label, va="center", fontsize=9)
for start, end in [(0.94, 0.915), (0.801, 0.763)]:
    ax.add_patch(
        FancyArrowPatch(
            (0.5, start),
            (0.5, end),
            arrowstyle="-|>",
            mutation_scale=12,
            color=INK,
            lw=0.8,
        )
    )
ax.text(
    0.5,
    0.052,
    "敏感性与固定方案压力边界  ·  逐箱 / 资源 / 通信验证",
    ha="center",
    fontsize=10,
    weight="bold",
)
ax.text(
    0.5,
    0.015,
    "同一事实来源；精确求解、启发式与条件最优分别限定",
    ha="center",
    fontsize=9,
)
fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
save(fig, "fig01_framework")
