# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Actual constraint slacks and sampling refinement; confidence intervals not applicable."""

from common import (
    COLORS,
    DATA,
    MARKERS,
    ORANGE,
    RED,
    TEAL,
    load_analysis,
    panel,
    paper_style,
    save,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
c = pd.read_csv(DATA / "constraint_slacks.csv")
c = c[c.question == "q3"].sort_values("soc_pct")
h = pd.read_csv(DATA / "hard_deadline_slacks.csv").sort_values("slack_s")
fig = plt.figure(figsize=(7, 5.2), layout="constrained")
gs = fig.add_gridspec(2, 2, width_ratios=[2.1, 1], height_ratios=[1, 1])
ax = fig.add_subplot(gs[:, 0])
for kind in COLORS:
    selected = c.type == kind
    ax.scatter(
        c.soc_pct[selected],
        np.arange(len(c))[selected],
        color=COLORS[kind],
        marker=MARKERS[kind],
        s=30,
        label=f"{kind} 型",
    )
ax.legend(loc="center right", fontsize=8)
ax.axvline(20, color=RED, ls="--", lw=1)
ax.set_yticks(range(len(c)), [x.replace("Q3-", "") for x in c.trip], fontsize=8)
ax.set_xlabel("返航 SOC (%)")
ax.set_ylabel("运输架次")
ax.invert_yaxis()
panel(ax, "a", "全部满足储备，但最紧余量较小")
ax.text(
    0.38,
    0.97,
    f"N={len(c)}；最低 {c.soc_pct.min():.2f}%",
    transform=ax.transAxes,
    va="top",
    fontsize=9,
)
b = fig.add_subplot(gs[0, 1])
b.plot(np.arange(1, len(h) + 1), h.slack_s / 60, color=TEAL, marker="o", ms=2)
b.axhline(0, color=RED, ls="--", lw=0.8)
b.set_xlabel("硬时限货箱（排序）")
b.set_ylabel("时限余量 (min)")
panel(b, "b", f"N={len(h)} 硬时限货箱")
b.text(
    0.05,
    0.95,
    f"最小 {h.slack_s.min():.1f} s",
    transform=b.transAxes,
    va="top",
    fontsize=8,
)
s = fig.add_subplot(gs[1, 1])
v = a["sampling_validation"]
s.plot(
    [x["step_s"] for x in v],
    [x["minimum_margin_db"] for x in v],
    color=ORANGE,
    marker="s",
)
s.axhline(0, color=RED, ls="--", lw=0.8)
s.set(
    xlim=(0.42, 1.08),
    xlabel="最大采样步长 (s)",
    ylabel="最小通信余量 (dB)",
    xticks=[0.5, 1],
    ylim=(0, 0.16),
)
for x in v:
    s.annotate(
        f"N={x['checked_states']:,}",
        (x["step_s"], x["minimum_margin_db"]),
        xytext=(0, -17),
        textcoords="offset points",
        ha="center",
        fontsize=7.5,
    )
panel(s, "c", "加密后仍通过；余量下降")
save(fig, "fig08_validation")
