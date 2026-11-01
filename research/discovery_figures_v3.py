"""Figures for the Best Bias Discovery entry (v3, 2026-11-01), in the shared entry style (research/figstyle.py): each
figure states its finding as a headline, says what is plotted in a subtitle and names its source; pointers mark the
named places. Inputs: report_discovery/stations.csv, stations.json, discovery.json, tracts_simple.json
(research/discovery_tracts.py). usage: python3 research/discovery_figures_v3.py"""
import json
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research")
import figstyle as fs
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import FancyBboxPatch, Patch

OUT = "report_discovery"
SRC = "Source: USGS National Structures Dataset (public domain, retrieved 2026-11-01) · Overture Maps 2026-08-19.0 · challenge strata table · analysis: mrSharafi"
LAND, TRIBAL = "#efede8", "#ddd6c6"


def pct(v):
    return 100 * v["rate"], 100 * (v["rate"] - v["ci_lo"]), 100 * (v["ci_hi"] - v["rate"])


def seg(ax, left, width, y, h, color, gap=8):
    """One rounded segment of a stacked bar; the gap is surface colour, never a stroke."""
    ax.add_patch(FancyBboxPatch((left + gap / 2, y - h / 2), max(width - gap, 2), h, boxstyle="round,pad=0,rounding_size=16",
                                mutation_aspect=h / 160, fc=color, ec="none"))


def fig_fate(st, out):
    vis = ~st.missing
    meta, other = int((vis & (st.meta_only == True)).sum()), int((vis & (st.meta_only != True)).sum())
    held = int((st.missing & st.held_as_building.fillna(False).astype(bool)).sum()); gone = int(st.missing.sum()) - held
    n = len(st); shown = meta + other
    assert (n, held, round(meta / shown, 6)) == (out["all"]["n"], out["missing_held_as_building"], round(out["meta_only_share_of_visible"], 6))
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    top, bot = fs.frame(fig, "Three in ten fire stations are missing from Overture",
                        f"All {n:,} reference fire stations, each looked up in Overture's places within 500 m", SRC)
    fig.subplots_adjust(top=top, bottom=bot + 0.02, left=0.0, right=1.0)
    h = 0.5
    ax.text(0, 2.42, "Is the station on Overture's map?", fontsize=9, color=fs.INK2, weight="medium")
    seg(ax, 0, shown, 2, h, fs.BLUE); seg(ax, shown, n - shown, 2, h, fs.ORANGE)
    ax.text(shown / 2, 2, f"Shown   {shown:,}  ·  {100 * shown / n:.0f}%", ha="center", va="center", color="white", weight="demibold", fontsize=11)
    ax.text(shown + (n - shown) / 2, 2, f"Missing   {n - shown:,}  ·  {100 * (n - shown) / n:.0f}%", ha="center", va="center",
            color="white", weight="demibold", fontsize=11)
    ax.text(0, 1.12, "Where do the shown ones come from?", fontsize=9, color=fs.INK2, weight="medium")
    ax.text(shown + 40, 1.12, "Is a missing one anywhere in Overture?", fontsize=9, color=fs.INK2, weight="medium")
    seg(ax, 0, meta, 0.7, h, fs.BLUE); seg(ax, meta, other, 0.7, h, fs.BLUE_L)
    seg(ax, shown, held, 0.7, h, fs.ORANGE_L); seg(ax, shown + held, gone, 0.7, h, fs.ORANGE)
    ax.text(meta / 2, 0.7, f"Only from Meta (Facebook)   {meta:,}", ha="center", va="center", color="white", weight="demibold", fontsize=10)
    ax.text(shown + held + gone / 2, 0.7, f"No fire-station building either\n{gone:,}", ha="center", va="center", color="white", weight="demibold", fontsize=10)
    fs.callout(ax, (meta + other / 2, 0.7 - h / 2 - 0.03), f"{other} from any other source", (-150, -26), ha="right")
    fs.callout(ax, (shown + held / 2, 0.7 - h / 2 - 0.03), f"{held} already in Overture as a fire-station\nbuilding, not as a place",
               (34, -32), ha="left")
    ax.set_xlim(-10, n + 10); ax.set_ylim(-0.3, 2.55); ax.axis("off")
    fs.save(fig, f"{OUT}/fig0_fate.png")


