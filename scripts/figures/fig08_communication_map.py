"""Communication counterfactual and formal relays, including refined failures."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    DATA,
    INK,
    LIGHT_BLUE,
    RED,
    DIRECT,
    RESULTS,
    BACKGROUND,
    load_analysis,
    panel,
    paper_style,
    save,
    terrain_map,
    scale_bar,
)

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "communication_states_05s.csv")
r = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
fig, axes = plt.subplots(
    1, 2, figsize=(WIDTH, 3.55), layout="constrained", sharex=True, sharey=True
)
for ax in axes:
    terrain_map(ax, a, weak=True)
    scale_bar(ax, 1)


def paths_by_state(g):
    points = g[["longitude", "latitude"]].to_numpy()
    need = (g.direct_margin_db.to_numpy()[:-1] < 0) | (
        g.direct_margin_db.to_numpy()[1:] < 0
    )
    bounds = np.r_[0, np.flatnonzero(need[1:] != need[:-1]) + 1, len(need)]
    for lo, hi in zip(bounds, bounds[1:]):
        path = points[lo : hi + 1]
        # Lossless display simplification of repeated/collinear native positions.
        path = path[np.r_[True, np.any(np.diff(path, axis=0) != 0, axis=1)]]
        if len(path) < 2:
            continue
        if len(path) > 2:
            u = np.diff(path, axis=0)
            turn = np.abs(u[:-1, 0] * u[1:, 1] - u[:-1, 1] * u[1:, 0])
            forward = (u[:-1] * u[1:]).sum(axis=1) > 0
            path = path[np.r_[True, (turn > 1e-16) | ~forward, True]]
        yield bool(need[lo]), path


for _, g in d.groupby("trip", sort=False):
    for need, path in paths_by_state(g):
        for i, ax in enumerate(axes):
            ax.add_collection(
                LineCollection(
                    [path],
                    colors=(RED if i == 0 else LIGHT_BLUE) if need else DIRECT,
                    linewidths=1.4 if need else 0.45,
                    linestyles=("dashed" if i == 0 else "dashdot") if need else "solid",
                    alpha=0.9 if need else 0.28,
                    zorder=3 if need else 2,
                )
            )
    stationary = (
        (g.longitude == g.longitude.shift())
        & (g.latitude == g.latitude.shift())
        & (g.direct_margin_db < 0)
    )
    need = g[stationary].drop_duplicates(["longitude", "latitude"])
    for i, ax in enumerate(axes):
        ax.scatter(
            need.longitude,
            need.latitude,
            s=7,
            color=RED if i == 0 else LIGHT_BLUE,
            zorder=3,
        )
for _, row in r.drop_duplicates(["悬停经度", "悬停纬度"]).iterrows():
    axes[1].scatter(
        row["悬停经度"],
        row["悬停纬度"],
        s=42,
        marker="^",
        fc=LIGHT_BLUE,
        ec=INK,
        lw=0.65,
        zorder=6,
    )
critical = d.loc[d.available_margin_db.idxmin()]
violations = int((d.available_margin_db < 0).sum())
axes[1].scatter(
    critical.longitude,
    critical.latitude,
    s=95,
    marker="*",
    fc=RED,
    ec=INK,
    lw=0.6,
    zorder=8,
)
axes[1].annotate(
    f"{critical.trip}\n{critical.available_margin_db:.3f} dB",
    (critical.longitude, critical.latitude),
    xytext=(12, -28),
    textcoords="offset points",
    fontsize=7.5,
    arrowprops={"arrowstyle": "-", "lw": 0.6, "color": INK},
    bbox={"fc": BACKGROUND, "ec": "none", "pad": 1.0, "alpha": 0.95},
    zorder=9,
)
for ax in axes:
    node = a["nodes"]["O01"]
    ax.annotate(
        "O01",
        (node["lon"], node["lat"]),
        xytext=(4, -11),
        textcoords="offset points",
        fontsize=7.5,
        zorder=9,
    )
axes[1].set_ylabel("")
axes[1].tick_params(labelleft=False)
panel(axes[0], "a", "无中继：直连不足轨迹")
panel(axes[1], "b", f"正式中继：加密发现 {violations} 处不足")
fig.legend(
    handles=[
        Line2D([], [], color=DIRECT, lw=0.8, label="直连可用轨迹"),
        Line2D([], [], color=RED, lw=1.5, ls="--", label="直连不足"),
        Line2D([], [], color=LIGHT_BLUE, lw=1.5, ls="-.", label="指定中继保障段"),
        Line2D([], [], ls="", marker="^", mfc=LIGHT_BLUE, mec=INK, label="中继悬停点"),
        Line2D([], [], ls="", marker="*", mfc=RED, mec=INK, ms=9, label="最紧加密状态"),
    ],
    loc="outside lower center",
    ncol=3,
)
save(fig, "fig08_communication_map")
