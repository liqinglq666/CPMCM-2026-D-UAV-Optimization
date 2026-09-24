"""Native DEM context and official task nodes; spokes are references, not schedules."""

import matplotlib.pyplot as plt
from common import GRAY, INK, load_analysis, paper_style, save, terrain_map

paper_style()
a = load_analysis()
fig, ax = plt.subplots(figsize=(6.5, 4.6), layout="constrained")
xy, terrain = terrain_map(ax, a)
for key, point in xy.items():
    if key != "O01":
        ax.plot(
            [xy["O01"][0], point[0]],
            [xy["O01"][1], point[1]],
            color=INK,
            alpha=0.20,
            lw=0.65,
            ls="--",
            zorder=2,
        )
bar = fig.colorbar(terrain, ax=ax, shrink=0.7, pad=0.025)
bar.set_label("DEM 海拔 (m)")
ax.set_title("任务空间：地形、调度中心与全部服务区", loc="left", pad=10)
ax.text(
    0.015,
    0.985,
    "虚线：O01 至服务区参考连线\n非正式多点调度路线",
    transform=ax.transAxes,
    va="top",
    fontsize=9,
    bbox={"facecolor": "white", "edgecolor": GRAY, "lw": 0.5, "pad": 4},
)
save(fig, "fig02_task_map")
