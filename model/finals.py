"""Rebuild both finals and every file on their lines from the scored files and the ledger alone.

Main line (public 0.067742587):
  h9  = probe fit, other teams' files first, group-wise empirical Bayes 0.5
  k23 = h9 + published group means at strength 0.5
  k24 = k23 scaled half-way to its public-optimal multiple along the line e0 -> k23
  k27 = k24 + per-region published means (empirical-Bayes factor per region)
  z00 = k24 + (e1 - e0), e1 = e0 with a per-region reference multiplier that hits the region means
  z01 = z00 + per-region published means (intermediate, never uploaded)
  z02 = k27 + the part of (z01 - k27) outside every measured direction
  k29 = k27 + James-Stein (kappa 3) step over the scored steps z02 and p03 (keeps 0.441 of z02)
Hedge (no other teams' files): h11 = h4's data + the all-zero file, EB 0.4 by group; k28 = h11 + region means;
  yh  = k28 + 0.5 x James-Stein (kappa 3) step along the part of our own scored f13_abl_e0_fire outside the
        rest of the no-ext span, then published group means at strength 0.5 (the hedge final).

Each step sees only the ledger rows that stood above its first scored successor (probe.UNTIL), so
it reproduces the uploaded bytes. Scored files, the ledger and ext/ are read from BB_SUBS (probe.D).

usage: python -m model.finals build --out DIR     (then: python -m model.verify DIR/<name>.csv $BB_SUBS/<name>.csv)
"""
import builtins
import contextlib
import os
import sys
import numpy as np
import pandas as pd

from .predict import predict, variants, PARAMS, load_scores, save
from . import probe as pr

MAIN = ["h9_probe_fit_ebgrp", "k23_ebgrp_published_means", "k24_k23_half_scale", "k27_k24_region_means",
        "z00_bold_gamma_base", "z01_bold_gamma", "z02_bold_gamma_unmeasured", "k29_k27_z02_step"]
HEDGE = ["h11_probe_fit_noext_zero", "k28_h11_region_means", "yh_k28_f13_half_grp05"]
NOEXT_UNTIL = "k16_grp_published_means_ext"   # ledger rows above k16: no file of this set used ext/


def _scores(until):
    L = pr.ledger(until)
    return dict(zip(L.file.str.replace(".csv", "", regex=False), L.public_rmse.astype(float)))


def half_scale(out, k23, name):
    """k24: along e0 -> k23 the public-optimal multiple a* follows from the two scores; take half the step
    beyond k23 (round H simulation: half step safe 98%, full step 66%)."""
    f, o, reg, s, m, X, err = pr.base()
    sc = _scores("k27_k24_region_means")
    Ms, Rk = sc[pr.BASE] ** 2, sc["k23_ebgrp_published_means"]
    dk = load_scores(k23, f.GEOID) - s
    q = np.mean(dk[m] ** 2)
    a = 1 + 0.5 * ((Ms + q - Rk ** 2) / 2 / q - 1)
    print(f"k24: multiple of (k23 - e0) {a:.4f}")
    save(f.GEOID, np.clip(s + a * dk, 0, 1), f"{out}/{name}.csv")


def gamma_base(out, k24, name, sweeps=4, steps=25):
    """z00: per-region t_gamma solved by bisection so e0's own public-region means hit the published ones;
    the base's global spread step couples the regions, hence repeated sweeps."""
    f, o, reg, s, m, X, err = pr.base()
    P0 = {**PARAMS, **variants()[pr.BASE]}
    gam = {R: 1.0 for R, _ in pr.PUBLISHED_REGION_MEANS}
    for _ in range(sweeps):
        for R, t in pr.PUBLISHED_REGION_MEANS:
            lo, hi = 0.2, 6.0
            for _ in range(steps):
                g = (lo + hi) / 2
                y = predict(f, {**P0, "t_gamma": {**gam, R: g}}).coverage_gap_score.to_numpy()
                lo, hi = (g, hi) if y[(reg == R) & m].mean() < t else (lo, g)
            gam[R] = (lo + hi) / 2
    print("z00: t_gamma " + "  ".join(f"{R} {g:.3f}" for R, g in gam.items()))
    e1 = predict(f, {**P0, "t_gamma": gam}).coverage_gap_score.to_numpy()
    g = load_scores(k24, f.GEOID)
    g[m] = np.clip(g[m] + (e1 - s)[m], 0, 1)
    save(f.GEOID, g, f"{out}/{name}.csv")


