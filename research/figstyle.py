"""Shared look for the entry figures (Best Documentation, Best Bias Discovery): one type family (Avenir Next), the
validated palette (blue #2a78d6 / orange #eb6834; text in ink tones, never in a series colour), editorial headline +
subtitle inside each figure, a muted source line, hairline grids and bars with a rounded data-end and a square
baseline."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

SURF, INK, INK2, MUTED, GRID, NEUTRAL = "#fcfcfb", "#1d1d1b", "#55544f", "#8a8984", "#e7e6e2", "#f1f0ec"
BLUE, BLUE_L, BLUE_D, ORANGE, ORANGE_L = "#2a78d6", "#86b6ef", "#1c5cab", "#eb6834", "#f6b89c"


def _load_font():
    """Avenir Next ships with macOS as one .ttc; matplotlib reads only its first face, so split out the four weights
    used here (into the temp dir, never the repo). Falls back to DejaVu Sans elsewhere."""
    import os, tempfile
    from matplotlib import font_manager as fm
    src = "/System/Library/Fonts/Avenir Next.ttc"
    if not os.path.exists(src):
        return "DejaVu Sans"
    from fontTools.ttLib import TTCollection
    out = os.path.join(tempfile.gettempdir(), "avenir_next_faces"); os.makedirs(out, exist_ok=True)
    col = None
    for i, tag in ((7, "Regular"), (5, "Medium"), (2, "DemiBold"), (0, "Bold")):
        path = os.path.join(out, f"AvenirNext-{tag}.ttf")
        if not os.path.exists(path):
            col = col or TTCollection(src); col.fonts[i].save(path)
        fm.fontManager.addfont(path)
    return "Avenir Next"


FONT = _load_font()
plt.rcParams.update({"font.family": FONT, "font.size": 9.5, "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "axes.linewidth": 0.8,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "xtick.major.size": 0, "ytick.major.size": 0, "legend.frameon": False})


def frame(fig, title, subtitle=None, source=None):
    """Headline (the finding, bold), subtitle (what is plotted) and a muted source line, placed in points so they
    sit the same on every figure size. Returns (top, bottom) for fig.subplots_adjust."""
    H = fig.get_figheight() * 72
    fig.text(0.0, 1 - 4 / H, title, fontsize=14, weight="bold", color=INK, va="top")
    y = 1 - 26 / H
    if subtitle:
        fig.text(0.0, y, subtitle, fontsize=9.6, color=INK2, va="top", linespacing=1.35)
        y -= (13 * len(subtitle.splitlines()) + 4) / H
    if source:
        fig.text(0.0, 2 / H, source, fontsize=7.2, color=MUTED, va="bottom")
    return y - 14 / H, (30 / H if source else 0.04)


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def rbar(ax, x, base, length, width, color, horizontal=False, radius_px=4, zorder=2):
    """Bar with a rounded data-end and a square baseline (radius in pixels, corrected for the axes aspect)."""
    fig = ax.figure; fig.canvas.draw_idle()
    bb = ax.get_window_extent(); x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    ux, uy = (x1 - x0) / bb.width, (y1 - y0) / bb.height          # data units per pixel
    if horizontal:   # x = bar centre on y, base / length along x
        r = min(radius_px * ux, abs(length) / 2)
        ax.add_patch(FancyBboxPatch((base, x - width / 2), length, width, boxstyle=f"round,pad=0,rounding_size={r}",
                                    mutation_aspect=uy / ux, fc=color, ec="none", zorder=zorder))
        ax.add_patch(Rectangle((base, x - width / 2), max(0, length - r), width, fc=color, ec="none", zorder=zorder))
    else:
        r = min(radius_px * ux, width / 2)                          # rounding is set in x units; mutation_aspect maps it to y
        ax.add_patch(FancyBboxPatch((x - width / 2, base), width, length, boxstyle=f"round,pad=0,rounding_size={r}",
                                    mutation_aspect=uy / ux, fc=color, ec="none", zorder=zorder))
        ax.add_patch(Rectangle((x - width / 2, base), width, max(0, length - radius_px * uy), fc=color, ec="none", zorder=zorder))


def save(fig, path, dpi=220):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)


def callout(ax, xy, text, offset, ring_pt=0, ha="left", size=8.4):
    """Pointer to a place or mark: an optional ring (diameter in points) on the target, an elbow leader line, and the
    label in a white rounded box. offset is in points from the target."""
    if ring_pt:
        ax.scatter(*xy, s=ring_pt ** 2, facecolor="none", edgecolor=INK, linewidth=1.1, zorder=6)
    ax.annotate(text, xy, xytext=offset, textcoords="offset points", ha=ha, va="center", fontsize=size, color=INK,
                linespacing=1.3, zorder=7,
                bbox=dict(boxstyle="round,pad=0.5,rounding_size=0.5", fc="white", ec=GRID, lw=0.9),
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.9, shrinkA=0, shrinkB=ring_pt / 2 + 1 if ring_pt else 2,
                                connectionstyle="angle,angleA=0,angleB=90,rad=3"))
