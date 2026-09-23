"""One visual system for the paper. Original code, informed by Icarus-Figures.
AI assistance: ChatGPT/Codex (OpenAI), 2026-09-23; exact model/release unavailable.
"""

from pathlib import Path
import json
import sys
import tempfile
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from paper_data import load_analysis as load_verified_analysis

DATA = ROOT / "paper/data"
RESULTS = ROOT / "results"
OUT = ROOT / "outputs/figures"
BLUE, ORANGE, TEAL, GRAY, RED = "#365B75", "#C87334", "#258275", "#939BA2", "#A23E48"
COLORS = {"A": BLUE, "B": TEAL, "C": ORANGE}
MARKERS = {"A": "o", "B": "s", "C": "^"}
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
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.7,
            "axes.edgecolor": "#65727B",
            "text.color": "#24333E",
            "axes.labelcolor": "#24333E",
            "xtick.direction": "out",
            "ytick.direction": "out",
            "lines.linewidth": 1.5,
            "legend.frameon": False,
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
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
            target = Path(staging) / f"{name}.{ext}"
            fig.savefig(target, dpi=300, bbox_inches="tight", pad_inches=0.06)
        for target in Path(staging).iterdir():
            target.replace(OUT / target.name)
    plt.close(fig)
    print(f"[fig] saved {name}.pdf/.svg/.png @300dpi", flush=True)


def panel(ax, label, title):
    ax.set_title(f"{label}  {title}", loc="left", pad=9)


def note(fig, text):
    fig.text(0.01, 0.006, text, fontsize=8, color="#59656F", va="bottom")


def gantt(ax, trips, question, small=False):
    sf, ef = (
        ("开始时刻（s）", "返回O01时刻（s）")
        if question == "q2"
        else ("开始时刻_s", "返回O01时刻_s")
    )
    ids = sorted(trips["无人机编号"].unique())
    for _, r in trips.iterrows():
        y = ids.index(r["无人机编号"])
        ax.barh(
            y,
            (r[ef] - r[sf]) / 3600,
            left=r[sf] / 3600,
            height=0.58,
            color=COLORS[r["机型编号"]],
            edgecolor="white",
            linewidth=0.7,
            hatch=HATCH[r["机型编号"]],
        )
        if not small:
            ax.text(
                (r[ef] + r[sf]) / 7200,
                y,
                str(r["架次编号"]).split("-")[-1],
                ha="center",
                va="center",
                fontsize=7,
                color="white",
            )
    ax.set_yticks(range(len(ids)), ids)
    ax.set_xlabel("时刻 $t$ (h)")
    ax.set_ylabel("实体无人机")
    ax.set_xlim(left=0)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.15)


def nodes_xy(analysis):
    # Coordinates remain longitude/latitude; plots correct the visual aspect ratio.
    return {k: (v["lon"], v["lat"]) for k, v in analysis["nodes"].items()}


def terrain_map(ax, analysis, labels=True):
    with (DATA / "terrain_map.json").open(encoding="utf-8") as f:
        dem = json.load(f)
    ax.contour(
        dem["longitude"],
        dem["latitude"],
        dem["elevation_m"],
        levels=7,
        colors="#C9CDCF",
        linewidths=0.4,
        zorder=0,
    )
    xy = nodes_xy(analysis)
    for key, (lon, lat) in xy.items():
        ax.scatter(
            lon,
            lat,
            marker="s" if key == "O01" else "o",
            s=35 if key == "O01" else 13,
            color=BLUE,
            zorder=4,
        )
        if labels:
            ax.annotate(
                key, (lon, lat), xytext=(3, 3), textcoords="offset points", fontsize=7.5
            )
    ax.set_xlabel("经度 (°E)")
    ax.set_ylabel("纬度 (°N)")
    ax.set_aspect(1 / np.cos(np.deg2rad(np.mean(dem["latitude"]))))
    ax.ticklabel_format(useOffset=False, axis="both")
    return xy