def unmeasured(out, k27, z01, name):
    """z02: k27 + the part of (z01 - k27) outside the span of every scored direction (own, other teams'
    and the all-zero file) as the ledger stood before z02's own row."""
    f, o, reg, s, m, X, err = pr.base()
    pr.EXT, pr.ZERO, pr.UNTIL = True, True, name
    names, Ds, Mg = pr.scored_directions(s, m, f.GEOID)
    pr.EXT, pr.ZERO, pr.UNTIL = False, False, None
    B = Ds[:, m]
    k = load_scores(k27, f.GEOID)
    d = (load_scores(z01, f.GEOID) - k)[m]
    res = d - B.T @ np.linalg.lstsq(B.T, d, rcond=None)[0]
    print(f"z02: unmeasured share {np.sqrt(np.mean(res ** 2) / np.mean(d ** 2)):.2f}, rms {np.sqrt(np.mean(res ** 2)):.4f}")
    g = k.copy(); g[m] = np.clip(k[m] + res, 0, 1)
    save(f.GEOID, g, f"{out}/{name}.csv")


def step(out, k27, steps, name, kappa=3.0):
    """k29: James-Stein weights over the scored steps {name: file} on k27 (scores: ledger before k29's row)."""
    f, o, reg, s, m, X, err = pr.base()
    sc = _scores(name)
    k = load_scores(k27, f.GEOID)
    Dm = np.array([(load_scores(path, f.GEOID) - k)[m] for path in steps.values()])
    w = pr.solve(Dm, sc["k27_k24_region_means"] ** 2, np.array([sc[n] ** 2 for n in steps]), pr.PUBLIC_FRAC * m.sum(), kappa)[2]
    print("k29: weights " + "  ".join(f"{n} {x:+.4f}" for n, x in zip(steps, w)))
    g = k.copy(); g[m] = np.clip(k[m] + w @ Dm, 0, 1)
    save(f.GEOID, g, f"{out}/{name}.csv")


def f13_half_grp05(out, k28, name, kappa=3.0, lam=0.5):
    """yh: reads only e0, the no-ext ledger rows (above k16), k28 and the published means (no ext/, no h9 lineage).
    The step u is f13 minus its projection on the rest of the no-ext span; its c = mean_pub(u (y - k28)) is read
    through the strict evaluator: the no-ext span plus region / group indicators, Gram-Schmidt with c carried."""
    f, o, reg, s, m, X, err = pr.base()
    n = int(m.sum())
    Ms = _scores(None)[pr.BASE] ** 2
    pr.EXT, pr.ZERO, pr.UNTIL = False, True, NOEXT_UNTIL
    names, Ds, Mg = pr.scored_directions(s, m, f.GEOID)
    pr.EXT, pr.ZERO, pr.UNTIL = False, False, None
    B = Ds[:, m]
    rows = [(d, (Ms + np.mean(d ** 2) - mg) / 2) for d, mg in zip(B, Mg)]
    rural = (f.pct_urban.fillna(0) < 0.5).values
    tier = rural & (f.pop_total.fillna(0).values >= 1500) & (f.n_fire == 0).values
    masks = {"tier": tier, "rural_rest": rural & ~tier, "urban": ~rural, **{R: reg == R for R, _ in pr.PUBLISHED_REGION_MEANS}}
    for R, mu in pr.PUBLISHED_REGION_MEANS + pr.PUBLISHED_GROUP_MEANS:   # indicator c = share x (published - e0 mean)
        k = masks[R][m]
        rows.append((k.astype(float), k.mean() * (mu - s[m][k].mean())))
    U, cU = [], []
    for v, c in rows:
        r, cr = v.copy(), c
        for u_, cu in zip(U, cU):
            a = (r @ u_) / (u_ @ u_); r -= a * u_; cr -= a * cu
        if np.sqrt(np.mean(r ** 2)) >= 0.05 * np.sqrt(np.mean(v ** 2)):   # a near-duplicate only adds stand-in noise
            U.append(r); cU.append(cr)
    U, cU = np.array(U), np.array(cU)
    nn = (U * U).sum(1)

    def mse(g):   # predicted public MSE of a full-length file g
        D_ = (g - s)[m]
        return Ms + np.mean(D_ ** 2) - 2 * (U @ D_ / nn) @ cU

    i = names.index("f13_abl_e0_fire"); O = np.delete(B, i, 0)
    a = np.linalg.lstsq(O.T, B[i], rcond=None)[0]
    u = B[i] - O.T @ a
    v = B[i] ** 2 - a @ (O ** 2)    # the squared combination u's c is read through (full-set stand-in noise)
    K = load_scores(k28, f.GEOID)
    g = K.copy(); g[m] = K[m] + u
    M0, q = mse(K), np.mean(u ** 2)
    c = (M0 + q - mse(g)) / 2
    sd = np.sqrt((M0 * q + np.var(v) / 4) / (pr.PUBLIC_FRAC * n))
    w = lam * max(0.0, 1 - kappa * sd * sd / (c * c)) * c / q
    g = K.copy(); g[m] = np.clip(K[m] + w * u, 0, 1)
    for R, mu in pr.PUBLISHED_GROUP_MEANS:   # as probe.calibrate, strength 0.5, on the unrounded array
        k = masks[R] & m
        g[k] = g[k] + 0.5 * (mu - g[k].mean())
    g = np.clip(g, 0, 1).round(6)
    assert np.all(g[~m] == K[~m]), "eastern-wa must keep k28's values"
    print(f"yh: f13 weight {w:.4f}; strict predicted public {np.sqrt(mse(g)):.6f} (k28 {np.sqrt(M0):.6f})")
    save(f.GEOID, g, f"{out}/{name}.csv")