def fig1(out):
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    top, bot = fs.frame(fig, "High wildfire hazard and tribal-area status both raise the gap",
                        "Reference fire stations missing from Overture, by tribal-area status and wildfire hazard (95% intervals)", SRC)
    fig.subplots_adjust(top=top - 0.07, bottom=bot + 0.14, left=0.07, right=0.98)
    ax.set_xlim(-0.6, 2.05); ax.set_ylim(0, 72)
    w, cells = 0.32, {}
    for j, (wq, col) in enumerate(((False, fs.BLUE), (True, fs.ORANGE))):
        for i, tr in enumerate((False, True)):
            v = next(h for h in out["hazard"] if h["tribal"] == tr and h["wildfire_top_quartile"] == wq)
            r, lo, hi = pct(v); x = i + (j - 0.5) * (w + 0.04); cells[(tr, wq)] = (x, r)
            fs.rbar(ax, x, 0, r, w, col)
            ax.plot([x, x], [r - lo, r + hi], color=fs.INK, lw=1.1, alpha=0.45, solid_capstyle="round", zorder=3)
            ax.text(x, r + hi + 1.6, f"{100 * v['rate']:.0f}%", ha="center", va="bottom", fontsize=13.5, weight="demibold", color=fs.INK)
            ax.text(x, -4.0, f"{v['missing']} of {v['n']:,}", ha="center", va="top", fontsize=8, color=fs.MUTED)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Non-tribal tracts", "Tribal-area tracts"], fontsize=10.5, color=fs.INK, weight="medium")
    ax.tick_params(axis="x", pad=22); ax.set_yticks([0, 20, 40, 60]); ax.set_yticklabels(["0", "20", "40", "60%"])
    fs.grid(ax)
    (x0, r0), (x1, r1) = cells[(False, False)], cells[(True, True)]
    xd = 1.5   # dimension line on the right: from the lowest to the highest rate
    for x, r in ((x0, r0), (x1, r1)):
        ax.plot([x + w / 2 + 0.03, xd + 0.04], [r, r], color=fs.INK2, lw=0.8, ls=(0, (1.5, 2.5)), zorder=1)
    ax.annotate("", (xd, r1), (xd, r0), arrowprops=dict(arrowstyle="<|-|>", color=fs.INK, lw=1.1, mutation_scale=9, shrinkA=0, shrinkB=0))
    ax.text(xd + 0.07, (r0 + r1) / 2, f"{r1 / r0:.1f}× raw\n(before\nadjustment)", ha="left", va="center", fontsize=10, weight="demibold",
            color=fs.INK, linespacing=1.25)
    hs = [Patch(color=fs.BLUE, label="Lower wildfire hazard"), Patch(color=fs.ORANGE, label=f"Top-quarter wildfire hazard (USFS WHP ≥ {out['missing_volunteer_top_quartile_wildfire']['whp_q75']:.1f})")]
    fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, top + 0.005), ncol=2, fontsize=8.8, handlelength=1.0, handleheight=1.0,
               columnspacing=1.6)
    fs.save(fig, f"{OUT}/fig1_compound.png")


