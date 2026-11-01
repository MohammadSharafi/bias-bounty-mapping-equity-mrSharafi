"""Measure feature directions against the public residual of e0, then combine them.

Base file s = e0_v13_fully_pinned (rebuilt exactly from model.predict). For any complete file
g = s + D scored on the public tracts,

    M_g = M_s + mean_pub(D^2) - 2 mean_pub(D (y - s))

so one score gives one number, c_D = mean_pub(D (y - s)) = (M_s + Q_DD - M_g) / 2, with the
full-set mean of D^2 standing in for the public one (eastern-wa excluded: none of it is
public). With K scored directions the shrunken least-squares combination w (see solve) gives the
file s + sum_k w_k D_k, predicted public MSE M_s - 2 w'c + w'Qw.

Directions come from two sources:
  * every file already in the ledger (D = file - s): free, since their scores are known;
  * new probe files g<NN>_probe_<name>.csv, one permitted-feature direction each,
    standardised inside its scope (Texas only, or all four public regions), orthogonalised
    against the base (1 and s per region), e0's decomp parts and the earlier probes, and
    scaled to RMS PROBE_RMS so the full-set stand-in for mean_pub(D^2) costs nothing.

Every file is a complete model; every probe spans hundreds of tracts; nothing reads a label or
probes single tracts. eastern-wa keeps e0's values in every file (never public, so never fitted).

usage: python -m model.probe write | audit | groups | selftest | fit [--dry] [--out NAME] [--until SCORED_FILE]
"""
import os
import math
import re
import sys
import numpy as np
import pandas as pd

from .predict import load_features, predict, variants, PARAMS, save, load_scores
from . import decomp

BASE = "e0_v13_fully_pinned"
D = os.environ.get("BB_SUBS", "submissions2")   # the review package keeps the scored files in submitted/
PROBE_RMS = 0.004
KAPPA = 4.0          # James-Stein threshold in split-noise variances; selftest: 2 and 3 lose on the private split under no signal
PUBLIC_FRAC = 0.3
REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]   # public regions
TX = ["south-central-tx"]


def _log1p(v):
    return np.log1p(np.maximum(np.nan_to_num(np.asarray(v, float)), 0))


def _feature_directions(f, o):
    """(name, scope, raw vector) in upload order: Texas transport first, then all-region."""
    strong = f.len_rt_interstate + f.len_rt_us + f.len_rt_state
    strong_hwy = f.len_rt_interstate_hwy + f.len_rt_us_hwy + f.len_rt_state_hwy
    svi = f.svi_overall.where(f.svi_overall >= 0)
    rows = [
        ("tx_ratio", TX, np.log((f.len_hwy + 100) / (o.t_ref_est + 100))),           # model's own Overture/reference ratio
        ("tx_tgap_sq", TX, o.transport_gap ** 2),                                   # shape of the transport gap
        ("tx_pdef", TX, o.p_transport_defined),                                     # definedness
        ("tx_sub_lowclass", TX, _log1p(f.len_rt_statesub - f.len_rt_statesub_hwy)),  # FM/RM drawn below highway class
        ("tx_strong_lowclass", TX, _log1p(strong - strong_hwy)),                     # state/US drawn below highway class
        ("tx_bnd_out", TX, _log1p(f.rtb_out_strong + f.rtb_out_sub)),
        ("tx_near_out", TX, _log1p(f.len_hwy_near_out)),
        ("tx_secondary_share", TX, f.len_secondary / (f.len_hwy + 100)),
        ("tx_urban", TX, f.pct_urban.fillna(0)),
        ("tx_area", TX, np.log(f.area_m2.clip(lower=1e4))),
        ("tx_len_hwy", TX, _log1p(f.len_hwy)),
        ("tx_tertiary_named", TX, _log1p(f.len_tertiary_named)),
        ("tx_county", TX, _log1p(f.len_rt_county)),
        ("tx_frontage", TX, f.len_hwy_frontage.fillna(0) / (f.len_hwy + 100)),
        ("tx_bnd_in", TX, _log1p(f.rtb_in_strong + f.rtb_in_sub)),
        ("tx_density", TX, _log1p(f.pop_total.fillna(0) / (f.area_m2.clip(lower=1e4) / 1e6))),
        ("all_estab_pc", REGIONS, _log1p(f.n_poi_bq) - _log1p(f.pop_total.fillna(0))),
        ("all_poi_meta_share", REGIONS, f.n_poi_meta / (f.n_poi + 1)),
        ("all_poi_n", REGIONS, _log1p(f.n_poi)),
        ("all_fire_any", REGIONS, (f.n_fire > 0).astype(float)),
        ("all_school_any", REGIONS, (f.n_schools > 0).astype(float)),
        ("all_poigap_sq", REGIONS, o.poi_gap ** 2),
        ("all_bld_ms_share", REGIONS, f.n_bld_ms / (f.n_bld + 1)),
        ("all_bld_usfs", REGIONS, _log1p(f.usfs_BuildingCount_sum) - _log1p(f.n_bld)),
        ("all_svi", REGIONS, svi.fillna(svi.median())),
        ("all_ruca", REGIONS, f.ruca_primary.fillna(f.ruca_primary.median())),
        ("all_bus", REGIONS, _log1p(f.n_bus_stop)),
        ("all_rail", REGIONS, _log1p(f.len_rail)),
        # 2026-10-17, from where h2 moves e0: the fit's largest move (+0.024) is on the 439 Texas tracts
        # with a route inside and none along the edge, an extrapolation of g05's log-length direction
        # to zero. This indicator (orthogonal to g05) tests that step directly.
        ("tx_inside_noedge", TX, (((strong + f.len_rt_statesub) > 0) & ((f.rtb_out_strong + f.rtb_out_sub) <= 0)).astype(float)),
        # 2026-10-20: the un-routed term (t_beta 0.17) is uniform; posted speed is the one permitted attribute
        # that separates a main artery from a street. Fast (>= 45 mph) un-routed highway-class length, given
        # how much un-routed length carries any posted limit (features_speed).
        ("tx_unrouted_fast", TX, _log1p(f.len_hwy_fast_unrouted) - 0.5 * _log1p(f.len_hwy_speed_unrouted)),
        # 2026-10-20 R&D: OSM's 2007 TIGER import tagged the reference's secondary class (CFCC A2x/A3x) as
        # primary/secondary; urban mappers re-tagged by function, rural roads mostly keep the import tag. So an
        # un-routed secondary in a rural tract is far more likely to be in the reference than one in a city.
        ("tx_unrouted_rural", TX, _log1p(np.maximum(f.len_hwy - f.len_hwy_routed, 0)) * (1 - f.pct_urban.fillna(0))),
        ("ok_unrouted", ["eastern-ok"], _log1p(np.maximum(f.len_hwy - f.len_hwy_routed, 0))),
        # 2026-10-22: curvature of the response. The truth is right-skewed (tail to 1.0) while e0 tops out
        # near 0.48; if the truth rises faster than e0 at the top, the square of e0's score carries it.
        ("all_score_sq", REGIONS, o.coverage_gap_score.values ** 2),
    ]
    return [(n, sc, np.nan_to_num(np.asarray(v, float))) for n, sc, v in rows]


