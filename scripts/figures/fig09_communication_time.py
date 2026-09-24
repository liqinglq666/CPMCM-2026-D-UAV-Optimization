"""Faithful minima and a non-interpolated comparison of the two audit grids."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    WIDTH,
    DATA,
    INK,
    LIGHT_BLUE,
    RED,
    DIRECT,
    RESULTS,
    grid,
    load_analysis,
    panel,
    paper_style,
    save,
    threshold,
    key_note,
)

paper_style()
a = load_analysis()
fine = pd.read_csv(DATA / "communication_states_05s.csv")
coarse = pd.read_csv(DATA / "communication_states.csv")
r = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
fig, (ax, local, window) = plt.subplots(
    3,
    1,
    figsize=(WIDTH, 5.7),
    gridspec_kw={"height_ratios": [1.55, 1.1, 1.0]},
    layout="constrained",
)
critical = fine.loc[fine.available_margin_db.idxmin()]
critical_color = RED if critical.available_margin_db < 0 else LIGHT_BLUE
rows = fine.loc[fine.groupby(np.floor(fine.time_s / 20)).available_margin_db.idxmin()]
ax.scatter(rows.time_s / 60, rows.available_margin_db, s=12, fc=DIRECT, ec=INK, lw=0.2)
ax.scatter(
    critical.time_s / 60,
    critical.available_margin_db,
    s=75,
    marker="*",
    fc=critical_color,
    ec=INK,
    lw=0.5,
    zorder=5,
)
threshold(ax, 0)
ax.set(
    ylabel="窗口最小余量 (dB)",
    xlabel="任务时间 (min)",
    ylim=(-2, rows.available_margin_db.max() * 1.2),
)
key_note(
    ax,
    (critical.time_s / 60, critical.available_margin_db),
    "最小链路余量",
    f"{critical.available_margin_db:.3f} dB",
    xytext=(0.34, 0.95),
)
grid(ax, "y")
panel(
    ax,
    "a",
    "加密回放通过，最紧链路余量仍较小"
    if critical.available_margin_db >= 0
    else "加密回放发现未覆盖状态",
)
vals = []
for data, marker, color, label in [
    (coarse, "o", DIRECT, "1.0 s 采样"),
    (fine, "s", LIGHT_BLUE, "0.5 s 采样"),
]:
    g = data[(data.trip == critical.trip) & (abs(data.time_s - critical.time_s) <= 3)]
    local.scatter(
        g.time_s - critical.time_s,
        g.available_margin_db,
        s=27,
        marker=marker,
        fc="white" if marker == "o" else color,
        ec=INK,
        lw=0.6,
        label=label,
        zorder=3,
    )
    vals.extend(g.available_margin_db)
local.scatter(
    0,
    critical.available_margin_db,
    s=75,
    marker="*",
    fc=critical_color,
    ec=INK,
    lw=0.5,
    zorder=5,
)
threshold(local, 0)
span = max(max(vals) - min(vals), abs(critical.available_margin_db), 0.02)
local.set(
    xlabel="相对最紧时刻 (s)",
    ylabel="链路余量 (dB)",
    ylim=(min(0.0, min(vals)) - span * 0.25, max(0.0, max(vals)) + span * 0.5),
)
fig.legend(*local.get_legend_handles_labels(), loc="outside upper center", ncol=2)
grid(local, "y")
panel(local, "b", f"{critical.trip}：两种网格独立复核最紧区间")
for i, (_, row) in enumerate(r.iterrows()):
    begin, end = row["建链完成时刻_s"] / 60, row["服务结束时刻_s"] / 60
    window.barh(
        i,
        end - begin,
        left=begin,
        height=0.6,
        fc=LIGHT_BLUE,
        ec=INK,
        lw=0.5,
        hatch="//" if i % 2 else "",
    )
    window.text(
        (begin + end) / 2,
        i,
        row["中继无人机编号"],
        ha="center",
        va="center",
        fontsize=7.5,
        bbox={"fc": "white", "ec": "none", "alpha": 0.85, "pad": 0.1},
    )
window.set_yticks(range(len(r)), r["中继架次编号"])
window.invert_yaxis()
window.set(
    xlabel="任务时间 (min)",
    ylabel="中继服务窗",
    xlim=(0, max(fine.time_s.max(), r["服务结束时刻_s"].max()) / 60 * 1.02),
)
ax.set_xlim(window.get_xlim())
grid(window)
panel(window, "c", "正式中继服务窗口与运输时序对应")
save(fig, "fig09_communication_time")
