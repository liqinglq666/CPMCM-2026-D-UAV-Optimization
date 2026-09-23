# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Deterministic reserve scenarios and fixed-plan thresholds; no statistical confidence intervals."""

from common import (
    BLUE,
    COLORS,
    DATA,
    MARKERS,
    ORANGE,
    RESULTS,
    load_analysis,
    panel,
    paper_style,
    save,
)
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "payload_reserve.csv")
s = pd.read_csv(RESULTS / "q1/Q1_sensitivity_summary.csv")
fig, (ax, step) = plt.subplots(
    2, 1, figsize=(7, 5), gridspec_kw={"height_ratios": [2.1, 1]}, layout="constrained"
)
for typ, group in d.groupby("type"):
    pivot = (
        group.pivot(index="reserve", columns="service", values="payload_kg").fillna(0)
        / a["types"][typ]["max_payload"]
        * 100
    )
    ax.fill_between(
        pivot.index * 100,
        pivot.min(axis=1),
        pivot.max(axis=1),
        color=COLORS[typ],
        alpha=0.1,
    )
    ax.plot(
        pivot.index * 100,
        pivot.min(axis=1),
        color=COLORS[typ],
        marker=MARKERS[typ],
        markevery=10,
        label=f"{typ} 型最受限服务区",
    )
ax.set_xlabel("返航安全余量 (%)")
ax.set_ylabel("额定载荷保留比例 (%)")
ax.set_ylim(0, 105)
ax.legend(loc="lower left", fontsize=8)
panel(ax, "a", "提高储备先压缩局部运载边界，再触发架次跳变")
ax.text(
    0.02,
    0.53,
    f"N={d.reserve.nunique()} 储备 × 15 服务区 × 3 机型；阴影为跨服务区范围\n不可达记为0：表示不能交付，不表示空载可达",
    transform=ax.transAxes,
    fontsize=8,
    va="top",
)
step.plot(
    s["返航安全余量"] * 100,
    s["最少往返架次数"],
    color=BLUE,
    marker="o",
    label="每个场景重新精确组批",
)
crit = a["fixed_plan_thresholds"]["q1"]["maximum_common_reserve"] * 100
step.axvline(crit, color=ORANGE, ls="--", label=f"基准固定方案阈值 {crit:.2f}%")
step.set(
    xlabel="返航安全余量 (%)",
    ylabel="最低架次数",
    yticks=sorted(s["最少往返架次数"].unique()),
)
step.legend(loc="upper left", fontsize=8)
panel(step, "b", f"N={len(s)} 个重新优化场景；连线不表示中间点已优化")
save(fig, "fig07_sensitivity")
