"""DEM determines cruise altitude; observed payload changes the energy budget."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from common import (
    WIDTH,
    BLUE,
    DATA,
    INK,
    GRAY,
    PALE_BLUE,
    DIRECT,
    load_analysis,
    panel,
    paper_style,
    save,
    grid,
)
from src.config import SERVICE_ALTITUDE_M, TERRAIN_CLEARANCE_M

paper_style()
a = load_analysis()
p = pd.read_csv(DATA / "terrain_profile.csv")
e = pd.read_csv(DATA / "energy_components.csv")
s = a["terrain_example"]
sid = s["service"]
chosen = e[e.service == sid]
fig, (ax, energy) = plt.subplots(
    2,
    1,
    figsize=(WIDTH, 4.6),
    gridspec_kw={"height_ratios": [1.8, 1]},
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
ax.add_collection(PolyCollection(polys, facecolor="#DDE4E0", edgecolor="none"))
d = s["distance"] / 1000
z0 = a["nodes"]["O01"]["elev"]
z1 = a["nodes"][sid]["elev"] + SERVICE_ALTITUDE_M
ax.plot(
    [0, 0, d, d],
    [z0, s["cruise_alt"], s["cruise_alt"], z1],
    color=BLUE,
    lw=1.65,
    label="计划飞行高度",
)
ax.axhline(s["max_dem"], color=GRAY, ls="--", lw=0.65)
ax.annotate(
    f"{TERRAIN_CLEARANCE_M:g} m 净空",
    xy=(d * 0.53, s["cruise_alt"]),
    xytext=(d * 0.70, s["cruise_alt"] + 75),
    ha="center",
    fontsize=8,
    arrowprops={"arrowstyle": "-", "color": INK, "lw": 0.65},
)
ax.text(0.08, z0 - 50, "O01", fontsize=8)
ax.text(d - 0.03, z1 - 55, sid, ha="right", fontsize=8)
ax.set(
    xlim=(-0.08, d + 0.08),
    ylim=(0, s["cruise_alt"] + 150),
    xlabel="沿航段水平距离 (km)",
    ylabel="海拔 (m)",
)
panel(ax, "a", f"O01–{sid}：沿途地形决定巡航高度")
ax.legend(loc="upper left", bbox_to_anchor=(0, 1.0), fontsize=7.5)
for i, r in enumerate(chosen.itertuples()):
    energy.barh(
        i, r.horizontal_kwh, height=0.52, color=PALE_BLUE, edgecolor=INK, lw=0.45
    )
    energy.barh(
        i,
        r.climb_kwh,
        left=r.horizontal_kwh,
        height=0.52,
        color=DIRECT,
        hatch="///",
        edgecolor=INK,
        lw=0.45,
    )
    energy.text(
        r.horizontal_kwh + r.climb_kwh + 0.035,
        i,
        f"{r.horizontal_kwh + r.climb_kwh:.2f} kWh",
        va="center",
        fontsize=8,
    )
energy.set_yticks(
    range(len(chosen)),
    [
        ("去程载货" if r.direction == "outbound" else "返程空载")
        + f" · {r.payload_kg:g} kg"
        for r in chosen.itertuples()
    ],
)
energy.invert_yaxis()
energy.set(
    xlabel="航段能耗 (kWh)",
    xlim=(0, (chosen.horizontal_kwh + chosen.climb_kwh).max() * 1.26),
)
grid(energy)
energy.legend(
    handles=[
        Patch(fc=PALE_BLUE, ec=INK, lw=0.4, label="水平航程"),
        Patch(fc=DIRECT, ec=INK, lw=0.4, hatch="///", label="爬升附加"),
    ],
    ncol=2,
    loc="lower right",
)
panel(energy, "b", "同一水平航段，载荷改变能量组成")
save(fig, "fig03_physics")
