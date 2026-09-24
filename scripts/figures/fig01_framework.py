"""Academic method diagram: shared rules are not inherited transport batches."""

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from common import WIDTH, GRAY, INK, BLUE, BACKGROUND, load_analysis, paper_style, save

paper_style()
a = load_analysis()
m = a["metrics"]
fig, ax = plt.subplots(figsize=(WIDTH, 7.05))
fig.subplots_adjust(left=0.012, right=0.988, top=0.992, bottom=0.008)
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis("off")


def box(x, y, w, h, text, fs=8.5, bold=False):
    ax.add_patch(
        Rectangle((x, y), w, h, facecolor=BACKGROUND, edgecolor=GRAY, lw=0.6, zorder=2)
    )
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        weight="bold" if bold else "normal",
        zorder=3,
        linespacing=1.4,
    )


def arrow(p, q):
    ax.add_patch(
        FancyArrowPatch(
            p, q, arrowstyle="-|>", mutation_scale=8, color=INK, lw=0.65, zorder=1
        )
    )


box(
    0.025,
    0.91,
    0.95,
    0.071,
    "输入数据与统一约束\n节点与货箱 / 30 m DEM / 机型与库存 / 交付时限 / 通信参数",
    8.5,
    True,
)
arrow((0.5, 0.91), (0.5, 0.882))
box(
    0.025,
    0.811,
    0.95,
    0.071,
    "统一物理计算共享底座\nDEM 航高 → 动态载荷 → 分阶段能量 → 返航储备、充电与链路",
    8.5,
    True,
)
# A dashed enclosure denotes scope, not another dependency edge.
ax.add_patch(
    Rectangle(
        (0.014, 0.234), 0.972, 0.55, fill=False, edgecolor=GRAY, lw=0.85, ls=(0, (4, 3))
    )
)
ax.text(
    0.035,
    0.77,
    "共享输入、物理规则与校验口径",
    fontsize=8,
    color=INK,
    va="center",
    bbox={"facecolor": BACKGROUND, "edgecolor": "none", "pad": 2},
)
arrow((0.25, 0.811), (0.25, 0.736))
arrow((0.75, 0.811), (0.75, 0.736))
# Shared base feeds the lower modules via the outside margins.
for x, mid in [(0.006, 0.25), (0.994, 0.75)]:
    ax.plot([0.5, x, x, mid], [0.795, 0.795, 0.496, 0.496], color=GRAY, lw=0.65)
    arrow((mid, 0.496), (mid, 0.477))
modules = [
    (
        0.045,
        0.514,
        "Q1  单点能力与精确组批",
        [
            "逐机型安全载荷边界",
            "不可拆货箱可行子集",
            "词典序集合划分 DP",
            f"{m['q1']['trips']} 批：单点组批精确解",
        ],
        None,
    ),
    (
        0.545,
        0.514,
        "Q2  多点运输与资源调度",
        [
            "重新构造多点运输任务",
            "迁移 / 交换 / 合并 / 拆分",
            "路线与资源邻域搜索",
            f"选定 {m['q2']['trips']} 架次并检验占用",
        ],
        "不沿用 Q1 单点批次",
    ),
    (
        0.045,
        0.257,
        "Q3  运输—中继联合优化",
        [
            "分组 / 路线 / 中继 / 资源外层搜索",
            "固定候选：HiGHS 词典序时序 LP",
            "1 s 通信终检与独立可行性验证",
            f"{m['q3']['transport_trips']} 运输 / {m['q3']['relay_sorties']} 中继联合方案",
        ],
        "固定离散候选后优化时序",
    ),
    (
        0.545,
        0.257,
        "Q4  固定计划的独立配置",
        [
            "固定正式联合方案",
            "提取不可拆分任务分量",
            "分区枚举与区间峰值核算",
            "独立资源需求与分类缺口",
        ],
        "固定正式联合方案后配置资源",
    ),
]
for x, y, title, steps, note in modules:
    ax.text(
        x + 0.205, y + 0.222, title, ha="center", va="center", fontsize=9, weight="bold"
    )
    ax.plot([x, x + 0.41], [y + 0.209, y + 0.209], color=BLUE, lw=1)
    for i, text in enumerate(steps):
        sy = y + 0.156 - i * 0.039
        box(x, sy, 0.41, 0.03, text, 8)
        if i < 3:
            arrow((x + 0.205, sy), (x + 0.205, sy - 0.009))
    if note:
        ax.text(x + 0.205, y + 0.008, note, ha="center", va="center", fontsize=7.5)
# Only this cross-question arrow denotes transfer of a formal plan.
arrow((0.456, 0.346), (0.544, 0.346))
ax.text(0.5, 0.375, "计划", ha="center", fontsize=7.5)
ax.text(0.5, 0.31, "继承", ha="center", fontsize=7.5)
for mid in (0.25, 0.75):
    arrow((mid, 0.232), (mid, 0.201))
box(
    0.025,
    0.091,
    0.95,
    0.11,
    "统一检验与边界分析\n逐箱交付 / 飞机与电池占用 / SOC / 硬截止 / 通信回放\n储备敏感性与固定计划压力界限",
    8.5,
    True,
)
ax.text(
    0.5,
    0.049,
    "精确组批 / 启发式离散搜索 / 条件时序最优 / 固定计划枚举",
    ha="center",
    fontsize=8,
)
save(fig, "fig01_framework")
