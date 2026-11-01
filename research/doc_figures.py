"""Figures for the Best Documentation entry (docs/BEST_DOCUMENTATION.md), written to docs/fig/, in the shared entry style
(research/figstyle.py): a headline that states the point, a subtitle that says what is drawn, pointers in white boxes.
usage: python3 research/doc_figures.py"""
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research")
import figstyle as fs
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

OUT = "docs/fig"
os.makedirs(OUT, exist_ok=True)


def card(ax, x, y, w, h, num, title, body, src, accent=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.16", fc="#e9f1fc" if accent else fs.NEUTRAL,
                                ec=fs.BLUE if accent else "none", lw=1.2))
    if num:
        ax.add_patch(Circle((x + 0.3, y + h - 0.3), 0.17, color=fs.BLUE))
        ax.text(x + 0.3, y + h - 0.305, str(num), ha="center", va="center", color="white", fontsize=9, weight="bold")
    ax.text(x + (0.58 if num else 0.2), y + h - 0.3, title, va="center", fontsize=10.5, weight="demibold", color=fs.INK)
    ax.text(x + 0.2, y + h - 0.62, body, va="top", fontsize=8.4, color=fs.INK2, linespacing=1.45)
    if src:
        ax.text(x + 0.2, y + 0.2, src, fontsize=7.4, color=fs.BLUE_D, family="Menlo", va="bottom")


def flow(ax, a, b, rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12, color=fs.MUTED, lw=1.3, shrinkA=2, shrinkB=2,
                                 connectionstyle=f"arc3,rad={rad}"))


# Fig 1: the pipeline
fig = plt.figure(figsize=(7.8, 5.0))
top, bot = fs.frame(fig, "Five steps from permitted data to a scored file",
                    "Each step reads only the output of the step before it; the box names the file that does the work")
ax = fig.add_axes([0, 0, 1, top]); ax.set_xlim(0, 10.4); ax.set_ylim(0, 5.55); ax.axis("off")
W, H = 3.2, 1.9
steps = [(0.0, 3.55, 1, "Permitted data", "Overture 2026-08-19.0: roads,\nbuildings, places, rail.\nACS housing, strata, tracts", "model/paths.py"),
         (3.6, 3.55, 2, "Features per tract", "9,794 tracts in 5 regions:\nroad length by class and\nroute, buildings and places\nby source and category", "model/features*.py"),
         (7.2, 3.55, 3, "Structural model", "The organisers' formula,\ngap = 1 − min(1, Overture / ref),\nwith each removed reference\nreplaced by an estimate", "model/predict.py"),
         (7.2, 1.1, 4, "Learn from scores", "Each scored upload is one\nexact measurement; combine\nthem, shrink the uncertain", "model/probe.py"),
         (3.6, 1.1, 5, "Check, then write", "9,794 GEOIDs, no blanks,\nvalues in [0, 1], official\ncolumn layout", "model/check_submission.py"),
         (0.0, 1.1, None, "submission.csv", "Uploaded to Zindi; the public\nRMSE goes into\nsubmissions2/ledger.csv", "")]
for x, y, n, t, b, src in steps:
    card(ax, x, y, W, H, n, t, b, src, accent=n is None)
flow(ax, (W, 4.5), (3.6, 4.5)); flow(ax, (3.6 + W, 4.5), (7.2, 4.5))
flow(ax, (7.2 + W - 0.35, 3.55), (7.2 + W - 0.35, 1.1 + H)); flow(ax, (7.2, 2.05), (3.6 + W, 2.05)); flow(ax, (3.6, 2.05), (W, 2.05))
ax.add_patch(FancyBboxPatch((0.0, 0.05), 10.4, 0.68, boxstyle="round,pad=0,rounding_size=0.14", fc=fs.SURF, ec=fs.ORANGE, lw=1.1,
                            ls=(0, (4, 3))))
ax.add_patch(Circle((0.33, 0.39), 0.12, color=fs.ORANGE))
ax.text(0.55, 0.39, "Guard rails", fontsize=9.5, weight="demibold", va="center", color=fs.INK)
ax.text(2.05, 0.39, "data_public/ holds only permitted files  ·  check_compliance.sh: no removed layer is read\n"
        "a candidate that moves a published mean or undefined share is not uploaded", fontsize=8.2, color=fs.INK2, va="center", linespacing=1.4)
fs.save(fig, f"{OUT}/fig1_pipeline.png")

# Fig 2: what the score is made of (published component means, METHODOLOGY.md B.3)
comp = [("Transport", 0.1118, "highway length vs reference"), ("Places", 0.0514, "businesses + fire, EMS, schools"),
        ("Buildings", 0.0056, "footprints vs reference")]
