"""Offline consistency search: rank candidate model structures by how well they reproduce every
published aggregate at once. No label and no removed layer is read; the published numbers are the
only reference.

Published (challenge page and bucket README):
  undefined share ("at least one component undefined" = transport undefined)
      eastern-ok 21%, maricopa-az 55%, northern-ca 37%, south-central-tx 28%   (rounded to 1%)
  component means over the 9,379 original tracts: transport 0.111771, poi 0.051414
  Overture/reference highway length ratio across the four regions: 0.71 to 1.59

For each candidate the transport mean and the Oklahoma ratio are pinned (Oklahoma is the region
that can reach 0.71); what is left unforced, the maximum ratio and the undefined shares, is the
consistency score. Lower is better. This ranks candidates for upload; it is not an RMSE.

usage: python -m model.constraints [out.csv]
"""
import itertools
import sys
import numpy as np
import pandas as pd

from .predict import load_features, predict, variants

UNDEF = {"eastern-ok": 0.21, "maricopa-az": 0.55, "northern-ca": 0.37, "south-central-tx": 0.28}
PUB = list(UNDEF)
RATIO_MIN, RATIO_MAX, T_MEAN = 0.71, 1.59, 0.111771


def evaluate(f, P):
    m = (f.region != "eastern-wa").values

    def run(w, tm):
        o = predict(f, {**P, "t_county": {"eastern-ok": w}, "t_mean": tm})
        r = pd.Series(f.len_hwy.values).groupby(o.region).sum() / o.t_ref_est.groupby(o.region).sum()
        return o, r

    def solve_tm(w):
        lo, hi = 0.05, 0.2
        for _ in range(22):
            tm = (lo + hi) / 2
            o, _ = run(w, tm)
            lo, hi = (tm, hi) if o.transport_gap[m].mean() < T_MEAN else (lo, tm)
        return tm

    lo, hi = 0.1, 1.5
    for _ in range(14):
        w = (lo + hi) / 2
        tm = solve_tm(w)
        o, r = run(w, tm)
        lo, hi = (lo, w) if r["eastern-ok"] < RATIO_MIN else (w, hi)
    sh = 1 - o.groupby("region").p_transport_defined.mean()
    rr = r[PUB]
    # unforced checks, each in units of its publication precision
    loss_ratio = ((rr.max() - RATIO_MAX) / 0.01) ** 2 + ((rr.max() / rr.min() - RATIO_MAX / RATIO_MIN) / 0.02) ** 2
    loss_undef = sum((max(0.0, abs(sh[k] - v) - 0.005) / 0.005) ** 2 for k, v in UNDEF.items())
    return {"ok_county": round(w, 3), "t_mean": round(tm, 4), "max_ratio": round(rr.max(), 3),
            "max_over_min": round(rr.max() / rr.min(), 3),
            **{f"undef_{k.split('-')[1]}": round(sh[k], 3) for k in PUB},
            "loss_ratio": round(loss_ratio, 2), "loss_undef": round(loss_undef, 2),
            "loss": round(loss_ratio + loss_undef, 2)}


def grid():
    base = {**variants()["c0_v12_pinned"]}
    opts = {
        "t_sub_mix": [False, True],
        "t_sub_p": [{"south-central-tx": (0.40, 0.90), "maricopa-az": (0.65, 0.90)},
                    {"south-central-tx": (0.55, 0.55), "maricopa-az": (0.71, 0.71)}],
        "t_bnd_p": [0.0, 0.9],
        "t_sigma": [0.35, 0.7],
    }
    for combo in itertools.product(*opts.values()):
        P = {**base, **dict(zip(opts, combo))}
        name = "mix%d_%s_edge%s_s%s" % (P["t_sub_mix"], "blend" if P["t_sub_p"]["south-central-tx"][0] == 0.40 else "flat",
                                       P["t_bnd_p"], P["t_sigma"])
        yield name, P


def main(out="out2/constraints_search.csv"):
    f = load_features()
    rows = []
    for name, P in grid():
        res = evaluate(f, P)
        rows.append({"candidate": name, **res})
        print(name, res, flush=True)
    df = pd.DataFrame(rows).sort_values("loss")
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print("wrote", out)


def pin_all(f, P, target_mean=T_MEAN):
    """Pin three free settings with three published numbers, in closed form plus one bisection:
    the scale-free max/min ratio (2.24) fixes the Oklahoma county weight, Oklahoma = 0.71 fixes the
    reference scale, and the published transport mean fixes sigma (the softness that turns the
    scaled reference into expected gaps). Returns the pinned parameters and the checks."""
    m = (f.region != "eastern-wa").values
    raw = lambda w: predict(f, {**P, "t_sigma": 0.0, "t_county": {"eastern-ok": w}})  # unscaled reference
    L = pd.Series(f.len_hwy.values).groupby(f.region.values).sum()
    e0 = raw(0.0).t_ref_est.groupby(f.region.values).sum()
    e1 = raw(1.0).t_ref_est.groupby(f.region.values).sum()
    r_hi = max((L / e0)[k] for k in PUB if k != "eastern-ok")          # highest non-Oklahoma ratio
    # (r_hi / r_ok) = 2.239 with r_ok = L_ok / E_ok(w), E_ok linear in w
    e_ok_target = L["eastern-ok"] * (RATIO_MAX / RATIO_MIN) / r_hi
    w = (e_ok_target - e0["eastern-ok"]) / (e1["eastern-ok"] - e0["eastern-ok"])
    c_star = (L["eastern-ok"] / e_ok_target) / RATIO_MIN              # scale so Oklahoma's ratio is 0.71
    # sigma: with the reference scale fixed at c_star, the mean expected gap rises with sigma
    lo, hi = 0.05, 2.0
    for _ in range(30):
        s = (lo + hi) / 2
        o = predict(f, {**P, "t_county": {"eastern-ok": w}, "t_sigma": s, "t_mean": None, "t_scale": c_star})
        lo, hi = (s, hi) if o.transport_gap[m].mean() < target_mean else (lo, s)
    o = predict(f, {**P, "t_county": {"eastern-ok": w}, "t_sigma": s, "t_mean": None, "t_scale": c_star})
    r = pd.Series(f.len_hwy.values).groupby(o.region).sum() / o.t_ref_est.groupby(o.region).sum()
    sh = 1 - o.groupby("region").p_transport_defined.mean()
    pinned = {"t_county": {"eastern-ok": round(float(w), 4)}, "t_sigma": round(float(s), 4), "t_mean": None,
              "t_scale": round(float(c_star), 5)}
    checks = {"ratios": {k: round(float(r[k]), 3) for k in PUB}, "transport_mean": round(float(o.transport_gap[m].mean()), 4),
              "undef": {k: round(float(sh[k]), 3) for k in PUB},
              "loss_undef": round(sum((max(0, abs(sh[k] - v) - 0.005) / 0.005) ** 2 for k, v in UNDEF.items()), 2)}
    return pinned, checks


if __name__ == "__main__":
    main(*sys.argv[1:])
