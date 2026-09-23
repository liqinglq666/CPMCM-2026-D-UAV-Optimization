# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Unified framework with real method objects; deterministic, confidence intervals not applicable."""

from common import (
    DATA,
    RESULTS,
    BLUE,
    TEAL,
    GRAY,
    COLORS,
    HATCH,
    paper_style,
    load_analysis,
    save,
    panel,
)
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

paper_style()
a = load_analysis()
q3 = pd.read_csv(RESULTS / "q3/Q3_transport_trips.csv")
r = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
p = pd.read_csv(DATA / "terrain_profile.csv")
d = pd.read_csv(DATA / "payload_reserve.csv")
fig = plt.figure(figsize=(7, 4.7))
geo = fig.add_axes([0.09, 0.60, 0.24, 0.26])
cap = fig.add_axes([0.09, 0.20, 0.24, 0.26])
hero = fig.add_axes([0.47, 0.20, 0.51, 0.66])
pos = p[p.end_m > p.begin_m]
geo.plot((pos.begin_m + pos.end_m) / 2000, pos.elevation_m, color=GRAY, lw=0.8)
geo.axhline(a["terrain_example"]["cruise_alt"], color=BLUE, ls="--", lw=1)
geo.set_xlabel("航程 (km)", fontsize=9)
geo.set_ylabel("海拔 (m)", fontsize=9)
panel(geo, "a", "地形 → 航段")
for typ in ["A", "B", "C"]:
    g = d[(d.service == a["terrain_example"]["service"]) & (d.type == typ)]
    cap.plot(g.reserve * 100, g.payload_kg, color=COLORS[typ], label=typ)
cap.set_xlabel("储备 (%)", fontsize=9)
cap.set_ylabel("载荷 (kg)", fontsize=9)
panel(cap, "b", "能量 → 可行域")
cap.legend(ncol=3, fontsize=7, loc="lower left")
ids = sorted(q3["无人机编号"].unique()) + sorted(r["中继无人机编号"].unique())
for _, row in q3.iterrows():
    y = ids.index(row["无人机编号"])
    hero.barh(
        y,
        (row["返回O01时刻_s"] - row["开始时刻_s"]) / 3600,
        left=row["开始时刻_s"] / 3600,
        height=0.65,
        color=COLORS[row["机型编号"]],
        edgecolor="white",
        lw=0.5,
        hatch=HATCH[row["机型编号"]],
    )
for _, row in r.iterrows():
    y = ids.index(row["中继无人机编号"])
    hero.barh(
        y,
        (row["返回O01时刻_s"] - row["开始时刻_s"]) / 3600,
        left=row["开始时刻_s"] / 3600,
        height=0.65,
        color="#E7ECEE",
        edgecolor=TEAL,
        lw=0.7,
    )
    hero.barh(
        y,
        (row["服务结束时刻_s"] - row["建链完成时刻_s"]) / 3600,
        left=row["建链完成时刻_s"] / 3600,
        height=0.4,
        color=TEAL,
        hatch="//",
    )
hero.set_yticks(range(len(ids)), ids)
hero.invert_yaxis()
hero.set_xlabel("联合任务时刻 (h)")
hero.set_ylabel("运输与中继资源")
hero.set_xlim(left=0)
panel(hero, "c", "资源顺序 + 通信窗口 → 联合时序")
hero.axhline(len(ids) - 2.5, color=GRAY, lw=0.7, ls=":")
for y in [0.73, 0.33]:
    fig.add_artist(
        FancyArrowPatch(
            (0.35, y),
            (0.41, y),
            transform=fig.transFigure,
            arrowstyle="-|>",
            mutation_scale=10,
            color=GRAY,
            lw=1,
        )
    )
fig.text(
    0.46,
    0.935,
    "固定离散方案 → LP → 逐相位通信核验",
    fontsize=10,
    weight="bold",
    color=BLUE,
)
fig.text(0.08, 0.065, f"Q1  {a['metrics']['q1']['trips']} 架次精确组批", fontsize=10)
fig.text(0.39, 0.065, f"Q2  {a['metrics']['q2']['trips']} 架次折中调度", fontsize=10)
fig.text(0.70, 0.065, f"Q3  {len(q3)} 运输 + {len(r)} 中继", fontsize=10)
fig.text(
    0.08,
    0.01,
    f"N={len(a['boxes'])} 箱；共用能耗与 DEM；浅色为中继飞行，深色为通信服务；仅采样保证。",
    fontsize=8,
    color="#59656F",
)
save(fig, "fig01_framework")
