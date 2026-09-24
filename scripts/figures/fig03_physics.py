# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Real DEM/energy mechanism; no statistical confidence interval is applicable."""

import matplotlib.pyplot as plt
import pandas as pd
from common import BLUE, DATA, GRAY, ORANGE, load_analysis, panel, paper_style, save
from matplotlib.collections import PolyCollection

from src.config import SERVICE_ALTITUDE_M, TERRAIN_CLEARANCE_M

paper_style()
a = load_analysis()
p = pd.read_csv(DATA / "terrain_profile.csv")
e = pd.read_csv(DATA / "energy_components.csv")
s = a["terrain_example"]
sid = s["service"]
chosen = e[e.service == sid]
fig, (ax, diag) = plt.subplots(
    2,
    1,
    figsize=(6.5, 4.7),
    gridspec_kw={"height_ratios": [2.2, 1]},
    layout="constrained",
)
polys = [
    [
        (r.begin_m / 1000, 0),
        (r.begin_m / 1000, r.elevation_m),
        (r.end_m / 1000, r.elevation_m),
        (r.end_m / 1000, 0),
    ]
    for r in p.itertuples()
    if r.end_m > r.begin_m
]
ax.add_collection(PolyCollection(polys, facecolor="#DDE2E5", edgecolor="none"))
d = s["distance"] / 1000
z0 = a["nodes"]["O01"]["elev"]
z1 = a["nodes"][sid]["elev"] + SERVICE_ALTITUDE_M
ax.plot([0, 0, d, d], [z0, s["cruise_alt"], s["cruise_alt"], z1], color=BLUE, lw=2)
ax.axhline(s["max_dem"], color=GRAY, ls=":", lw=1)
ax.annotate(
    f"{TERRAIN_CLEARANCE_M:g} m 净空",
    xy=(d * 0.54, s["cruise_alt"]),
    xytext=(d * 0.54, s["cruise_alt"] + 85),
    ha="center",
    arrowprops={"arrowstyle": "->", "color": BLUE},
)
ax.text(d * 0.04, z0 + 35, "O01")
ax.text(d * 0.84, z1 - 55, sid + f" +{SERVICE_ALTITUDE_M:g} m")
ax.set(
    xlim=(-0.08, d + 0.08),
    ylim=(0, s["cruise_alt"] + 140),
    xlabel="沿航段水平距离 (km)",
    ylabel="海拔 (m)",
)
panel(ax, "a", f"最高地形约束航高：O01 → {sid}")
for i, r in enumerate(chosen.itertuples()):
    diag.barh(i, r.horizontal_kwh, color=BLUE, label="水平航程" if i == 0 else None)
    diag.barh(
        i,
        r.climb_kwh,
        left=r.horizontal_kwh,
        color=ORANGE,
        edgecolor="#24333E",
        linewidth=0,
        hatch="//",
        label="爬升附加" if i == 0 else None,
    )
    diag.text(
        r.horizontal_kwh + r.climb_kwh + 0.03,
        i,
        f"{r.payload_kg:g} kg",
        va="center",
        fontsize=9,
    )
diag.set_yticks(
    range(len(chosen)),
    ["去程载货" if k == "outbound" else "返程空载" for k in chosen.direction],
)
diag.set_xlabel("航段能耗 (kWh)")
diag.set_ylabel("阶段")
diag.set_xlim(0, (chosen.horizontal_kwh + chosen.climb_kwh).max() * 1.22)
diag.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.5))
panel(diag, "b", "同一路径，载荷改变水平与爬升能耗")

save(fig, "fig03_physics")
