"""Four-question argument and inheritance; result anchors come from validated files.
AI assistance: ChatGPT/Codex, OpenAI, 2026-09-24; exact model unavailable.
"""

from common import BLUE, TEAL, ORANGE, GRAY, RESULTS, load_analysis, paper_style, save
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

paper_style()
a = load_analysis()
m = a["metrics"]
resources = pd.read_csv(RESULTS / "q4/Q4_resource_summary.csv")
gaps = resources.groupby("K")["缺口"].sum()
fig, ax = plt.subplots(figsize=(7.2, 5.2))
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis("off")
ax.text(
    0.02,
    0.975,
    "统一底座：DEM 航高 → 剩余载荷 → 分阶段能量 → 返航与充电",
    fontsize=11,
    weight="bold",
    va="top",
    color=BLUE,
)
rows = [
    (
        0.77,
        BLUE,
        "Q1  能力边界",
        "额定载荷为何不够？\n单点往返边界 → 不可拆货箱划分",
        f"{m['q1']['trips']} 架次\n单点组批精确",
    ),
    (
        0.55,
        TEAL,
        "Q2  运输执行",
        "能运走，能否按时？\n实体无人机 + 电池周转 + 交付时限",
        f"{m['q2']['trips']} 架次选点\n有限启发式候选",
    ),
    (
        0.33,
        ORANGE,
        "Q3  通信时序",
        "运输可行，链路是否可用？\n沿程遮挡 → 指定中继 → 联合窗口",
        f"{m['q3']['transport_trips']} 运输 + {m['q3']['relay_sorties']} 中继\n固定方案时序 LP",
    ),
    (
        0.11,
        BLUE,
        "Q4  独立配置",
        "禁止跨组共享，还缺多少资源？\n固定 Q3 任务 → 连通分量 → 分区",
        f"两组缺 {gaps.loc[2]} / 三组缺 {gaps.loc[3]}\n固定计划精确枚举",
    ),
]
for y, color, title, argument, result in rows:
    ax.add_patch(
        FancyBboxPatch(
            (0.015, y - 0.065),
            0.97,
            0.155,
            boxstyle="round,pad=0.009",
            facecolor="#F5F7F8",
            edgecolor=color,
            linewidth=1,
        )
    )
    ax.text(
        0.035, y + 0.025, title, color=color, fontsize=11, weight="bold", va="center"
    )
    ax.text(0.30, y + 0.005, argument, fontsize=9.5, va="center", linespacing=1.6)
    ax.plot([0.735, 0.735], [y - 0.044, y + 0.062], color=GRAY, lw=0.6)
    ax.text(
        0.855,
        y + 0.006,
        result,
        fontsize=9.5,
        va="center",
        ha="center",
        linespacing=1.6,
    )
for y, label in [
    (0.675, "继承物理规则；重新组批与排程"),
    (0.455, "继承资源—时间模型；另行固定离散候选"),
    (0.235, "直接固定运输架次、时序与中继保障关系"),
]:
    ax.add_patch(
        FancyArrowPatch(
            (0.12, y + 0.021),
            (0.12, y - 0.021),
            arrowstyle="-|>",
            mutation_scale=11,
            color=GRAY,
            linewidth=1,
        )
    )
    ax.text(0.30, y, label, fontsize=8.5, va="center", color="#59656F")
fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.03)
save(fig, "fig01_framework")