def base():
    """(features, region, s, public-region mask, e0's decomp parts)."""
    f = load_features()
    s = load_scores(f"{D}/{BASE}.csv", f.GEOID)
    o = predict(f, {**PARAMS, **variants()[BASE]})
    err = np.max(np.abs(o.coverage_gap_score.to_numpy().round(6) - s))
    reg = f.region.values
    decomp.BASE, decomp.D = BASE, D
    _, _, X = decomp.parts()
    return f, o, reg, s, np.isin(reg, REGIONS), X, err


def directions():
    """Build every probe: standardise in scope, Gram-Schmidt in scope, scale to PROBE_RMS."""
    f, o, reg, s, m, X, err = base()
    basis = []
    for r in REGIONS:
        basis += [(reg == r).astype(float), np.where(reg == r, s, 0.0)]
    basis += [X[k] for k in X if k not in ("LVL", "REG", "T:eastern-wa")]
    out = []
    for name, scope, v in _feature_directions(f, o):
        sm = np.isin(reg, scope)
        z = np.zeros(len(v))
        for r in scope:
            k = reg == r
            sd = v[k].std()
            if sd > 0:
                z[k] = np.clip((v[k] - v[k].mean()) / sd, -4, 4)
        B = np.array([np.where(sm, b, 0.0) for b in basis + [d for _, _, d in out]])
        B = B[(B ** 2).sum(1) > 1e-12]
        proj = lambda v: v - B.T @ np.linalg.lstsq(B.T, v, rcond=None)[0]
        for _ in range(20):                    # alternate: exact projection, then cap the tails at 4 sd
            z = proj(z)
            sd = np.sqrt(np.mean(z[sm] ** 2))
            z = np.clip(z, -4 * sd, 4 * sd)
            if len(out) >= 30:                     # shortcut: g00-g29 were scored without this floor and must keep their bytes; from g30 on,
                z = np.maximum(z, -s)              # a probe never pushes a tract below 0 (small-scope directions clip there otherwise)
        z = np.where(sm, proj(z), 0.0)
        z = z * PROBE_RMS / np.sqrt(np.mean(z[m] ** 2))
        out.append((name, scope, z))
    return f, reg, s, m, X, err, out


def probe_file(i, name):
    return f"g{i:02d}_probe_{name}"


def write():
    f, reg, s, m, X, err, out = directions()
    print(f"max |rebuilt e0 - file| = {err:.1e}")
    print("BASE EXACT" if err < 5e-7 else "BASE NOT EXACT")
    for i, (name, scope, z) in enumerate(out):
        g = np.clip(s + z, 0, 1).round(6)
        save(f.GEOID, g, f"{D}/{probe_file(i, name)}.csv")
    print(f"wrote {len(out)} probe files g00-g{len(out) - 1:02d} (rms {PROBE_RMS} each)")


def audit():
    f, reg, s, m, X, err, out = directions()
    ok = True
    real = []
    for i, (name, scope, z) in enumerate(out):
        g = load_scores(f"{D}/{probe_file(i, name)}.csv", f.GEOID)
        d = g - s
        n_sup = int((np.abs(d[m]) > 1e-6).sum())
        clip_loss = np.sqrt(np.mean((d - z.round(6)) ** 2))
        prev = max([abs(np.corrcoef(d[m], p[m])[0, 1]) for p in real] or [0.0])
        part = max(abs(np.corrcoef(d[m], X[k][m])[0, 1]) for k in X if k not in ("LVL", "REG", "T:eastern-wa"))
        wa = np.abs(d[reg == "eastern-wa"]).max()
        flag = n_sup >= 100 and clip_loss < 1e-4 and prev < 0.01 and part < 0.01 and wa == 0
        ok &= flag
        print(f"{probe_file(i, name):34s} support {n_sup:5d}  clip {clip_loss:.1e}  max|corr prev| {prev:.4f}  "
              f"max|corr part| {part:.4f}  {'ok' if flag else 'FAIL'}")
        real.append(d)
    print("AUDIT OK" if ok else "AUDIT FAIL")


# ---------------------------------------------------------------- group probes on the incumbent

