"""All refined states shown spatially; direct insufficiency is not an actual handover log."""

import matplotlib.pyplot as plt
import pandas as pd
from common import (
    DATA,
    INK,
    LIGHT_BLUE,
    ORANGE,
    RESULTS,
    YELLOW,
    load_analysis,
    panel,
    paper_style,
    save,
    terrain_map,
)

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "communication_states_05s.csv")
relays = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
fig = plt.figure(figsize=(6.5, 5.5), layout="constrained")
gs = fig.add_gridspec(2, 1, height_ratios=[4.6, 1])
ax = fig.add_subplot(gs[0])
schematic = fig.add_subplot(gs[1])
xy, _ = terrain_map(ax, a)
for _, g in d.groupby("trip", sort=False):
    ax.plot(g.longitude, g.latitude, color=INK, alpha=0.22, lw=0.55, zorder=2)
# Keep every spatial state (duplicate vertical/hover coordinates coincide).
need = d[d.direct_margin_db < 0].drop_duplicates(["longitude", "latitude"])
ax.scatter(
    need.longitude,
    need.latitude,
    s=4,
    color=ORANGE,
    zorder=3,
    label="直连不足；需指定中继",
)
r = relays.drop_duplicates(["悬停经度", "悬停纬度"])
ax.scatter(
    r["悬停经度"],
    r["悬停纬度"],
    s=65,
    marker="^",
    facecolor=LIGHT_BLUE,
    edgecolor=INK,
    lw=0.7,
    zorder=7,
    label="中继悬停点",
)
critical = d.loc[d.available_margin_db.idxmin()]
ax.scatter(
    critical.longitude,
    critical.latitude,
    s=135,
    marker="*",
    facecolor=YELLOW,
    edgecolor=INK,
    lw=0.7,
    zorder=8,
    label="最紧采样状态（直连）",
)
ax.legend(loc="upper left", fontsize=9, handletextpad=0.4)
panel(ax, "a", "直连不足位于实际航段内部")
schematic.axis("off")
schematic.text(0.015, 0.86, "固定离散方案", weight="bold", fontsize=10)
schematic.text(
    0.015,
    0.42,
    "货箱 / 路线 / 机型与资源顺序\n中继位置、高度与保障关系",
    fontsize=9,
    va="center",
    linespacing=1.5,
)
schematic.annotate(
    "",
    xy=(0.54, 0.44),
    xytext=(0.44, 0.44),
    arrowprops={"arrowstyle": "->", "color": INK, "lw": 1},
)
schematic.text(0.58, 0.86, "LP 优化时序", weight="bold", fontsize=10)
schematic.text(
    0.58,
    0.42,
    "运输开始 / 中继服务窗口\n延误与联合完工",
    fontsize=9,
    va="center",
    linespacing=1.5,
)
save(fig, "fig08_communication_map")
