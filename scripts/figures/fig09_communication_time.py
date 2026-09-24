"""Actual argmin times, refined critical-state inset and relay windows; no smoothed claims."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    BLUE,
    DATA,
    INK,
    LIGHT_BLUE,
    RED,
    RESULTS,
    YELLOW,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
)

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "communication_states_05s.csv")
r = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
fig, (ax, inset, window) = plt.subplots(
    3,
    1,
    figsize=(6.5, 6.3),
    gridspec_kw={"height_ratios": [2.1, 1, 1.1]},
    layout="constrained",
)
# Each plotted minimum retains the exact time of that row. Separate categories;
# neither joining disconnected tasks nor interpolating mode/occlusion transitions.
display_maxima = []
for mask, color, mark, label in [
    (d.direct_margin_db >= 0, BLUE, "o", "直连可用"),
    (d.direct_margin_db < 0, LIGHT_BLUE, "^", "需指定中继"),
]:
    group = d[mask].assign(bin=np.floor(d[mask].time_s / 30))
    rows = d.loc[group.groupby("bin").available_margin_db.idxmin()]
    display_maxima.append(rows.available_margin_db.max())
    ax.scatter(
        rows.time_s / 3600,
        rows.available_margin_db,
        s=18,
        facecolor=color,
        edgecolor=INK,
        lw=0.25,
        marker=mark,
        label=label,
    )
critical = d.loc[d.available_margin_db.idxmin()]
ax.axhline(0, color=RED, ls="--", lw=0.8)
ax.scatter(
    critical.time_s / 3600,
    critical.available_margin_db,
    s=110,
    marker="*",
    facecolor=YELLOW,
    edgecolor=INK,
    zorder=5,
)
ax.set(
    xlabel="任务时刻 (h)",
    ylabel="可用链路余量 (dB)",
    ylim=(-1, np.ceil(max(display_maxima) / 5) * 5),
)
grid(ax, "y")
ax.legend(loc="upper right", fontsize=9)
panel(ax, "a", "0.5 s 回放：局部最小余量仍接近阈值")
# Inset displays individual consecutive records around the exact critical time.

local = d[(d.trip == critical.trip) & (abs(d.time_s - critical.time_s) <= 3)]
inset.scatter(
    local.time_s - critical.time_s,
    local.available_margin_db,
    s=14,
    color=BLUE,
    edgecolor=INK,
    lw=0.3,
)
inset.scatter(
    0,
    critical.available_margin_db,
    s=70,
    marker="*",
    facecolor=YELLOW,
    edgecolor=INK,
    zorder=4,
)
inset.axhline(0, color=RED, ls="--", lw=0.7)
inset.set_ylim(-0.025, max(0.3, local.available_margin_db.max() * 1.1))
inset.set_xlabel("相对最紧时刻 (s)", fontsize=8.5, labelpad=1)
inset.tick_params(labelsize=8.5)
panel(
    inset,
    "b",
    f"{critical.trip} 局部回放：最小 {critical.available_margin_db:.3f} dB（直连）",
)
inset.set_ylabel("链路余量 (dB)")
grid(inset, "y")
for i, (_, row) in enumerate(r.iterrows()):
    begin, end = row["建链完成时刻_s"] / 3600, row["服务结束时刻_s"] / 3600
    window.barh(
        i,
        end - begin,
        left=begin,
        height=0.6,
        facecolor=LIGHT_BLUE,
        edgecolor=INK,
        lw=0.6,
        hatch="//" if row["中继无人机编号"] == "R02" else "",
    )
window.set_yticks(range(len(r)), r["中继架次编号"])
window.invert_yaxis()
window.set(
    xlabel="任务时刻 (h)",
    ylabel="中继服务窗",
    xlim=(0, max(d.time_s.max(), r["服务结束时刻_s"].max()) / 3600 * 1.02),
)
ax.set_xlim(window.get_xlim())
grid(window)
panel(window, "c", "服务窗口将空间覆盖落实到任务时间轴")
save(fig, "fig09_communication_time")