def fig_robust(rb):
    """Finding 1 inside each region: missing share, lower vs top-quartile hazard and non-tribal vs tribal."""
    regs = [("eastern-ok", "Eastern Oklahoma"), ("northern-ca", "Northern California"), ("maricopa-az", "Maricopa, Arizona"),
            ("south-central-tx", "South-Central Texas")]
    W = rb["within_region"]; ck = json.load(open(f"{OUT}/checks.json"))
    hz, tb = ck["hazard_or_by_region_rural_tribal"], ck["tribal_or_by_region_rural_hazard"]   # region and rural/urban held fixed
    fig, axs = plt.subplots(1, 2, figsize=(7.8, 4.1), sharey=True)
    top, bot = fs.frame(fig, "The hazard gap holds in every region; the tribal-area gap in Oklahoma and Arizona",
                        "Stations missing from Overture within each region: blue = lower-risk group, orange = higher-risk group", SRC)
    fig.subplots_adjust(top=top - 0.15, bottom=bot + 0.1, left=0.2, right=0.98, wspace=0.12)
    for ax, key, ttl, orr in ((axs[0], "top", "Wildfire hazard: lower vs top quarter", hz),
                              (axs[1], "tribal", "Tribal-area status: non-tribal vs tribal-area", tb)):
        for y, (R, name) in enumerate(regs):
            lo, hi = W.get(f"{R}|{key}|False"), W.get(f"{R}|{key}|True")
            if not lo or not hi:
                ax.text(2, y, "no tribal-area stations", va="center", fontsize=8, color=fs.MUTED); continue
            x0, x1 = 100 * lo["rate"], 100 * hi["rate"]; up = x1 > x0
            ax.annotate("", (x1, y), (x0, y), arrowprops=dict(arrowstyle="-|>", color=fs.ORANGE if up else fs.MUTED, lw=2,
                        mutation_scale=12, shrinkA=4, shrinkB=5))
            ax.scatter([x0], [y], s=46, color=fs.BLUE, edgecolor=fs.SURF, linewidth=1.6, zorder=4)
            ax.scatter([x1], [y], s=46, color=fs.ORANGE, edgecolor=fs.SURF, linewidth=1.6, zorder=4)
            for x, other, bold in ((x0, x1, False), (x1, x0, True)):
                right = x >= other
                ax.text(x + (2.2 if right else -2.2), y, f"{x:.0f}%", ha="left" if right else "right", va="center", fontsize=8.6,
                        color=fs.INK if bold else fs.INK2, weight="demibold" if bold else "normal")
            if hi["n"] < 50:
                ax.text(max(x0, x1) + 10.5, y, f"n = {hi['n']}", ha="left", va="center", fontsize=7.4, color=fs.MUTED)
        ax.set_xlim(0, 80); ax.set_xticks([0, 20, 40, 60, 80]); ax.set_xticklabels(["0", "20", "40", "60", "80%"]); fs.grid(ax, "x")
        ax.spines["bottom"].set_visible(False); ax.set_ylim(3.6, -0.6)
        ax.text(0, -1.45, ttl, fontsize=9.6, weight="demibold", color=fs.INK)
        ax.text(0, -0.95, f"odds ratio, region + rural/urban fixed: {orr['or']:.2f} ({orr['lo']:.2f}–{orr['hi']:.2f})", fontsize=8,
                color=fs.INK2)
    axs[0].set_yticks(range(4)); axs[0].set_yticklabels([r[1] for r in regs], fontsize=9.6, color=fs.INK, weight="medium")
    fs.save(fig, f"{OUT}/fig1b_robust.png")

def rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"] if geom["type"] == "MultiPolygon" else []
    return [np.asarray(p[0]) for p in polys]


def station(st, key, region):
    r = st[st.name.str.contains(key, na=False) & st.missing & (st.region == region)].iloc[0]
    return float(r.lon), float(r.lat)


