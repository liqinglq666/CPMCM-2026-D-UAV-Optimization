"""Finite candidate comparison; no global Pareto or uniqueness claim."""

import matplotlib.pyplot as plt
import pandas as pd
from common import INK, PALE_BLUE, RESULTS, YELLOW, grid, panel, paper_style, save

paper_style()
d = pd.read_csv(RESULTS / "q2/Q2_tradeoff_frontier.csv")
trips = pd.read_csv(RESULTS / "q2/Q2_transport_trips_balanced.csv")
selected = d[d.trips == len(trips)].iloc[0]
fig, (ax, b) = plt.subplots(
    2,
    1,
    figsize=(6.5, 4.8),
    gridspec_kw={"height_ratios": [2.4, 1]},
    layout="constrained",
)
ax.scatter(
    d.energy, d.weighted_tardiness / 1000, s=65, color=PALE_BLUE, edgecolor=INK, lw=0.7
)
ax.scatter(
    selected.energy,
    selected.weighted_tardiness / 1000,
    s=170,
    marker="*",
    facecolor=YELLOW,
    edgecolor=INK,
    lw=0.8,
    zorder=5,
)
for r in d.itertuples():
    ax.annotate(
        str(r.trips),
        (r.energy, r.weighted_tardiness / 1000),
        xytext=(6, 6 if r.trips != 21 else -14),
        textcoords="offset points",
        fontsize=10,
    )
ax.set(
    xlabel="运输能耗 (kWh)",
    ylabel="加权延误 ($10^3$ 系数·s)",
    ylim=(235, 1060),
    xlim=(77.5, 83.1),
)
grid(ax, "both")
panel(ax, "a", "继续压缩架次，会付出及时性代价")
ax.text(
    0.98,
    0.95,
    f"标注为架次数；共 {len(d)} 个候选\n星号：显式选定 {len(trips)} 架次",
    transform=ax.transAxes,
    ha="right",
    va="top",
    fontsize=9,
)
b.scatter(d.trips, d.makespan / 3600, s=45, facecolor=PALE_BLUE, edgecolor=INK, lw=0.7)
b.scatter(
    selected.trips,
    selected.makespan / 3600,
    s=120,
    marker="*",
    facecolor=YELLOW,
    edgecolor=INK,
    zorder=4,
)
b.set(
    xlabel="候选架次数",
    ylabel="运输完工 (h)",
    xticks=d.trips.tolist(),
    ylim=(2.8, 4.45),
)
b.invert_xaxis()
grid(b, "y")
panel(b, "b", "减少飞行批次，并不保证更早完工")
save(fig, "fig06_tradeoff")
