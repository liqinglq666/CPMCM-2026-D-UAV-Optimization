# AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""Forty-five official service/type cases, deterministic; confidence intervals not applicable."""

from common import COLORS, DATA, GRAY, MARKERS, load_analysis, panel, paper_style, save
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

paper_style()
a = load_analysis()
d = pd.read_csv(DATA / "payload_reserve.csv")
d = d[np.isclose(d.reserve, 0.2)]
fig, (ax, ratio) = plt.subplots(
    2,
    1,
    figsize=(7, 4.9),
    gridspec_kw={"height_ratios": [2.2, 1]},
    layout="constrained",
)
for typ, group in d.groupby("type"):
    g = group.sort_values("distance_m")
    ax.plot(
        g.distance_m / 1000,
        g.payload_kg,
        color=COLORS[typ],
        marker=MARKERS[typ],
        label=f"{typ} 型",
        ms=4,
    )
    ax.axhline(
        a["types"][typ]["max_payload"], color=COLORS[typ], ls=":", lw=0.7, alpha=0.5
    )
    ratio.plot(
        g.distance_m / 1000,
        100 * g.payload_kg / g.rated_payload_kg,
        color=COLORS[typ],
        marker=MARKERS[typ],
        ms=3,
        label=typ,
    )
    for r in g[g.payload_kg < g.rated_payload_kg - 1e-8].itertuples():
        if typ == "C" and r.service in ("S004", "S008"):
            ax.annotate(
                r.service,
                (r.distance_m / 1000, r.payload_kg),
                xytext=(0, -15),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )
ax.set_ylabel("最大安全载荷 $q^*$ (kg)")
ax.set_xlabel("单程水平距离 (km)")
ax.legend(ncol=3, loc="lower left")
ax.set_ylim(bottom=0)
panel(ax, "a", "远端任务开始受电池约束，而非仅受额定载荷约束")
ratio.axhline(100, color=GRAY, ls="--", lw=0.8)
ratio.set(xlabel="单程水平距离 (km)", ylabel="额定载荷占比 (%)", ylim=(0, 110))
panel(ratio, "b", "地形也影响边界：连线只连接实际服务区，不代表距离响应函数")
ax.text(
    0.02,
    0.95,
    f"N={len(d)}；储备 20%；点为真实服务区",
    transform=ax.transAxes,
    va="top",
    fontsize=9,
)
save(fig, "fig03_payload_boundary")