def fig_maps(st, tracts):
    regs = [("eastern-ok", "Eastern Oklahoma"), ("northern-ca", "Northern California"), ("south-central-tx", "South-Central Texas"),
            ("maricopa-az", "Maricopa, Arizona")]
    # pointers to the named stations of the entry's table (all missing, rural tribal tracts, top wildfire hazard)
    marks = {"northern-ca": [(["Yurok Volunteer Fire Department Station 1", "Yurok Volunteer Fire Department Station 2", "Willow Creek Volunteer"], "Yurok & Hoopa Valley\n3 stations missing", (58, 14), "left"),
                             (["Anderson Valley"], "Anderson Valley\nhazard index 4,263", (26, -44), "left")],
             "eastern-ok": [(["Battiest", "Pickens", "Honobia"], "Choctaw Nation\nBattiest · Pickens · Honobia", (-40, -38), "right"),
                            (["Highway 100"], "Cherokee Nation\nStilwell", (-70, 50), "right")]}
    fig = plt.figure(figsize=(8, 8.9))
    top, bot = fs.frame(fig, "Missing stations are spread across the countryside",
                        "Every reference fire station on its census tracts; circles mark stations named in the table below", SRC)
    gs = fig.add_gridspec(2, 2, top=top - 0.035, bottom=bot + 0.065, left=0.0, right=1.0, hspace=0.17, wspace=0.05)
    for k, (R, name) in enumerate(regs):
        ax = fig.add_subplot(gs[k // 2, k % 2]); T = tracts[R]
        for tribal, col in ((False, LAND), (True, TRIBAL)):
            ax.add_collection(PolyCollection([r for t in T if t["tribal"] == tribal for r in rings(t["geom"])], facecolors=col,
                                             edgecolors=fs.SURF, linewidths=0.18))
        s = st[st.region == R]
        ax.scatter(s[~s.missing].lon, s[~s.missing].lat, s=6, c=fs.BLUE, alpha=0.8, linewidths=0, zorder=3)
        ax.scatter(s[s.missing].lon, s[s.missing].lat, s=15, c=fs.ORANGE, edgecolors=fs.SURF, linewidths=0.6, zorder=4)
        ax.autoscale_view(); ax.set_aspect(1 / np.cos(np.radians(s.lat.mean())), adjustable="datalim"); ax.axis("off")
        for keys, label, off, ha in marks.get(R, []):
            pts = np.array([station(st, key, R) for key in keys])
            for p in pts:
                ax.scatter(*p, s=70, facecolor="none", edgecolor=fs.INK, linewidth=1.1, zorder=6)
            fs.callout(ax, tuple(pts.mean(axis=0)), label, off, ha=ha, size=8)
        ax.text(0.0, 1.085, name, transform=ax.transAxes, fontsize=11.5, weight="demibold", color=fs.INK)
        ax.text(0.0, 1.015, f"{100 * s.missing.mean():.0f}% missing  ·  {int(s.missing.sum())} of {len(s):,} stations",
                transform=ax.transAxes, fontsize=8.8, color=fs.INK2)
    hs = [plt.Line2D([], [], marker="o", ls="", color=fs.BLUE, ms=4.5, label="Station shown in Overture"),
          plt.Line2D([], [], marker="o", ls="", color=fs.ORANGE, ms=6.5, markeredgecolor=fs.SURF, label="Station missing from Overture"),
          plt.Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=fs.INK, ms=8, label="Named in the table"),
          Patch(color=TRIBAL, label="Tribal-area tract")]
    fig.legend(handles=hs, loc="lower left", bbox_to_anchor=(0.0, bot - 0.005), ncol=4, fontsize=8.6, handlelength=1.0, columnspacing=1.5,
               handletextpad=0.4)
    fs.save(fig, f"{OUT}/fig2_maps.png")


def short(name):
    for a, b in (("Volunteer Fire Department", "VFD"), ("Volunteer Fire Company", "VFC"), ("Volunteer Fire Fighters Association", "VFFA"),
                 ("Fire Department and Emergency Medical Services", "FD & EMS"), ("Rural Fire Association", "RFA"),
                 ("Fire Department", "FD"), ("Fire Station", "FS"), ("Station ", "St. "), ("Community ", ""), (" Headquarters", " HQ")):
        name = name.replace(a, b)
    return name


def place_labels(ax, pts, names, size=7.6, avoid=()):
    """Greedy label placement: try offsets around each point, keep the first box that hits no earlier box or point."""
    import matplotlib.patheffects as pe
    fig = ax.figure; fig.canvas.draw(); r = fig.canvas.get_renderer()
    taken = [ax.transData.transform(p) for p in pts]; boxes = [a.get_window_extent(r).expanded(1.1, 1.3) for a in avoid]
    offs = [(7, 0, "left", "center"), (-7, 0, "right", "center"), (6, 7, "left", "bottom"), (-6, 7, "right", "bottom"),
            (6, -7, "left", "top"), (-6, -7, "right", "top"), (0, 10, "center", "bottom"), (0, -10, "center", "top")]
    for p, nm in zip(pts, names):
        for dx, dy, ha, va in offs:
            t = ax.annotate(nm, p, xytext=(dx * 1.5, dy * 1.5), textcoords="offset points", ha=ha, va=va, fontsize=size, color=fs.INK, zorder=8,
                            path_effects=[pe.withStroke(linewidth=2.6, foreground="white")],
                            arrowprops=dict(arrowstyle="-", color=fs.INK2, lw=0.6, shrinkA=1, shrinkB=4.5))
            bb = t.get_window_extent(r).expanded(1.04, 1.15)
            hit = any(bb.overlaps(b) for b in boxes) or any(bb.contains(*q) for q in taken)
            if not hit and ax.get_window_extent(r).contains(bb.x0, bb.y0) and ax.get_window_extent(r).contains(bb.x1, bb.y1):
                boxes.append(bb); break
            t.remove()


def scalebar(ax, km=10):
    """Scale bar in the lower-right corner; returns its artists so labels can avoid them."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim(); lat = (y0 + y1) / 2
    deg = km / (111.32 * np.cos(np.radians(lat))); x, y = x1 - 0.05 * (x1 - x0) - deg, y0 + 0.05 * (y1 - y0)
    ln, = ax.plot([x, x + deg], [y, y], color=fs.INK, lw=2.2, solid_capstyle="butt", zorder=9)
    tx = ax.text(x + deg / 2, y + 0.018 * (y1 - y0), f"{km} km", ha="center", va="bottom", fontsize=7.6, color=fs.INK, zorder=9)
    return ln, tx


def fig_closeups(st, tracts):
    boxes = [("northern-ca", (-124.15, -123.35, 40.75, 41.55), "Klamath and Trinity rivers, California", "all", 10),
             ("eastern-ok", (-95.75, -94.55, 34.15, 34.75), "Southeastern Oklahoma, Choctaw Nation", "named", 10)]
    named = ["Battiest", "Pickens", "Honobia", "Bethel", "Big Cedar Volunteer Fire Department Station 1", "Clayton", "Hochatown",
             "Sherwood", "Antlers", "Albion", "Nashoba", "Ringold"]
    fig = plt.figure(figsize=(8, 5.6))
    top, bot = fs.frame(fig, "Up close, most stations are simply not there",
                        "Every reference fire station in two high-hazard areas; station names shown where they fit", SRC)
    gs = fig.add_gridspec(1, 2, top=top - 0.06, bottom=bot + 0.075, left=0.0, right=1.0, wspace=0.06)
    for k, (R, (x0, x1, y0, y1), title, lab, km) in enumerate(boxes):
        ax = fig.add_subplot(gs[0, k])
        for tribal, col in ((False, LAND), (True, TRIBAL)):
            ax.add_collection(PolyCollection([r for t in tracts[R] if t["tribal"] == tribal for r in rings(t["geom"])], facecolors=col,
                                             edgecolors="white", linewidths=0.8))
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)), adjustable="datalim")
        ax.apply_aspect(); (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim(); ax.set_xticks([]); ax.set_yticks([])   # both panels the same size
        b = st[(st.region == R) & st.lon.between(x0, x1) & st.lat.between(y0, y1)].sort_values("lat", ascending=False)
        for sp in ax.spines.values():
            sp.set_color(fs.GRID)
        ax.scatter(b[~b.missing].lon, b[~b.missing].lat, s=46, c=fs.BLUE, edgecolors="white", linewidths=1.6, zorder=5)
        ax.scatter(b[b.missing].lon, b[b.missing].lat, s=58, c=fs.ORANGE, edgecolors="white", linewidths=1.6, zorder=6)
        pick = b if lab == "all" else b[b.name.apply(lambda n: any(key in n for key in named))]
        place_labels(ax, list(zip(pick.lon, pick.lat)), [short(n) for n in pick.name], avoid=scalebar(ax, km))
        ax.text(0.0, 1.09, title, transform=ax.transAxes, fontsize=10.5, weight="demibold", color=fs.INK)
        ax.text(0.0, 1.025, f"{int(b.missing.sum())} of {len(b)} stations missing  ·  wildfire hazard {b.usfs_WHP_mean.min():.0f}–{b.usfs_WHP_mean.max():.0f} (top-quarter cut-off 153.3)",
                transform=ax.transAxes, fontsize=8.2, color=fs.INK2)
    hs = [plt.Line2D([], [], marker="o", ls="", color=fs.BLUE, ms=6, label="Shown in Overture"),
          plt.Line2D([], [], marker="o", ls="", color=fs.ORANGE, ms=7, label="Missing from Overture"),
          Patch(color=TRIBAL, label="Tribal-area tract"), Patch(color=LAND, label="Other tract")]
    fig.legend(handles=hs, loc="lower left", bbox_to_anchor=(0.0, bot - 0.005), ncol=4, fontsize=8.6, handlelength=1.0, columnspacing=1.6)
    fs.save(fig, f"{OUT}/fig2b_closeups.png")


def fig3(out):
    order = [(False, False, "Urban, non-tribal"), (False, True, "Urban, tribal"), (True, False, "Rural, non-tribal"), (True, True, "Rural, tribal")]
    fig, ax = plt.subplots(figsize=(7.0, 4.1))
    top, bot = fs.frame(fig, "It is the place, not the kind of department",
                        "Stations missing from Overture by tract type, volunteer vs career departments (95% intervals)", SRC)
    fig.subplots_adjust(top=top - 0.09, bottom=bot + 0.12, left=0.2, right=0.97)
    for k, (ru, tr, lab) in enumerate(order):
        if k % 2 == 1:
            ax.axhspan(k - 0.5, k + 0.5, color=fs.NEUTRAL, zorder=0, lw=0)
        for dv, vol, col in ((-0.14, True, fs.ORANGE), (0.14, False, fs.BLUE)):
            v = next(x for x in out["strata"] if x["rural"] == ru and x["tribal"] == tr and x["volunteer"] == vol)
            r, lo, hi = pct(v)
            ax.plot([r - lo, r + hi], [k + dv, k + dv], color=col, lw=3, alpha=0.3, solid_capstyle="round", zorder=2)
            ax.scatter(r, k + dv, s=70, color=col, edgecolor=fs.SURF, linewidth=2, zorder=4)
            ax.text(r + hi + 1.5, k + dv, f"{r:.0f}%", va="center", fontsize=9.2, color=fs.INK, weight="demibold")
            ax.text(r + hi + 7.0, k + dv, f"n = {v['n']:,}", va="center", fontsize=7.8, color=fs.MUTED)
    ax.set_yticks(range(4)); ax.set_yticklabels([o[2] for o in order], color=fs.INK, fontsize=10, weight="medium"); ax.invert_yaxis()
    ax.set_ylim(3.5, -0.5); ax.set_xlim(0, 82); ax.set_xticks([0, 20, 40, 60, 80]); ax.set_xticklabels(["0", "20", "40", "60", "80%"])
    fs.grid(ax, "x"); ax.spines["bottom"].set_visible(False)
    ax.set_xlabel("Reference stations missing from Overture", fontsize=8.8, color=fs.INK2, labelpad=6)
    fs.callout(ax, (33.5, 2 - 0.14), "Rural volunteer stations are\nmissed less, not more", (-30, -42), ring_pt=16, ha="right", size=8)
    hs = [plt.Line2D([], [], marker="o", ls="", color=fs.ORANGE, ms=7, label="Volunteer departments"),
          plt.Line2D([], [], marker="o", ls="", color=fs.BLUE, ms=7, label="Career / combination departments")]
    fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, top + 0.005), ncol=2, fontsize=8.8, handletextpad=0.3, columnspacing=1.6)
    fs.save(fig, f"{OUT}/fig3_place.png")


def fig5(disc):
    rows = disc["buildings"]["by_osm_share"]
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    top, bot = fs.frame(fig, "Where nobody maps by hand, buildings go missing",
                        "Tracts with a building gap above 0.02, by the share of their Overture buildings mapped in OpenStreetMap",
                        "Source: Microsoft US Building Footprints (challenge reference) · Overture Maps 2026-08-19.0 · analysis: mrSharafi")
    fig.subplots_adjust(top=top - 0.03, bottom=bot + 0.21, left=0.06, right=0.98)
    x = np.arange(len(rows)); ax.set_xlim(-0.6, len(rows) - 0.4); ax.set_ylim(0, 13.5)
    for xi, r in zip(x, rows):
        g = 100 * r["share_gap_gt_0.02"]
        fs.rbar(ax, xi, 0, g, 0.5, fs.ORANGE if xi == 0 else fs.BLUE)
        ax.text(xi, g + 0.35, f"{g:.1f}%", ha="center", va="bottom", fontsize=11.5, weight="demibold", color=fs.INK)
        ax.text(xi, -1.6, f"{r['n']:,} tracts\nrural {100 * r['rural']:.0f}%  ·  tribal {100 * r['tribal']:.0f}%", ha="center", va="top",
                fontsize=7.6, color=fs.MUTED, linespacing=1.45)
    ax.set_xticks(x); ax.set_xticklabels([r["osm_share"].replace("-", "–") for r in rows], fontsize=9.5, color=fs.INK, weight="medium")
    ax.set_yticks([0, 4, 8, 12]); ax.set_yticklabels(["0", "4", "8", "12%"]); fs.grid(ax)
    ax.set_xlabel("Share of the tract's Overture buildings mapped by hand (OpenStreetMap)", fontsize=8.8, color=fs.INK2, labelpad=42)
    r0, r4 = 100 * rows[0]["share_gap_gt_0.02"], 100 * rows[-1]["share_gap_gt_0.02"]
    fs.callout(ax, (0.27, 10.4), f"{r0 / r4:.1f}× the rate of tracts\nthat are mostly hand-mapped", (34, 4), size=9)
    fs.save(fig, f"{OUT}/fig5_buildings.png")


if __name__ == "__main__":
    st = pd.read_csv(f"{OUT}/stations.csv"); out = json.load(open(f"{OUT}/stations.json")); disc = json.load(open(f"{OUT}/discovery.json"))
    assert len(st) == out["all"]["n"] and int(st.missing.sum()) == out["all"]["missing"], "stations.csv and stations.json disagree"
    fig_fate(st, out); fig1(out); fig_robust(json.load(open(f"{OUT}/robust.json"))); T = json.load(open(f"{OUT}/tracts_simple.json")); fig_maps(st, T); fig_closeups(st, T); fig3(out); fig5(disc)
    print("wrote fig0_fate, fig1_compound, fig2_maps, fig2b_closeups, fig3_place, fig5_buildings in", OUT)
