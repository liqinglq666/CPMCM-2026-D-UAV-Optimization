"""Native DEM, display-only illumination and data-selected representative nodes."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from common import (
    WIDTH,
    GRAY,
    INK,
    RESULTS,
    BACKGROUND,
    load_analysis,
    paper_style,
    save,
    terrain_map,
    scale_bar,
)

paper_style()
a = load_analysis()
legs = pd.read_csv(RESULTS / "q1/Q1_leg_physics.csv")
payload = pd.read_csv(RESULTS / "q1/Q1_max_safe_payload.csv").set_index("服务区编号")
far = legs.loc[legs.distance.idxmax(), "service"]
high = max((k for k in a["nodes"] if k != "O01"), key=lambda k: a["nodes"][k]["elev"])
ratios = pd.DataFrame(
    {
        k: payload[f"{k}型最大安全载荷（kg）"] / a["types"][k]["max_payload"]
        for k in a["types"]
    }
)
limited = ratios.min(axis=1).idxmin()
fig, ax = plt.subplots(figsize=(WIDTH, 4.72), layout="constrained")
xy, terrain = terrain_map(ax, a)
for key, p in xy.items():
    if key != "O01":
        ax.plot(
            [xy["O01"][0], p[0]],
            [xy["O01"][1], p[1]],
            color=INK,
            alpha=0.10,
            lw=0.45,
            ls="--",
            zorder=2,
        )
roles = {}
for sid, role in [(far, "最远"), (high, "最高"), (limited, "能量限制最强")]:
    roles.setdefault(sid, []).append(role)
# Fixed offsets are annotation layout, never data edits.
for sid, labels in roles.items():
    px, py = xy[sid]
    dx = -12 if px > sum(ax.get_xlim()) / 2 else 9
    dy = 13 if py < sum(ax.get_ylim()) / 2 else -18
    ax.annotate(
        sid + " · " + " / ".join(labels),
        xy[sid],
        xytext=(dx, dy),
        textcoords="offset points",
        ha="right" if dx < 0 else "left",
        va="center",
        fontsize=8,
        arrowprops={"arrowstyle": "-", "lw": 0.55, "color": INK},
        bbox={"facecolor": BACKGROUND, "edgecolor": "none", "pad": 1.5, "alpha": 0.92},
        zorder=8,
    )
ax.annotate(
    "O01",
    xy["O01"],
    xytext=(6, -12),
    textcoords="offset points",
    fontsize=8,
    weight="bold",
    zorder=9,
)
scale_bar(ax, 2)
ax.annotate(
    "N",
    xy=(0.94, 0.93),
    xytext=(0.94, 0.82),
    xycoords="axes fraction",
    ha="center",
    fontsize=8,
    arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 0.8},
)
bar = fig.colorbar(terrain, ax=ax, fraction=0.038, pad=0.025, shrink=0.82)
bar.set_label("DEM 海拔 (m)")
bar.outline.set_visible(False)
ax.legend(
    handles=[
        Line2D([], [], marker="*", color=INK, ls="", ms=7, label="调度中心"),
        Line2D(
            [],
            [],
            marker="o",
            mfc=BACKGROUND,
            mec=INK,
            color=INK,
            ls="",
            ms=4,
            label="15 个服务区",
        ),
        Line2D([], [], ls="--", color=GRAY, lw=0.6, label="几何参考连线"),
    ],
    loc="lower center",
    bbox_to_anchor=(0.5, 1.015),
    ncol=3,
)
save(fig, "fig02_task_map")