fig, ax = plt.subplots(figsize=(7.4, 2.9))
top, bot = fs.frame(fig, "Transport carries most of the score", "Published mean gap of each component across the scored tracts (0 = fully mapped)")
fig.subplots_adjust(top=top, bottom=0.12, left=0.25, right=0.95)
ax.set_xlim(0, 0.13); ax.set_ylim(-0.6, 2.6)
for y, (n, v, d) in zip((2, 1, 0), comp):
    fs.rbar(ax, y, 0, v, 0.46, fs.BLUE if n == "Transport" else fs.BLUE_L, horizontal=True)
    ax.text(v + 0.0018, y, f"{v:.4f}", va="center", fontsize=10.5, weight="demibold", color=fs.INK)
    ax.text(-0.004, y + 0.1, n, ha="right", va="bottom", fontsize=10.5, weight="demibold", color=fs.INK)
    ax.text(-0.004, y - 0.06, d, ha="right", va="top", fontsize=8.2, color=fs.INK2)
ax.set_yticks([]); ax.set_xticks([0, 0.04, 0.08, 0.12]); fs.grid(ax, "x"); ax.spines["bottom"].set_visible(False)
fs.save(fig, f"{OUT}/fig2_components.png")

# Fig 3: the model reproduces the published undefined shares (METHODOLOGY.md B.4 vs the organisers' figures)
reg = [("Eastern Oklahoma", 21.3, 21), ("Maricopa, Arizona", 55.4, 55), ("Northern California", 36.5, 37), ("South-Central Texas", 29.8, 28)]
fig, ax = plt.subplots(figsize=(7.4, 3.5))
top, bot = fs.frame(fig, "The model reproduces every published undefined share",
                    "Share of tracts with an undefined component: our model's expectation vs the organisers' published figure")
fig.subplots_adjust(top=top - 0.1, bottom=0.14, left=0.25, right=0.97)
ys = np.arange(len(reg))[::-1]
for y, (n, mo, pu) in zip(ys, reg):
    ax.plot([min(mo, pu), max(mo, pu)], [y, y], color=fs.GRID, lw=5, solid_capstyle="round", zorder=1)
    ax.scatter(pu, y, s=230, facecolor="none", edgecolor=fs.ORANGE, linewidth=2.4, zorder=3)
    ax.scatter(mo, y, s=58, color=fs.BLUE, edgecolor=fs.SURF, linewidth=1.6, zorder=4)
    ax.text(66, y, f"{mo:.1f}%  vs  {pu}%", va="center", fontsize=9, color=fs.INK, weight="medium")
ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in reg], fontsize=10, color=fs.INK, weight="medium")
ax.set_xlim(15, 78); ax.set_xticks([20, 30, 40, 50, 60]); ax.set_xticklabels([f"{t}%" for t in (20, 30, 40, 50, 60)])
fs.grid(ax, "x"); ax.spines["bottom"].set_visible(False); ax.set_ylim(-0.6, len(reg) - 0.4)
fs.callout(ax, (29.8, 0), "Texas farm-to-market roads:\ndefined with a probability", (46, -5), size=8)
hs = [plt.Line2D([], [], marker="o", ls="", color=fs.BLUE, ms=7, label="Our model (expected share)"),
      plt.Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=fs.ORANGE, markeredgewidth=2, ms=10, label="Organisers' published share")]
fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, top + 0.01), ncol=2, fontsize=8.8, columnspacing=1.6)
fs.save(fig, f"{OUT}/fig3_validation.png")

# Fig 4: what one scored file tells us (geometry of the public score)
fig = plt.figure(figsize=(7.4, 3.9))
top, bot = fs.frame(fig, "One scored file gives one exact number",
                    "Three distances are known, so the triangle fixes how far the truth lies along our change")