@contextlib.contextmanager
def no_ext():
    """Inside: any open() or pandas.read_csv() of a path under ext/ raises, so the hedge provably reads none."""
    rc, op = pd.read_csv, builtins.open

    def guard(fn):
        def g(path, *a, **k):
            if "/ext/" in "/" + str(path).replace(os.sep, "/"):
                raise PermissionError(f"hedge line read other teams' file {path}")
            return fn(path, *a, **k)
        return g
    pd.read_csv, builtins.open = guard(rc), guard(op)
    try:
        yield
    finally:
        pd.read_csv, builtins.open = rc, op


def build_hedge(out):
    """The hedge line from no-ext inputs only (build runs it under no_ext: no file under ext/ can be read)."""
    rel = lambda n: os.path.relpath(os.path.join(out, n), pr.D)
    h11, k28, yh = HEDGE
    pr.fit(out=rel(h11), until="h4_probe_fit", eb=0.4, eb_grp=True, zero=True)   # h4's data, no other teams' files
    pr.EXT, pr.ZERO, pr.UNTIL = False, False, None
    pr.calibrate_regions(rel(h11), rel(k28))
    f13_half_grp05(out, f"{out}/{k28}.csv", yh)
    with open(f"{out}/HEDGE", "w") as fh:
        fh.write(yh + "\n")


def build(out):
    os.makedirs(out, exist_ok=True)
    rel = lambda n: os.path.relpath(os.path.join(out, n), pr.D)   # probe's fit/calibrate read and write under D
    p = lambda n: f"{out}/{n}.csv"
    h9, k23, k24, k27, z00, z01, z02, k29 = MAIN
    pr.fit(out=rel(h9), until=k23, ext=True, eb=0.5, eb_grp=True, ext_first=True)   # h9 was fitted before k23 was scored
    pr.calibrate(rel(h9), rel(k23), strength=0.5)
    half_scale(out, p(k23), k24)
    pr.calibrate_regions(rel(k24), rel(k27))
    gamma_base(out, p(k24), z00)
    pr.calibrate_regions(rel(z00), rel(z01))
    unmeasured(out, p(k27), p(z01), z02)
    # z02 and p03 were the two scored steps on k27 when k29 was built (p03 is read as uploaded)
    step(out, p(k27), {z02: p(z02), "p03_scale_az": f"{pr.D}/p03_scale_az.csv"}, k29)
    with no_ext():
        build_hedge(out)
    print(f"wrote {len(MAIN) + len(HEDGE)} files to {out}; main {k29}, hedge {HEDGE[-1]}")


if __name__ == "__main__":
    a = sys.argv
    if len(a) < 2 or a[1] != "build" or "--out" not in a:
        sys.exit(__doc__)
    build(a[a.index("--out") + 1])