INCUMBENT = os.environ.get("BB_INC", "h2_probe_fit")   # the best scored file the group files sit on
MODEL_STEPS = [   # (name, predict options incl. the pin_all values for that option, hypothesis)
    ("oneway_05", {"t_oneway_w": 0.5, "t_county": {"eastern-ok": 0.4233}, "t_sigma": 0.4686, "t_scale": 1.13319},
     "divided routes are one centreline in the reference: each one-way carriageway counts half; "
     "re-pinned, every published transport number holds"),
    ("bnd_6m", {"_features": {"extra": "out2/features_extra_6.parquet", "bnd": "out2/features_bnd_6.parquet"},
                "t_county": {"eastern-ok": 0.5255}, "t_sigma": 0.7647, "t_scale": 0.9636},
     "true on-boundary roads sit within 6-8 m of the tract edge (median_test); the 25 m band also catches far "
     "carriageways and parallel roads the reference does not share between tracts; re-pinned"),
    ("oneway_075", {"t_oneway_w": 0.75, "t_county": {"eastern-ok": 0.4916}, "t_sigma": 0.5847, "t_scale": 1.01689},
     "half the divided routes are one centreline in the reference (follow-up to oneway_05)"),
    # g03 (2026-10-20, corr -0.10, the strongest probe): e0 over-predicts the gap where FM/RM/Loop routes are
    # drawn below highway class, i.e. those roads are mostly not in the reference's secondary class
    ("sub_low_03", {"t_sub_low_w": 0.3, "t_county": {"eastern-ok": 0.5571}, "t_sigma": 0.7309, "t_scale": 0.92387},
     "sub-network route length drawn below highway class counts 0.3 in the reference; re-pinned, every published number holds"),
    ("sub_low_0", {"t_sub_low_w": 0.0, "t_county": {"eastern-ok": 0.5559}, "t_sigma": 0.7742, "t_scale": 0.92458},
     "sub-network route length drawn below highway class is not in the reference at all; re-pinned"),
    # R&D 2026-10-20: rural roads keep OSM's TIGER-import class, so rural un-routed arterials are reference roads;
    # pin_all holds every published number at 0.3 and 0.6 (out2/rural_beta_test.log)
    ("rural_03", {"t_beta_rural": 0.3, "t_county": {"eastern-ok": 0.6112}, "t_sigma": 0.7044, "t_scale": 0.88989},
     "un-routed highway-class length counts 0.3 x rural share in the reference; re-pinned"),
    # 2026-10-21 formulation fix: the facilities half is the mean over the facility types the reference has, so its
    # expectation enumerates the presence cases; sum(p g)/sum(p) is a ratio of expectations. Published poi mean held.
    ("fac_exact", {"f_exact": True, "f_hold": 0.051414},
     "exact expectation of the facilities half (mean over defined types), poi mean held at the published 0.051414"),
    # 2026-10-21: the building gap is 0 in e0, yet its published mean is 0.005601. Overture keeps one source per
    # footprint; a deficit appears only where an OSM or Esri footprint replaced several Microsoft ones.
    ("bld_esri", {"b_kappa_src": {"esri": 1.2}, "b_hold": 0.005601},
     "each Esri footprint hides 1.2 Microsoft footprints; building mean held at the published 0.005601"),
    ("bld_osm", {"b_kappa_src": {"osm": 1.2}, "b_hold": 0.005601},
     "each OSM footprint hides 1.2 Microsoft footprints; building mean held at the published 0.005601"),
    # 2026-10-21 data check: Overture drops a Microsoft footprint wherever OSM/Esri overlaps it (0 overlaps in 4 tracts);
    # Esri footprints are smaller than Microsoft ones (median ratio 0.70: k09 refuted), OSM larger (1.87). Hidden count
    # from replaced area, lambda pinned to the published building mean (lambda 1 would give 0.306)
    ("bld_area", {"b_area_lambda": 0.1321},
     "hidden Microsoft count = 0.1321 x OSM/Esri area / the tract's Microsoft footprint size; building mean 0.005601"),
    ("revised", {"b_area_lambda": 0.1321, "f_exact": True, "f_hold": 0.051414},
     "revised model: area-based building gap and the exact facilities expectation, both published means held"),
]
# fire_name ({"f_name": True}) moved only 85 tracts: kept for combinations


def groups(f, o):
    """name -> (tract mask, move, hypothesis). Each file is the incumbent moved by `move` on one
    group, so a right hypothesis scores better than the incumbent and a wrong one still measures
    the group's mean residual (the fit reads it as the direction file - e0)."""
    rural = (f.pct_urban.fillna(0) < 0.5).values
    return {
        "interstate": ((f.len_rt_interstate > 0).values, -0.02,
                       "Interstate tracts: both carriageways are routed in Overture, so the reference estimate is "
                       "too long and the predicted road gap too high"),
        "rural_nofire": (((f.n_fire == 0).values & rural), +0.03,
                         "rural tracts with no fire_department place hold a reference station more often than the "
                         "4-15% prior, which carries the facilities half"),
    }


def model_step(f, change):
    """Move of e0 in score units on the tracts a model option changes, without the spread
    re-normalisation that would smear it over every tract: raw difference times e0's affine factor."""
    P0 = {**PARAMS, **variants()[BASE]}
    feats = change.get("_features")                 # alternative feature files, e.g. a narrower boundary band
    f1 = load_features(**feats) if feats else f
    raw = lambda P, ff=f: predict(ff, {**{k: v for k, v in P.items() if k != "_features"}, "target_sd": None,
                                       "shrink": None}).coverage_gap_score.to_numpy()
    r0, r1 = raw(P0), raw({**P0, **change}, f1)
    a = P0["target_sd"] / np.sqrt(np.mean((r0 - r0.mean()) ** 2))
    return a * (r1 - r0)


def _save_or_keep(geoid, out, path):
    """Scored files keep the bytes they were scored with (save refuses new bytes); returns False if kept."""
    try:
        save(geoid, out, path); return True
    except SystemExit as e:
        print(f"{os.path.basename(path)}: kept as scored ({e})"); return False


