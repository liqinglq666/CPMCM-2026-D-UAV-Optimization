"""Fixed semantics, 160 mm A4 figures and deterministic, traceable exports."""

import json
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize
from matplotlib.ticker import MaxNLocator, FuncFormatter
from matplotlib.text import Text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from paper_data import load_analysis as load_verified_analysis

DATA, RESULTS, OUT = ROOT / "paper/data", ROOT / "results", ROOT / "outputs/figures"
BLUE, GREEN, ORANGE = "#299EDF", "#91D477", "#F66532"
LIGHT_BLUE, PALE_BLUE, YELLOW = "#78C3FE", "#ABE5FB", "#FADA00"
RED, GRAY, INK, BACKGROUND = "#E72451", "#BFC4C8", "#222222", "#FDFFFF"
COLORS = dict(A=BLUE, B=GREEN, C=ORANGE)
MARKERS = dict(A="o", B="s", C="^")
LINESTYLES = dict(A="-", B="--", C="-.")
HATCH = dict(A="", B="//", C="..")
DIRECT = "#677E8D"
TERRAIN_CMAP = LinearSegmentedColormap.from_list(
    "subdued_terrain", ["#F0F5F2", "#CFDBD3", "#B8C5BB", "#ABAFA0", "#D0C7B4"]
)
WIDTH = 160 / 25.4


def paper_style():
    bundled = ROOT / "paper/fonts/NotoSansSC-Regular.ttf"
    if bundled.is_file():
        font_manager.fontManager.addfont(bundled)
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(
        (
            n
            for n in [
                "Noto Sans SC",
                "Noto Sans CJK SC",
                "Source Han Sans SC",
                "Microsoft YaHei",
            ]
            if n in available
        ),
        None,
    )
    if font is None:
        raise RuntimeError("Run scripts/setup_paper_fonts.py first")
    plt.rcParams.update(
        {
            "font.family": [font, "DejaVu Sans"],
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9,
            "axes.titleweight": "bold",
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
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
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "lines.linewidth": 1.3,
            "legend.frameon": False,
            "legend.handlelength": 1.6,
            "legend.columnspacing": 1.25,
            "axes.unicode_minus": False,
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": BACKGROUND,
            "savefig.facecolor": BACKGROUND,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "svg.fonttype": "path",
            "svg.hashsalt": "uav-final-figures-2026",
            "mathtext.fontset": "stix",
            "axes.grid": False,
            "hatch.linewidth": 0.4,
            "figure.constrained_layout.h_pad": 0.045,
            "figure.constrained_layout.w_pad": 0.045,
            "figure.constrained_layout.hspace": 0.13,
            "figure.constrained_layout.wspace": 0.10,
        }
    )


def load_analysis():
    return load_verified_analysis(ROOT)