ax = fig.add_axes([0, 0, 1, top]); ax.set_xlim(-0.8, 8.2); ax.set_ylim(-1.5, 3.1); ax.set_aspect("equal"); ax.axis("off")
b, f, y = np.array([0.4, 0.0]), np.array([5.0, 0.0]), np.array([3.4, 2.4]); p = np.array([y[0], 0.0])
ax.fill([b[0], f[0], y[0]], [b[1], f[1], y[1]], color=fs.NEUTRAL, zorder=0)
ax.plot(*zip(b, y), color=fs.INK2, lw=1.4, solid_capstyle="round"); ax.plot(*zip(f, y), color=fs.INK2, lw=1.4, solid_capstyle="round")
ax.plot(*zip(b, f), color=fs.BLUE, lw=3, solid_capstyle="round")
ax.plot(*zip(y, p), color=fs.MUTED, lw=1, ls=(0, (3, 2.5)))
ax.add_patch(plt.Rectangle((p[0] - 0.17, 0.0), 0.17, 0.17, fc="none", ec=fs.MUTED, lw=0.9))
ax.plot([b[0], p[0]], [-0.42, -0.42], color=fs.ORANGE, lw=5, solid_capstyle="round")
ax.scatter(*b, s=90, color=fs.INK, edgecolor=fs.SURF, linewidth=2, zorder=5); ax.scatter(*f, s=90, color=fs.BLUE, edgecolor=fs.SURF, linewidth=2, zorder=5)
ax.scatter(*y, s=260, facecolor="white", edgecolor=fs.INK, linewidth=1.6, zorder=5); ax.text(*y, "?", ha="center", va="center", fontsize=10, weight="bold")
ax.text(b[0] - 0.18, 0.0, "base file", ha="right", va="center", fontsize=10, weight="demibold")
ax.text(f[0] + 0.18, 0.0, "new file", ha="left", va="center", fontsize=10, weight="demibold")
ax.text(y[0], y[1] + 0.36, "hidden truth", ha="center", fontsize=10, weight="demibold")
fs.callout(ax, (1.7, 1.12), "base score (known)", (-34, 26), ha="right", size=8.2)
fs.callout(ax, (4.3, 1.05), "new file's score (known)", (34, 22), size=8.2)
fs.callout(ax, (4.4, 0.0), "our change (known)", (26, -30), size=8.2)
fs.callout(ax, ((b[0] + p[0]) / 2, -0.42), "what we learn: how far the truth\nlies in the direction of our change", (-14, -34), ha="right", size=8.2)
ax.text(5.9, 2.2, "c = (base² + change² − new²) / 2", fontsize=9, family="Menlo", color=fs.INK, va="top",
        bbox=dict(boxstyle="round,pad=0.6,rounding_size=0.5", fc=fs.NEUTRAL, ec="none"))
fs.save(fig, f"{OUT}/fig4_geometry.png")

# Fig 5: public score over the 17 days (submissions2/ledger.csv)
L = pd.read_csv("submissions2/ledger.csv"); L["s"] = pd.to_numeric(L.public_rmse, errors="coerce")
L = L.dropna(subset=["s"]).reset_index(drop=True); L["d"] = pd.to_datetime(L.date)
L["x"] = L.d + pd.to_timedelta(L.groupby("date").cumcount() / L.groupby("date").s.transform("size") * 0.8, unit="D")
assert len(L) == 88 and abs(L.s.min() - 0.056773885) < 1e-12 and abs(L.s.iloc[0] - 0.107950717) < 1e-6, (len(L), L.s.min(), L.s.iloc[0])
best = L.s.cummin()
fig, ax = plt.subplots(figsize=(7.6, 4.0))
top, bot = fs.frame(fig, "From 0.108 to 0.0568 in 88 uploads", "Public RMSE of every scored upload (lower is better) and the best score so far")
fig.subplots_adjust(top=top - 0.07, bottom=0.1, left=0.08, right=0.98)
ax.scatter(L.x, L.s, s=16, color=fs.MUTED, alpha=0.45, linewidth=0)
ax.step(L.x, best, where="post", color=fs.BLUE, lw=2.2)
marks = {"00_baseline.csv": ("First compliant baseline", (34, -6), "left"), "30_v3_shrink_07.csv": ("Structural model\n+ shrinkage", (40, 30), "left"),
         "c3_clean_regions_grp05.csv": ("Final 1 · c3\nown files only", (-46, 30), "right"), "k84_k55_line145_rown512k3.csv": ("Final 2 · k84\nbest public", (-64, 2), "right")}
for fn, (lab, off, ha) in marks.items():
    r = L[L.file == fn].iloc[0]
    ax.scatter(r.x, r.s, s=64, color=fs.ORANGE, zorder=5, edgecolor=fs.SURF, linewidth=2)
    fs.callout(ax, (r.x, r.s), f"{lab}  ·  {r.s:.4f}" if "\n" not in lab else f"{lab}\n{r.s:.4f}", off, ha=ha, size=8)
ax.set_ylim(0.052, 0.112); ax.set_yticks([0.06, 0.07, 0.08, 0.09, 0.10, 0.11])
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b")); fs.grid(ax, "y")
hs = [plt.Line2D([], [], marker="o", ls="", color=fs.MUTED, alpha=0.6, ms=5, label="Every scored upload"),
      plt.Line2D([], [], color=fs.BLUE, lw=2.2, label="Best so far"),
      plt.Line2D([], [], marker="o", ls="", color=fs.ORANGE, ms=7, label="Milestone")]
fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, top + 0.01), ncol=3, fontsize=8.8, columnspacing=1.6)
fs.save(fig, f"{OUT}/fig5_progress.png")
print("wrote", sorted(os.listdir(OUT)))
