"""Shared, semantically fixed scientific figure style; original data-driven artwork."""

import json
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from paper_data import load_analysis as load_verified_analysis

DATA, RESULTS, OUT = ROOT / "paper/data", ROOT / "results", ROOT / "outputs/figures"
BLUE, GREEN, ORANGE = "#299EDF", "#91D477", "#F66532"
LIGHT_BLUE, PALE_BLUE, YELLOW = "#78C3FE", "#ABE5FB", "#FADA00"
RED, GRAY, INK, BACKGROUND = "#E72451", "#BFC4C8", "#222222", "#FDFFFF"
COLORS = {"A": BLUE, "B": GREEN, "C": ORANGE}
MARKERS = {"A": "o", "B": "s", "C": "^"}
LINESTYLES = {"A": "-", "B": "--", "C": "-."}
HATCH = {"A": "", "B": "//", "C": ".."}


def paper_style():
    bundled = ROOT / "paper/fonts/NotoSansSC-Regular.ttf"
    if bundled.is_file():
        font_manager.fontManager.addfont(bundled)
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(
        (n for n in ["Noto Sans SC", "SimHei", "Microsoft YaHei"] if n in available),
        None,
    )
    if font is None:
        raise RuntimeError("Run python scripts/setup_paper_fonts.py before plotting")
    plt.rcParams.update(
        {
            "font.family": [font, "DejaVu Sans"],
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "axes.edgecolor": GRAY,
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "lines.linewidth": 1.4,
            "legend.frameon": False,
            "axes.unicode_minus": False,
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": BACKGROUND,
            "savefig.facecolor": BACKGROUND,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "svg.fonttype": "path",
            "svg.hashsalt": "uav-paper-2026",
            "mathtext.fontset": "stix",
            "axes.grid": False,
        }
    )


def load_analysis():
    return load_verified_analysis(ROOT)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUT) as staging:
        for ext in ("pdf", "svg", "png"):
            fig.savefig(
                Path(staging) / f"{name}.{ext}",
                dpi=300,
                bbox_inches="tight",
                pad_inches=0.07,
            )
        for target in Path(staging).iterdir():
            target.replace(OUT / target.name)
    plt.close(fig)
    print(f"[fig] {name}: PDF / SVG / 300 dpi PNG", flush=True)


def panel(ax, label, title):
    ax.set_title(f"({label})  {title}", loc="left", pad=10)


def grid(ax, axis="x"):
    ax.grid(axis=axis, color=GRAY, alpha=0.25, linewidth=0.5)
    ax.set_axisbelow(True)


def nodes_xy(analysis):
    return {k: (v["lon"], v["lat"]) for k, v in analysis["nodes"].items()}


def terrain_map(ax, analysis, labels=True):
    dem = json.loads((DATA / "terrain_map.json").read_text())
    levels = np.linspace(
        np.floor(np.min(dem["elevation_m"]) / 100) * 100,
        np.ceil(np.max(dem["elevation_m"]) / 100) * 100,
        7,
    )
    # Discrete subdued elevation bands, never a continuous gradient or rainbow.
    terrain = ax.contourf(
        dem["longitude"],
        dem["latitude"],
        dem["elevation_m"],
        levels=levels,
        colors=["#F8FBFC", "#EDF3F4", "#E3ECEB", "#D8E4E0", "#CBDAD3", "#BBCDC3"],
        zorder=0,
    )
    ax.contour(
        dem["longitude"],
        dem["latitude"],
        dem["elevation_m"],
        levels=levels,
        colors=GRAY,
        linewidths=0.35,
        zorder=1,
    )
    xy = nodes_xy(analysis)
    # Label offsets are layout choices; coordinates are always read from inputs.
    offsets = {
        "O01": (-7, -15),
        "S001": (5, -12),
        "S003": (5, -10),
        "S007": (5, -11),
        "S011": (-7, 6),
        "S014": (5, -12),
    }
    for key, (lon, lat) in xy.items():
        ax.scatter(
            lon,
            lat,
            marker="s" if key == "O01" else "o",
            s=45 if key == "O01" else 25,
            facecolor=INK if key == "O01" else BLUE,
            edgecolor=INK,
            linewidth=0.5,
            zorder=5,
        )
        if labels:
            dx, dy = offsets.get(key, (5, 5))
            ax.annotate(
                key,
                (lon, lat),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=9,
                ha="right" if dx < 0 else "left",
                zorder=6,
                bbox={
                    "facecolor": BACKGROUND,
                    "edgecolor": "none",
                    "pad": 0.4,
                    "alpha": 0.85,
                },
            )
    ax.set_xlabel("经度 (°E)")
    ax.set_ylabel("纬度 (°N)")
    ax.set_aspect(1 / np.cos(np.deg2rad(np.mean(dem["latitude"]))))
    ax.ticklabel_format(useOffset=False, axis="both")
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.yaxis.set_major_locator(MaxNLocator(5))
    return xy, terrain