def save(fig, name):
    """Never tighten the canvas: final PDF width stays exactly 160 mm."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = []
    clipped = []
    inactive_ticks = set()
    # Matplotlib retains Text artists for locator ticks outside view limits;
    # Axis.draw does not paint those artists, even though get_visible() is True.
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo - 1e-10 <= tick.get_loc() <= hi + 1e-10:
                    inactive_ticks.update((tick.label1, tick.label2))
    for t in fig.findobj(Text):
        if t in inactive_ticks or not t.get_visible() or not t.get_text().strip():
            continue
        bb = t.get_window_extent(renderer)
        # Hidden secondary tick labels are not an actual panel annotation.
        if bb.width <= 0 or bb.height <= 0:
            continue
        texts.append(float(t.get_fontsize()))
        if (
            bb.x0 < -1
            or bb.y0 < -1
            or bb.x1 > fig.bbox.width + 1
            or bb.y1 > fig.bbox.height + 1
        ):
            clipped.append(t.get_text())
    audit = {
        "figure_id": name,
        "width_mm": float(fig.get_figwidth() * 25.4),
        "height_mm": float(fig.get_figheight() * 25.4),
        "minimum_text_pt": min(texts),
        "canvas_clipped_text": clipped,
        "export_dpi": 300,
        "font_family": plt.rcParams["font.family"],
    }
    qadir = ROOT / "outputs/figure-qa"
    qadir.mkdir(parents=True, exist_ok=True)
    (qadir / (name + ".json")).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    if clipped:
        raise ValueError(f"{name}: text outside fixed A4-width canvas: {clipped}")
    if min(texts) < 7.49:
        raise ValueError(f"{name}: text smaller than 7.5 pt at print size")
    with tempfile.TemporaryDirectory(dir=OUT) as staging:
        for ext in ("pdf", "svg", "png"):
            meta = (
                {"Date": None}
                if ext == "svg"
                else ({"CreationDate": None, "ModDate": None} if ext == "pdf" else {})
            )
            fig.savefig(Path(staging) / f"{name}.{ext}", dpi=300, metadata=meta)
        for target in Path(staging).iterdir():
            target.replace(OUT / target.name)
    plt.close(fig)
    print(
        f"[fig] {name}: PDF / SVG / 300 dpi PNG; 160 mm; min {min(texts):g} pt",
        flush=True,
    )


def panel(ax, label, title):
    ax.set_title(f"({label})  {title}", loc="left", pad=8)


def grid(ax, axis="x"):
    ax.grid(axis=axis, color=GRAY, alpha=0.23, linewidth=0.45)
    ax.set_axisbelow(True)


def threshold(ax, value, axis="y", color=RED):
    f = ax.axhline if axis == "y" else ax.axvline
    return f(value, color=color, ls="--", lw=0.8, zorder=1)


def key_note(ax, xy, title, value, xytext=(0.05, 0.95)):
    return ax.annotate(
        f"{title}\n{value}",
        xy=xy,
        xycoords="data",
        xytext=xytext,
        textcoords="axes fraction",
        va="top",
        ha="left",
        fontsize=8,
        linespacing=1.6,
        arrowprops={"arrowstyle": "-", "color": INK, "lw": 0.65},
        bbox={"facecolor": BACKGROUND, "edgecolor": "none", "pad": 1.5, "alpha": 0.95},
        zorder=8,
    )


def nodes_xy(analysis):
    return {k: (v["lon"], v["lat"]) for k, v in analysis["nodes"].items()}


def terrain_map(ax, analysis, labels=False, weak=False, show_nodes=True):
    dem = json.loads((DATA / "terrain_map.json").read_text())
    x, y, z = (
        np.array(dem["longitude"]),
        np.array(dem["latitude"]),
        np.array(dem["elevation_m"]),
    )
    # Display illumination only. Elevation, physics and coordinates are never modified.
    dy = abs(y[1] - y[0]) * 111320
    dx = abs(x[1] - x[0]) * 111320 * np.cos(np.deg2rad(y.mean()))
    shade = LightSource(azdeg=315, altdeg=45).hillshade(z, vert_exag=1, dx=dx, dy=dy)
    norm = Normalize(np.floor(z.min() / 100) * 100, np.ceil(z.max() / 100) * 100)
    rgb = TERRAIN_CMAP(norm(z))[..., :3]
    rgb = np.clip(rgb * (0.86 + 0.14 * shade[..., None]), 0, 1)
    if weak:
        rgb = 0.62 + 0.38 * rgb
    extent = (
        x[0] - (x[1] - x[0]) / 2,
        x[-1] + (x[1] - x[0]) / 2,
        y[-1] - (y[-2] - y[-1]) / 2,
        y[0] + (y[-2] - y[-1]) / 2,
    )
    ax.imshow(rgb, extent=extent, origin="upper", interpolation="nearest", zorder=0)
    ax.contour(
        x,
        y,
        z,
        levels=np.arange(np.ceil(z.min() / 100) * 100, z.max(), 100),
        colors=INK,
        alpha=0.11 if weak else 0.22,
        linewidths=0.35,
        zorder=1,
    )
    xy = nodes_xy(analysis)
    if show_nodes:
        for key, (lon, lat) in xy.items():
            ax.scatter(
                lon,
                lat,
                marker="*" if key == "O01" else "o",
                s=70 if key == "O01" else 16,
                facecolor=INK if key == "O01" else BACKGROUND,
                edgecolor=INK,
                lw=0.65,
                zorder=5,
            )
    if labels:
        for key in labels if isinstance(labels, (list, tuple, set)) else xy:
            ax.annotate(
                key,
                xy[key],
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7.5,
                zorder=9,
            )
    ax.set_aspect(1 / np.cos(np.deg2rad(y.mean())))
    ax.set(
        xlim=(extent[0], extent[1]),
        ylim=(extent[2], extent[3]),
        xlabel="经度 (°E)",
        ylabel="纬度 (°N)",
    )
    ax.xaxis.set_major_locator(MaxNLocator(4 if weak else 5))
    ax.yaxis.set_major_locator(MaxNLocator(4 if weak else 5))
    fmt = FuncFormatter(lambda v, p: f"{v:.2f}")
    ax.xaxis.set_major_formatter(fmt)
    ax.yaxis.set_major_formatter(fmt)
    return xy, matplotlib.cm.ScalarMappable(norm=norm, cmap=TERRAIN_CMAP)


def scale_bar(ax, km=2):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length = km * 1000 / (111320 * np.cos(np.deg2rad((y0 + y1) / 2)))
    x = x0 + 0.06 * (x1 - x0)
    y = y0 + 0.07 * (y1 - y0)
    ax.plot([x, x + length], [y, y], color=INK, lw=1.4, zorder=9)
    ax.text(
        x + length / 2,
        y + 0.017 * (y1 - y0),
        f"{km:g} km",
        ha="center",
        va="bottom",
        fontsize=7.5,
        zorder=9,
    )