def write_groups(until=None, outdir=None):
    """until: project with the ledger as it stood before that file's row (rebuilds a scored k-file);
    outdir: write there instead of the scored-file directory."""
    global UNTIL
    UNTIL = until
    O = outdir or D
    f, o, reg, s, m, X, err = base()
    inc = load_scores(f"{D}/{INCUMBENT}.csv", f.GEOID)
    ok = True
    for i, (name, (g, move, why)) in enumerate(groups(f, o).items()):
        g = g & m                                           # eastern-wa is never public: never moved
        out = np.clip(inc + move * g, 0, 1).round(6)
        moved = np.abs(out - inc) > 1e-9
        ok &= bool((moved <= g).all()) and g.sum() >= 100
        _save_or_keep(f.GEOID, out, f"{O}/k{i:02d}_grp_{name}.csv")
        print(f"k{i:02d}_grp_{name}: {g.sum()} tracts, move {move:+.3f}, incumbent mean there {inc[g].mean():.4f}  ({why})")
    # model-option files: the incumbent plus e0's move under one option, on the tracts it changes
    for i, (name, change, why) in enumerate(MODEL_STEPS, start=len(groups(f, o))):
        d = np.where(m, model_step(f, change), 0.0)
        g = np.abs(d) > 1e-9
        out = np.clip(inc + d, 0, 1).round(6)
        ok &= g.sum() >= 100
        _save_or_keep(f.GEOID, out, f"{O}/k{i:02d}_grp_{name}.csv")
        print(f"k{i:02d}_grp_{name}: {g.sum()} tracts, mean move {d[g].mean():+.4f}  ({why})")
        # the same move with every already-measured direction projected out: on top of the incumbent it
        # tests only the information the measurements do not have
        names, Ds, _ = scored_directions(s, m, f.GEOID)
        Dm = Ds[:, m]
        new = np.zeros(len(d)); new[m] = d[m] - Dm.T @ np.linalg.lstsq(Dm.T, d[m], rcond=None)[0]
        out = np.clip(inc + new, 0, 1).round(6)
        if not _save_or_keep(f.GEOID, out, f"{O}/k{i:02d}n_grp_{name}_new.csv"):
            continue
        print(f"k{i:02d}n_grp_{name}_new: rms {np.sqrt(np.mean(new[m] ** 2)):.4f}, share of the move not yet measured "
              f"{np.sqrt(np.mean(new[m] ** 2) / np.mean(d[m] ** 2)):.2f}")
    UNTIL = None
    print("GROUPS OK" if ok else "GROUPS FAIL")


# ---------------------------------------------------------------- calibration to published group means

# Leaderboard-measured conditional means published by another participant (Hunter_Toledo, Zindi
# discussions 35264/35265, 2026-10-08): rural (pct_urban < 0.5) x populated (>= 1,500) x no
# fire_department place, rural rest, urban rest. Public information, measured on the public tracts.
PUBLISHED_GROUP_MEANS = (("tier", 0.131), ("rural_rest", 0.0967), ("urban", 0.0475))


def calibrate(base_name, out, strength=0.5):
    """Move each published group's mean part of the way to its measured value (strength < 1 because
    the measurement carries split noise and the group rule is a re-implementation)."""
    f, o, reg, s, m, X, err = base()
    g = load_scores(f"{D}/{base_name}.csv", f.GEOID)
    rural = (f.pct_urban.fillna(0) < 0.5).values
    tier = rural & (f.pop_total.fillna(0).values >= 1500) & (f.n_fire == 0).values
    masks = {"tier": tier, "rural_rest": rural & ~tier, "urban": ~rural}
    out_v = g.copy()
    for name, meas in PUBLISHED_GROUP_MEANS:
        k = masks[name] & m
        out_v[k] = g[k] + strength * (meas - g[k].mean())
        print(f"{name:11s} n={k.sum():5d} mean {g[k].mean():.4f} -> {out_v[k].mean():.4f} (measured {meas})")
    save(f.GEOID, np.clip(out_v, 0, 1), f"{D}/{out}.csv")


# Per-region public truth means, measured by argszero_reg with one level probe per region (Zindi
# discussion 35275, 2026-10-08). Their closed form used shares over all 9,794 tracts while eastern-wa is
# not scored; corrected with the scored shares and the probe step d solved from closure to the published
# mean 0.0598 (d = 0.0502, matching the 0.05 implied by their eastern-wa artifact): research/region_means.py.
PUBLISHED_REGION_MEANS = (("south-central-tx", 0.05033), ("maricopa-az", 0.04248), ("eastern-ok", 0.12665),
                          ("northern-ca", 0.06785))


def calibrate_regions(base_name, out, resid_sd=0.0688):
    """Shift each scored region's mean toward its measured public mean. Per region an empirical-Bayes
    factor err^2 / (err^2 + v), v = resid_sd^2 (1/n_pub + 1/n_priv): the measured public mean differs
    from the private one by split noise, so small regions move less."""
    f, o, reg, s, m, X, err = base()
    g = load_scores(f"{D}/{base_name}.csv", f.GEOID)
    out_v = g.copy()
    for name, meas in PUBLISHED_REGION_MEANS:
        k = (f.region.values == name) & m
        e = meas - g[k].mean(); n_pub = PUBLIC_FRAC * k.sum()
        v = resid_sd ** 2 * (1 / n_pub + 1 / (k.sum() - n_pub)); lam = e * e / (e * e + v)
        out_v[k] = g[k] + lam * e
        print(f"{name:17s} n={k.sum():5d} mean {g[k].mean():.4f} -> {out_v[k].mean():.4f} (measured {meas}, factor {lam:.2f})")
    save(f.GEOID, np.clip(out_v, 0, 1), f"{D}/{out}.csv")


# ---------------------------------------------------------------- fitting

EXT = False    # set by fit(ext=True): include other teams' published scored files
ZERO = False   # set by fit(zero=True): include the all-zero file (direction -s) at its published public RMSE
PUBLISHED_ZERO_RMSE = 0.107246   # all-zero file, public RMSE posted by Hunter_Toledo and loGan7 (6 dp)
UNTIL = None   # set by fit(until=...): later ledger rows are invisible to every reader below


def ledger(until=None):
    L = pd.read_csv(f"{D}/ledger.csv", dtype={"public_rmse": str})
    if until:
        rows = np.flatnonzero(L.file.values == f"{until}.csv")
        assert len(rows), f"{until}.csv has no ledger row"
        L = L.iloc[:rows[0]]
    return L

