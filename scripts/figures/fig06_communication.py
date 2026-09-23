# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Communication samples are deterministic, not a continuous-time certificate or confidence interval."""

from common import (
    BLUE,
    DATA,
    ORANGE,
    RED,
    RESULTS,
    TEAL,
    load_analysis,
    panel,
    paper_style,
    save,
    terrain_map,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "communication_states.csv")
r = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
fig, (ax, t) = plt.subplots(
    2, 1, figsize=(7, 6), gridspec_kw={"height_ratios": [2.2, 1]}, layout="constrained"
)
xy = terrain_map(ax, a)
for _, group in d.groupby("trip"):
    ax.plot(group.longitude, group.latitude, color=BLUE, alpha=0.35, lw=0.6)
need = d[d.direct_margin_db < 0]
ax.scatter(
    need.longitude.iloc[::10],
    need.latitude.iloc[::10],
    s=4,
    color=ORANGE,
    label="直连不足的采样状态",
    zorder=3,
)
unique = r.drop_duplicates(["悬停经度", "悬停纬度"])
ax.scatter(
    unique["悬停经度"],
    unique["悬停纬度"],
    marker="^",
    s=65,
    facecolor="white",
    edgecolor=TEAL,
    lw=1.5,
    label="中继悬停点",
    zorder=5,
)
critical = d.loc[d.available_margin_db.idxmin()]
ax.scatter(
    [critical.longitude],
    [critical.latitude],
    marker="*",
    s=120,
    color=RED,
    zorder=6,
    label="最小采样余量",
)
ax.legend(loc="upper left", fontsize=8)
panel(ax, "a", "中继在受地形遮挡的轨迹片段恢复可用链路")
# Lower envelope in 60 s bins; exact global critical state retained and annotated.
window = (
    d.assign(window=np.floor(d.time_s / 60))
    .groupby("window")
    .agg(time=("time_s", "min"), margin=("available_margin_db", "min"))
)
t.plot(window.time / 3600, window.margin, color=BLUE, marker="o", ms=2.5, lw=1)
t.axhline(0, color=RED, ls="--", lw=0.8)
t.scatter(
    critical.time_s / 3600,
    critical.available_margin_db,
    color=RED,
    marker="*",
    s=70,
    zorder=5,
)
t.annotate(
    f"最小 {critical.available_margin_db:.3f} dB",
    xy=(critical.time_s / 3600, critical.available_margin_db),
    xytext=(0.85, 12),
    arrowprops={"arrowstyle": "->", "color": RED},
    fontsize=9,
)
t.set_xlabel("任务时刻 (h)")
t.set_ylabel("可用链路余量 (dB)")
t.set_ylim(bottom=-1)
panel(t, "b", f"N={len(d):,} 状态；60 s 窗口最小值；步长 ≤1 s")
save(fig, "fig06_communication")