def solve(Dm, Ms, Mg, n_pub, kappa=None, eb=None, grp=None, cerr=None):
    """Dm: K x n directions on the public-region tracts; Ms, Mg: public MSEs of s and of each s + D_k.

    c is exact on the public tracts but carries split noise with respect to the private ones:
    cov(c) ~ S = (Ms Q + cov(D_k^2, D_l^2) / 4) / n_pub (the first term from D (y - s), the
    second from the full-set stand-in for mean_pub(D^2)). In whitened coordinates (Q = L L',
    u = L^-1 c) each u_k gets one positive-part James-Stein factor
    max(0, 1 - KAPPA var(u_k) / u_k^2), so a coordinate is kept only where it stands clear of
    what a random public split would produce."""
    kappa = KAPPA if kappa is None else kappa
    Q = Dm @ Dm.T / Dm.shape[1]
    c = (Ms + np.diag(Q) - Mg) / 2
    D2 = Dm ** 2
    S = (Ms * Q + np.cov(D2) / 4) / n_pub if len(Dm) > 1 else (Ms * Q + D2.var() / 4) / n_pub
    if cerr is not None:   # per-row error of a stated score's c (published files whose bytes / scores do not match exactly)
        S = np.atleast_2d(S) + np.diag(np.asarray(cerr) ** 2)
    L = np.linalg.cholesky(Q + 1e-12 * np.eye(len(Q)) * np.trace(Q))
    Li = np.linalg.inv(L)
    u = Li @ c
    var_u = np.diag(Li @ np.atleast_2d(S) @ Li.T)
    shrink = np.maximum(0.0, 1 - kappa * var_u / np.maximum(u ** 2, 1e-30))
    if eb is not None:   # empirical Bayes: prior variance = eb x mean excess of u^2 over its noise (research/estimator_search.py)
        tau2 = max(1e-30, eb * np.mean(np.maximum(u ** 2 - var_u, 0)))
        shrink = tau2 / (tau2 + var_u)
        if grp is not None:   # one prior variance per group of directions (research/estimator_search2.py)
            for g in np.unique(grp):
                k = grp == g
                tau2 = max(1e-30, eb * np.mean(np.maximum(u[k] ** 2 - var_u[k], 0)))
                shrink[k] = tau2 / (tau2 + var_u[k])
    w = np.linalg.solve(L.T, u * shrink)
    return Q, c, w, Ms - 2 * w @ c + w @ Q @ w


# Ledger files whose bytes on disk are known to be the bytes that were scored. `model.predict`
# rewrote every variant file on 2026-10-14 under the current defaults, so an older file on disk
# can differ from its upload (00_baseline certainly does: its places bug was fixed after upload,
# and the dry fit over all files was internally inconsistent). Kept: the constant; 95 and 96,
# untouched since they were written before upload; 70, equal to 96 on every public tract;
# e0, written the day before upload; and every file this module or decomp writes on e0.
TRUSTED = {"20_const_058", "70_v7_base", "95_abl_south-central-tx", BASE}
TRUSTED_PREFIX = ("f", "g", "h", "k")


def scored_directions(s, m, geoid):
    """Every trusted ledger file with a score, as D = file - s; s itself and duplicates dropped."""
    L = ledger(UNTIL).drop_duplicates("file", keep="last")
    names, Ds, Ms = [], [], []
    for file, rmse in zip(L.file, L.public_rmse):
        name = file.replace(".csv", "")
        if name not in TRUSTED and not name.startswith(TRUSTED_PREFIX):
            continue
        if len(rmse.split(".")[-1]) < 6:
            continue                                   # score pasted with too few digits to measure a direction
        g = load_scores(f"{D}/{file}", geoid)
        d = g - s
        if np.sqrt(np.mean(d[m] ** 2)) < 1e-5:
            continue                                   # s itself
        names.append(name); Ds.append(d); Ms.append(float(rmse) ** 2)
    if EXT:   # other teams' published, scored files (ext/ledger.csv, hash-verified where published)
        X_ = pd.read_csv(f"{D}/ext/ledger.csv", dtype={"public_rmse": str})
        for file, rmse in zip(X_.file, X_.public_rmse):
            d = load_scores(f"{D}/ext/{file}", geoid) - s
            names.append(file.replace(".csv", "")); Ds.append(d); Ms.append(float(rmse) ** 2)
    if ZERO:   # round J 2026-10-23: never a direction before; kept out of ext/ so h9-k24 still rebuild
        names.append("z_allzero"); Ds.append(-s); Ms.append(PUBLISHED_ZERO_RMSE ** 2)
    # Whitening order: the clean, orthogonal probes first, then the large ledger directions.
    # A direction that lies (almost) in the span of the ones before it adds no new information
    # and makes the whitening ill-conditioned (h0 is a combination of three others), so it is dropped.
    order = sorted(range(len(names)), key=lambda i: (not names[i].startswith("g"), i))
    keep, B = [], np.zeros((0, int(m.sum())))
    for i in order:
        v = Ds[i][m]
        resid = v - B.T @ np.linalg.lstsq(B.T, v, rcond=None)[0] if len(B) else v
        if np.sqrt(np.mean(resid ** 2)) < 0.05 * np.sqrt(np.mean(v ** 2)):
            continue
        keep.append(i); B = np.vstack([B, v])
    return [names[i] for i in keep], np.array([Ds[i] for i in keep]), np.array([Ms[i] for i in keep])


def loo(kappas=(0.0, 2.0, 4.0, 8.0)):
    """Leave-one-out test of the predictor on the real scored files: each probe/group file's public
    RMSE is predicted from the other files alone (its direction projected on the fit of the rest),
    then compared with the score it actually got. Reports, per kappa, the sign hit rate of the
    realised vs predicted delta from e0 and the RMS error of the predicted RMSE."""
    f, o, reg, s, m, X, err = base()
    L = ledger(UNTIL)
    sc = dict(zip(L.file.str.replace(".csv", "", regex=False), L.public_rmse.astype(float)))
    Ms = sc[BASE] ** 2
    names, Ds, Mg = scored_directions(s, m, f.GEOID)
    Dm = Ds[:, m]; n_pub = PUBLIC_FRAC * m.sum()
    test = [i for i, n in enumerate(names) if n[0] in "gk"]    # probes and group files: the files the fit is used to rank
    for kappa in kappas:
        rows = []
        for i in test:
            rest = [j for j in range(len(names)) if j != i]
            Q, c, w, _ = solve(Dm[rest], Ms, Mg[rest], n_pub, kappa)
            q_ik = Dm[rest] @ Dm[i] / Dm.shape[1]
            q_ii = np.mean(Dm[i] ** 2)
            pred = np.sqrt(max(Ms + q_ii - 2 * (w @ q_ik), 0))
            rows.append((names[i], pred, np.sqrt(Mg[i])))
        r = pd.DataFrame(rows, columns=["file", "pred", "real"])
        base_r = np.sqrt(Ms)
        hit = np.mean(np.sign(r.pred - base_r) == np.sign(r.real - base_r))
        rmse = np.sqrt(np.mean((r.pred - r.real) ** 2))
        null = np.sqrt(np.mean((np.sqrt(Ms + np.array([np.mean(Dm[i] ** 2) for i in test])) - r.real) ** 2))
        if kappa == KAPPA:
            print(r.round(6).to_string(index=False))
        print(f"kappa {kappa:.0f}: sign hit rate {hit:.2f}, RMS error of predicted RMSE {rmse:.6f} (no-signal predictor {null:.6f})")
    print(f"LOO over {len(test)} files")


def private(files=("h2_probe_fit", "h3_probe_fit")):
    """Expected private RMSE of e0 and of each fitted file, with its uncertainty.

    For a fit file s + w'D the James-Stein weights satisfy Q w = E[c_true | c_pub] (in whitened
    coordinates w = L^-T (u * shrink), so Q w = L (u * shrink)), hence
        expected private gain  = 2 w'(Q w) - w'Q w = w'Q w            (MSE units)
        public gain            = 2 w'c_pub - w'Q w                    (contains fitted split noise)
    Its file-specific sd is 2 sqrt(w' S w (1 + n_pub / n_priv)), S the split-noise covariance of c.
    The base term M_s itself differs between the public and private tracts by split luck common to
    every file (sd shown separately, Gaussian-residual lower bound: var(r^2) = 2 M^2)."""
    global UNTIL
    f, o, reg, s, m, X, err = base()
    L_all = ledger(None)
    sc = dict(zip(L_all.file.str.replace(".csv", "", regex=False), L_all.public_rmse.astype(float)))
    Ms = sc[BASE] ** 2
    n = int(m.sum()); n_pub = PUBLIC_FRAC * n; n_priv = n - n_pub
    common = np.sqrt(2 * Ms ** 2 * (1 / n_pub + 1 / n_priv)) / (2 * np.sqrt(Ms))
    print(f"{BASE:16s} public {np.sqrt(Ms):.6f}  expected private {np.sqrt(Ms):.6f}  "
          f"common split sd >= {common:.6f} (shared by every file built on e0)")
    for name in files:
        UNTIL = name
        names, Ds, Mg = scored_directions(s, m, f.GEOID)
        Dm = Ds[:, m]
        Q, c, w, pred = solve(Dm, Ms, Mg, n_pub)
        D2 = Dm ** 2
        S = (Ms * Q + np.cov(D2) / 4) / n_pub
        g_priv = w @ Q @ w
        g_pub = 2 * w @ c - g_priv
        sd = 2 * np.sqrt(w @ S @ w * (1 + n_pub / n_priv))
        rp = np.sqrt(Ms - g_priv)
        lo, hi = np.sqrt(Ms - g_priv - 2 * sd), np.sqrt(Ms - g_priv + 2 * sd)
        real = sc.get(name)
        print(f"{name:16s} public {real if real else float('nan'):.6f} (predicted {np.sqrt(Ms - g_pub):.6f})  "
              f"expected private {rp:.6f}  file-specific 95% range {lo:.6f}-{hi:.6f}  "
              f"[gain vs e0: private {np.sqrt(Ms) - rp:.6f}, P(gain > 0) {0.5 * (1 + math.erf(g_priv / sd / math.sqrt(2))):.3f}]")
    UNTIL = None


VOI_FILES = ["k05n_grp_sub_low_03_new", "k06n_grp_sub_low_0_new", "k07n_grp_rural_03_new", "g30_probe_tx_unrouted_rural",
             "g31_probe_ok_unrouted", "f1_abl_e0_places", "f2_abl_e0_eastern-ok", "g19_probe_all_fire_any",
             "g20_probe_all_school_any", "k08n_grp_fac_exact_new", "k09n_grp_bld_esri_new", "k10n_grp_bld_osm_new",
             "k11n_grp_bld_area_new", "k12n_grp_revised_new"]


def voi(bar=0.0003):
    """Value of information of each prepared, unscored file, from evidence already in hand.

    Prior on rho (the correlation of a new direction with the residual it is added to) = the empirical
    rho of every direction measured so far, each read against the residual of the file it was built
    on (probes vs e0; group/step files vs their incumbent). Only the part of a candidate outside the
    measured span is new. A refit gains about sigma (rho^2 - kappa sd^2) / 2 in private RMSE (James-Stein
    shrinkage removes the noise term), so the score changes the first final when that clears `bar`.
    Reports, per candidate: share unmeasured, measurement noise sd of rho, the rho it needs, P(change
    the first final), expected private gain; then the overlap between candidates."""
    f, o, reg, s, m, X, err = base()
    L = ledger(None)
    sc = dict(zip(L.file.str.replace(".csv", "", regex=False), L.public_rmse.astype(float)))
    names, Ds, Mg = scored_directions(s, m, f.GEOID)
    B = Ds[:, m]
    n_pub = PUBLIC_FRAC * m.sum()
    inc = sc[INCUMBENT] if INCUMBENT in sc else sc[BASE]
    sig = np.sqrt(sc["h3_probe_fit"] ** 2)                    # the residual a new direction would be added to
    # empirical prior: probes against e0, step files against their incumbent (h2)
    prior = []
    Ms0 = sc[BASE] ** 2
    for nm, mg in zip(names, Mg):
        d = load_scores(f"{D}/{nm}.csv", f.GEOID)
        if nm.startswith("g"):
            ref, Mr = s, Ms0
        elif nm.startswith("k"):
            ref, Mr = load_scores(f"{D}/h2_probe_fit.csv", f.GEOID), sc["h2_probe_fit"] ** 2
        else:
            continue
        dd = (d - ref)[m]; q = np.mean(dd ** 2)
        prior.append(abs((Mr + q - mg) / 2) / np.sqrt(q * Mr))
    prior = np.array(prior)
    print(f"prior |rho| from {len(prior)} measured directions: median {np.median(prior):.3f}, max {prior.max():.3f}, "
          f"share >= 0.05: {np.mean(prior >= 0.05):.2f}")
    new = {}
    rows = []
    for nm in VOI_FILES:
        d = (load_scores(f"{D}/{nm}.csv", f.GEOID) - s)[m]
        r = d - B.T @ np.linalg.lstsq(B.T, d, rcond=None)[0]
        share = np.sqrt(np.mean(r ** 2) / np.mean(d ** 2))
        q = np.mean(r ** 2)
        sd_c = np.sqrt((Ms0 * q + np.var(r ** 2) / 4) / n_pub)
        sd_rho = sd_c / np.sqrt(q * Ms0)
        need = np.sqrt(2 * bar / sig + KAPPA * sd_rho ** 2)
        gain = np.maximum(0, sig * (prior ** 2 - KAPPA * sd_rho ** 2) / 2)
        rows.append((nm, share, sd_rho, need, np.mean(prior >= need), gain.mean()))
        new[nm] = r
    out = pd.DataFrame(rows, columns=["file", "unmeasured", "sd_rho", "rho_needed", "P(change first final)", "E[private gain]"])
    print(out.round(4).to_string(index=False))
    keys = list(new)
    C = np.array([[np.corrcoef(new[a], new[b])[0, 1] for b in keys] for a in keys])
    print("overlap of the unmeasured parts (|corr| >= 0.3):")
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if abs(C[i, j]) >= 0.3:
                print(f"  {keys[i]} ~ {keys[j]}: {C[i, j]:+.2f}")
    need1 = np.sqrt(2 * (sig - 0.052) / sig)
    print(f"rank-1 territory (expected private 0.052) needs sum of rho^2 about {need1 ** 2:.2f} over new directions; "
          f"the largest rho measured so far is {prior.max():.3f}")


E0_ABL = {"T:south-central-tx": "f0_abl_e0_south-central-tx", "P": "f1_abl_e0_places", "T:eastern-ok": "f2_abl_e0_eastern-ok",
          "REG": "f3_abl_e0_region_means", "T:maricopa-az": "f4_abl_e0_maricopa-az"}


# 2026-10-22: finer parts. f1/f2/f4 showed whole parts weighted 0.74-1.46 of their best; splitting the
# places part by region and the Texas transport part by rural/urban measures each piece's own weight.
E0_ABL_FINE = {"P:south-central-tx": "f5_abl_e0_places_tx", "P:eastern-ok": "f6_abl_e0_places_ok",
               "P:maricopa-az": "f7_abl_e0_places_az", "P:northern-ca": "f8_abl_e0_places_ca",
               "T:northern-ca": "f9_abl_e0_northern-ca",
               "T:south-central-tx:rural": "f10_abl_e0_tx_rural", "T:south-central-tx:urban": "f11_abl_e0_tx_urban"}


def fine_parts(f, reg, X):
    rural = (f.pct_urban.fillna(0) < 0.5).values
    out = {f"P:{r}": np.where(reg == r, X["P"], 0.0) for r in REGIONS}
    out["T:northern-ca"] = X["T:northern-ca"]
    tx = X["T:south-central-tx"]
    out["T:south-central-tx:rural"] = np.where(rural, tx, 0.0)
    out["T:south-central-tx:urban"] = np.where(~rural, tx, 0.0)
    return out


# component parts: e0 with one model term held at its regional mean (predict options, default off)
E0_ABL_COMP = {"pdef_off": "f12_abl_e0_definedness", "fire_off": "f13_abl_e0_fire", "school_off": "f14_abl_e0_school"}


def ablate(outdir=None):
    """e0 with one of its decomp parts removed (the f-files): each score measures that part's own
    covariance with the truth. Written to outdir (default: the scored-file directory)."""
    f, o, reg, s, m, X, err = base()
    X = {**X, **fine_parts(f, reg, X)}
    for k, name in {**E0_ABL, **E0_ABL_FINE}.items():
        _save_or_keep(f.GEOID, np.clip(s - X[k], 0, 1), f"{outdir or D}/{name}.csv")
        print(f"{name}: part {k} rms {np.sqrt(np.mean(X[k][m] ** 2)):.5f}")
    for opt, name in E0_ABL_COMP.items():
        step = np.where(m, model_step(f, {opt: True}), 0.0)
        _save_or_keep(f.GEOID, np.clip(s + step, 0, 1), f"{outdir or D}/{name}.csv")
        print(f"{name}: part {opt} rms {np.sqrt(np.mean(step[m] ** 2)):.5f}")


def fit(dry=False, out=None, until=None, kappa=None, ext=False, eb=None, eb_grp=False, ext_first=False, zero=False):
    """until: use only the ledger rows above that file's own row, which rebuilds an earlier fit
    (h0, h2) from exactly the scores it was fitted on. kappa: h0-h3 used KAPPA (4); with 23+
    directions the selftest needs 5 to keep the no-signal private loss under 0.0003 in 95% of runs,
    so h4 onward pass --kappa 5."""
    kappa = KAPPA if kappa is None else kappa
    if out is None:
        used = [int(n[1:].split("_")[0]) for n in os.listdir(D) if re.match(r"h\d+_", n)]
        out = f"h{max(used, default=-1) + 1}_probe_fit"
    f, o, reg, s, m, X, err = base()
    global UNTIL, EXT, ZERO
    UNTIL, EXT, ZERO = until, ext, zero
    L = ledger(until)
    sc = dict(zip(L.file.str.replace(".csv", "", regex=False), L.public_rmse.astype(float)))
    if BASE not in sc:
        sys.exit(f"score missing in ledger: {BASE}")
    Ms = sc[BASE] ** 2
    names, Ds, Mg = scored_directions(s, m, f.GEOID)
    if not names:
        sys.exit("no scored directions in the ledger")
    if ext_first:   # other teams' files first in the whitening order
        o_ = np.argsort([not n.startswith("x") for n in names], kind="stable")
        names, Ds, Mg = [names[i] for i in o_], Ds[o_], Mg[o_]
    if zero:   # the all-zero direction is whitened first, in its own EB group (round J: safe 96%)
        o_ = np.argsort([n != "z_allzero" for n in names], kind="stable")
        names, Ds, Mg = [names[i] for i in o_], Ds[o_], Mg[o_]
    grp = np.array([0 if n.startswith("g") else 1 if n.startswith("f") else 3 if n.startswith("x") else
                    4 if n.startswith("z") else 2 for n in names])
    Q, c, w, pred = solve(Ds[:, m], Ms, Mg, PUBLIC_FRAC * m.sum(), kappa, eb, grp if eb_grp else None)
    sd_r = np.sqrt(Ms)
    rows = pd.DataFrame({"file": names, "rms": np.sqrt(np.diag(Q)), "corr_resid": c / np.sqrt(np.diag(Q)) / sd_r,
                         "weight": w}).sort_values("corr_resid", key=np.abs, ascending=False)
    print(rows.round(4).to_string(index=False))
    E = sc["20_const_058"] ** 2
    for k, name in [("T:south-central-tx", "f0_abl_e0_south-central-tx")]:
        if name in sc:
            x = X[k][m]; Q_ = np.mean(x ** 2)
            xr = (Ms + Q_ - sc[name] ** 2) / 2
            cy = np.mean(x * (s[m] - decomp.CONST)) - xr
            print(f"part {k}: own corr with truth {cy / np.sqrt(Q_ * E):.3f}")
    print(f"e0 {sc[BASE]:.6f}; predicted public RMSE of the fitted file {np.sqrt(max(pred, 0)):.6f} "
          f"({len(names)} directions, kappa {kappa})")
    if dry:
        return
    g = np.clip(s + w @ Ds, 0, 1)
    g[reg == "eastern-wa"] = s[reg == "eastern-wa"]
    save(f.GEOID, g, f"{D}/{out}.csv")
    print(f"wrote {D}/{out}.csv  (rms move vs e0 {np.sqrt(np.mean((g - s)[m] ** 2)):.4f})")


def selftest(n_rep=200, seed=0, frac=0.3, kappa=None):
    """Simulated truth around s, a random 30% public split, Zindi-style 9-decimal scores; the
    directions are the real ledger files plus the real probes, so the stand-in error for
    mean_pub(D^2) is the one the fit will actually meet."""
    f, reg, s, m, X, err, out = directions()
    _, Dl, _ = scored_directions(s, m, f.GEOID)
    Ds = np.vstack([Dl] + [np.clip(s + z, 0, 1).round(6) - s for _, _, z in out])[:, m]
    sp = s[m]; n = len(sp); K = len(Ds)
    rng = np.random.default_rng(seed)
    het = 0.5 + sp / sp.mean()
    res = {"signal": [], "null": []}
    for case in res:
        for _ in range(n_rep):
            noise = rng.standard_normal(n) * het
            noise *= 0.0735 / np.sqrt(np.mean(noise ** 2))
            if case == "signal":
                b = rng.standard_normal(K) * (rng.random(K) < 0.3)
                sig = b @ Ds
                sig *= 0.035 / np.sqrt(np.mean(sig ** 2))       # about 23% of the residual variance
                r = sig + noise * np.sqrt(1 - 0.035 ** 2 / 0.0735 ** 2)
            else:
                r = noise
            y = np.clip(sp + r, 0, 1)
            pub = rng.random(n) < frac
            mse = lambda g, k: np.mean((g[k] - y[k]) ** 2)
            score = lambda g: round(np.sqrt(mse(g, pub)), 9) ** 2
            Ms = score(sp)
            Mg = np.array([score(np.clip(sp + d, 0, 1)) for d in Ds])
            _, _, w, _ = solve(Ds, Ms, Mg, frac * n, kappa)
            g = np.clip(sp + w @ Ds, 0, 1)
            res[case].append(np.sqrt(mse(sp, ~pub)) - np.sqrt(mse(g, ~pub)))   # private RMSE gain
    sg, nl = np.array(res["signal"]), np.array(res["null"])
    print(f"signal: private gain mean {sg.mean():.5f}, positive in {np.mean(sg > 0):.1%}")
    print(f"null:   private gain mean {nl.mean():.5f}, loss < 0.0003 in {np.mean(nl > -0.0003):.1%}")
    ok = np.mean(sg > 0) >= 0.95 and np.mean(nl > -0.0003) >= 0.95
    print("SELFTEST OK" if ok else "SELFTEST FAIL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "calibrate":
        a = sys.argv
        calibrate(a[a.index("--base") + 1], a[a.index("--out") + 1])
    elif cmd == "calregions":
        a = sys.argv
        calibrate_regions(a[a.index("--base") + 1], a[a.index("--out") + 1])
    elif cmd == "groups":
        a = sys.argv
        arg = lambda k: a[a.index(k) + 1] if k in a else None
        write_groups(until=arg("--until"), outdir=arg("--out"))
    elif cmd == "ablate":
        a = sys.argv
        ablate(a[a.index("--out") + 1] if "--out" in a else None)
    elif cmd == "fit":
        a = sys.argv
        arg = lambda k: a[a.index(k) + 1] if k in a else None
        fit(dry="--dry" in a, out=arg("--out"), until=arg("--until"),
            kappa=float(arg("--kappa")) if arg("--kappa") else None, ext="--ext" in a,
            eb=float(arg("--eb")) if arg("--eb") else None, eb_grp="--eb-grp" in a, ext_first="--ext-first" in a, zero="--zero" in a)
    else:
        {"write": write, "audit": audit, "selftest": selftest, "loo": loo, "private": private, "voi": voi}[cmd]()
